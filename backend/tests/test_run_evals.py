import asyncio

import evals.run_evals as evals_module
from app.orchestration.state import CoordinatorExecution, CoordinatorStages
from evals.run_evals import evaluate_current_workflow
from tests.factories import (
    completed_work_record,
    construct_eval_case,
    construct_run_observation,
    finalization_state,
    pending_execution,
    sample_plan,
)


def test_evaluate_current_workflow_success(monkeypatch):
    test_eval_case = construct_eval_case(
        expected_path_prefixes=["backend/"],
        forbidden_path_prefixes=["frontend/"],
    )
    test_run_observation = construct_run_observation(
        tests_passed=True,
        changed_paths=["backend/app/models.py", "backend/app/schemas.py"],
    )
    test_run_state = finalization_state()
    cleaned_states: list[CoordinatorExecution] = []

    async def fake_run_until_final_approval(case):
        assert case == test_eval_case
        return test_run_state

    def fake_build_run_observation(worktree, latency_seconds):
        assert worktree == test_run_state.integration_worktree
        assert latency_seconds >= 0
        return test_run_observation

    monkeypatch.setattr(
        evals_module, "_run_until_final_approval", fake_run_until_final_approval
    )
    monkeypatch.setattr(
        evals_module, "_build_run_observation", fake_build_run_observation
    )
    monkeypatch.setattr(
        evals_module, "_clean_up_resources", cleaned_states.append
    )

    result = asyncio.run(evaluate_current_workflow(test_eval_case))


    assert result.case_id == test_eval_case.id
    assert result.configuration == "full_workflow"
    assert result.observation == test_run_observation
    assert result.passed
    assert result.reasons == []
    assert cleaned_states == [test_run_state]


def test_evaluate_current_workflow_failure_records_error_and_cleans_owned_state(
    monkeypatch,
):
    test_eval_case = construct_eval_case(
        expected_path_prefixes=["backend/"],
        forbidden_path_prefixes=["frontend/"],
    )
    pending_work = completed_work_record("backend").model_copy(
        update={"work_execution": pending_execution("approval-1")}
    )
    partial_state = CoordinatorExecution(
        stage=CoordinatorStages.AWAITING_APPROVALS,
        work_records=[pending_work],
    )
    cleaned_states: list[CoordinatorExecution] = []

    async def fake_invoke_planner(_trusted_root, objective):
        assert objective == test_eval_case.objective
        return sample_plan()

    async def fake_start_coordinator(_plan):
        return partial_state

    async def fake_resume_coordinator(_plan, _state, _resolutions):
        raise RuntimeError("worker resume failed")

    monkeypatch.setattr(evals_module, "invoke_planner", fake_invoke_planner)
    monkeypatch.setattr(evals_module, "start_coordinator", fake_start_coordinator)
    monkeypatch.setattr(evals_module, "resume_coordinator", fake_resume_coordinator)
    monkeypatch.setattr(
        evals_module, "_clean_up_resources", cleaned_states.append
    )

    result = asyncio.run(evaluate_current_workflow(test_eval_case))

    assert not result.passed
    assert not result.observation.tests_passed
    assert result.observation.changed_paths == []
    assert result.observation.error == "RuntimeError: worker resume failed"
    assert "Workflow Error: RuntimeError: worker resume failed" in result.reasons
    assert cleaned_states == [partial_state]
