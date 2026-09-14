import asyncio
import json
from pathlib import Path

from app.agents.planning import invoke_planner
from app.models.models import ApprovalDecision
from app.orchestration.coordinator import resume_coordinator, start_coordinator
from app.orchestration.repository_checks import git_diff, run_tests
from app.orchestration.state import (
    CoordinatorExecution,
    CoordinatorStages,
    pending_approval_requests,
)
from app.orchestration.worktrees import Worktree
from app.repository.operations import SAMPLE_REPOSITORY_ROOT
from app.schemas.schemas import ApprovalResolution
from evals.models import EvalCase, EvalResult, RunObservation

CASES_PATH = Path(__file__).with_name("cases.json")
APPROVAL_PAUSE_STAGES = {
    CoordinatorStages.AWAITING_APPROVALS,
    CoordinatorStages.MERGE_REPAIR_AWAITING_APPROVALS,
    CoordinatorStages.REVIEW_FIX_AWAITING_APPROVALS,
}


def _validate_cases(raw_cases: object) -> list[EvalCase]:
    """Validate the JSON collection at the boundary of the eval harness."""
    if not isinstance(raw_cases, list):
        raise TypeError("Eval cases must be a JSON array.")

    # json.loads() returns ordinary Python dictionaries. Pydantic validates each
    # dictionary directly; from_attributes=True is only needed for objects whose
    # values must be read from attributes, such as many ORM objects.
    return [EvalCase.model_validate(item) for item in raw_cases]


async def evaluation_orchestration(raw_cases: object) -> list[EvalResult]:
    """Evaluate cases sequentially so each run is isolated and easy to debug."""
    results: list[EvalResult] = []

    for case in _validate_cases(raw_cases):
        results.append(await evaluate_current_workflow(case))

    return results


async def evaluate_current_workflow(case: EvalCase) -> EvalResult:
    """Run and score one case.

    This is intentionally the next implementation checkpoint. Build it in this
    order: execute the workflow, collect a RunObservation before cleanup, clean
    up in finally, score the case against the observation, then return EvalResult.
    """
    raise NotImplementedError(f"Workflow evaluation is not implemented: {case.id}")


async def _run_until_final_approval(
    case: EvalCase,
) -> CoordinatorExecution:
    """Run the user's original planner/resume loop up to the inspection boundary."""
    plan = await invoke_planner(SAMPLE_REPOSITORY_ROOT, case.objective)
    execution = await start_coordinator(plan)

    while execution.stage != CoordinatorStages.AWAITING_FINAL_APPROVAL:
        if execution.stage not in APPROVAL_PAUSE_STAGES:
            raise RuntimeError(
                f"Eval workflow returned an unexpected stage: {execution.stage}"
            )

        resolutions = _approve_fixture_edits(execution)
        execution = await resume_coordinator(plan, execution, resolutions)

    return execution


def _approve_fixture_edits(
    execution: CoordinatorExecution,
) -> dict[str, ApprovalResolution]:
    """Approve only the fixture-scoped apply-patch interruptions used by workers."""
    requests = pending_approval_requests(execution)
    if not requests:
        raise RuntimeError("Paused eval workflow did not expose an approval request.")

    resolutions: dict[str, ApprovalResolution] = {}
    for request in requests:
        if request.tool_name.rsplit(".", maxsplit=1)[-1] != "apply_patch":
            raise RuntimeError(
                f"Eval refused to auto-approve unexpected tool: {request.tool_name}"
            )
        resolutions[request.call_id] = ApprovalResolution(
            decision=ApprovalDecision.Approved
        )

    return resolutions


def _load_cases(path: Path = CASES_PATH) -> object:
    """Load raw JSON; shape validation remains _validate_cases' responsibility."""
    return json.loads(path.read_text(encoding="utf-8"))


def _build_run_observation(
    test_worktree: Worktree,
    latency_seconds: float,
) -> RunObservation:
    test_outcome = run_tests(test_worktree.path)
    diff_output = git_diff(test_worktree.path)
    return RunObservation(
        tests_passed=test_outcome.passed,
        changed_paths=list(diff_output.changed_paths),
        latency_seconds=latency_seconds,
    )


if __name__ == "__main__":
    asyncio.run(evaluation_orchestration(_load_cases()))
