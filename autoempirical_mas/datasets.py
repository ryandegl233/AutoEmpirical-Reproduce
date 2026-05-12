from __future__ import annotations

from typing import Iterable, Optional

import pandas as pd

from .schemas import IssueRecord, TaskType


def load_records(task: TaskType, path: Optional[str] = None, limit: Optional[int] = None) -> Iterable[IssueRecord]:
    if task == "filtering":
        csv_path = path or "data/sampled_issues_dataset.csv"
        df = pd.read_csv(csv_path)
        source = df.head(limit) if limit else df
        for idx, row in source.iterrows():
            yield IssueRecord(
                record_id=str(idx),
                task_type="filtering",
                issue_url=str(row.get("issue", "")),
                title=str(row.get("title", "")),
                state=str(row.get("state", "")),
                created_at=str(row.get("created_at", "")),
                body=str(row.get("body", "")),
                comments_content=str(row.get("comments_content", "")),
                ground_truth_filter=int(row.get("label")) if "label" in row and pd.notna(row.get("label")) else None,
            )
    else:
        csv_path = path or "data/clean_CollectedIssues.csv"
        df = pd.read_csv(csv_path)
        source = df.head(limit) if limit else df
        for idx, row in source.iterrows():
            yield IssueRecord(
                record_id=str(idx),
                task_type="classification",
                issue_url=str(row.get("Faults", "")),
                title=str(row.get("title", "")),
                state=str(row.get("state", "")),
                created_at=str(row.get("created_at", "")),
                body=str(row.get("body", "")),
                comments_content=str(row.get("comments_content", "")),
                ground_truth_symptom_id=str(row.get("symptom_id", "")),
                ground_truth_root_cause_id=str(row.get("root_causes_id", "")),
            )
