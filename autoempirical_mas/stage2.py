from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Tuple

from .json_utils import clamp_confidence
from .schemas import IssueRecord


BASE_WEIGHTS = {
    "links": 0.40,
    "comments": 0.30,
    "metadata": 0.20,
    "text": 0.10,
}


def body_quality(body: str) -> str:
    text = str(body or "").strip()
    if not text or text.lower() == "nan":
        return "absent"
    if re.fullmatch(r"https?://\S+", text) or (len(text) < 120 and "github.com" in text.lower()):
        return "url_only"
    if len(text) < 100:
        return "short"
    return "rich"


def text_availability(quality: str) -> str:
    if quality == "rich":
        return "full"
    if quality in {"short", "url_only"}:
        return "short_body"
    return "title_only"


def make_stage2_user_prompt(issue: IssueRecord) -> str:
    return issue.issue_report() + f"\n### Issue URL\n{issue.issue_url}"


def _normalize_text(output: Dict[str, Any], issue: IssueRecord) -> Dict[str, Any]:
    quality = str(output.get("body_quality") or body_quality(issue.body))
    verdict = str(output.get("text_verdict") or "ambiguous")
    if verdict not in {"likely_bug", "likely_not_bug", "ambiguous"}:
        verdict = "ambiguous"
    return {
        "bug_signals": output.get("bug_signals") if isinstance(output.get("bug_signals"), list) else [],
        "non_bug_signals": output.get("non_bug_signals") if isinstance(output.get("non_bug_signals"), list) else [],
        "text_verdict": verdict,
        "confidence": clamp_confidence(output.get("confidence")),
        "body_quality": quality if quality in {"rich", "short", "url_only", "absent"} else body_quality(issue.body),
    }


def _normalize_comments(output: Dict[str, Any]) -> Dict[str, Any]:
    verdict = str(output.get("developer_verdict") or "ambiguous")
    if verdict not in {"confirmed_bug", "rejected", "ambiguous", "no_comments"}:
        verdict = "ambiguous"
    return {
        "confirmation_signals": output.get("confirmation_signals")
        if isinstance(output.get("confirmation_signals"), list)
        else [],
        "rejection_signals": output.get("rejection_signals") if isinstance(output.get("rejection_signals"), list) else [],
        "developer_verdict": verdict,
        "confidence": clamp_confidence(output.get("confidence")),
        "key_quote": str(output.get("key_quote") or ""),
    }


def _normalize_links(output: Dict[str, Any]) -> Dict[str, Any]:
    evidence = str(output.get("fix_evidence") or "cannot_determine")
    if evidence not in {"merged_fix", "open_pr", "no_fix", "cannot_determine"}:
        evidence = "cannot_determine"
    return {
        "linked_prs": output.get("linked_prs") if isinstance(output.get("linked_prs"), list) else [],
        "linked_commits": output.get("linked_commits") if isinstance(output.get("linked_commits"), list) else [],
        "fix_evidence": evidence,
        "confidence": clamp_confidence(output.get("confidence")),
    }


def _normalize_metadata(output: Dict[str, Any]) -> Dict[str, Any]:
    verdict = str(output.get("metadata_verdict") or "ambiguous")
    if verdict not in {"likely_bug", "likely_not_bug", "ambiguous"}:
        verdict = "ambiguous"
    labels = output.get("github_labels") if isinstance(output.get("github_labels"), list) else []
    return {
        "github_labels": labels,
        "issue_state": str(output.get("issue_state") or ""),
        "has_bug_label": bool(output.get("has_bug_label")),
        "has_wontfix_label": bool(output.get("has_wontfix_label")),
        "metadata_verdict": verdict,
        "confidence": clamp_confidence(output.get("confidence")),
    }


def normalize_stage2_analyzer_outputs(
    text: Dict[str, Any],
    comments: Dict[str, Any],
    links: Dict[str, Any],
    metadata: Dict[str, Any],
    issue: IssueRecord,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    return (
        _normalize_text(text, issue),
        _normalize_comments(comments),
        _normalize_links(links),
        _normalize_metadata(metadata),
    )


def _stage_score(kind: str, output: Dict[str, Any]) -> float:
    if kind == "text":
        verdict = output.get("text_verdict")
        if verdict == "likely_bug":
            return clamp_confidence(output.get("confidence"))
        if verdict == "likely_not_bug":
            return -clamp_confidence(output.get("confidence"))
        return 0.0
    if kind == "comments":
        verdict = output.get("developer_verdict")
        if verdict == "confirmed_bug":
            return clamp_confidence(output.get("confidence"))
        if verdict == "rejected":
            return -clamp_confidence(output.get("confidence"))
        return 0.0
    if kind == "links":
        evidence = output.get("fix_evidence")
        if evidence == "merged_fix":
            return clamp_confidence(output.get("confidence"))
        if evidence == "open_pr":
            return clamp_confidence(output.get("confidence")) * 0.45
        if evidence == "no_fix":
            return -clamp_confidence(output.get("confidence")) * 0.25
        return 0.0
    if kind == "metadata":
        verdict = output.get("metadata_verdict")
        if verdict == "likely_bug":
            return clamp_confidence(output.get("confidence"))
        if verdict == "likely_not_bug":
            return -clamp_confidence(output.get("confidence"))
        return 0.0
    return 0.0


def _weights_for_text_quality(quality: str) -> Dict[str, float]:
    weights = dict(BASE_WEIGHTS)
    if quality in {"url_only", "absent"}:
        removed = weights["text"] - 0.05
        weights["text"] = 0.05
        for key in ("links", "comments", "metadata"):
            weights[key] += removed * (BASE_WEIGHTS[key] / 0.90)
    return weights


def _collect_evidence(items: Iterable[Any]) -> List[str]:
    evidence: List[str] = []
    for item in items:
        if isinstance(item, list):
            evidence.extend(str(value) for value in item if value)
        elif item:
            evidence.append(str(item))
    return evidence


def synthesize_stage2_evidence(
    text: Dict[str, Any],
    comments: Dict[str, Any],
    links: Dict[str, Any],
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    quality = str(text.get("body_quality") or "absent")
    weights = _weights_for_text_quality(quality)
    outputs = {"text": text, "comments": comments, "links": links, "metadata": metadata}
    weighted_score = sum(weights[key] * _stage_score(key, outputs[key]) for key in weights)

    confidence = abs(weighted_score)
    if weighted_score >= 0.45:
        verdict = "Accepted"
    elif weighted_score <= -0.45:
        verdict = "Rejected"
    else:
        verdict = "Uncertain"

    supporting = _collect_evidence(
        [
            text.get("bug_signals"),
            comments.get("confirmation_signals"),
            comments.get("key_quote"),
            links.get("linked_prs"),
            links.get("linked_commits"),
            metadata.get("github_labels"),
        ]
    )
    conflicting = _collect_evidence([text.get("non_bug_signals"), comments.get("rejection_signals")])

    return {
        "synthesized_verdict": verdict,
        "confidence": round(confidence, 3),
        "evidence_summary": {
            "text": {"verdict": text.get("text_verdict"), "weight": round(weights["text"], 3)},
            "comments": {"verdict": comments.get("developer_verdict"), "weight": round(weights["comments"], 3)},
            "links": {"verdict": links.get("fix_evidence"), "weight": round(weights["links"], 3)},
            "metadata": {"verdict": metadata.get("metadata_verdict"), "weight": round(weights["metadata"], 3)},
        },
        "supporting_evidence": supporting,
        "conflicting_evidence": conflicting,
        "linked_commits": links.get("linked_commits") if isinstance(links.get("linked_commits"), list) else [],
    }


def normalize_critic_output(output: Dict[str, Any], synthesized: Dict[str, Any]) -> Dict[str, Any]:
    pattern = str(output.get("invalid_pattern") or "none")
    if pattern not in {"none", "wrong_version", "usage_error", "duplicate", "feature_request"}:
        pattern = "none"
    revised = str(output.get("revised_verdict") or synthesized["synthesized_verdict"])
    if revised not in {"Accepted", "Rejected", "Uncertain"}:
        revised = synthesized["synthesized_verdict"]
    return {
        "invalid_pattern": pattern,
        "revised_verdict": revised,
        "revised_confidence": clamp_confidence(output.get("revised_confidence"), synthesized["confidence"]),
        "evidence_for_revision": output.get("evidence_for_revision")
        if isinstance(output.get("evidence_for_revision"), list)
        else [],
    }


def arbitrate_stage2(
    issue: IssueRecord,
    synthesized: Dict[str, Any],
    critic: Dict[str, Any] | None,
    api_calls: int,
) -> Dict[str, Any]:
    if critic and critic.get("invalid_pattern") != "none":
        verdict = critic["revised_verdict"]
        confidence = critic["revised_confidence"]
        invalid_pattern = critic["invalid_pattern"]
        evidence = critic.get("evidence_for_revision") or synthesized.get("supporting_evidence", [])
    else:
        verdict = synthesized["synthesized_verdict"]
        confidence = synthesized["confidence"]
        invalid_pattern = None
        evidence = synthesized.get("supporting_evidence", [])

    strong_positive = synthesized["evidence_summary"]["links"]["verdict"] == "merged_fix"
    strong_negative = synthesized["evidence_summary"]["comments"]["verdict"] == "rejected"
    if confidence < 0.45 or (strong_positive and strong_negative):
        verdict = "Uncertain"

    quality = body_quality(issue.body)
    return {
        "record_id": issue.record_id,
        "verdict": verdict,
        "confidence": round(clamp_confidence(confidence), 3),
        "evidence": evidence[:8],
        "linked_commits": synthesized.get("linked_commits", []),
        "invalid_pattern": invalid_pattern,
        "review_flag": verdict == "Uncertain" or invalid_pattern is not None,
        "text_available": text_availability(quality),
        "api_calls": api_calls,
        "evidence_summary": synthesized["evidence_summary"],
        "conflicting_evidence": synthesized.get("conflicting_evidence", [])[:8],
    }
