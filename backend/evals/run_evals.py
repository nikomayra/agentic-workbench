import asyncio
import json
import time
from pathlib import Path

from agents import trace

from app.agents.planning import PlannerError, invoke_planner
from app.agents.reviewer import ReviewerError
from app.agents.workers import WorkerError
from app.config import configure_agents
from app.models.models import ApprovalDecision
from app.orchestration.coordinator import resume_coordinator, start_coordinator
from app.orchestration.repository_checks import git_diff, run_tests
from app.orchestration.state import (
    CoordinatorExecution,
    CoordinatorStages,
    pending_approval_requests,
)
from app.orchestration.worktrees import (
    Worktree,
    delete_generated_branch,
    remove_worktree_checkout,
)
from app.repository.operations import SAMPLE_REPOSITORY_ROOT
from app.schemas.schemas import ApprovalResolution
from evals.models import EvalCase, EvalResult, RunObservation
from evals.scoring import case_scorer

CASES_PATH = Path(__file__).with_name("cases.json")
RESULTS_PATH = Path(__file__).with_name("results.json")
APPROVAL_PAUSE_STAGES = {
    CoordinatorStages.AWAITING_APPROVALS,
    CoordinatorStages.MERGE_REPAIR_AWAITING_APPROVALS,
    CoordinatorStages.REVIEW_FIX_AWAITING_APPROVALS,
}
EVAL_WORKFLOW_ERRORS = (PlannerError, ReviewerError, WorkerError, RuntimeError)

# Sets openai key in env so we don't have to import app.main to make agent calls
configure_agents()


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
    """Run and score one case."""
    run_state: CoordinatorExecution | None = None
    trace_id: str = ""
    start_time = time.perf_counter()

    try:
        try:
            run_state, trace_id = await _run_until_final_approval(case)
            if run_state.integration_worktree is None:
                raise RuntimeError("Run completed with no integration worktree.")
            if trace_id == "":
                raise RuntimeError("Run completed with no trace id")

            observation = _build_run_observation(
                run_state.integration_worktree,
                time.perf_counter() - start_time,
            )

        except EVAL_WORKFLOW_ERRORS as exc:
            observation = RunObservation(
                tests_passed=False,
                changed_paths=[],
                latency_seconds=time.perf_counter() - start_time,
                error=f"{type(exc).__name__}: {exc}",
            )

        score = case_scorer(case, observation)

        return EvalResult(
            case_id=case.id,
            configuration="full_workflow",
            observation=observation,
            trace_id=trace_id,
            passed=score.passed,
            reasons=score.reasons,
        )
    finally:
        if run_state is not None:
            _clean_up_resources(run_state)


async def _run_until_final_approval(
    case: EvalCase,
) -> tuple[CoordinatorExecution, str]:
    """Run the user's original planner/resume loop up to the inspection boundary."""
    execution: CoordinatorExecution | None = None

    try:
        with trace(case.id) as case_trace:
            plan = await invoke_planner(SAMPLE_REPOSITORY_ROOT, case.objective)
            execution = await start_coordinator(plan)

            while execution.stage != CoordinatorStages.AWAITING_FINAL_APPROVAL:
                if execution.stage not in APPROVAL_PAUSE_STAGES:
                    raise RuntimeError(
                        f"Eval workflow returned an unexpected stage: {execution.stage}"
                    )

                resolutions = _approve_fixture_edits(execution)
                execution = await resume_coordinator(plan, execution, resolutions)

            return (execution, case_trace.trace_id)
    except Exception:
        # Assignment to the caller happens only when this function returns. If it
        # raises, this function is the last layer that can see its partial state.
        if execution is not None:
            _clean_up_resources(execution)
        raise


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


def _clean_up_resources(saved_state: CoordinatorExecution) -> None:
    for work_record in saved_state.work_records:
        remove_worktree_checkout(work_record.worktree, force=True)
        delete_generated_branch(work_record.worktree)

    if not saved_state.integration_worktree:
        return

    remove_worktree_checkout(saved_state.integration_worktree, force=True)
    delete_generated_branch(saved_state.integration_worktree)


def _load_cases(path: Path = CASES_PATH) -> object:
    """Load raw JSON; shape validation remains _validate_cases' responsibility."""
    return json.loads(path.read_text(encoding="utf-8"))


def _save_results(results: list[EvalResult], path: Path = RESULTS_PATH) -> None:
    """Write JSON-compatible evaluation results to one report file."""
    report = [result.model_dump(mode="json") for result in results]
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _build_run_observation(
    eval_integration_worktree: Worktree,
    latency_seconds: float,
) -> RunObservation:
    """Build an observation for a workflow that produced an inspectable worktree."""
    test_outcome = run_tests(eval_integration_worktree.path)
    diff_output = git_diff(eval_integration_worktree.path)
    return RunObservation(
        tests_passed=test_outcome.passed,
        changed_paths=list(diff_output.changed_paths),
        latency_seconds=latency_seconds,
    )


def _print_summary_report(results: list[EvalResult]) -> None:
    if not results:
        return

    failures = [
        {"case_id": r.case_id, "passed": r.passed, "reasons": r.reasons}
        for r in results
        if r.passed == False
    ]

    avg_latency = sum([result.observation.latency_seconds for result in results]) / len(
        results
    )

    total_cases_run = len(results)
    total_failures = len([result for result in results if result.passed == False])
    total_passed = len([result for result in results if result.passed == True])

    passed_results = [result for result in results if result.passed]

    fastest_pass = min(
        passed_results,
        key=lambda result: result.observation.latency_seconds,
        default=None,
    )

    slowest_pass = max(
        passed_results,
        key=lambda result: result.observation.latency_seconds,
        default=None,
    )

    summary = {
        "Total cases run": total_cases_run,
        "Total Failures": total_failures,
        "Total Passed": total_passed,
        "Average run latency": avg_latency,
        "Fastest passed case run": fastest_pass,
        "Slowest passed case run": slowest_pass,
        "Failed case run(s)": failures,
    }

    print(json.dumps(summary, indent=2))


async def main() -> None:
    results = await evaluation_orchestration(_load_cases())
    _save_results(results)
    _print_summary_report(results)


if __name__ == "__main__":
    asyncio.run(main())
