from __future__ import annotations

import csv
import http.client
import io
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

import pandas as pd

from autoempirical_dataset.download_sources import (
    DownloadPlan,
    candidate_files_from_github,
    classify_source,
    content_length,
    gitlab_archive_fallback_urls,
    http_request,
    sanitize_filename,
    zenodo_file_urls,
)

ProgressCallback = Callable[[str], None]

TABLE_EXTENSIONS = {".csv", ".tsv", ".xlsx", ".xls", ".json", ".jsonl", ".md", ".txt"}
SYMPTOM_COLUMNS = {"symptom", "symptoms", "bug symptom", "failure symptom", "observed behavior"}
ROOT_CAUSE_COLUMNS = {"root cause", "root causes", "rootcause", "cause", "bug cause"}
HIGH_PRIORITY_FILENAME_KEYWORDS = (
    "root cause",
    "root_cause",
    "root-cause",
    "rootcause",
    "symptom",
    "taxonomy",
    "label",
    "annotation",
    "annotated",
    "dataset",
    "data",
    "bug",
    "bugs",
)
LOW_PRIORITY_FILENAME_KEYWORDS = ("readme", "requirement", "requirements", "license", "contributing")


@dataclass(frozen=True)
class Stage1Groups:
    accepted: pd.DataFrame
    redownload: pd.DataFrame
    stage2_missing: pd.DataFrame


@dataclass(frozen=True)
class CandidateValidation:
    accepted: bool
    matched_symptom_column: str = ""
    matched_root_cause_column: str = ""
    reject_reason: str = ""


@dataclass(frozen=True)
class CandidateStatus:
    paper_id: str
    source_index: Any
    source_url: str
    target_url: str
    status: str
    output_path: str = ""
    matched_symptom_column: str = ""
    matched_root_cause_column: str = ""
    reject_reason: str = ""
    error: str = ""


def truthy(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def falsey(value: Any) -> bool:
    return str(value).strip().lower() == "false"


def split_stage1_groups(checklist: pd.DataFrame) -> Stage1Groups:
    existing = checklist["is_existing_in_raw"].map(truthy)
    checked_ok = checklist["is_manual_checked_OK"].map(truthy)
    checked_bad = checklist["is_manual_checked_OK"].map(falsey)
    return Stage1Groups(
        accepted=checklist[existing & checked_ok].copy(),
        redownload=checklist[existing & checked_bad].copy(),
        stage2_missing=checklist[~existing].copy(),
    )


def copy_tree_without_overwrite(source_dir: Path, target_dir: Path) -> tuple[int, int]:
    copied = 0
    already_exists = 0
    for root, _, files in os.walk(source_dir):
        root_path = Path(root)
        relative_root = root_path.relative_to(source_dir)
        destination_root = target_dir / relative_root
        destination_root.mkdir(parents=True, exist_ok=True)
        for filename in files:
            source_file = root_path / filename
            target_file = destination_root / filename
            if target_file.exists():
                already_exists += 1
                continue
            shutil.copy2(source_file, target_file)
            copied += 1
    return copied, already_exists


def prepare_stage1_raw(
    checklist_path: Path,
    raw_dir: Path,
    stage1_dir: Path,
    manifest_dir: Path,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    checklist = pd.read_csv(checklist_path)
    groups = split_stage1_groups(checklist)
    stage1_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    accepted_rows: list[dict[str, Any]] = []
    for _, row in groups.accepted.iterrows():
        paper_id = str(row["paper_id"])
        source = raw_dir / paper_id
        target = stage1_dir / paper_id
        copied = 0
        already_exists = 0
        status = "missing_source"
        if source.is_dir():
            copied, already_exists = copy_tree_without_overwrite(source, target)
            status = "copied" if already_exists == 0 else "already_exists"
        accepted_rows.append(
            {
                "paper_id": paper_id,
                "source_index": row.get("source_index", ""),
                "source_raw_dir": str(source),
                "stage1_dir": str(target),
                "file_count": copied + already_exists,
                "copied_files": copied,
                "already_exists_files": already_exists,
                "status": status,
            }
        )

    accepted = pd.DataFrame(accepted_rows)
    missing = groups.stage2_missing.copy()
    accepted.to_csv(manifest_dir / "stage1_accepted.csv", index=False, encoding="utf-8-sig")
    missing.to_csv(manifest_dir / "stage2_missing_raw.csv", index=False, encoding="utf-8-sig")
    return accepted, missing


def normalize_column_name(value: Any) -> str:
    text = str(value).strip().lower()
    text = re.sub(r"[_\-]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text


def match_column(columns: Iterable[Any], accepted_names: set[str]) -> str:
    for column in columns:
        normalized = normalize_column_name(column)
        if normalized in accepted_names:
            return str(column)
    return ""


def validate_columns(columns: Iterable[Any]) -> CandidateValidation:
    columns = list(columns)
    symptom = match_column(columns, SYMPTOM_COLUMNS)
    root_cause = match_column(columns, ROOT_CAUSE_COLUMNS)
    if symptom and root_cause:
        return CandidateValidation(True, symptom, root_cause)
    missing = []
    if not symptom:
        missing.append("symptom")
    if not root_cause:
        missing.append("root cause")
    return CandidateValidation(False, reject_reason="Missing required column(s): " + ", ".join(missing))


def _decode_text(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def _validate_delimited_text(text: str, delimiter: Optional[str] = None) -> CandidateValidation:
    non_empty_lines = [line for line in text.splitlines() if line.strip()]
    if not non_empty_lines:
        return CandidateValidation(False, reject_reason="No table-like content found.")
    sample = "\n".join(non_empty_lines[:10])
    delimiters = [delimiter] if delimiter else [",", "\t", "|"]
    best_header: list[str] = []
    for item in delimiters:
        if item is None:
            continue
        try:
            reader = csv.reader(io.StringIO(sample), delimiter=item)
            header = next(reader, [])
        except csv.Error:
            continue
        header = [cell.strip() for cell in header if cell.strip()]
        if len(header) > len(best_header):
            best_header = header
        validation = validate_columns(header)
        if validation.accepted:
            return validation
    if best_header:
        validation = validate_columns(best_header)
        if validation.reject_reason:
            return validation
    return CandidateValidation(False, reject_reason="No parseable table header found.")


def _validate_json(content: bytes, suffix: str) -> CandidateValidation:
    text = _decode_text(content)
    try:
        if suffix == ".jsonl":
            first_record = next((json.loads(line) for line in text.splitlines() if line.strip()), None)
            if first_record is None:
                return CandidateValidation(False, reject_reason="Empty JSONL file.")
            records = [first_record]
        else:
            payload = json.loads(text)
            records = payload if isinstance(payload, list) else [payload]
    except json.JSONDecodeError as exc:
        return CandidateValidation(False, reject_reason=f"JSON parse failed: {exc}")

    for record in records:
        if isinstance(record, dict):
            validation = validate_columns(record.keys())
            if validation.accepted:
                return validation
            for value in record.values():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    nested = validate_columns(value[0].keys())
                    if nested.accepted:
                        return nested
    return CandidateValidation(False, reject_reason="No JSON object with required columns found.")


def validate_candidate_content(filename: str, content: bytes) -> CandidateValidation:
    suffix = Path(filename).suffix.lower()
    if suffix not in TABLE_EXTENSIONS:
        return CandidateValidation(False, reject_reason=f"Unsupported candidate extension: {suffix or '<none>'}.")
    if suffix in {".xlsx", ".xls"}:
        try:
            workbook = pd.ExcelFile(io.BytesIO(content))
            for sheet in workbook.sheet_names:
                frame = pd.read_excel(workbook, sheet_name=sheet, nrows=1)
                validation = validate_columns(frame.columns)
                if validation.accepted:
                    return validation
            return CandidateValidation(False, reject_reason="Workbook has no sheet with required columns.")
        except Exception as exc:
            return CandidateValidation(False, reject_reason=f"Excel parse failed: {type(exc).__name__}: {exc}")
    if suffix in {".json", ".jsonl"}:
        return _validate_json(content, suffix)
    text = _decode_text(content)
    if suffix == ".tsv":
        return _validate_delimited_text(text, "\t")
    if suffix == ".csv":
        return _validate_delimited_text(text, ",")
    return _validate_delimited_text(text)


def fetch_bytes(url: str, max_bytes: int, timeout: int = 60) -> tuple[bytes, str, str]:
    size, status, content_type = content_length(url, timeout=timeout)
    if size is not None and size > max_bytes:
        raise RuntimeError(f"File exceeds max_bytes ({size} > {max_bytes}).")
    request = http_request(url)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise RuntimeError(f"Download exceeded max_bytes ({len(data)} > {max_bytes}).")
        return data, str(response.status), response.headers.get("content-type", "")


def candidate_filename_from_url(url: str, fallback: str) -> str:
    parsed = urllib.parse.urlparse(url)
    name = Path(urllib.parse.unquote(parsed.path)).name
    return sanitize_filename(name or fallback)


def is_skippable_candidate_filename(filename: str) -> bool:
    normalized = normalize_column_name(Path(filename).name)
    stem = normalize_column_name(Path(filename).stem)
    return normalized in LOW_PRIORITY_FILENAME_KEYWORDS or stem in LOW_PRIORITY_FILENAME_KEYWORDS


def candidate_priority(filename: str) -> int:
    normalized = normalize_column_name(filename)
    score = 0
    for keyword in HIGH_PRIORITY_FILENAME_KEYWORDS:
        if normalize_column_name(keyword) in normalized:
            score += 10
    suffix = Path(filename).suffix.lower()
    if suffix in {".csv", ".tsv", ".xlsx", ".xls"}:
        score += 3
    elif suffix in {".json", ".jsonl"}:
        score += 2
    elif suffix in {".md", ".txt"}:
        score += 1
    return score


def ranked_candidate_targets(targets: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    filtered = [
        target
        for target in targets
        if Path(target.get("filename", "")).suffix.lower() in TABLE_EXTENSIONS
        and not is_skippable_candidate_filename(target.get("filename", ""))
    ]
    return sorted(filtered, key=lambda target: (-candidate_priority(target.get("filename", "")), target.get("filename", "")))


def candidate_targets(row: pd.Series, plan: DownloadPlan, max_github_files: int, progress: Optional[ProgressCallback]) -> list[dict[str, str]]:
    source_url = str(row.get("supplementary_link", "")).strip()
    if plan.mode == "direct_file":
        if "gitlab.com/" in source_url:
            return ranked_candidate_targets(
                [
                    {"target_url": url, "filename": sanitize_filename(plan.filename_hint)}
                    for url in gitlab_archive_fallback_urls(source_url)
                ]
            )
        return ranked_candidate_targets([{"target_url": plan.target_url, "filename": sanitize_filename(plan.filename_hint)}])
    if plan.mode == "github_contents":
        candidates = candidate_files_from_github(plan.target_url, max_github_files, progress=progress)
        return ranked_candidate_targets(
            [
                {
                    "target_url": candidate["download_url"],
                    "filename": sanitize_filename(candidate["path"].replace("/", "__")),
                }
                for candidate in candidates
            ]
        )
    if plan.mode == "zenodo":
        return ranked_candidate_targets(
            [
                {"target_url": item["download_url"], "filename": sanitize_filename(item["path"])}
                for item in zenodo_file_urls(plan.target_url)
            ]
        )
    return []


def redownload_stage1_candidates(
    checklist_path: Path,
    sources_path: Path,
    candidates_dir: Path,
    manifest_dir: Path,
    max_bytes: int = 500 * 1024 * 1024,
    max_github_files: int = 250,
    source_indexes: Optional[set[int]] = None,
    progress: Optional[ProgressCallback] = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    checklist = pd.read_csv(checklist_path)
    sources = pd.read_csv(sources_path)
    groups = split_stage1_groups(checklist)
    redownload = groups.redownload.merge(
        sources,
        on=["paper_id", "source_index"],
        how="left",
        suffixes=("", "_source"),
    )
    if source_indexes:
        redownload = redownload[redownload["source_index"].astype(int).isin(source_indexes)]
    manifest_dir.mkdir(parents=True, exist_ok=True)

    statuses: list[CandidateStatus] = []
    for _, row in redownload.iterrows():
        paper_id = str(row.get("paper_id", ""))
        source_index = row.get("source_index", "")
        source_url = str(row.get("supplementary_link", "")).strip()
        plan = classify_source(row)
        if progress:
            progress(f"start #{source_index} {paper_id} ({plan.category}, {plan.mode})")
        if plan.mode == "manual":
            statuses.append(
                CandidateStatus(
                    paper_id,
                    source_index,
                    source_url,
                    plan.target_url,
                    "manual_needed",
                    reject_reason=plan.reason,
                )
            )
            continue
        try:
            targets = candidate_targets(row, plan, max_github_files, progress)
            if not targets:
                statuses.append(
                    CandidateStatus(
                        paper_id,
                        source_index,
                        source_url,
                        plan.target_url,
                        "rejected",
                        reject_reason="No candidate files found.",
                    )
                )
                continue
            for index, target_info in enumerate(targets, start=1):
                target_url = target_info["target_url"]
                filename = target_info["filename"] or candidate_filename_from_url(target_url, f"candidate_{index}")
                if Path(filename).suffix.lower() not in TABLE_EXTENSIONS:
                    statuses.append(
                        CandidateStatus(
                            paper_id,
                            source_index,
                            source_url,
                            target_url,
                            "rejected",
                            reject_reason=f"Unsupported candidate extension: {Path(filename).suffix.lower() or '<none>'}.",
                        )
                    )
                    continue
                try:
                    content, _, _ = fetch_bytes(target_url, max_bytes)
                    validation = validate_candidate_content(filename, content)
                    if not validation.accepted:
                        statuses.append(
                            CandidateStatus(
                                paper_id,
                                source_index,
                                source_url,
                                target_url,
                                "rejected",
                                reject_reason=validation.reject_reason,
                            )
                        )
                        continue
                    output_path = candidates_dir / paper_id / filename
                    if output_path.exists():
                        status = "already_exists"
                    else:
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        output_path.write_bytes(content)
                        status = "accepted"
                    statuses.append(
                        CandidateStatus(
                            paper_id,
                            source_index,
                            source_url,
                            target_url,
                            status,
                            str(output_path),
                            validation.matched_symptom_column,
                            validation.matched_root_cause_column,
                        )
                    )
                    time.sleep(0.1)
                except (
                    urllib.error.HTTPError,
                    urllib.error.URLError,
                    TimeoutError,
                    RuntimeError,
                    http.client.RemoteDisconnected,
                ) as exc:
                    statuses.append(
                        CandidateStatus(
                            paper_id,
                            source_index,
                            source_url,
                            target_url,
                            "failed",
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    )
        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            RuntimeError,
            json.JSONDecodeError,
            http.client.RemoteDisconnected,
        ) as exc:
            statuses.append(
                CandidateStatus(
                    paper_id,
                    source_index,
                    source_url,
                    plan.target_url,
                    "failed",
                    error=f"{type(exc).__name__}: {exc}",
                )
            )

    status_frame = pd.DataFrame([status.__dict__ for status in statuses])
    accepted_frame = status_frame[status_frame["status"].isin(["accepted", "already_exists"])].copy() if not status_frame.empty else status_frame
    status_frame.to_csv(manifest_dir / "stage1_redownload_status.csv", index=False, encoding="utf-8-sig")
    accepted_frame.to_csv(manifest_dir / "stage1_redownload_accepted.csv", index=False, encoding="utf-8-sig")
    return status_frame, accepted_frame
