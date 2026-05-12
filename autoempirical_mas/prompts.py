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
