from pathlib import Path

from evals.models import EvalCase, RunObservation
from evals.scoring import case_scorer


def _construct_eval_case(
    expected_path_prefixes: list[str], forbidden_path_prefixes: list[str]
) -> EvalCase:
    return EvalCase(
        id="test_eval_case",
        objective="test_objective",
        expected_path_prefixes=[Path(prefix) for prefix in expected_path_prefixes],
        forbidden_path_prefixes=[Path(prefix) for prefix in forbidden_path_prefixes],
    )


def _construct_run_observation(
    tests_passed: bool, changed_paths: list[str], error: str | None = None
) -> RunObservation:
    return RunObservation(
        tests_passed=tests_passed,
        changed_paths=[Path(path) for path in changed_paths],
        latency_seconds=50,
        error=error,
    )


def test_known_result_passes():
    expected_path_prefixes = ["backend/"]
    forbidden_path_prefixes = ["frontend/"]

    changed_paths = ["backend/app/models.py", "backend/app/schemas.py"]

    test_eval_case = _construct_eval_case(
        expected_path_prefixes, forbidden_path_prefixes
    )
    test_run_observation = _construct_run_observation(
        tests_passed=True, changed_paths=changed_paths
    )

    score = case_scorer(test_eval_case, test_run_observation)

    assert score.passed
    assert not score.reasons


def test_known_result_fails_and_reports_why():
    expected_path_prefixes = ["backend/"]
    forbidden_path_prefixes = ["frontend/"]

    changed_paths = ["frontend/src/App.tsx"]

    test_eval_case = _construct_eval_case(
        expected_path_prefixes, forbidden_path_prefixes
    )
    test_run_observation = _construct_run_observation(
        tests_passed=False, changed_paths=changed_paths
    )

    score = case_scorer(test_eval_case, test_run_observation)

    assert not score.passed
    assert score.reasons == [
        "Tests Failed",
        "Expected path areas not touched: backend",
        "Forbidden path areas affected: frontend/src/App.tsx",
    ]
