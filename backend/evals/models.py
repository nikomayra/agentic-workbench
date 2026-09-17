from enum import StrEnum, unique
from pathlib import Path

from pydantic import BaseModel, ConfigDict


@unique
class EvalConfiguration(StrEnum):
    """
    | `single_worker` | Raw objective → one worker |
    | `planner_worker` | Planner → its plan converted into one worker assignment |
    | `full_workflow` | Planner → decomposer → one/many workers → reviewer |
    """

    FULL_WORKFLOW = "full_workflow"
    SINGLE_WORKER = "single_worker"
    PLANNER_WORKER = "planner_worker"


class EvalCase(BaseModel):
    """One repeatable objective and its machine-checkable expectations."""

    model_config = ConfigDict(extra="forbid")

    id: str
    objective: str
    expected_path_prefixes: list[Path]
    forbidden_path_prefixes: list[Path]


class RunObservation(BaseModel):
    """Raw facts collected from one workflow run before it is scored."""

    tests_passed: bool
    changed_paths: list[Path]
    latency_seconds: float
    error: str | None = None
    metrics: TraceMetrics


class ExecutionFacts(BaseModel):
    tests_passed: bool
    changed_paths: list[Path]
    error: str | None = None


class EvalResult(BaseModel):
    """One report row combining the run facts with the scorer's judgment."""

    case_id: str
    configuration: str
    estimated_cost_usd: float | None = None
    trace_id: str
    observation: RunObservation
    passed: bool
    reasons: list[str]


class TraceMetrics(BaseModel):
    requests: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_input_tokens: int
    agent_turns: int
