from __future__ import annotations

from typing import Iterable, Optional

import pandas as pd

from .schemas import IssueRecord, TaskType


def _row_text(row: pd.Series, *columns: str) -> str:
    for column in columns:
        if column in row and pd.notna(row.get(column)):
            return str(row.get(column))
    return ""


def load_records(task: TaskType, path: Optional[str] = None, limit: Optional[int] = None) -> Iterable[IssueRecord]:
    if task == "filtering":
        csv_path = path or "data/sampled_issues_dataset.csv"
        df = pd.read_csv(csv_path)
        source = df.head(limit) if limit else df
        for idx, row in source.iterrows():
            yield IssueRecord(
                record_id=_row_text(row, "record_id") or str(idx),
                task_type="filtering",
                issue_url=_row_text(row, "issue", "issue_url", "url"),
                title=_row_text(row, "title"),
                state=_row_text(row, "state"),
                created_at=_row_text(row, "created_at"),
                body=_row_text(row, "body"),
                comments_content=_row_text(row, "comments_content", "comments"),
                ground_truth_filter=int(row.get("label")) if "label" in row and pd.notna(row.get("label")) else None,
            )
    else:
        csv_path = path or "data/clean_CollectedIssues.csv"
        df = pd.read_csv(csv_path)
        source = df.head(limit) if limit else df
        for idx, row in source.iterrows():
            yield IssueRecord(
                record_id=_row_text(row, "record_id") or str(idx),
                task_type="classification",
                issue_url=_row_text(row, "Faults", "issue_url", "issue", "url"),
                title=_row_text(row, "title"),
                state=_row_text(row, "state"),
                created_at=_row_text(row, "created_at"),
                body=_row_text(row, "body"),
                comments_content=_row_text(row, "comments_content", "comments"),
                ground_truth_symptom_id=str(row.get("symptom_id", "")),
                ground_truth_root_cause_id=str(row.get("root_causes_id", "")),
            )
