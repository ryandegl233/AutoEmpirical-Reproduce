from __future__ import annotations

import time
from typing import Dict, List, Optional

from .agents import (
    RoleAgent,
    make_arbitrator_user_prompt,
    make_classification_user_prompt,
    make_critic_user_prompt,
    make_filter_user_prompt,
    normalize_classification_output,
    normalize_filter_output,
)
from .llm import BaseLLMClient
from .prompts import (
    arbitrator_prompt,
    critic_prompt,
    evidence_agent_prompt,
    filtering_agent_prompt,
    root_cause_agent_prompt,
    single_classification_prompt,
    stage2_comment_analyzer_prompt,
    stage2_link_analyzer_prompt,
    stage2_metadata_analyzer_prompt,
    stage2_text_analyzer_prompt,
    stage2_validity_critic_prompt,
    symptom_agent_prompt,
)
from .schemas import AgentCall, ExperimentResult, IssueRecord
from .stage2 import (
    arbitrate_stage2,
    make_stage2_user_prompt,
    normalize_critic_output,
    normalize_stage2_analyzer_outputs,
    synthesize_stage2_evidence,
)


FILTER_SCHEMA = (
    '{"label":"Accepted|Rejected","confidence":0.0-1.0,'
    '"evidence":["..."],"rationale":"one sentence"}'
)
CLASSIFICATION_SCHEMA = (
    '{"bug_symptom":{"primary_category":"[Letter]Name","subcategory":"[Letter.Number]Name",'
    '"specific_type":"[Letter.Number.Number]Name"},"root_cause":'
    '{"primary_category":"[Letter]Name","subcategory":"[Letter.Number]Name"},'
    '"confidence":0.0-1.0,"evidence":["..."],"rationale":"one sentence"}'
)


class MASPipeline:
    def __init__(self, llm: BaseLLMClient, base_prompts: Dict[str, Dict[str, str]], variant: str):
        self.llm = llm
        self.base_prompts = base_prompts
        self.variant = variant

    def run(self, issue: IssueRecord) -> ExperimentResult:
        start = time.perf_counter()
        calls: List[AgentCall] = []

        if self.variant == "stage2_verify_v2":
            final_output = self._run_stage2_verify_v2(issue, calls)
        elif issue.task_type == "filtering":
            final_output = self._run_filtering(issue, calls)
        else:
            final_output = self._run_classification(issue, calls)

        wall_time = time.perf_counter() - start
        invalid = any(call.error for call in calls) or not final_output
        return ExperimentResult(
            record_id=issue.record_id,
            task_type=issue.task_type,
            issue_url=issue.issue_url,
            variant=self.variant,
            final_output=final_output,
            calls=calls,
            invalid_output=invalid,
            wall_time_seconds=wall_time,
            total_prompt_tokens=sum(call.prompt_tokens for call in calls),
            total_completion_tokens=sum(call.completion_tokens for call in calls),
            total_tokens=sum(call.total_tokens for call in calls),
            api_calls=len(calls),
        )

    def _run_stage2_verify_v2(self, issue: IssueRecord, calls: List[AgentCall]) -> Dict:
        prompt = make_stage2_user_prompt(issue)
        text_agent = RoleAgent("Stage2 Text Analyzer", stage2_text_analyzer_prompt(), self.llm)
        comment_agent = RoleAgent("Stage2 Comment Analyst", stage2_comment_analyzer_prompt(), self.llm)
        link_agent = RoleAgent("Stage2 Link Analyst", stage2_link_analyzer_prompt(), self.llm)
        metadata_agent = RoleAgent("Stage2 Metadata Analyzer", stage2_metadata_analyzer_prompt(), self.llm)

        text_call = text_agent.run(prompt)
        comment_call = comment_agent.run(prompt)
        link_call = link_agent.run(prompt)
        metadata_call = metadata_agent.run(prompt)
        calls.extend([text_call, comment_call, link_call, metadata_call])

        text, comments, links, metadata = normalize_stage2_analyzer_outputs(
            text_call.parsed_output,
            comment_call.parsed_output,
            link_call.parsed_output,
            metadata_call.parsed_output,
            issue,
        )
        synthesized = synthesize_stage2_evidence(text, comments, links, metadata)

        critic = None
        if synthesized["confidence"] < 0.75:
            critic_agent = RoleAgent("Stage2 Validity Critic", stage2_validity_critic_prompt(), self.llm)
            critic_prompt = (
                prompt
                + f"\n\n## Stage2 Analyzer Outputs\n"
                + str({"text": text, "comments": comments, "links": links, "metadata": metadata})
                + f"\n\n## Synthesized Verdict\n{synthesized}"
            )
            critic_call = critic_agent.run(critic_prompt)
            calls.append(critic_call)
            critic = normalize_critic_output(critic_call.parsed_output, synthesized)

        return arbitrate_stage2(issue, synthesized, critic, api_calls=len(calls))

    def _run_evidence(self, issue: IssueRecord, calls: List[AgentCall]) -> Optional[Dict]:
        if self.variant == "mas_without_evidence":
            return None
        agent = RoleAgent("Evidence Agent", evidence_agent_prompt(), self.llm)
        call = agent.run(issue.issue_report())
        calls.append(call)
        return call.parsed_output if call.valid_json else None

    def _run_filtering(self, issue: IssueRecord, calls: List[AgentCall]) -> Dict:
        base = self.base_prompts["sys_filteration"]["template"]
        evidence = self._run_evidence(issue, calls)

        if self.variant == "single_agent":
            agent = RoleAgent("Filter Agent", filtering_agent_prompt(base), self.llm)
            call = agent.run(make_filter_user_prompt(issue, evidence))
            calls.append(call)
            return normalize_filter_output(call.parsed_output)

        candidates = []
        multi_filter_variants = {
            "majority_vote",
            "self_consistency",
            "full_mas",
            "mas_without_evidence",
            "mas_without_critic",
            "mas_without_confidence",
        }
        for idx in range(3 if self.variant in multi_filter_variants else 1):
            agent = RoleAgent(f"Filter Agent {idx + 1}", filtering_agent_prompt(base), self.llm)
            call = agent.run(make_filter_user_prompt(issue, evidence))
            calls.append(call)
            candidates.append(call)

        if self.variant in {"majority_vote", "self_consistency", "mas_without_arbitrator"}:
            return self._vote_filter(candidates)

        critic = None
        if self.variant != "mas_without_critic":
            critic_agent = RoleAgent("Critic Agent", critic_prompt("fault-related issue filtering"), self.llm)
            critic = critic_agent.run(make_critic_user_prompt(issue, candidates, evidence))
            calls.append(critic)

        arbitrator = RoleAgent("Arbitrator Agent", arbitrator_prompt("fault-related issue filtering"), self.llm)
        final_call = arbitrator.run(make_arbitrator_user_prompt(issue, candidates, critic, evidence, FILTER_SCHEMA))
        calls.append(final_call)
        output = normalize_filter_output(final_call.parsed_output)
        if self.variant != "mas_without_confidence" and output["confidence"] < 0.45:
            output["rationale"] = (output["rationale"] + " Low-confidence case flagged for human review.").strip()
        return output

    def _run_classification(self, issue: IssueRecord, calls: List[AgentCall]) -> Dict:
        base = self.base_prompts["sys_classification"]["template"]
        evidence = self._run_evidence(issue, calls)

        if self.variant == "single_agent":
            agent = RoleAgent("Single Classification Agent", single_classification_prompt(base), self.llm)
            call = agent.run(make_classification_user_prompt(issue, evidence))
            calls.append(call)
            return normalize_classification_output(call.parsed_output)

        candidates = []
        if self.variant in {"majority_vote", "self_consistency"}:
            for idx in range(3):
                agent = RoleAgent(f"Single Classification Agent {idx + 1}", single_classification_prompt(base), self.llm)
                call = agent.run(make_classification_user_prompt(issue, evidence))
                calls.append(call)
                candidates.append(call)
            return self._vote_classification(candidates)

        symptom_agent = RoleAgent("Symptom Classifier Agent", symptom_agent_prompt(base), self.llm)
        symptom_call = symptom_agent.run(make_classification_user_prompt(issue, evidence))
        calls.append(symptom_call)
        candidates.append(symptom_call)

        root_agent = RoleAgent("Root Cause Classifier Agent", root_cause_agent_prompt(base), self.llm)
        root_call = root_agent.run(make_classification_user_prompt(issue, evidence))
        calls.append(root_call)
        candidates.append(root_call)

        if self.variant == "mas_without_arbitrator":
            return self._merge_symptom_root(symptom_call, root_call)

        critic = None
        if self.variant != "mas_without_critic":
            critic_agent = RoleAgent("Critic Agent", critic_prompt("taxonomy classification"), self.llm)
            critic = critic_agent.run(make_critic_user_prompt(issue, candidates, evidence))
            calls.append(critic)

        arbitrator = RoleAgent("Arbitrator Agent", arbitrator_prompt("taxonomy classification"), self.llm)
        final_call = arbitrator.run(make_arbitrator_user_prompt(issue, candidates, critic, evidence, CLASSIFICATION_SCHEMA))
        calls.append(final_call)
        output = normalize_classification_output(final_call.parsed_output)
        if self.variant != "mas_without_confidence" and output["confidence"] < 0.45:
            output["rationale"] = (output["rationale"] + " Low-confidence case flagged for human review.").strip()
        return output

    def _vote_filter(self, candidates: List[AgentCall]) -> Dict:
        labels = [normalize_filter_output(call.parsed_output)["label"] for call in candidates]
        accepted = labels.count("Accepted")
        label = "Accepted" if accepted >= len(labels) / 2 else "Rejected"
        return {"label": label, "confidence": max(accepted, len(labels) - accepted) / len(labels), "evidence": [], "rationale": "Majority vote."}

    def _vote_classification(self, candidates: List[AgentCall]) -> Dict:
        normalized = [normalize_classification_output(call.parsed_output) for call in candidates]
        return normalized[0] if normalized else normalize_classification_output({})

    def _merge_symptom_root(self, symptom_call: AgentCall, root_call: AgentCall) -> Dict:
        symptom = normalize_classification_output(symptom_call.parsed_output)
        root = normalize_classification_output(root_call.parsed_output)
        symptom["root_cause"] = root["root_cause"]
        symptom["confidence"] = min(symptom["confidence"], root["confidence"])
        symptom["rationale"] = "Merged symptom and root-cause specialist outputs."
        return symptom
