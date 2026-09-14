from pathlib import Path

from pydantic import BaseModel, ConfigDict


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


class EvalResult(BaseModel):
    """One report row combining the run facts with the scorer's judgment."""

    case_id: str
    configuration: str
    observation: RunObservation
    passed: bool
    reasons: list[str]
