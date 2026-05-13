from __future__ import annotations

from dataclasses import dataclass
from typing import List


UNIFIED_COLUMNS: List[str] = [
    "record_id",
    "paper_id",
    "source_project",
    "artifact_type",
    "software_domain",
    "source_platform",
    "issue_url",
    "title",
    "body",
    "comments",
    "created_at",
    "updated_at",
    "state",
    "original_labels",
    "normalized_labels",
    "collection_metadata",
]


NORMALIZED_LABEL_KEYS: List[str] = [
    "bug_type",
    "symptom",
    "root_cause",
    "component",
    "fix_type",
    "severity_or_impact",
    "reproducibility",
    "mapping_confidence",
    "mapping_method",
]


@dataclass(frozen=True)
class LocalDatasetSpec:
    source_name: str
    path: str
    paper_id: str
    artifact_type: str
    software_domain: str
    source_platform: str
    source_project: str
    priority: int


LOCAL_DATASETS: List[LocalDatasetSpec] = [
    LocalDatasetSpec(
        source_name="tfjs_manual_fault_labels",
        path="data/clean_CollectedIssues.csv",
        paper_id="ase2022_towards_understanding_the_faults_of",
        artifact_type="bug_report",
        software_domain="deep_learning_framework",
        source_platform="github_issues",
        source_project="tensorflow/tfjs",
        priority=1,
    ),
    LocalDatasetSpec(
        source_name="tfjs_filtering_sample",
        path="data/sampled_issues_dataset.csv",
        paper_id="ase2022_towards_understanding_the_faults_of",
        artifact_type="bug_report",
        software_domain="deep_learning_framework",
        source_platform="github_issues",
        source_project="tensorflow/tfjs",
        priority=2,
    ),
    LocalDatasetSpec(
        source_name="tfjs_raw_issues",
        path="data/framework_tfjs_orig_issues.csv",
        paper_id="ase2022_towards_understanding_the_faults_of",
        artifact_type="bug_report",
        software_domain="deep_learning_framework",
        source_platform="github_issues",
        source_project="tensorflow/tfjs",
        priority=3,
    ),
]
