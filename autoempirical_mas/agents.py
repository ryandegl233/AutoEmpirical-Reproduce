from __future__ import annotations

from typing import Any, Dict, List, Optional

from .json_utils import clamp_confidence, extract_json_object, normalize_filter_label
from .llm import BaseLLMClient
from .schemas import AgentCall, IssueRecord


class RoleAgent:
    def __init__(self, name: str, system_prompt: str, llm: BaseLLMClient):
        self.name = name
        self.system_prompt = system_prompt
        self.llm = llm

    def run(self, user_prompt: str) -> AgentCall:
        try:
            response = self.llm.complete(self.name, self.system_prompt, user_prompt)
            parsed = extract_json_object(response.content)
            return AgentCall(
                agent=self.name,
                model=self.llm.model,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                total_tokens=response.total_tokens,
                latency_seconds=response.latency_seconds,
                raw_output=response.content,
                parsed_output=parsed or {},
                valid_json=parsed is not None,
            )
        except Exception as exc:
            return AgentCall(agent=self.name, model=self.llm.model, error=str(exc), valid_json=False)


def make_filter_user_prompt(issue: IssueRecord, evidence: Optional[Dict[str, Any]] = None) -> str:
    extra = f"\n\n## Extracted Evidence\n{evidence}" if evidence else ""
    return issue.issue_report() + extra


def make_classification_user_prompt(issue: IssueRecord, evidence: Optional[Dict[str, Any]] = None) -> str:
    extra = f"\n\n## Extracted Evidence\n{evidence}" if evidence else ""
    return "Please classify the following issue report.\n\n" + issue.issue_report() + extra


def make_critic_user_prompt(issue: IssueRecord, candidates: List[AgentCall], evidence: Optional[Dict[str, Any]]) -> str:
    candidate_payload = [
        {"agent": call.agent, "valid_json": call.valid_json, "output": call.parsed_output or call.raw_output}
        for call in candidates
    ]
    return (
        issue.issue_report()
        + f"\n\n## Evidence\n{evidence or {}}\n\n## Candidate Outputs\n{candidate_payload}"
    )


def make_arbitrator_user_prompt(
    issue: IssueRecord,
    candidates: List[AgentCall],
    critic: Optional[AgentCall],
    evidence: Optional[Dict[str, Any]],
    task_schema: str,
) -> str:
    candidate_payload = [
        {"agent": call.agent, "valid_json": call.valid_json, "output": call.parsed_output or call.raw_output}
        for call in candidates
    ]
    critic_payload = critic.parsed_output if critic else {}
    return (
        issue.issue_report()
        + f"\n\n## Evidence\n{evidence or {}}\n\n## Candidate Outputs\n{candidate_payload}"
        + f"\n\n## Critic Feedback\n{critic_payload}\n\nReturn schema:\n{task_schema}"
    )


def normalize_filter_output(output: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "label": normalize_filter_label(output.get("label") or output.get("decision")),
        "confidence": clamp_confidence(output.get("confidence")),
        "evidence": output.get("evidence") if isinstance(output.get("evidence"), list) else [],
        "rationale": str(output.get("rationale", "")),
    }


def normalize_classification_output(output: Dict[str, Any]) -> Dict[str, Any]:
    symptom = output.get("bug_symptom") if isinstance(output.get("bug_symptom"), dict) else {}
    root = output.get("root_cause") if isinstance(output.get("root_cause"), dict) else {}
    return {
        "bug_symptom": {
            "primary_category": str(symptom.get("primary_category", "")),
            "subcategory": str(symptom.get("subcategory", "")),
            "specific_type": str(symptom.get("specific_type", "")),
        },
        "root_cause": {
            "primary_category": str(root.get("primary_category", "")),
            "subcategory": str(root.get("subcategory", "")),
        },
        "confidence": clamp_confidence(output.get("confidence")),
        "evidence": output.get("evidence") if isinstance(output.get("evidence"), list) else [],
        "rationale": str(output.get("rationale", "")),
    }
