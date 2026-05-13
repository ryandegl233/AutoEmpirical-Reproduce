from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

import pandas as pd


BUG_REPORT_KEYWORDS = [
    "github issues",
    "issue",
    "issues",
    "bugzilla",
    "jira",
    "bug reports",
    "bug tracking",
    "developer-verified bug reports",
    "idea issue tracker",
]

SECONDARY_KEYWORDS = [
    "stackoverflow",
    "stack overflow",
    "commits",
    "defects4j",
    "bugswarm",
    "data dump",
    "forum posts",
]


def make_paper_id(row: pd.Series) -> str:
    venue = str(row.get("Venue", "")).strip().lower()
    year = str(row.get("Year", "")).strip()
    title = str(row.get("Paper Name", "")).lower()
    words = re.findall(r"[a-z0-9]+", title)
    slug = "_".join(words[:5]) or "paper"
    return f"{venue}{year}_{slug}"


def infer_source_platform(collect_type: Any, link: Any) -> str:
    text = f"{collect_type} {link}".lower()
    if "github" in text:
        return "github_issues"
    if "jira" in text:
        return "jira"
    if "bugzilla" in text:
        return "bugzilla"
    if "stackoverflow" in text or "stack overflow" in text:
        return "stack_overflow"
    if "defects4j" in text:
        return "defects4j"
    if "bugswarm" in text:
        return "bugswarm"
    if "commit" in text:
        return "commits"
    if str(collect_type).strip().lower() in {"issue", "issues"}:
        return "issue_tracker"
    return "other"


def infer_artifact_type(collect_type: Any) -> str:
    text = str(collect_type).lower()
    if any(keyword in text for keyword in SECONDARY_KEYWORDS):
        if "github issues" in text or "bug reports" in text:
            return "mixed"
        return "secondary_artifact"
    if any(keyword in text for keyword in BUG_REPORT_KEYWORDS):
        return "bug_report"
    return "unknown"


def infer_batch(artifact_type: str, link: Any) -> str:
    link_text = str(link).lower()
    if artifact_type == "bug_report" and any(host in link_text for host in ["github.com", "zenodo.org", "google.com"]):
        return "A"
    if artifact_type in {"bug_report", "mixed"}:
        return "B"
    return "C"


def infer_processing_status(batch: str, paper_id: str) -> str:
    if paper_id == "ase2022_towards_understanding_the_faults_of":
        return "implemented_local_seed"
    if batch == "C":
        return "deferred_non_bug_report_or_mixed_artifact"
    return "pending_raw_download_or_converter"


def infer_domain(scope: Any) -> str:
    text = str(scope).lower()
    checks = [
        ("deep_learning_framework", ["deep learning", "tensorflow", "pytorch", "dl framework", "dl engines"]),
        ("compiler", ["compiler", "wasm", "gcc", "clang"]),
        ("database", ["database", "dbms", "transaction"]),
        ("cloud", ["cloud", "kubernetes", "container", "operator"]),
        ("mobile", ["android", "mobile"]),
        ("iot_robotics", ["iot", "robot", "uav", "aerial"]),
        ("blockchain", ["ethereum", "blockchain"]),
        ("program_repair", ["program repair", "defects4j", "bugswarm"]),
        ("web", ["javascript", "wechat", "webassembly"]),
    ]
    for domain, keywords in checks:
        if any(keyword in text for keyword in keywords):
            return domain
    return "general_software"


def build_source_manifest(excel_path: str | Path) -> pd.DataFrame:
    df = pd.read_excel(excel_path, sheet_name="Dataset Collection")
    records: list[Dict[str, Any]] = []
    for _, row in df.iterrows():
        paper_id = make_paper_id(row)
        link = row.get("Supplementary Link", "")
        collect_type = row.get("Collect Type", "")
        artifact_type = infer_artifact_type(collect_type)
        batch = infer_batch(artifact_type, link)
        source_platform = infer_source_platform(collect_type, link)
        if paper_id == "ase2022_towards_understanding_the_faults_of":
            source_platform = "github_issues"
        records.append(
            {
                "paper_id": paper_id,
                "source_index": row.get("Index", ""),
                "venue": row.get("Venue", ""),
                "year": row.get("Year", ""),
                "paper_name": row.get("Paper Name", ""),
                "supplementary_link": link,
                "software_domain": infer_domain(row.get("Research Scope", "")),
                "research_scope": row.get("Research Scope", ""),
                "period": row.get("Period", ""),
                "collect_type": collect_type,
                "source_platform": source_platform,
                "artifact_type": artifact_type,
                "batch": batch,
                "collect_number": row.get("Collect Number", ""),
                "manual_analysis_number": row.get("Manual Analysis Number", ""),
                "license_status": "unknown",
                "access_status": "not_checked",
                "processing_status": infer_processing_status(batch, paper_id),
                "notes": row.get("Notes", ""),
            }
        )
    return pd.DataFrame(records)
