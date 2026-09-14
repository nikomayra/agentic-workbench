from dataclasses import dataclass
from pathlib import Path

from evals.models import EvalCase, RunObservation


@dataclass(frozen=True)
class CaseScore:
    passed: bool
    reasons: list[str]


def _is_within(path: Path, prefix: Path) -> bool:
    """Return whether path is the prefix itself or one of its descendants."""
    return prefix == path or prefix in path.parents


def case_scorer(eval_case: EvalCase, run_observation: RunObservation) -> CaseScore:
    """
    Initial Rules:
    - No workflow error
    - Tests passed
    - Every expected path prefix was touched
    - No forbidden path prefix was touched
    """
    reasons: list[str] = []
    if run_observation.error:
        reasons.append(f"Workflow Error: {run_observation.error}")

    if not run_observation.tests_passed:
        reasons.append("Tests Failed")

    missing_expected_prefixes = [
        prefix
        for prefix in eval_case.expected_path_prefixes
        if not any(
            _is_within(path, prefix) for path in run_observation.changed_paths
        )
    ]
    forbidden_paths = [
        path
        for path in run_observation.changed_paths
        if any(
            _is_within(path, prefix)
            for prefix in eval_case.forbidden_path_prefixes
        )
    ]

    if missing_expected_prefixes:
        reasons.append(
            "Expected path areas not touched: "
            + ", ".join(path.as_posix() for path in missing_expected_prefixes)
        )

    if forbidden_paths:
        reasons.append(
            "Forbidden path areas affected: "
            + ", ".join(path.as_posix() for path in forbidden_paths)
        )

    return CaseScore(passed=not reasons, reasons=reasons)
