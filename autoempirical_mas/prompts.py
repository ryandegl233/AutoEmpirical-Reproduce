from __future__ import annotations

from typing import Dict

import yaml


JSON_ONLY = "Return only valid JSON. Do not wrap it in markdown. Do not add explanations outside JSON."


def load_base_prompts(path: str = "data/prompts.yaml") -> Dict[str, Dict[str, str]]:
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def filtering_agent_prompt(base_prompt: str) -> str:
    return (
        base_prompt
        + "\n\nYou are the Filter Agent. Make an independent binary decision.\n"
        + JSON_ONLY
        + '\nSchema: {"label":"Accepted|Rejected","confidence":0.0-1.0,'
        + '"evidence":["short quote or observation"],"rationale":"one sentence"}'
    )


def evidence_agent_prompt() -> str:
    return (
        "You are the Evidence Agent for empirical software fault analysis. "
        "Extract concise evidence from the issue report that helps decide filtering, "
        "bug symptom, and root cause. Do not classify the issue.\n"
        + JSON_ONLY
        + '\nSchema: {"evidence":["..."],"missing_context":["..."],"ambiguity_notes":["..."]}'
    )


def symptom_agent_prompt(base_prompt: str) -> str:
    return (
        base_prompt
        + "\n\nYou are the Symptom Classifier Agent. Focus only on observable bug symptom. "
        "Still return the full schema, but set root_cause to your best estimate only if needed by the schema.\n"
        + JSON_ONLY
    )


def root_cause_agent_prompt(base_prompt: str) -> str:
    return (
        base_prompt
        + "\n\nYou are the Root Cause Classifier Agent. Focus on the underlying technical cause. "
        "Still return the full schema, but preserve the symptom fields if needed by the schema.\n"
        + JSON_ONLY
    )


def single_classification_prompt(base_prompt: str) -> str:
    return base_prompt + "\n\nYou are a structured single-agent baseline.\n" + JSON_ONLY


def critic_prompt(task_name: str) -> str:
    return (
        f"You are the Critic Agent for {task_name}. Check whether candidate outputs are supported "
        "by extracted evidence and taxonomy definitions. Identify contradictions or unsupported labels.\n"
        + JSON_ONLY
        + '\nSchema: {"is_consistent":true|false,"concerns":["..."],"suggested_fix":null|{...},'
        + '"confidence":0.0-1.0}'
    )


def arbitrator_prompt(task_name: str) -> str:
    return (
        f"You are the Arbitrator Agent for {task_name}. Fuse candidate labels, evidence, and critic feedback. "
        "Prefer labels supported by explicit issue evidence. If candidates disagree, choose the most defensible "
        "label and lower confidence.\n"
        + JSON_ONLY
    )


def stage2_text_analyzer_prompt() -> str:
    return (
        "You are the Text Analyzer Agent. Follow these steps in order:\n"
        "STEP 1 - Scan title and body for bug-report signals: error messages, stack traces, crash, fail, "
        "wrong, unexpected, expected-vs-actual behavior, reproducible steps, and environment info.\n"
        "STEP 2 - Scan for non-bug signals: feature request, how-to question, documentation request, "
        "working as intended, or usage confusion.\n"
        "STEP 3 - Account for short body. If body length is under 100 characters, lower confidence.\n"
        + JSON_ONLY
        + '\nSchema: {"bug_signals":["..."],"non_bug_signals":["..."],'
        + '"text_verdict":"likely_bug|likely_not_bug|ambiguous","confidence":0.0-1.0,'
        + '"body_quality":"rich|short|url_only|absent"}'
    )


def stage2_comment_analyzer_prompt() -> str:
    return (
        "You are the Comment Analyst Agent. Extract maintainer or developer signals from comments. "
        "Confirmed fixes, merged PRs, and maintainer confirmations support confirmed_bug. "
        "Working-as-intended, duplicate, usage-error, and feature-request statements support rejected.\n"
        + JSON_ONLY
        + '\nSchema: {"confirmation_signals":["..."],"rejection_signals":["..."],'
        + '"developer_verdict":"confirmed_bug|rejected|ambiguous|no_comments",'
        + '"confidence":0.0-1.0,"key_quote":"short quote or empty"}'
    )


def stage2_link_analyzer_prompt() -> str:
    return (
        "You are the Link Analyst Agent. Extract PR and commit links from the issue report. "
        "Classify whether linked evidence indicates a merged fix, an open PR, no fix, or cannot determine.\n"
        + JSON_ONLY
        + '\nSchema: {"linked_prs":["..."],"linked_commits":["..."],'
        + '"fix_evidence":"merged_fix|open_pr|no_fix|cannot_determine","confidence":0.0-1.0}'
    )


def stage2_metadata_analyzer_prompt() -> str:
    return (
        "You are the Metadata Analyzer Agent. Use structured metadata such as labels, state, milestone, "
        "and issue URL only. Bug or confirmed labels support likely_bug; wontfix, invalid, duplicate, "
        "question, documentation, and enhancement labels support likely_not_bug.\n"
        + JSON_ONLY
        + '\nSchema: {"github_labels":["..."],"issue_state":"open|closed|unknown",'
        + '"has_bug_label":true|false,"has_wontfix_label":true|false,'
        + '"metadata_verdict":"likely_bug|likely_not_bug|ambiguous","confidence":0.0-1.0}'
    )


def stage2_validity_critic_prompt() -> str:
    return (
        "You are the Validity Critic. Check only for these invalid-bug patterns: "
        "wrong_version, usage_error, duplicate, feature_request. If none match, keep the synthesized verdict.\n"
        + JSON_ONLY
        + '\nSchema: {"invalid_pattern":"none|wrong_version|usage_error|duplicate|feature_request",'
        + '"revised_verdict":"Accepted|Rejected|Uncertain","revised_confidence":0.0-1.0,'
        + '"evidence_for_revision":["..."]}'
    )
