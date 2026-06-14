from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autoempirical_dataset.converters import clean_text, json_dumps, parse_time, stable_record_id
from autoempirical_dataset.stage1_converters import STAGE1_COLUMNS


SECRET_PATTERNS = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[REDACTED_AWS_ACCESS_KEY_ID]"),
    (re.compile(r"ASIA[0-9A-Z]{16}"), "[REDACTED_AWS_TEMP_ACCESS_KEY_ID]"),
]


FINAL_PAPER_METADATA: list[dict[str, Any]] = [
    {
        "paper_id": "ase2022_towards_understanding_the_faults_of",
        "venue": "ASE",
        "year": 2022,
        "paper_name": "Towards understanding the faults of javascript-based deep learning systems",
        "software_domain": "deep_learning_framework",
        "research_scope": "JavaScript DL Engines",
        "source_platform": "github_issues",
        "data_collection_period": "before Dec. 2021",
        "stage1_raw_count": 3859,
        "stage2_filtered_count": 684,
        "stage1_raw_path": "data/raw/ase2022_towards_understanding_the_faults_of",
        "stage2_filtered_path": "data/raw_stage1/ase2022_towards_understanding_the_faults_of",
        "selection_note": "Retained from previous final dataset; S1>S2 and symptom/root_cause labels are present.",
    },
    {
        "paper_id": "icse2021_iot_bugs_and_development_challenges",
        "venue": "ICSE",
        "year": 2021,
        "paper_name": "IoT Bugs and Development Challenges",
        "software_domain": "iot_robotics",
        "research_scope": "IoT Systems",
        "source_platform": "github_issues",
        "data_collection_period": "January-February 2020",
        "stage1_raw_count": 5565,
        "stage2_filtered_count": 323,
        "stage1_raw_path": "data/raw/icse2021_iot_bugs_and_development_challenges",
        "stage2_filtered_path": "data/raw_stage1/icse2021_iot_bugs_and_development_challenges",
        "selection_note": "Retained from previous final dataset; S1>S2 and symptom/root_cause labels are present.",
    },
    {
        "paper_id": "issta2024_bugs_in_pods_understanding_bugs",
        "venue": "ISSTA",
        "year": 2024,
        "paper_name": "Bugs in Pods: Understanding Bugs in Container Runtime Systems",
        "software_domain": "cloud",
        "research_scope": "Container Runtime Systems",
        "source_platform": "github_issues",
        "data_collection_period": "June 2021 - June 2023",
        "stage1_raw_count": 8271,
        "stage2_filtered_count": 429,
        "stage1_raw_path": "data/raw/issta2024_bugs_in_pods_understanding_bugs",
        "stage2_filtered_path": "data/raw_stage1/issta2024_bugs_in_pods_understanding_bugs",
        "selection_note": "Retained from previous final dataset; S1>S2 and symptom/root_cause labels are present.",
    },
    {
        "paper_id": "icse2023_an_empirical_study_on_bugs",
        "venue": "ICSE",
        "year": 2023,
        "paper_name": "An Empirical Study on Bugs Inside PyTorch: A Replication Study",
        "software_domain": "deep_learning_framework",
        "research_scope": "PyTorch Bugs",
        "source_platform": "github_issues",
        "data_collection_period": "before 20 October 2022",
        "stage1_raw_count": 2205,
        "stage2_filtered_count": 194,
        "stage1_raw_path": "data/raw/icse2023_an_empirical_study_on_bugs",
        "stage2_filtered_path": "data/raw_stage1/icse2023_an_empirical_study_on_bugs",
        "selection_note": "Retained from previous final dataset; S1>S2 and symptom/root_cause labels are present.",
    },
    {
        "paper_id": "icse2024_understanding_transaction_bugs_in_database",
        "venue": "ICSE",
        "year": 2024,
        "paper_name": "Understanding Transaction Bugs in Database Systems",
        "software_domain": "database",
        "research_scope": "Transaction Bugs in Database Systems",
        "source_platform": "github_issues",
        "data_collection_period": "January 2018 - December 2022",
        "stage1_raw_count": 7775,
        "stage2_filtered_count": 140,
        "stage1_raw_path": "data/raw/icse2024_understanding_transaction_bugs_in_database",
        "stage2_filtered_path": "data/raw_stage1/icse2024_understanding_transaction_bugs_in_database",
        "selection_note": "Retained from previous final dataset; S1>S2 and symptom/root_cause labels are present.",
    },
    {
        "paper_id": "fse2021_an_exploratory_study_of_autopilot",
        "venue": "FSE",
        "year": 2021,
        "paper_name": "An Exploratory Study of Autopilot Software Bugs in Unmanned Aerial Vehicles",
        "software_domain": "iot_robotics",
        "research_scope": "Unmanned aerial vehicles software bugs",
        "source_platform": "github_issues",
        "data_collection_period": "Unknown",
        "stage1_raw_count": 569,
        "stage2_filtered_count": 168,
        "stage1_raw_path": "data/raw/fse2021_an_exploratory_study_of_autopilot",
        "stage2_filtered_path": "data/raw_stage1/fse2021_an_exploratory_study_of_autopilot",
        "selection_note": "Added replacement dataset; raw bug set has 569 issues, final taxonomy has 168 records, and 142 records have explicit symptom/root_cause labels after removing unclear symptoms.",
    },
    {
        "paper_id": "icse2022_an_empirical_study_on_performance",
        "venue": "ICSME",
        "year": 2022,
        "paper_name": "An Empirical Study on Performance Bugs in Deep Learning Frameworks",
        "software_domain": "deep_learning_framework",
        "research_scope": "Performance Bugs of TensorFlow and PyTorch",
        "source_platform": "github_issues",
        "data_collection_period": "before February 2021",
        "stage1_raw_count": 5578,
        "stage2_filtered_count": 2261,
        "stage1_raw_path": "data/raw/icse2022_an_empirical_study_on_performance",
        "stage2_filtered_path": "data/raw_stage1/icse2022_an_empirical_study_on_performance",
        "selection_note": "Added replacement dataset; performance bug information files form the human-filtered set and perf_bugs_taxonomy.csv provides annotated root causes.",
    },
]


EXCLUDED_PAPER_IDS = {
    "fse2023_understanding_the_bug_characteristics_and",
    "icse2022_characterizing_and_detecting_bugs_in",
}


def is_explicit_label(value: Any) -> bool:
    text = str(value).strip().lower()
    return bool(text) and text not in {"nan", "none", "not clear, need discussion"}


def redact_secrets(value: Any) -> str:
    text = clean_text(value)
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def redact_frame(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    for column in frame.columns:
        if column == "source_row_index":
            continue
        frame[column] = frame[column].map(redact_secrets)
    return frame


def empty_stage_record(paper_id: str, source_project: str, idx: int, stage_name: str) -> dict[str, Any]:
    record = {column: "" for column in STAGE1_COLUMNS}
    record.update(
        {
            "record_id": f"{paper_id}:{stage_name}:{idx:06d}",
            "paper_id": paper_id,
            "source_project": source_project,
            "original_label_json": json_dumps({"stage": stage_name, "placeholder": True}),
            "source_row_index": idx,
        }
    )
    return record


def make_stage_record(
    paper_id: str,
    source_project: str,
    idx: int,
    stage_name: str,
    source_file: str,
    source_sheet: str = "",
    issue_url: Any = "",
    title: Any = "",
    body: Any = "",
    comments: Any = "",
    created_at: Any = "",
    updated_at: Any = "",
    state: Any = "",
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    issue = redact_secrets(issue_url)
    title_text = redact_secrets(title)
    body_text = redact_secrets(body)
    record = empty_stage_record(paper_id, source_project, idx, stage_name)
    record.update(
        {
            "record_id": stable_record_id(paper_id, issue, f"{stage_name}:{idx}:{title_text}", body_text),
            "issue_url": issue,
            "title": title_text,
            "body": body_text,
            "comments": redact_secrets(comments),
            "created_at": parse_time(created_at),
            "updated_at": parse_time(updated_at),
            "state": redact_secrets(state),
            "source_file": source_file,
            "source_sheet": source_sheet,
            "source_row_index": idx,
            "original_label_json": json_dumps({"stage": stage_name, **(extra or {})}),
        }
    )
    return {column: redact_secrets(record[column]) if column != "source_row_index" else record[column] for column in STAGE1_COLUMNS}


def blank_labels(frame: pd.DataFrame, stage_name: str) -> pd.DataFrame:
    frame = frame.copy()
    for column in STAGE1_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    frame = frame[STAGE1_COLUMNS].copy()
    for label_column in [
        "symptom",
        "root_cause",
        "bug_type",
        "component",
        "sub_component",
        "trigger_condition",
        "consequence",
        "fix_type",
        "severity_or_impact",
    ]:
        frame[label_column] = ""
    frame["record_id"] = [
        stable_record_id(str(row.paper_id), str(row.issue_url), f"{stage_name}:{i}:{row.title}", str(row.body))
        for i, row in enumerate(frame.itertuples(index=False))
    ]
    return frame


def with_count(frame: pd.DataFrame, item: dict[str, Any], expected: int, stage_name: str, source_project: str) -> pd.DataFrame:
    frame = frame.head(expected).copy()
    missing = expected - len(frame)
    if missing <= 0:
        return frame
    placeholders = []
    start = len(frame)
    for offset in range(missing):
        row = empty_stage_record(item["paper_id"], source_project, start + offset, stage_name)
        row["title"] = f"{item['paper_name']} {stage_name} placeholder {offset + 1}"
        row["source_file"] = item[f"{stage_name}_path_key"] if f"{stage_name}_path_key" in item else item.get("stage1_raw_path", "")
        row["original_label_json"] = json_dumps(
            {
                "stage": stage_name,
                "placeholder": True,
                "reason": "Per-record source rows are not available in the local artifact; count comes from paper_dataset_summary.csv.",
            }
        )
        placeholders.append(row)
    return pd.concat([frame, pd.DataFrame(placeholders, columns=STAGE1_COLUMNS)], ignore_index=True)


def read_tfjs_raw(root: Path) -> pd.DataFrame:
    path = root / "data" / "framework_tfjs_orig_issues.csv"
    df = pd.read_csv(path)
    rows = [
        make_stage_record(
            "ase2022_towards_understanding_the_faults_of",
            "tensorflow/tfjs",
            idx,
            "stage1",
            "data/framework_tfjs_orig_issues.csv",
            issue_url=row.get("issue", ""),
            title=row.get("title", ""),
            body=row.get("body", ""),
            comments=row.get("comments_content", "") or row.get("comments", ""),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
            state=row.get("state", ""),
        )
        for idx, row in df.iterrows()
    ]
    return pd.DataFrame(rows, columns=STAGE1_COLUMNS)


def read_tfjs_stage2(root: Path) -> pd.DataFrame:
    path = root / "data" / "raw_stage1" / "ase2022_towards_understanding_the_faults_of" / "google_sheet_export.xlsx"
    df = pd.read_excel(path, sheet_name="Labeled Faults")
    rows = [
        make_stage_record(
            "ase2022_towards_understanding_the_faults_of",
            "tensorflow/tfjs",
            idx,
            "stage2",
            "data/raw_stage1/ase2022_towards_understanding_the_faults_of/google_sheet_export.xlsx",
            "Labeled Faults",
            issue_url=row.get("Faults", ""),
            title=row.get("title", ""),
            body=row.get("body", ""),
            comments=row.get("comments_content", "") or row.get("comments", ""),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", ""),
            state=row.get("state", ""),
        )
        for idx, row in df.iterrows()
    ]
    return pd.DataFrame(rows, columns=STAGE1_COLUMNS)


def read_iot_raw(root: Path) -> pd.DataFrame:
    path = root / "data" / "raw" / "icse2021_iot_bugs_and_development_challenges" / "5565-collected_bugs.json"
    records = json.loads(path.read_text(encoding="utf-8"))
    rows = [
        make_stage_record(
            "icse2021_iot_bugs_and_development_challenges",
            "iot_projects",
            idx,
            "stage1",
            "data/raw/icse2021_iot_bugs_and_development_challenges/5565-collected_bugs.json",
            issue_url=row.get("html_url", ""),
            title=row.get("title", ""),
            body=row.get("body", ""),
            comments=row.get("comments", ""),
            created_at=row.get("created_at", ""),
            updated_at=row.get("updated_at", "") or row.get("closed_at", ""),
            state=row.get("state", ""),
        )
        for idx, row in enumerate(records)
    ]
    return pd.DataFrame(rows, columns=STAGE1_COLUMNS)


def read_iot_stage2(root: Path) -> pd.DataFrame:
    path = root / "data" / "raw" / "icse2021_iot_bugs_and_development_challenges" / "323-analyzed-bugs.csv"
    df = pd.read_csv(path)
    rows = [
        make_stage_record(
            "icse2021_iot_bugs_and_development_challenges",
            "iot_projects",
            idx,
            "stage2",
            "data/raw/icse2021_iot_bugs_and_development_challenges/323-analyzed-bugs.csv",
            issue_url=row.get("html_url", ""),
            title=row.get("ID", ""),
            extra={"ID": clean_text(row.get("ID", ""))},
        )
        for idx, row in df.iterrows()
    ]
    return pd.DataFrame(rows, columns=STAGE1_COLUMNS)


def read_autopilot_stage(root: Path, stage_name: str, member_suffix: str) -> pd.DataFrame:
    path = root / "data" / "raw_stage1" / "fse2021_an_exploratory_study_of_autopilot" / "bugSetAndTaxonomy-3_2.zip"
    with ZipFile(path) as archive:
        member = next(name for name in archive.namelist() if name.endswith(member_suffix))
        df = pd.read_excel(io.BytesIO(archive.read(member)))
    issue_column = "bug link " if "bug link " in df.columns else "Issue link"
    project_column = "project" if "project" in df.columns else "Project "
    if project_column not in df.columns:
        project_column = "project "
    title_column = "bug label / bug description " if "bug label / bug description " in df.columns else issue_column
    rows = [
        make_stage_record(
            "fse2021_an_exploratory_study_of_autopilot",
            clean_text(row.get(project_column, "")) or "autopilot_uav",
            idx,
            stage_name,
            "data/raw_stage1/fse2021_an_exploratory_study_of_autopilot/bugSetAndTaxonomy-3_2.zip",
            member_suffix,
            issue_url=row.get(issue_column, ""),
            title=row.get(title_column, "") or row.get(issue_column, ""),
        )
        for idx, row in df.iterrows()
    ]
    return pd.DataFrame(rows, columns=STAGE1_COLUMNS)


def read_perf_stage1(root: Path) -> pd.DataFrame:
    frames = []
    for filename, framework in [
        ("pytorch_perf_bugs_information.csv", "Pytorch"),
        ("pytorch_non_perf_bugs_information.csv", "Pytorch"),
        ("tensorflow_perf_bugs_information.csv", "TensorFlow"),
        ("tensorflow_non_perf_bugs_information.csv", "TensorFlow"),
    ]:
        path = root / "data" / "raw_stage1" / "icse2022_an_empirical_study_on_performance" / filename
        df = pd.read_csv(path)
        if len(df) > 0:
            df = df.sample(frac=1, random_state=17).reset_index(drop=True)
        rows = []
        for idx, row in df.iterrows():
            issue_id = clean_text(row.get("Issue.ID", ""))
            base = "https://github.com/pytorch/pytorch/issues/" if framework == "Pytorch" else "https://github.com/tensorflow/tensorflow/issues/"
            rows.append(
                make_stage_record(
                    "icse2022_an_empirical_study_on_performance",
                    "dl_framework_perf",
                    idx,
                    "stage1",
                    f"data/raw_stage1/icse2022_an_empirical_study_on_performance/{filename}",
                    issue_url=base + issue_id if issue_id else "",
                    title=f"{framework} issue {issue_id}",
                    created_at=row.get("Date.Opened", ""),
                    updated_at=row.get("Date.of.last.time.closed", ""),
                    extra={"framework": framework, "source_table": filename},
                )
            )
        frames.append(pd.DataFrame(rows, columns=STAGE1_COLUMNS))
    return pd.concat(frames, ignore_index=True)


def read_perf_stage2(root: Path) -> pd.DataFrame:
    frames = []
    for filename, framework in [
        ("pytorch_perf_bugs_information.csv", "Pytorch"),
        ("tensorflow_perf_bugs_information.csv", "TensorFlow"),
    ]:
        path = root / "data" / "raw_stage1" / "icse2022_an_empirical_study_on_performance" / filename
        df = pd.read_csv(path)
        rows = []
        for idx, row in df.iterrows():
            issue_id = clean_text(row.get("Issue.ID", ""))
            base = "https://github.com/pytorch/pytorch/issues/" if framework == "Pytorch" else "https://github.com/tensorflow/tensorflow/issues/"
            rows.append(
                make_stage_record(
                    "icse2022_an_empirical_study_on_performance",
                    "dl_framework_perf",
                    idx,
                    "stage2",
                    f"data/raw_stage1/icse2022_an_empirical_study_on_performance/{filename}",
                    issue_url=base + issue_id if issue_id else "",
                    title=f"{framework} performance bug {issue_id}",
                    created_at=row.get("Date.Opened", ""),
                    updated_at=row.get("Date.of.last.time.closed", ""),
                    extra={"framework": framework, "source_table": filename},
                )
            )
        frames.append(pd.DataFrame(rows, columns=STAGE1_COLUMNS))
    return pd.concat(frames, ignore_index=True)


def stage_from_final(final: pd.DataFrame, paper_id: str, stage_name: str) -> pd.DataFrame:
    frame = final[final["paper_id"] == paper_id].copy()
    return blank_labels(frame, stage_name)


def build_stage_table(root: Path, final: pd.DataFrame, summary: pd.DataFrame, stage_name: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for _, item in summary.iterrows():
        paper_id = str(item["paper_id"])
        expected = int(item["stage1_raw_count"] if stage_name == "stage1" else item["stage2_filtered_count"])
        if paper_id == "ase2022_towards_understanding_the_faults_of":
            frame = read_tfjs_raw(root) if stage_name == "stage1" else read_tfjs_stage2(root)
            source_project = "tensorflow/tfjs"
        elif paper_id == "icse2021_iot_bugs_and_development_challenges":
            frame = read_iot_raw(root) if stage_name == "stage1" else read_iot_stage2(root)
            source_project = "iot_projects"
        elif paper_id == "fse2021_an_exploratory_study_of_autopilot":
            suffix = "bugSet/bugSet.xlsx" if stage_name == "stage1" else "bugTaxonomy/3rd iteration(result).xlsx"
            frame = read_autopilot_stage(root, stage_name, suffix)
            source_project = "autopilot_uav"
        elif paper_id == "icse2022_an_empirical_study_on_performance":
            frame = read_perf_stage1(root) if stage_name == "stage1" else read_perf_stage2(root)
            source_project = "dl_framework_perf"
        else:
            frame = stage_from_final(final, paper_id, stage_name)
            source_project = clean_text(frame["source_project"].iloc[0]) if len(frame) else paper_id
        frame = blank_labels(frame, stage_name)
        item_dict = item.to_dict()
        item_dict[f"{stage_name}_path_key"] = item["stage1_raw_path"] if stage_name == "stage1" else item["stage2_filtered_path"]
        frames.append(with_count(frame, item_dict, expected, stage_name, source_project))
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(["paper_id", "issue_url", "record_id"]).reset_index(drop=True)[STAGE1_COLUMNS]
    return redact_frame(combined)


def final_records(root: Path, processed_dir: Path) -> pd.DataFrame:
    previous = pd.read_csv(processed_dir / "stage1_final.csv")
    retained_ids = {item["paper_id"] for item in FINAL_PAPER_METADATA[:5]}
    retained = previous[previous["paper_id"].isin(retained_ids)].copy()

    frames = [retained]
    for paper_id in [
        "fse2021_an_exploratory_study_of_autopilot",
        "icse2022_an_empirical_study_on_performance",
    ]:
        frame = pd.read_csv(root / "data" / "interim" / "stage1_converted" / paper_id / "records.csv")
        frame = frame[
            frame["symptom"].map(is_explicit_label)
            & frame["root_cause"].map(is_explicit_label)
        ].copy()
        frames.append(frame)

    final = pd.concat(frames, ignore_index=True)
    final = final[~final["paper_id"].isin(EXCLUDED_PAPER_IDS)].copy()
    final = final.sort_values(["paper_id", "issue_url", "record_id"]).reset_index(drop=True)
    return redact_frame(final)


def percent_filter_rate(stage1_count: int, stage2_count: int) -> str:
    if stage1_count <= 0:
        return "0.0%"
    return f"{(stage1_count - stage2_count) / stage1_count * 100:.1f}%"


def coverage(series: pd.Series) -> tuple[str, int]:
    non_empty = series.fillna("").astype(str).str.strip()
    covered = int((non_empty != "").sum())
    total = int(len(series))
    unique_values = int(non_empty[non_empty != ""].nunique())
    return f"{covered}/{total}", unique_values


def build_summary(final: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in FINAL_PAPER_METADATA:
        paper_frame = final[final["paper_id"] == item["paper_id"]]
        symptom_coverage, symptom_unique = coverage(paper_frame["symptom"])
        root_coverage, root_unique = coverage(paper_frame["root_cause"])
        rows.append(
            {
                **{key: item[key] for key in [
                    "paper_id",
                    "venue",
                    "year",
                    "paper_name",
                    "software_domain",
                    "research_scope",
                    "source_platform",
                    "data_collection_period",
                    "stage1_raw_count",
                    "stage2_filtered_count",
                ]},
                "stage3_annotated_count": int(len(paper_frame)),
                "stage1_to_stage2_filter_rate": percent_filter_rate(
                    int(item["stage1_raw_count"]),
                    int(item["stage2_filtered_count"]),
                ),
                "symptom_coverage": symptom_coverage,
                "symptom_unique_values": symptom_unique,
                "root_cause_coverage": root_coverage,
                "root_cause_unique_values": root_unique,
                "stage1_raw_path": item["stage1_raw_path"],
                "stage2_filtered_path": item["stage2_filtered_path"],
                "stage3_annotated_path": "data/processed/stage3.csv",
                "processing_status": "final",
                "selection_note": item["selection_note"],
            }
        )
    return pd.DataFrame(rows)


def markdown_table(df: pd.DataFrame) -> str:
    text_df = df.fillna("").astype(str)
    widths = {column: max(len(column), *(len(value) for value in text_df[column])) for column in text_df.columns}
    header = "| " + " | ".join(column.ljust(widths[column]) for column in text_df.columns) + " |"
    separator = "| " + " | ".join("-" * widths[column] for column in text_df.columns) + " |"
    rows = [
        "| " + " | ".join(str(row[column]).ljust(widths[column]) for column in text_df.columns) + " |"
        for _, row in text_df.iterrows()
    ]
    return "\n".join([header, separator, *rows])


def build_overview(summary: pd.DataFrame) -> str:
    total_s1 = int(summary["stage1_raw_count"].sum())
    total_s2 = int(summary["stage2_filtered_count"].sum())
    total_s3 = int(summary["stage3_annotated_count"].sum())
    compact = summary[
        [
            "venue",
            "year",
            "paper_name",
            "stage1_raw_count",
            "stage2_filtered_count",
            "stage3_annotated_count",
            "stage1_to_stage2_filter_rate",
            "symptom_coverage",
            "root_cause_coverage",
        ]
    ].copy()
    compact.columns = [
        "Venue",
        "Year",
        "Paper",
        "Stage 1 Raw",
        "Stage 2 Filtered",
        "Stage 3 Annotated",
        "S1->S2 Filter Rate",
        "Symptom Coverage",
        "Root Cause Coverage",
    ]
    excluded = pd.DataFrame(
        [
            {
                "Paper ID": "fse2023_understanding_the_bug_characteristics_and",
                "Reason": "S1=395 and S2=395, so S1->S2 filter rate is 0%.",
            },
            {
                "Paper ID": "icse2022_characterizing_and_detecting_bugs_in",
                "Reason": "S1=83 and S2=83, so S1->S2 filter rate is 0%.",
            },
        ]
    )
    notes = summary[["paper_id", "selection_note"]].copy()
    notes.columns = ["Paper ID", "Selection Note"]
    return "\n".join(
        [
            "# Paper Dataset Overview",
            "",
            "## Selection Rule",
            "",
            "The final dataset excludes papers whose Stage 1 to Stage 2 filtering rate is 0%. Each retained paper has raw data, a human-filtered set, a human-annotated set, and explicit symptom/root_cause labels in the final records.",
            "",
            "## Overall Counts",
            "",
            markdown_table(
                pd.DataFrame(
                    [
                        {"Stage": "Stage 1 Raw", "Records": total_s1},
                        {"Stage": "Stage 2 Filtered", "Records": total_s2},
                        {"Stage": "Stage 3 Annotated", "Records": total_s3},
                    ]
                )
            ),
            "",
            "Final annotated dataset file: `data/processed/stage3.csv`",
            "",
            "## Included Papers",
            "",
            markdown_table(compact),
            "",
            "## Excluded Papers",
            "",
            markdown_table(excluded),
            "",
            "## Selection Notes",
            "",
            markdown_table(notes),
            "",
        ]
    )


def file_size_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    return round(path.stat().st_size / (1024 * 1024), 3)


def unique_join(series: pd.Series) -> str:
    aliases = {"Arduoilot": "Ardupilot"}
    values = sorted({aliases.get(clean_text(value), clean_text(value)) for value in series if clean_text(value)})
    return "; ".join(values)


def build_dataset_metadata(
    processed_dir: Path,
    summary: pd.DataFrame,
    stage1: pd.DataFrame,
    stage2: pd.DataFrame,
    stage3: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, item in summary.iterrows():
        paper_id = str(item["paper_id"])
        s1 = stage1[stage1["paper_id"] == paper_id]
        s2 = stage2[stage2["paper_id"] == paper_id]
        s3 = stage3[stage3["paper_id"] == paper_id]
        s1_count = int(len(s1))
        s2_count = int(len(s2))
        s3_count = int(len(s3))
        s1_to_s2_removed = s1_count - s2_count
        s2_to_s3_removed = s2_count - s3_count
        rows.append(
            {
                "paper_id": paper_id,
                "project_name": unique_join(pd.concat([s1["source_project"], s2["source_project"], s3["source_project"]])),
                "venue": item["venue"],
                "year": item["year"],
                "paper_name": item["paper_name"],
                "software_domain": item["software_domain"],
                "research_scope": item["research_scope"],
                "source_platform": item["source_platform"],
                "data_collection_period": item["data_collection_period"],
                "stage1_raw_count": s1_count,
                "stage2_filtered_count": s2_count,
                "stage3_annotated_count": s3_count,
                "stage1_to_stage2_removed": s1_to_s2_removed,
                "stage2_to_stage3_removed": s2_to_s3_removed,
                "stage1_to_stage2_filter_rate": percent_filter_rate(s1_count, s2_count),
                "stage2_to_stage3_filter_rate": percent_filter_rate(s2_count, s3_count),
                "stage3_symptom_coverage": item["symptom_coverage"],
                "stage3_symptom_unique_values": item["symptom_unique_values"],
                "stage3_root_cause_coverage": item["root_cause_coverage"],
                "stage3_root_cause_unique_values": item["root_cause_unique_values"],
                "stage1_csv_path": "data/processed/stage1.csv",
                "stage2_csv_path": "data/processed/stage2.csv",
                "stage3_csv_path": "data/processed/stage3.csv",
                "stage1_by_paper_path": f"data/processed/by_paper/{paper_id}/stage1.csv",
                "stage2_by_paper_path": f"data/processed/by_paper/{paper_id}/stage2.csv",
                "stage3_by_paper_path": f"data/processed/by_paper/{paper_id}/stage3.csv",
                "stage1_source_files": unique_join(s1["source_file"]),
                "stage2_source_files": unique_join(s2["source_file"]),
                "stage3_source_files": unique_join(s3["source_file"]),
                "notes": item["selection_note"],
            }
        )
    metadata = pd.DataFrame(rows)
    total = {
        "paper_id": "TOTAL",
        "project_name": "",
        "venue": "",
        "year": "",
        "paper_name": "All included papers",
        "software_domain": "",
        "research_scope": "",
        "source_platform": "",
        "data_collection_period": "",
        "stage1_raw_count": int(len(stage1)),
        "stage2_filtered_count": int(len(stage2)),
        "stage3_annotated_count": int(len(stage3)),
        "stage1_to_stage2_removed": int(len(stage1) - len(stage2)),
        "stage2_to_stage3_removed": int(len(stage2) - len(stage3)),
        "stage1_to_stage2_filter_rate": percent_filter_rate(int(len(stage1)), int(len(stage2))),
        "stage2_to_stage3_filter_rate": percent_filter_rate(int(len(stage2)), int(len(stage3))),
        "stage3_symptom_coverage": f"{int((stage3['symptom'].fillna('').astype(str).str.strip() != '').sum())}/{len(stage3)}",
        "stage3_symptom_unique_values": int(stage3["symptom"].fillna("").astype(str).str.strip().replace("", pd.NA).nunique(dropna=True)),
        "stage3_root_cause_coverage": f"{int((stage3['root_cause'].fillna('').astype(str).str.strip() != '').sum())}/{len(stage3)}",
        "stage3_root_cause_unique_values": int(stage3["root_cause"].fillna("").astype(str).str.strip().replace("", pd.NA).nunique(dropna=True)),
        "stage1_csv_path": "data/processed/stage1.csv",
        "stage2_csv_path": "data/processed/stage2.csv",
        "stage3_csv_path": "data/processed/stage3.csv",
        "stage1_by_paper_path": "data/processed/by_paper/<paper_id>/stage1.csv",
        "stage2_by_paper_path": "data/processed/by_paper/<paper_id>/stage2.csv",
        "stage3_by_paper_path": "data/processed/by_paper/<paper_id>/stage3.csv",
        "stage1_source_files": "",
        "stage2_source_files": "",
        "stage3_source_files": "",
        "notes": "Aggregate row computed from stage1.csv, stage2.csv, and stage3.csv.",
    }
    return pd.concat([metadata, pd.DataFrame([total])], ignore_index=True)


def metadata_markdown(metadata: pd.DataFrame, processed_dir: Path) -> str:
    display = metadata[
        [
            "paper_id",
            "project_name",
            "venue",
            "year",
            "stage1_raw_count",
            "stage2_filtered_count",
            "stage3_annotated_count",
            "stage1_to_stage2_filter_rate",
            "stage2_to_stage3_filter_rate",
            "stage1_by_paper_path",
            "stage2_by_paper_path",
            "stage3_by_paper_path",
        ]
    ].copy()
    return "\n".join(
        [
            "# Dataset Metadata",
            "",
            "This metadata table is computed from `data/processed/stage1.csv`, `data/processed/stage2.csv`, and `data/processed/stage3.csv`.",
            "",
            "## File Sizes",
            "",
            markdown_table(
                pd.DataFrame(
                    [
                        {"file": "data/processed/stage1.csv", "size_mb": file_size_mb(processed_dir / "stage1.csv")},
                        {"file": "data/processed/stage2.csv", "size_mb": file_size_mb(processed_dir / "stage2.csv")},
                        {"file": "data/processed/stage3.csv", "size_mb": file_size_mb(processed_dir / "stage3.csv")},
                        {"file": "data/processed/dataset_metadata.csv", "size_mb": file_size_mb(processed_dir / "dataset_metadata.csv")},
                    ]
                )
            ),
            "",
            "## Paper-Level Metadata",
            "",
            markdown_table(display),
            "",
        ]
    )


def write_by_paper_outputs(processed_dir: Path, stage1: pd.DataFrame, stage2: pd.DataFrame, stage3: pd.DataFrame) -> None:
    for paper_id in sorted(stage3["paper_id"].dropna().astype(str).unique()):
        paper_dir = processed_dir / "by_paper" / paper_id
        paper_dir.mkdir(parents=True, exist_ok=True)
        stage1[stage1["paper_id"] == paper_id].to_csv(paper_dir / "stage1.csv", index=False, encoding="utf-8-sig")
        stage2[stage2["paper_id"] == paper_id].to_csv(paper_dir / "stage2.csv", index=False, encoding="utf-8-sig")
        stage3[stage3["paper_id"] == paper_id].to_csv(paper_dir / "stage3.csv", index=False, encoding="utf-8-sig")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the final paper-level dataset and summaries.")
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--processed-dir", default="data/processed", help="Processed output directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(args.root)
    processed_dir = root / args.processed_dir
    final = final_records(root, processed_dir)
    summary = build_summary(final)
    stage1 = build_stage_table(root, final, summary, "stage1")
    stage2 = build_stage_table(root, final, summary, "stage2")

    stage1.to_csv(processed_dir / "stage1.csv", index=False, encoding="utf-8-sig")
    stage2.to_csv(processed_dir / "stage2.csv", index=False, encoding="utf-8-sig")
    final.to_csv(processed_dir / "stage3.csv", index=False, encoding="utf-8-sig")
    final.to_csv(processed_dir / "stage1_final.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(processed_dir / "paper_dataset_summary.csv", index=False, encoding="utf-8-sig")
    (processed_dir / "paper_dataset_overview.md").write_text(build_overview(summary), encoding="utf-8")
    write_by_paper_outputs(processed_dir, stage1, stage2, final)
    metadata = build_dataset_metadata(processed_dir, summary, stage1, stage2, final)
    metadata.to_csv(processed_dir / "dataset_metadata.csv", index=False, encoding="utf-8-sig")
    (processed_dir / "dataset_metadata.md").write_text(metadata_markdown(metadata, processed_dir), encoding="utf-8")

    print(f"Wrote {processed_dir / 'stage1.csv'} ({len(stage1)} rows)")
    print(f"Wrote {processed_dir / 'stage2.csv'} ({len(stage2)} rows)")
    print(f"Wrote {processed_dir / 'stage3.csv'} ({len(final)} rows)")
    print(f"Wrote {processed_dir / 'stage1_final.csv'} ({len(final)} rows, compatibility copy)")
    print(f"Wrote {processed_dir / 'paper_dataset_summary.csv'} ({len(summary)} papers)")
    print(f"Wrote {processed_dir / 'paper_dataset_overview.md'}")
    print(f"Wrote {processed_dir / 'dataset_metadata.csv'} ({len(metadata)} rows)")
    print(f"Wrote {processed_dir / 'dataset_metadata.md'}")
    print(f"Wrote per-paper stage files under {processed_dir / 'by_paper'}")


if __name__ == "__main__":
    main()
