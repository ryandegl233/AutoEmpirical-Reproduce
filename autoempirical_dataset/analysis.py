from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pandas as pd

from .schema import UNIFIED_COLUMNS


def load_json_cell(value: Any) -> Dict[str, Any]:
    if pd.isna(value) or str(value).strip() == "":
        return {}
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}


def validate_schema(df: pd.DataFrame) -> list[str]:
    issues: list[str] = []
    missing = [column for column in UNIFIED_COLUMNS if column not in df.columns]
    if missing:
        issues.append(f"Missing required columns: {', '.join(missing)}")
    for column in ["created_at", "updated_at"]:
        if column in df.columns:
            values = df[column].dropna().astype(str)
            non_empty = values[values.str.strip() != ""]
            parsed = pd.to_datetime(non_empty, errors="coerce", utc=True)
            invalid = int(parsed.isna().sum())
            if invalid:
                issues.append(f"{column} has {invalid} unparsable non-empty values")
    if "issue_url" in df.columns:
        urls = df["issue_url"].dropna().astype(str)
        suspicious = urls[(urls.str.strip() != "") & (~urls.str.contains(r"^https?://", regex=True))]
        if len(suspicious):
            issues.append(f"issue_url has {len(suspicious)} non-empty values that are not http(s) URLs")
    return issues


def markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    text_df = df.fillna("").astype(str)
    header = "| " + " | ".join(text_df.columns) + " |"
    separator = "| " + " | ".join(["---"] * len(text_df.columns)) + " |"
    rows = ["| " + " | ".join(row) + " |" for row in text_df.to_numpy()]
    return "\n".join([header, separator, *rows])


def build_summary_tables(dataset: pd.DataFrame, manifest: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    by_source = (
        dataset.groupby(["paper_id", "software_domain", "source_platform", "artifact_type"], dropna=False)
        .size()
        .reset_index(name="records")
        .sort_values("records", ascending=False)
    )
    by_domain = dataset.groupby("software_domain", dropna=False).size().reset_index(name="records")
    by_platform = dataset.groupby("source_platform", dropna=False).size().reset_index(name="records")
    by_state = dataset.groupby("state", dropna=False).size().reset_index(name="records").sort_values("records", ascending=False)

    text_stats = pd.DataFrame(
        [
            {
                "records": len(dataset),
                "papers_in_manifest": manifest["paper_id"].nunique() if "paper_id" in manifest else 0,
                "papers_in_dataset": dataset["paper_id"].nunique() if len(dataset) else 0,
                "software_domains_in_dataset": dataset["software_domain"].nunique() if len(dataset) else 0,
                "records_with_title": int((dataset["title"].astype(str).str.len() > 0).sum()) if len(dataset) else 0,
                "records_with_body": int((dataset["body"].astype(str).str.len() > 0).sum()) if len(dataset) else 0,
                "records_with_comments": int((dataset["comments"].astype(str).str.len() > 0).sum()) if len(dataset) else 0,
                "records_with_original_labels": int((dataset["original_labels"].astype(str) != "{}").sum()) if len(dataset) else 0,
                "duplicate_issue_urls": int(dataset["issue_url"].duplicated().sum()) if len(dataset) else 0,
            }
        ]
    )
    return {
        "summary": text_stats,
        "records_by_source": by_source,
        "records_by_domain": by_domain,
        "records_by_platform": by_platform,
        "records_by_state": by_state,
    }


def write_quality_report(path: Path, dataset: pd.DataFrame, manifest: pd.DataFrame, schema_issues: list[str]) -> None:
    tables = build_summary_tables(dataset, manifest)
    implemented = manifest[manifest["processing_status"].astype(str).str.contains("implemented", na=False)]
    pending = manifest[manifest["processing_status"].astype(str).str.contains("pending", na=False)]
    deferred = manifest[manifest["processing_status"].astype(str).str.contains("deferred", na=False)]
    lines = [
        "# AutoEmpirical Phase-1 Dataset Quality Report",
        "",
        "## Build Summary",
        "",
        markdown_table(tables["summary"]),
        "",
        "## Source Manifest Status",
        "",
        f"- Implemented sources: {len(implemented)}",
        f"- Pending bug-report sources: {len(pending)}",
        f"- Deferred secondary/mixed sources: {len(deferred)}",
        "",
        "## Schema Validation",
        "",
    ]
    if schema_issues:
        lines.extend([f"- {issue}" for issue in schema_issues])
    else:
        lines.append("- No schema issues detected.")
    lines.extend(
        [
            "",
            "## Records by Source",
            "",
            markdown_table(tables["records_by_source"]),
            "",
            "## Records by Domain",
            "",
            markdown_table(tables["records_by_domain"]),
            "",
            "## Records by Platform",
            "",
            markdown_table(tables["records_by_platform"]),
            "",
            "## Records by State",
            "",
            markdown_table(tables["records_by_state"].head(20)),
            "",
            "## Notes",
            "",
            "- This first reproducible build uses local seed data already present in the repository.",
            "- External sources from the Excel workbook are registered in the manifest and marked pending or deferred until raw data is downloaded and licensed for redistribution.",
            "- Original labels are preserved as JSON strings; normalized labels are coarse mappings for cross-paper analysis.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_data_dictionary(path: Path) -> None:
    descriptions = {
        "record_id": "Stable SHA1-based identifier scoped by paper_id.",
        "paper_id": "Stable identifier derived from venue, year, and paper title in the source manifest.",
        "source_project": "Project or ecosystem that produced the bug report.",
        "artifact_type": "Primary artifact class, e.g., bug_report, mixed, secondary_artifact.",
        "software_domain": "Coarse software domain inferred from the empirical study scope.",
        "source_platform": "Source platform such as github_issues, jira, bugzilla, stack_overflow.",
        "issue_url": "Canonical URL for the bug report when available.",
        "title": "Bug report title.",
        "body": "Bug report body or description.",
        "comments": "Concatenated comments or discussion text.",
        "created_at": "UTC ISO timestamp when available.",
        "updated_at": "UTC ISO timestamp when available.",
        "state": "Original issue state.",
        "original_labels": "JSON object containing labels exactly as provided or derived from the source dataset.",
        "normalized_labels": "JSON object with coarse cross-paper labels and mapping metadata.",
        "collection_metadata": "JSON object with conversion provenance and source-row details.",
    }
    lines = ["# AutoEmpirical Phase-1 Data Dictionary", ""]
    for column in UNIFIED_COLUMNS:
        lines.append(f"## `{column}`")
        lines.append("")
        lines.append(descriptions[column])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
