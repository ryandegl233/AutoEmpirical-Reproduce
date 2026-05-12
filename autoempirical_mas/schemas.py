from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional


TaskType = Literal["filtering", "classification"]


@dataclass
class IssueRecord:
    record_id: str
    task_type: TaskType
    title: str
    body: str
    comments_content: str
    state: str = ""
    created_at: str = ""
    issue_url: str = ""
    ground_truth_filter: Optional[int] = None
    ground_truth_symptom_id: Optional[str] = None
    ground_truth_root_cause_id: Optional[str] = None

    def issue_report(self) -> str:
        return (
            "## Issue Report\n"
            f"### Title\n{self.title}\n"
            f"### State\n{self.state}\n"
            f"### Created At\n{self.created_at}\n"
            f"### Body\n{self.body}\n"
            f"### Other Comments\n{self.comments_content}"
        )


@dataclass
class AgentCall:
    agent: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_seconds: float = 0.0
    raw_output: str = ""
    parsed_output: Dict[str, Any] = field(default_factory=dict)
    valid_json: bool = False
    error: Optional[str] = None


@dataclass
class EvidenceResult:
    evidence: List[str]
    missing_context: List[str]
    ambiguity_notes: List[str]


@dataclass
class FilteringDecision:
    label: Literal["Accepted", "Rejected"]
    confidence: float
    evidence: List[str]
    rationale: str


@dataclass
class ClassificationDecision:
    bug_symptom: Dict[str, str]
    root_cause: Dict[str, str]
    confidence: float
    evidence: List[str]
    rationale: str


@dataclass
class ExperimentResult:
    record_id: str
    task_type: TaskType
    issue_url: str
    variant: str
    final_output: Dict[str, Any]
    calls: List[AgentCall]
    invalid_output: bool
    wall_time_seconds: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    api_calls: int

    def to_jsonable(self) -> Dict[str, Any]:
        data = asdict(self)
        data["calls"] = [asdict(call) for call in self.calls]
        return data
