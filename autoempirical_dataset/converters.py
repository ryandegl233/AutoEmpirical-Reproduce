from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Iterable

import pandas as pd

from .schema import LOCAL_DATASETS, NORMALIZED_LABEL_KEYS, UNIFIED_COLUMNS, LocalDatasetSpec


def clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value)
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def json_dumps(data: Dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def parse_time(value: Any) -> str:
    if pd.isna(value) or str(value).strip() == "":
        return ""
    parsed = pd.to_datetime(value, errors="coerce", utc=True)
    if pd.isna(parsed):
        return clean_text(value)
    return parsed.isoformat()


def stable_record_id(paper_id: str, issue_url: str, title: str, body: str) -> str:
    seed = issue_url or f"{title}\n{body}"
    digest = hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{paper_id}:{digest}"


def empty_normalized_labels(method: str = "unmapped", confidence: float = 0.0) -> Dict[str, Any]:
    labels = {key: "" for key in NORMALIZED_LABEL_KEYS}
    labels["mapping_confidence"] = confidence
    labels["mapping_method"] = method
    return labels


def labels_from_manual_row(row: pd.Series) -> tuple[Dict[str, Any], Dict[str, Any]]:
    original = {
        key: clean_text(row.get(key, ""))
        for key in [
            "sub-symptom",
            "symptoms",
            "root causes",
            "sub-component",
            "components of Tensorflow.js",
            "fix",
            "fix patterns",
            "3-level architecture",
            "development stages",
            "sub_symptom_id",
            "symptom_id",
            "root_causes_id",
        ]
        if key in row.index and clean_text(row.get(key, "")) != ""
    }
    normalized = empty_normalized_labels("source_field_mapping", 0.75)
    normalized.update(
        {
            "bug_type": "software_fault",
            "symptom": clean_text(row.get("symptoms", "")),
            "root_cause": clean_text(row.get("root causes", "")),
            "component": clean_text(row.get("components of Tensorflow.js", "")) or clean_text(row.get("sub-component", "")),
            "fix_type": clean_text(row.get("fix patterns", "")) or clean_text(row.get("fix", "")),
        }
    )
    return original, normalized


def labels_from_filter_row(row: pd.Series) -> tuple[Dict[str, Any], Dict[str, Any]]:
    label = clean_text(row.get("label", ""))
    original = {"filter_label": label} if label else {}
    normalized = empty_normalized_labels("source_filter_label_mapping", 0.5 if label else 0.0)
    if label != "":
        normalized["bug_type"] = "accepted_fault_report" if label in {"1", "1.0", "Accepted"} else "rejected_or_non_fault_report"
    return original, normalized


def row_to_unified(row: pd.Series, spec: LocalDatasetSpec, source_row_index: int) -> Dict[str, Any]:
    issue_url = clean_text(row.get("Faults", "")) or clean_text(row.get("issue", ""))
    title = clean_text(row.get("title", ""))
    body = clean_text(row.get("body", ""))
    comments = clean_text(row.get("comments_content", "")) or clean_text(row.get("comments", ""))
    if spec.source_name == "tfjs_manual_fault_labels":
        original_labels, normalized_labels = labels_from_manual_row(row)
    elif spec.source_name == "tfjs_filtering_sample":
        original_labels, normalized_labels = labels_from_filter_row(row)
    else:
        original_labels, normalized_labels = {}, empty_normalized_labels()

    metadata = {
        "local_source_name": spec.source_name,
        "local_source_path": spec.path,
        "source_row_index": int(source_row_index),
        "conversion_status": "converted",
    }
    return {
        "record_id": stable_record_id(spec.paper_id, issue_url, title, body),
        "paper_id": spec.paper_id,
        "source_project": spec.source_project,
        "artifact_type": spec.artifact_type,
        "software_domain": spec.software_domain,
        "source_platform": spec.source_platform,
        "issue_url": issue_url,
        "title": title,
        "body": body,
        "comments": comments,
        "created_at": parse_time(row.get("created_at", "")),
        "updated_at": parse_time(row.get("updated_at", "")),
        "state": clean_text(row.get("state", "")),
        "original_labels": json_dumps(original_labels),
        "normalized_labels": json_dumps(normalized_labels),
        "collection_metadata": json_dumps(metadata),
    }


def read_csv_safely(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except pd.errors.ParserError:
        return pd.read_csv(path, engine="python", on_bad_lines="skip")


def convert_local_dataset(spec: LocalDatasetSpec, root: Path) -> pd.DataFrame:
    path = root / spec.path
    if not path.exists():
        return pd.DataFrame(columns=UNIFIED_COLUMNS)
    df = read_csv_safely(path)
    rows = [row_to_unified(row, spec, idx) for idx, row in df.iterrows()]
    return pd.DataFrame(rows, columns=UNIFIED_COLUMNS)


def convert_all_local_datasets(root: Path) -> Dict[str, pd.DataFrame]:
    return {spec.source_name: convert_local_dataset(spec, root) for spec in LOCAL_DATASETS}


def merge_and_deduplicate(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    combined = pd.concat(list(frames), ignore_index=True)
    if combined.empty:
        return pd.DataFrame(columns=UNIFIED_COLUMNS)
    combined["_has_url"] = combined["issue_url"].astype(str).str.len() > 0
    combined["_label_size"] = combined["original_labels"].astype(str).str.len()
    combined = combined.sort_values(["_has_url", "_label_size"], ascending=[False, False])
    dedupe_key = combined["issue_url"].where(combined["_has_url"], combined["record_id"])
    combined = combined.loc[~dedupe_key.duplicated()].copy()
    combined = combined.drop(columns=["_has_url", "_label_size"])
    combined = combined.sort_values(["paper_id", "issue_url", "record_id"]).reset_index(drop=True)
    return combined[UNIFIED_COLUMNS]

