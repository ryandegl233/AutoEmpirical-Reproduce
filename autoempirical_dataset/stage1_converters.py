from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from zipfile import ZipFile

import pandas as pd

from autoempirical_dataset.converters import clean_text, json_dumps, parse_time, stable_record_id


STAGE1_COLUMNS = [
    "record_id",
    "paper_id",
    "source_project",
    "issue_url",
    "title",
    "body",
    "comments",
    "created_at",
    "updated_at",
    "state",
    "symptom",
    "root_cause",
    "bug_type",
    "component",
    "sub_component",
    "trigger_condition",
    "consequence",
    "fix_type",
    "severity_or_impact",
    "original_label_json",
    "source_file",
    "source_sheet",
    "source_row_index",
]


@dataclass(frozen=True)
class Stage1SourceSpec:
    paper_id: str
    source_project: str
    source_file: str
    source_sheet: str
    converter: Callable[[Path, "Stage1SourceSpec"], pd.DataFrame]


def original_json(row: pd.Series, fields: list[str]) -> str:
    return json_dumps({field: clean_text(row.get(field, "")) for field in fields if clean_text(row.get(field, ""))})


def single_line_text(value: Any) -> str:
    return " ".join(clean_text(value).split())


def make_record(spec: Stage1SourceSpec, row: pd.Series, idx: int, **values: Any) -> dict[str, Any]:
    issue_url = clean_text(values.get("issue_url", ""))
    title = clean_text(values.get("title", ""))
    body = clean_text(values.get("body", ""))
    record = {column: "" for column in STAGE1_COLUMNS}
    record.update(
        {
            "record_id": stable_record_id(spec.paper_id, issue_url, title, body or json.dumps(values, ensure_ascii=False)),
            "paper_id": spec.paper_id,
            "source_project": spec.source_project,
            "issue_url": issue_url,
            "title": title,
            "body": body,
            "comments": clean_text(values.get("comments", "")),
            "created_at": parse_time(values.get("created_at", "")),
            "updated_at": parse_time(values.get("updated_at", "")),
            "state": clean_text(values.get("state", "")),
            "symptom": clean_text(values.get("symptom", "")),
            "root_cause": clean_text(values.get("root_cause", "")),
            "bug_type": clean_text(values.get("bug_type", "")),
            "component": clean_text(values.get("component", "")),
            "sub_component": clean_text(values.get("sub_component", "")),
            "trigger_condition": clean_text(values.get("trigger_condition", "")),
            "consequence": clean_text(values.get("consequence", "")),
            "fix_type": clean_text(values.get("fix_type", "")),
            "severity_or_impact": clean_text(values.get("severity_or_impact", "")),
            "original_label_json": clean_text(values.get("original_label_json", "{}")) or "{}",
            "source_file": spec.source_file,
            "source_sheet": spec.source_sheet,
            "source_row_index": int(idx),
        }
    )
    for column in STAGE1_COLUMNS:
        if column != "source_row_index":
            record[column] = single_line_text(record[column])
    return record


def non_empty_frame(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=STAGE1_COLUMNS)


def read_csv_multilevel_header(path: Path) -> pd.DataFrame:
    header = pd.read_csv(path, nrows=2, header=None)
    names = []
    for top, bottom in zip(header.iloc[0], header.iloc[1]):
        top_text = clean_text(top)
        bottom_text = clean_text(bottom)
        names.append(bottom_text or top_text)
    return pd.read_csv(path, skiprows=2, names=names)


def read_excel_table(path: Path, sheet: str, header: int = 0) -> pd.DataFrame:
    return pd.read_excel(path, sheet_name=sheet, header=header)


def convert_ase2020_cp_detector(root: Path, spec: Stage1SourceSpec) -> pd.DataFrame:
    path = root / spec.source_file
    df = pd.read_excel(path, sheet_name=spec.source_sheet, header=1)
    rows = []
    for idx, row in df.iterrows():
        bug_id = clean_text(row.get("bugID（link）", ""))
        if not bug_id:
            continue
        rows.append(
            make_record(
                spec,
                row,
                idx,
                issue_url=bug_id if bug_id.startswith("http") else "",
                title=bug_id,
                body=bug_id,
                symptom=row.get("Symptom", ""),
                root_cause=row.get("Configuration Option", ""),
                bug_type="configuration-related performance bug",
                component=row.get("Running Stage", ""),
                sub_component=row.get("Configuration Option", ""),
                trigger_condition=row.get("Numeric", ""),
                consequence=row.get("Symptom pattern", ""),
                original_label_json=original_json(row, list(map(str, df.columns))),
            )
        )
    return non_empty_frame(rows)


def convert_ase2021_wasm(root: Path, spec: Stage1SourceSpec) -> pd.DataFrame:
    df = read_csv_multilevel_header(root / spec.source_file)
    rows = []
    for idx, row in df.iterrows():
        issue_url = clean_text(row.get("URL", ""))
        if not issue_url:
            continue
        symptom_bits = [
            name
            for name in [
                "Stack Trace?",
                "Incorrect Result Output/ Ground Truth Known?",
                "Faulty WebAssembly Output?",
                "Cannot Reproduce Locally",
            ]
            if clean_text(row.get(name, "")).upper() == "TRUE"
        ]
        rows.append(
            make_record(
                spec,
                row,
                idx,
                issue_url=issue_url,
                title=row.get("Title", ""),
                created_at=row.get("Created Date", ""),
                updated_at=row.get("Closed Date", ""),
                symptom="; ".join(symptom_bits),
                root_cause=row.get("Root Cause Category", ""),
                bug_type=row.get("WebAssembly-Specific Paradigm", ""),
                component=row.get("Root Cause Category 2", ""),
                fix_type=row.get("Bug Fix Category", ""),
                original_label_json=original_json(row, list(map(str, df.columns))),
            )
        )
    return non_empty_frame(rows)


def convert_tfjs(root: Path, spec: Stage1SourceSpec) -> pd.DataFrame:
    df = read_excel_table(root / spec.source_file, spec.source_sheet)
    rows = []
    fields = list(map(str, df.columns))
    for idx, row in df.iterrows():
        issue_url = clean_text(row.get("Faults", ""))
        if not issue_url:
            continue
        rows.append(
            make_record(
                spec,
                row,
                idx,
                issue_url=issue_url,
                title=row.get("title", ""),
                body=row.get("body", ""),
                comments=row.get("comments_content", "") or row.get("comments", ""),
                created_at=row.get("created_at", ""),
                updated_at=row.get("updated_at", ""),
                state=row.get("state", ""),
                symptom=row.get("symptoms", ""),
                root_cause=row.get("root causes", ""),
                component=row.get("components of Tensorflow.js", ""),
                sub_component=row.get("sub-component", ""),
                fix_type=row.get("fix patterns", "") or row.get("fix", ""),
                bug_type=row.get("3-level architecture", ""),
                original_label_json=original_json(row, fields),
            )
        )
    return non_empty_frame(rows)


def convert_autopilot_zip(root: Path, spec: Stage1SourceSpec) -> pd.DataFrame:
    path = root / spec.source_file
    with ZipFile(path) as archive:
        taxonomy_member = next(name for name in archive.namelist() if name.endswith("bugTaxonomy/3rd iteration(result).xlsx"))
        desc_member = next(name for name in archive.namelist() if name.endswith("bugTaxonomy/1st Iteration.xlsx"))
        taxonomy_content = io.BytesIO(archive.read(taxonomy_member))
        desc_content = io.BytesIO(archive.read(desc_member))
    df = pd.read_excel(taxonomy_content)
    desc_df = pd.read_excel(desc_content)
    descriptions = {
        clean_text(row.get("Issue link", "")): clean_text(row.get("bug label / bug description ", ""))
        for _, row in desc_df.iterrows()
    }
    rows = []
    fields = list(map(str, df.columns))
    for idx, row in df.iterrows():
        issue_url = clean_text(row.get("bug link ", ""))
        if not issue_url:
            continue
        description = descriptions.get(issue_url, "")
        rows.append(
            make_record(
                spec,
                row,
                idx,
                issue_url=issue_url,
                title=description or issue_url,
                body=description,
                symptom=description,
                root_cause=row.get("category", ""),
                bug_type=row.get("category", ""),
                component=row.get("project", ""),
                original_label_json=json_dumps(
                    {
                        "taxonomy": {field: clean_text(row.get(field, "")) for field in fields},
                        "first_iteration_description": description,
                    }
                ),
            )
        )
    return non_empty_frame(rows)


def convert_fse2023_fl(root: Path, spec: Stage1SourceSpec) -> pd.DataFrame:
    df = read_excel_table(root / spec.source_file, spec.source_sheet)
    rows = []
    fields = [field for field in map(str, df.columns) if not field.startswith("Unnamed")]
    for idx, row in df.iterrows():
        issue_url = clean_text(row.get("Bug", ""))
        if not issue_url.startswith("http"):
            continue
        rows.append(
            make_record(
                spec,
                row,
                idx,
                issue_url=issue_url,
                source_project=row.get("Framework", ""),
                title=row.get("Bug", ""),
                symptom=row.get("Symptom", ""),
                root_cause=row.get("Root Cause", ""),
                bug_type=row.get("Bug Stage", ""),
                component=row.get("Framework", ""),
                original_label_json=original_json(row, fields),
            )
        )
    return non_empty_frame(rows)


def parse_labels_cell(value: Any) -> dict[str, Any]:
    text = clean_text(value)
    labels: dict[str, Any] = {}
    for part in text.splitlines():
        if ":" in part:
            key, raw = part.split(":", 1)
            labels[clean_text(key)] = clean_text(raw)
    return labels


def convert_icpc2025_app_ui(root: Path, spec: Stage1SourceSpec) -> pd.DataFrame:
    path = root / spec.source_file
    frames = []
    for sheet in ["development_set", "test_set"]:
        df = read_excel_table(path, sheet)
        rows = []
        fields = list(map(str, df.columns))
        for idx, row in df.iterrows():
            labels = parse_labels_cell(row.get("Labels", ""))
            bug_type = clean_text(row.get("AndroR2 Bug Type", ""))
            symptom = labels.get("OBs", "") or bug_type
            rows.append(
                make_record(
                    Stage1SourceSpec(spec.paper_id, spec.source_project, spec.source_file, sheet, spec.converter),
                    row,
                    idx,
                    issue_url=row.get("Links", ""),
                    title=f"Bug {clean_text(row.get('Bug_id', ''))}".strip(),
                    body=row.get("Bug Reports", ""),
                    symptom=symptom,
                    root_cause="",
                    bug_type=bug_type,
                    original_label_json=json_dumps({"source_fields": {field: clean_text(row.get(field, "")) for field in fields}, "parsed_labels": labels}),
                )
            )
        frames.append(non_empty_frame(rows))
    return pd.concat(frames, ignore_index=True)


def convert_icse2022_perf(root: Path, spec: Stage1SourceSpec) -> pd.DataFrame:
    df = pd.read_csv(root / spec.source_file)
    rows = []
    for idx, row in df.iterrows():
        issue_id = clean_text(row.get("Issue.ID", ""))
        framework = clean_text(row.get("Framework", ""))
        if not issue_id:
            continue
        base = "https://github.com/pytorch/pytorch/issues/" if framework.lower().startswith("pytorch") else "https://github.com/tensorflow/tensorflow/issues/"
        rows.append(
            make_record(
                spec,
                row,
                idx,
                issue_url=base + issue_id,
                title=f"{framework} performance bug {issue_id}",
                symptom="performance bug",
                root_cause=row.get("Category", ""),
                bug_type="performance bug",
                component=framework,
                original_label_json=original_json(row, list(map(str, df.columns))),
            )
        )
    return non_empty_frame(rows)


def convert_icse2022_webug(root: Path, spec: Stage1SourceSpec) -> pd.DataFrame:
    df = read_excel_table(root / spec.source_file, spec.source_sheet)
    rows = []
    fields = list(map(str, df.columns))
    for idx, row in df.iterrows():
        issue_url = clean_text(row.get("Bug_url", ""))
        if not issue_url:
            continue
        rows.append(
            make_record(
                spec,
                row,
                idx,
                issue_url=issue_url,
                title=row.get("Bug_Description", ""),
                body=row.get("Bug_Description", ""),
                symptom=row.get("Consequence", ""),
                root_cause=row.get("Root Cause", ""),
                bug_type=row.get("Source", ""),
                component=row.get("Project", ""),
                sub_component=row.get("Sub_cause", ""),
                trigger_condition=row.get("Trigger_Condition", ""),
                consequence=row.get("Consequence", ""),
                fix_type=row.get("Fix_Strategy", ""),
                original_label_json=original_json(row, fields),
            )
        )
    return non_empty_frame(rows)


def convert_icse2023_pytorch(root: Path, spec: Stage1SourceSpec) -> pd.DataFrame:
    df = read_excel_table(root / spec.source_file, spec.source_sheet)
    rows = []
    fields = list(map(str, df.columns))
    for idx, row in df.iterrows():
        issue_url = clean_text(row.get("Issue URL", ""))
        if not issue_url:
            continue
        rows.append(
            make_record(
                spec,
                row,
                idx,
                issue_url=issue_url,
                title=f"PyTorch issue {clean_text(row.get('Issue #', ''))}",
                symptom=row.get("Symptom", ""),
                root_cause=row.get("Root cause", ""),
                component=row.get("Component", ""),
                fix_type=row.get("Repair pattern", ""),
                original_label_json=original_json(row, fields),
            )
        )
    return non_empty_frame(rows)


def convert_icse2024_txbug(root: Path, spec: Stage1SourceSpec) -> pd.DataFrame:
    df = pd.read_excel(root / spec.source_file, sheet_name=spec.source_sheet, header=0)
    rows = []
    fields = list(map(str, df.columns))
    symptom_column = (
        "Failure Symptom\n"
        "1. Incorrect database state\n"
        "2. Incorrect DBMS state\n"
        "3. Incorrect query result\n"
        "4. Unexpected error\n"
        "5. Operation error\n"
        "6. Assertion fail\n"
        "7. Crash\n"
        "8. DBMS hang\n"
        "9. Missing blocking\n"
        "10. Unnecessary blocking\n"
        "11. Unnecessarily long blocking\n"
        "12. Low performance\n"
        "13. Wrong error message\n"
        "14. Missing error"
    )
    fix_pattern_column = "Fix Pattern\n1. Document fix\n2. Code fix\n3. -"
    for idx, row in df.iterrows():
        bug_url = clean_text(row.get("Bug URL", ""))
        bug_id = clean_text(row.get(" Bug ID", "")) or clean_text(row.get("Bug ID", ""))
        if not bug_url.startswith("http"):
            continue
        report_description = clean_text(row.get("Bug Report Description", ""))
        triggering_description = clean_text(row.get("Triggering Description", ""))
        rows.append(
            make_record(
                spec,
                row,
                idx,
                issue_url=bug_url,
                title=report_description or bug_id,
                body=report_description,
                created_at=row.get("Submitted Date", ""),
                state=row.get("Bug Status", ""),
                symptom=row.get(symptom_column, ""),
                root_cause=row.get("Root Cause", ""),
                component=row.get("Database", ""),
                trigger_condition=triggering_description,
                severity_or_impact=row.get("Severity", ""),
                fix_type=row.get(fix_pattern_column, "") or row.get("Fixing Information", ""),
                original_label_json=original_json(row, fields),
            )
        )
    return non_empty_frame(rows)


STAGE1_SOURCES = [
    Stage1SourceSpec("ase2021_an_empirical_study_of_bugs", "webassembly_compilers", "data/raw_stage1/ase2021_an_empirical_study_of_bugs/qualitative_dataset.csv", "", convert_ase2021_wasm),
    Stage1SourceSpec("ase2022_towards_understanding_the_faults_of", "tensorflow/tfjs", "data/raw_stage1/ase2022_towards_understanding_the_faults_of/google_sheet_export.xlsx", "Labeled Faults", convert_tfjs),
    Stage1SourceSpec("fse2021_an_exploratory_study_of_autopilot", "autopilot_uav", "data/raw_stage1/fse2021_an_exploratory_study_of_autopilot/bugSetAndTaxonomy-3_2.zip", "bugTaxonomy/3rd iteration(result).xlsx", convert_autopilot_zip),
    Stage1SourceSpec("fse2023_understanding_the_bug_characteristics_and", "federated_learning", "data/raw_stage1/fse2023_understanding_the_bug_characteristics_and/Manual_Labelling__Manual_Labelling.xlsx", "Sheet1", convert_fse2023_fl),
    Stage1SourceSpec("icse2022_an_empirical_study_on_performance", "dl_framework_perf", "data/raw_stage1/icse2022_an_empirical_study_on_performance/perf_bugs_taxonomy.csv", "", convert_icse2022_perf),
    Stage1SourceSpec("icse2022_characterizing_and_detecting_bugs_in", "wechat_miniprograms", "data/raw_stage1/icse2022_characterizing_and_detecting_bugs_in/BugSet.xlsx", "Sheet1", convert_icse2022_webug),
    Stage1SourceSpec("icse2023_an_empirical_study_on_bugs", "pytorch", "data/raw_stage1/icse2023_an_empirical_study_on_bugs/PyTorchBugDataset.xlsx", "Dataset", convert_icse2023_pytorch),
    Stage1SourceSpec("icse2024_understanding_transaction_bugs_in_database", "database_transactions", "data/raw_stage1/icse2024_understanding_transaction_bugs_in_database/TXBug_Set.xlsx", "ALL", convert_icse2024_txbug),
]


def convert_stage1_source(root: Path, spec: Stage1SourceSpec) -> pd.DataFrame:
    frame = spec.converter(root, spec)
    return frame[STAGE1_COLUMNS]


def convert_all_stage1_sources(root: Path) -> dict[str, pd.DataFrame]:
    return {spec.paper_id: convert_stage1_source(root, spec) for spec in STAGE1_SOURCES}


def merge_stage1_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    if not frames:
        return pd.DataFrame(columns=STAGE1_COLUMNS)
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.drop_duplicates(subset=["record_id"], keep="first")
    return combined.sort_values(["paper_id", "issue_url", "record_id"]).reset_index(drop=True)[STAGE1_COLUMNS]


def build_conversion_report(converted: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    spec_by_id = {spec.paper_id: spec for spec in STAGE1_SOURCES}
    for paper_id, frame in converted.items():
        spec = spec_by_id[paper_id]
        rows.append(
            {
                "paper_id": paper_id,
                "source_file": spec.source_file,
                "source_sheet": spec.source_sheet,
                "output_rows": len(frame),
                "missing_symptom": int((frame["symptom"].astype(str).str.strip() == "").sum()) if len(frame) else 0,
                "missing_root_cause": int((frame["root_cause"].astype(str).str.strip() == "").sum()) if len(frame) else 0,
            }
        )
    return pd.DataFrame(rows)


def label_dictionary_markdown() -> str:
    descriptions = {
        "record_id": "Stable identifier scoped by paper_id and issue URL or row content.",
        "paper_id": "Stable paper/source identifier.",
        "source_project": "Project, ecosystem, or study-specific source name.",
        "issue_url": "Canonical bug/issue/report URL when available.",
        "title": "Bug/report title or concise record summary.",
        "body": "Bug report body, description, or primary source text.",
        "comments": "Comments or discussion text when available.",
        "created_at": "Parsed creation/submission timestamp when available.",
        "updated_at": "Parsed update/close timestamp when available.",
        "state": "Original issue/report state.",
        "symptom": "Observed failure, behavior, symptom, consequence, or equivalent source label.",
        "root_cause": "Root cause, cause category, taxonomy category, configuration option, or equivalent source label.",
        "bug_type": "Source bug type/category.",
        "component": "Affected framework/project/component.",
        "sub_component": "Source sub-component or subtype.",
        "trigger_condition": "Triggering condition or reproduction condition.",
        "consequence": "Failure consequence/effect.",
        "fix_type": "Repair/fix pattern or strategy.",
        "severity_or_impact": "Severity, priority, or impact label.",
        "original_label_json": "JSON preserving source labels and mapped fields.",
        "source_file": "Raw stage1 file used by the converter.",
        "source_sheet": "Sheet name or logical table name.",
        "source_row_index": "Zero-based source row index after parser header handling.",
    }
    lines = ["# Stage1 Label Dictionary", ""]
    for column in STAGE1_COLUMNS:
        lines.extend([f"## `{column}`", "", descriptions[column], ""])
    return "\n".join(lines)
