from evals.scoring import case_scorer
from tests.factories import construct_eval_case, construct_run_observation


def test_known_result_passes():
    expected_path_prefixes = ["backend/"]
    forbidden_path_prefixes = ["frontend/"]

    changed_paths = ["backend/app/models.py", "backend/app/schemas.py"]

    test_eval_case = construct_eval_case(
        expected_path_prefixes, forbidden_path_prefixes
    )
    test_run_observation = construct_run_observation(
        tests_passed=True, changed_paths=changed_paths
    )

    score = case_scorer(test_eval_case, test_run_observation)

    assert score.passed
    assert not score.reasons


def test_known_result_fails_and_reports_why():
    expected_path_prefixes = ["backend/"]
    forbidden_path_prefixes = ["frontend/"]

    changed_paths = ["frontend/src/App.tsx"]

    test_eval_case = construct_eval_case(
        expected_path_prefixes, forbidden_path_prefixes
    )
    test_run_observation = construct_run_observation(
        tests_passed=False, changed_paths=changed_paths
    )

    score = case_scorer(test_eval_case, test_run_observation)

    assert not score.passed
    assert score.reasons == [
        "Tests Failed",
        "Expected path areas not touched: backend",
        "Forbidden path areas affected: frontend/src/App.tsx",
    ]
