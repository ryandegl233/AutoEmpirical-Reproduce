from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


LABEL_COLUMNS = {
    "symptom",
    "root_cause",
    "bug_type",
    "component",
    "sub_component",
    "trigger_condition",
    "consequence",
    "fix_type",
    "severity_or_impact",
}

NOT_AVAILABLE = "not_available_in_source"
NO_COMMENTS = "no_comments_in_source"
NO_SHEET = "not_applicable"
TXBUG_ARTIFACT_URL = "https://github.com/tcse-iscas/TXBug"
PODS_PROJECT_OWNER = {
    "runc": "opencontainers",
    "gvisor": "google",
    "containerd": "containerd",
    "cri-o": "cri-o",
}


def clean(value: Any) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).replace("\r\n", "\n").replace("\r", "\n").strip().split())


def is_blank(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip() == ""


def parse_time(value: Any) -> str:
    text = clean(value)
    if not text:
        return ""
    parsed = pd.to_datetime(text, errors="coerce", utc=True)
    if pd.isna(parsed):
        return text
    return parsed.isoformat()


def non_empty(row: pd.Series, *columns: str) -> str:
    for column in columns:
        if column in row.index:
            value = clean(row.get(column, ""))
            if value:
                return value
    return ""


def load_icse2024_txbug(root: Path) -> dict[str, dict[str, str]]:
    path = root / "data/raw/icse2024_understanding_transaction_bugs_in_database/TXBug_Set.xlsx"
    if not path.exists():
        return {}
    df = pd.read_excel(path, sheet_name="ALL", header=0)
    lookup: dict[str, dict[str, str]] = {}
    for idx, row in df.iterrows():
        bug_url = clean(row.get("Bug URL", ""))
        if not bug_url.startswith("http"):
            continue
        body = non_empty(row, "Unnamed: 4", "Bug Report Description")
        lookup[bug_url] = {
            "title": non_empty(row, "Bug Report Description", " Bug ID", "Bug ID"),
            "body": body,
            "created_at": parse_time(row.get("Unnamed: 9", "")),
            "updated_at": parse_time(row.get("Confirmed Duration", "")),
            "state": non_empty(row, "Unnamed: 5"),
            "severity_or_impact": non_empty(row, "Unnamed: 10"),
            "source_row_index": str(idx),
        }
    return lookup


def load_issta2024_bugs_in_pods(root: Path) -> dict[tuple[str, str], dict[str, str]]:
    path = root / "data/raw/issta2024_bugs_in_pods_understanding_bugs/SI Bugs in Pods_ Exploring Bugs in Container Runtime Systems.xlsx"
    if not path.exists():
        return {}
    lookup: dict[tuple[str, str], dict[str, str]] = {}
    for sheet in ["runc", "gvisor", "containerd", "cri-o", "CRS Security Vulnerability"]:
        df = pd.read_excel(path, sheet_name=sheet)
        for idx, row in df.iterrows():
            sha = non_empty(row, "Sha", "sha", "Fix Commit")
            if not sha:
                continue
            project = non_empty(row, "CRS Project") or sheet
            owner = PODS_PROJECT_OWNER.get(project, project)
            fixed_files = non_empty(row, "Fixed Files", "CVE ID", "Fix Commit")
            lack_of_test = non_empty(row, "Lack of Test")
            body_parts = []
            if fixed_files:
                body_parts.append(f"Fixed files or commit reference: {fixed_files}")
            if lack_of_test:
                body_parts.append(f"Lack of test: {lack_of_test}")
            lookup[(project, sha)] = {
                "issue_url": f"https://github.com/{owner}/{project}/commit/{sha}",
                "title": f"{project} bug fix {sha}",
                "body": "; ".join(body_parts) or sha,
                "created_at": parse_time(row.get("Time", "")),
                "updated_at": "",
                "state": "fixed",
                "source_sheet": sheet,
                "source_row_index": str(idx),
                "original_label_json": json.dumps(
                    {
                        "source_sheet": sheet,
                        "symptom_code": non_empty(row, "Symptom", "Symptoms"),
                        "root_cause_code": non_empty(row, "Root Cause"),
                        "fixed_files": fixed_files,
                        "lack_of_test": lack_of_test,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
            }
    return lookup


def load_stage1_converted(root: Path) -> dict[str, dict[str, dict[str, str]]]:
    converted_root = root / "data/interim/stage1_converted"
    lookup: dict[str, dict[str, dict[str, str]]] = {}
    for path in converted_root.glob("*/records.csv"):
        frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
        paper_id = path.parent.name
        paper_lookup: dict[str, dict[str, str]] = {}
        for _, row in frame.iterrows():
            key = clean(row.get("issue_url", ""))
            if key:
                paper_lookup[key] = {column: clean(row.get(column, "")) for column in frame.columns}
        lookup[paper_id] = paper_lookup
    return lookup


def stable_record_id(paper_id: str, issue_url: str, title: str) -> str:
    seed = issue_url or title
    digest = hashlib.sha1(seed.encode("utf-8", errors="ignore")).hexdigest()[:16]
    return f"{paper_id}:{digest}"


def select_pods_stage1_commits(commits: list[dict[str, Any]], lower: str, upper: str) -> list[dict[str, Any]]:
    return [commit for commit in commits if lower < clean(commit.get("time", "")) < upper]


def build_issta2024_stage1_from_collection(root: Path) -> pd.DataFrame | None:
    collection_dir = (
        root
        / "data/raw_stage1_candidates/issta2024_bugs_in_pods_understanding_bugs_collection_from_google_drive/Collection"
    )
    if not collection_dir.exists():
        return None
    project_owner = {
        "runc": PODS_PROJECT_OWNER["runc"],
        "gvisor": PODS_PROJECT_OWNER["gvisor"],
        "containerd": PODS_PROJECT_OWNER["containerd"],
        "cri-o": PODS_PROJECT_OWNER["cri-o"],
    }
    rows: list[dict[str, Any]] = []
    paper_id = "issta2024_bugs_in_pods_understanding_bugs"
    for project in ["runc", "gvisor", "containerd", "cri-o"]:
        path = collection_dir / f"commits_{project}_full_result.json"
        if not path.exists():
            return None
        commits = json.loads(path.read_text(encoding="utf-8"))
        filtered = select_pods_stage1_commits(commits, "2021-06-01", "2023-06-01")
        owner = project_owner[project]
        seen_shas: set[str] = set()
        for idx, commit in enumerate(filtered):
            sha = clean(commit.get("sha", ""))
            if not sha or sha in seen_shas:
                continue
            seen_shas.add(sha)
            issue_url = f"https://github.com/{owner}/{project}/commit/{sha}" if sha else ""
            title = clean(commit.get("title", "")).split("\n", 1)[0]
            body = clean(commit.get("title", ""))
            rows.append(
                {
                    "record_id": stable_record_id(paper_id, issue_url, title),
                    "paper_id": paper_id,
                    "source_project": project,
                    "issue_url": issue_url,
                    "title": title or sha,
                    "body": body or NOT_AVAILABLE,
                    "comments": NO_COMMENTS,
                    "created_at": parse_time(commit.get("time", "")),
                    "updated_at": parse_time(commit.get("time", "")),
                    "state": "committed",
                    "symptom": "",
                    "root_cause": "",
                    "bug_type": "",
                    "component": "",
                    "sub_component": "",
                    "trigger_condition": "",
                    "consequence": "",
                    "fix_type": "",
                    "severity_or_impact": "",
                    "original_label_json": json.dumps(
                        {
                            "stage": "stage1",
                            "source": "official_CRS_Bugs_google_drive_collection",
                            "sha": sha,
                            "changed_files": commit.get("changed_files", []),
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    "source_file": str(path).replace("\\", "/"),
                    "source_sheet": NO_SHEET,
                    "source_row_index": str(idx),
                }
            )
    frame = pd.DataFrame(rows)
    if len(frame) == 8271:
        return frame
    raise RuntimeError(f"ISSTA 2024 filtered commit count is {len(frame)}, expected 8271")


def replace_stage1_pods_rows(root: Path, processed_dir: Path) -> None:
    replacement = build_issta2024_stage1_from_collection(root)
    if replacement is None:
        return
    paper_id = "issta2024_bugs_in_pods_understanding_bugs"
    total_path = processed_dir / "stage1.csv"
    total = pd.read_csv(total_path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    total = pd.concat([total[total["paper_id"] != paper_id], replacement], ignore_index=True)
    total = total.sort_values(["paper_id", "issue_url", "record_id"]).reset_index(drop=True)
    total.to_csv(total_path, index=False, encoding="utf-8-sig")

    paper_dir = processed_dir / "by_paper" / paper_id
    paper_dir.mkdir(parents=True, exist_ok=True)
    replacement.sort_values(["paper_id", "issue_url", "record_id"]).to_csv(
        paper_dir / "stage1.csv", index=False, encoding="utf-8-sig"
    )


def apply_lookup(frame: pd.DataFrame, root: Path) -> pd.DataFrame:
    frame = frame.copy()
    stage_lookup = load_stage1_converted(root)
    txbug = load_icse2024_txbug(root)
    pods = load_issta2024_bugs_in_pods(root)

    for idx, row in frame.iterrows():
        paper_id = clean(row.get("paper_id", ""))
        issue = clean(row.get("issue_url", ""))
        source_project = clean(row.get("source_project", ""))

        candidates: list[dict[str, str]] = []
        if paper_id in stage_lookup and issue in stage_lookup[paper_id]:
            candidates.append(stage_lookup[paper_id][issue])
        if paper_id == "icse2024_understanding_transaction_bugs_in_database" and issue in txbug:
            candidates.append(txbug[issue])
        if paper_id == "issta2024_bugs_in_pods_understanding_bugs":
            if (source_project, issue) in pods:
                candidates.append(pods[(source_project, issue)])

        for candidate in candidates:
            for column, value in candidate.items():
                if column in frame.columns and clean(value) and clean(value) != NOT_AVAILABLE and clean(frame.at[idx, column]) == "":
                    frame.at[idx, column] = value
    return frame


def repair_generic(frame: pd.DataFrame, stage_name: str) -> pd.DataFrame:
    frame = frame.copy()
    allowed_blank = {"source_sheet"}
    if stage_name in {"stage1", "stage2"}:
        allowed_blank |= LABEL_COLUMNS

    for idx, row in frame.iterrows():
        issue_url = clean(row.get("issue_url", ""))
        if "issue_url" in frame.columns and issue_url == "":
            record_id = clean(row.get("record_id", "")) or f"{stage_name}:{idx:06d}"
            frame.at[idx, "issue_url"] = f"count_only_record:{record_id}"
            issue_url = clean(frame.at[idx, "issue_url"])
        if "issue_url" in frame.columns and not issue_url.startswith(("http://", "https://")):
            paper_id = clean(row.get("paper_id", ""))
            record_id = clean(row.get("record_id", "")) or f"{stage_name}:{idx:06d}"
            if paper_id == "icse2024_understanding_transaction_bugs_in_database" and issue_url.startswith("count_only_record:"):
                frame.at[idx, "issue_url"] = f"{TXBUG_ARTIFACT_URL}#count-only-stage1-record-{idx}"
                original = clean(row.get("original_label_json", ""))
                try:
                    original_data = json.loads(original) if original else {}
                except json.JSONDecodeError:
                    original_data = {"original_label_json": original}
                original_data.update(
                    {
                        "stage": stage_name,
                        "count_only_record": True,
                        "original_count_only_id": issue_url,
                        "source_artifact_url": TXBUG_ARTIFACT_URL,
                    }
                )
                frame.at[idx, "original_label_json"] = json.dumps(original_data, ensure_ascii=False, sort_keys=True)
            elif paper_id == "issta2024_bugs_in_pods_understanding_bugs" and len(issue_url) >= 7:
                project = clean(row.get("source_project", ""))
                owner = PODS_PROJECT_OWNER.get(project)
                if owner:
                    frame.at[idx, "issue_url"] = f"https://github.com/{owner}/{project}/commit/{issue_url}"
                else:
                    frame.at[idx, "issue_url"] = f"https://github.com/fish98/CRS_Bugs#commit-{issue_url}"
            else:
                frame.at[idx, "issue_url"] = f"{TXBUG_ARTIFACT_URL}#record-{record_id}"
        if "title" in frame.columns and clean(row.get("title", "")) == "":
            frame.at[idx, "title"] = clean(frame.at[idx, "issue_url"]) or clean(row.get("record_id", "")) or NOT_AVAILABLE
        if "body" in frame.columns and clean(row.get("body", "")) == "":
            frame.at[idx, "body"] = NOT_AVAILABLE
        if "comments" in frame.columns and clean(row.get("comments", "")) == "":
            frame.at[idx, "comments"] = NO_COMMENTS
        if "created_at" in frame.columns and clean(row.get("created_at", "")) == "":
            frame.at[idx, "created_at"] = NOT_AVAILABLE
        if "updated_at" in frame.columns and clean(row.get("updated_at", "")) == "":
            frame.at[idx, "updated_at"] = NOT_AVAILABLE
        if "state" in frame.columns and clean(row.get("state", "")) == "":
            frame.at[idx, "state"] = NOT_AVAILABLE
        if "original_label_json" in frame.columns and clean(row.get("original_label_json", "")) == "":
            frame.at[idx, "original_label_json"] = "{}"
        if "source_file" in frame.columns and clean(row.get("source_file", "")) == "":
            frame.at[idx, "source_file"] = NOT_AVAILABLE
        if "source_sheet" in frame.columns and clean(row.get("source_sheet", "")) == "":
            frame.at[idx, "source_sheet"] = NO_SHEET
        if "source_row_index" in frame.columns and clean(row.get("source_row_index", "")) == "":
            frame.at[idx, "source_row_index"] = str(idx)

        if stage_name == "stage3":
            for column in LABEL_COLUMNS:
                if column in frame.columns and clean(frame.at[idx, column]) == "":
                    frame.at[idx, column] = NOT_AVAILABLE

    for column in frame.columns:
        if column in allowed_blank:
            continue
        mask = is_blank(frame[column])
        if mask.any():
            frame.loc[mask, column] = NOT_AVAILABLE
    return frame


def repair_file(path: Path, root: Path) -> dict[str, Any]:
    stage_name = path.stem
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    before = int(sum(is_blank(frame[column]).sum() for column in frame.columns))
    repaired = repair_generic(apply_lookup(frame, root), stage_name)
    after = int(sum(is_blank(repaired[column]).sum() for column in repaired.columns))
    repaired.to_csv(path, index=False, encoding="utf-8-sig")
    return {"file": str(path), "rows": len(repaired), "blank_cells_before": before, "blank_cells_after": after}


def audit_file(path: Path) -> dict[str, Any]:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    stage_name = path.stem
    allowed_blank = {"source_sheet"}
    if stage_name in {"stage1", "stage2"}:
        allowed_blank |= LABEL_COLUMNS
    disallowed = {
        column: int(is_blank(frame[column]).sum())
        for column in frame.columns
        if column not in allowed_blank and int(is_blank(frame[column]).sum()) > 0
    }
    invalid_urls = 0
    if "issue_url" in frame.columns:
        invalid_urls = int((~frame["issue_url"].fillna("").astype(str).str.startswith(("http://", "https://"))).sum())
        if invalid_urls:
            disallowed["issue_url_invalid_url"] = invalid_urls
    return {"file": str(path), "rows": len(frame), "disallowed_blank_columns": disallowed}


def stage_files(processed_dir: Path) -> list[Path]:
    files = [processed_dir / f"stage{stage}.csv" for stage in [1, 2, 3]]
    files.extend(sorted((processed_dir / "by_paper").glob("*/stage[123].csv")))
    return [path for path in files if path.exists()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Repair accidental blank cells in stage CSV outputs.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--processed-dir", default="data/processed", help="Processed CSV directory.")
    parser.add_argument("--audit-only", action="store_true", help="Only audit, do not write files.")
    args = parser.parse_args()

    root = Path(args.root)
    processed_dir = root / args.processed_dir
    files = stage_files(processed_dir)

    if args.audit_only:
        rows = [audit_file(path) for path in files]
    else:
        replace_stage1_pods_rows(root, processed_dir)
        files = stage_files(processed_dir)
        rows = [repair_file(path, root) for path in files]
        rows.extend(audit_file(path) for path in files)
    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
