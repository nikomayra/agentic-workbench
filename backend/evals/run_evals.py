import asyncio
import json
import time
import uuid
from pathlib import Path

from agents import add_trace_processor, trace
from tqdm import tqdm

from app.agents.planning import PlannerError, invoke_planner
from app.agents.reviewer import ReviewerError
from app.agents.workers import (
    WorkerError,
    WorkerInput,
    WorkExecution,
    WorkExecutionStatus,
    Workstream,
    invoke_worker,
    resume_worker,
)
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
    commit_worktree_changes,
    create_worktree,
    delete_generated_branch,
    remove_worktree_checkout,
)
from app.repository.operations import SAMPLE_REPOSITORY_ROOT
from app.schemas.schemas import ApprovalRequest, ApprovalResolution
from evals.models import (
    EvalCase,
    EvalConfiguration,
    EvalResult,
    ExecutionFacts,
    RunObservation,
    TraceMetrics,
)
from evals.observability import EvalTraceProcessor
from evals.scoring import case_scorer

CASES_PATH = Path(__file__).with_name("cases.json")
RESULTS_PATH = Path(__file__).with_name("results.json")
APPROVAL_PAUSE_STAGES = {
    CoordinatorStages.AWAITING_APPROVALS,
    CoordinatorStages.MERGE_REPAIR_AWAITING_APPROVALS,
    CoordinatorStages.REVIEW_FIX_AWAITING_APPROVALS,
}
EVAL_WORKFLOW_ERRORS = (PlannerError, ReviewerError, WorkerError, RuntimeError)

# Published GPT-5.6 Luna text-token prices in USD per one million tokens as of 16 Sept. 2026.
# This remains an estimate because TraceMetrics does not currently separate
# cache-write tokens, which may be billed differently from ordinary input.
INPUT_USD_PER_MILLION = 0.20
CACHED_INPUT_USD_PER_MILLION = 0.02
OUTPUT_USD_PER_MILLION = 1.20


def _validate_cases(raw_cases: object) -> list[EvalCase]:
    """Validate the JSON collection at the boundary of the eval harness."""
    if not isinstance(raw_cases, list):
        raise TypeError("Eval cases must be a JSON array.")

    # json.loads() returns ordinary Python dictionaries. Pydantic validates each
    # dictionary directly; from_attributes=True is only needed for objects whose
    # values must be read from attributes, such as many ORM objects.
    return [EvalCase.model_validate(item) for item in raw_cases]


def _format_workflow_error(exc: BaseException) -> str:
    """Flatten expected TaskGroup failures into one readable result message."""
    if isinstance(exc, BaseExceptionGroup):
        return "; ".join(_format_workflow_error(item) for item in exc.exceptions)
    return f"{type(exc).__name__}: {exc}"


def _estimated_cost_usd(metrics: TraceMetrics) -> float:
    """Estimate model cost from the token categories captured by the eval."""
    uncached_input_tokens = max(
        metrics.input_tokens - metrics.cached_input_tokens,
        0,
    )
    return (
        uncached_input_tokens * INPUT_USD_PER_MILLION
        + metrics.cached_input_tokens * CACHED_INPUT_USD_PER_MILLION
        + metrics.output_tokens * OUTPUT_USD_PER_MILLION
    ) / 1_000_000


async def evaluation_orchestration(
    raw_cases: object, trace_processor: EvalTraceProcessor
) -> list[EvalResult]:
    """Evaluate cases sequentially so each run is isolated and easy to debug."""
    eval_workflow_configurations = list(EvalConfiguration)

    results: list[EvalResult] = []
    cases = _validate_cases(raw_cases)
    progress = tqdm(
        total=len(eval_workflow_configurations) * len(cases),
        desc="Evaluating",
        unit="case",
    )

    for config in eval_workflow_configurations:
        for case in cases:
            progress.set_description(
                f"Evaluating Configuration {config}, Case {case.id}"
            )
            results.append(
                await evaluate_current_workflow(config, case, trace_processor)
            )
            progress.update(1)

    return results


async def evaluate_current_workflow(
    workflow_config: EvalConfiguration,
    case: EvalCase,
    trace_processor: EvalTraceProcessor,
) -> EvalResult:
    """Run and score one case."""
    start_time = time.perf_counter()

    with trace(
        case.id,
        metadata={"case_id": case.id, "configuration": workflow_config.value},
    ) as case_trace:
        try:
            execution_facts = await _execution_mapper(workflow_config, case)

            observation = RunObservation(
                tests_passed=execution_facts.tests_passed,
                changed_paths=execution_facts.changed_paths,
                latency_seconds=time.perf_counter() - start_time,
                error=execution_facts.error,
                metrics=trace_processor.metrics_collection.metrics_for(
                    case_trace.trace_id
                ),
            )

        except* EVAL_WORKFLOW_ERRORS as exc:
            observation = RunObservation(
                tests_passed=False,
                changed_paths=[],
                latency_seconds=time.perf_counter() - start_time,
                error=_format_workflow_error(exc),
                metrics=trace_processor.metrics_collection.metrics_for(
                    case_trace.trace_id
                ),
            )

        score = case_scorer(case, observation)

        return EvalResult(
            case_id=case.id,
            configuration=workflow_config,
            estimated_cost_usd=_estimated_cost_usd(observation.metrics),
            observation=observation,
            trace_id=case_trace.trace_id,
            passed=score.passed,
            reasons=score.reasons,
        )


async def _execution_mapper(
    configuration: EvalConfiguration, case: EvalCase
) -> ExecutionFacts:
    match configuration:
        case EvalConfiguration.FULL_WORKFLOW:
            return await execute_full_workflow(case)

        case EvalConfiguration.PLANNER_WORKER:
            return await execute_planner_worker_workflow(case)

        case EvalConfiguration.SINGLE_WORKER:
            return await execute_single_worker_workflow(case)

        case _:
            raise RuntimeError("Unsupported configuration detected")


async def execute_single_worker_workflow(case: EvalCase) -> ExecutionFacts:
    """Run the raw objective through one worker without planning or review."""

    single_workstream = Workstream(
        name=case.id,
        task=case.objective,
        intended_paths=[],
        acceptance_criteria=[
            "Implement the requested objective and keep relevant tests passing."
        ],
    )
    worktree = create_worktree(f"eval_{case.id}_{uuid.uuid4()}")
    try:
        await _run_worker_until_complete(
            WorkerInput(workstream=single_workstream), worktree
        )
        commit_worktree_changes(worktree, f"Evaluate {case.id}")
        test_outcome = run_tests(worktree.path)
        diff_output = git_diff(worktree.path)
        exc_facts = ExecutionFacts(
            tests_passed=test_outcome.passed,
            changed_paths=list(diff_output.changed_paths),
        )
    except EVAL_WORKFLOW_ERRORS as exc:
        exc_facts = ExecutionFacts(
            tests_passed=False,
            changed_paths=[],
            error=_format_workflow_error(exc),
        )
    finally:
        remove_worktree_checkout(worktree, force=True)
        delete_generated_branch(worktree)

    return exc_facts


async def execute_planner_worker_workflow(case: EvalCase) -> ExecutionFacts:
    """Use a planner, then give its complete plan to one worker without review."""

    worktree: Worktree | None = None
    try:
        plan = await invoke_planner(SAMPLE_REPOSITORY_ROOT, case.objective)
        worktree = create_worktree(f"eval_{case.id}_{uuid.uuid4()}")
        combined_plan_steps = "\n".join(
            f"{step.title}: {step.description}" for step in plan.steps
        )
        single_workstream = Workstream(
            name=case.id,
            task=(
                f"Original objective:\n{case.objective}\n\n"
                f"Planner summary:\n{plan.summary}\n\n"
                f"Plan steps:\n{combined_plan_steps}"
            ),
            intended_paths=[],
            acceptance_criteria=[step.acceptance_criteria for step in plan.steps],
        )
        await _run_worker_until_complete(
            WorkerInput(workstream=single_workstream), worktree
        )
        commit_worktree_changes(worktree, f"Evaluate {case.id}")
        test_outcome = run_tests(worktree.path)
        diff_output = git_diff(worktree.path)
        exc_facts = ExecutionFacts(
            tests_passed=test_outcome.passed,
            changed_paths=list(diff_output.changed_paths),
        )
    except EVAL_WORKFLOW_ERRORS as exc:
        exc_facts = ExecutionFacts(
            tests_passed=False,
            changed_paths=[],
            error=_format_workflow_error(exc),
        )
    finally:
        if worktree is not None:
            remove_worktree_checkout(worktree, force=True)
            delete_generated_branch(worktree)

    return exc_facts


async def execute_full_workflow(case: EvalCase) -> ExecutionFacts:
    """Execute the full_workflow (default) per Eval case"""
    state: CoordinatorExecution | None = None
    try:
        state = await _run_until_final_approval(case)
        if state.integration_worktree is None:
            raise RuntimeError("Run completed with no integration worktree.")

        test_outcome = run_tests(state.integration_worktree.path)
        diff_output = git_diff(state.integration_worktree.path)
        exc_facts = ExecutionFacts(
            tests_passed=test_outcome.passed,
            changed_paths=list(diff_output.changed_paths),
        )
    except* EVAL_WORKFLOW_ERRORS as exc:
        exc_facts = ExecutionFacts(
            tests_passed=False, changed_paths=[], error=_format_workflow_error(exc)
        )
    finally:
        if state is not None:
            _clean_up_coordinator_resources(state)

    return exc_facts


async def _run_worker_until_complete(
    worker_input: WorkerInput, worktree: Worktree
) -> WorkExecution:
    """Run a single worker to the inspection boundary."""
    execution = await invoke_worker(worktree.path, worker_input)

    while execution.status != WorkExecutionStatus.COMPLETED:
        if execution.status != WorkExecutionStatus.PENDING_APPROVAL:
            raise RuntimeError(
                f"Single-worker eval workflow returned an unexpected status: {execution.status}"
            )
        if execution.run_state is None:
            raise RuntimeError(
                "Single-worker eval workflow failed to return run_state"
            )
        resolutions = _approve_fixture_edits(execution.approval_requests)
        execution = await resume_worker(
            worktree.path, execution.run_state, resolutions
        )

    return execution


async def _run_until_final_approval(
    case: EvalCase,
) -> CoordinatorExecution:
    """Run the user's original planner/resume loop up to the inspection boundary."""
    execution: CoordinatorExecution | None = None

    try:
        plan = await invoke_planner(SAMPLE_REPOSITORY_ROOT, case.objective)
        execution = await start_coordinator(plan)

        while execution.stage != CoordinatorStages.AWAITING_FINAL_APPROVAL:
            if execution.stage not in APPROVAL_PAUSE_STAGES:
                raise RuntimeError(
                    f"Eval workflow returned an unexpected stage: {execution.stage}"
                )
            requests = pending_approval_requests(execution)
            resolutions = _approve_fixture_edits(requests)
            execution = await resume_coordinator(plan, execution, resolutions)

        return execution
    except Exception:
        # Assignment to the caller happens only when this function returns. If it
        # raises, this function is the last layer that can see its partial state.
        if execution is not None:
            _clean_up_coordinator_resources(execution)
        raise


def _approve_fixture_edits(
    requests: list[ApprovalRequest],
) -> dict[str, ApprovalResolution]:
    """Approve only the fixture-scoped apply-patch interruptions used by workers."""

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


def _clean_up_coordinator_resources(saved_state: CoordinatorExecution) -> None:
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


def _print_summary_report(results: list[EvalResult]) -> None:
    if not results:
        return

    # Global totals calculations
    total_cases_run = len(results)
    total_failures = len([result for result in results if result.passed == False])
    total_passed = len([result for result in results if result.passed == True])
    total_tokens = sum([result.observation.metrics.total_tokens for result in results])
    total_agent_turns = sum(
        [result.observation.metrics.agent_turns for result in results]
    )
    total_estimated_cost = sum(result.estimated_cost_usd or 0.0 for result in results)

    failures = [
        {"case_id": r.case_id, "passed": r.passed, "reasons": r.reasons}
        for r in results
        if r.passed == False
    ]

    avg_latency = sum([result.observation.latency_seconds for result in results]) / len(
        results
    )

    avg_tokens_per_case = sum(
        [result.observation.metrics.total_tokens for result in results]
    ) / len(results)

    avg_turns_per_case = sum(
        [result.observation.metrics.agent_turns for result in results]
    ) / len(results)

    # Per-configuration breakdown
    configs_breakdown = {}
    for config in {result.configuration for result in results}:
        config_results = [r for r in results if r.configuration == config]
        config_passed = len([r for r in config_results if r.passed])
        config_failed = len([r for r in config_results if not r.passed])
        config_total = len(config_results)
        config_pass_rate = (
            (config_passed / config_total * 100) if config_total > 0 else 0
        )
        config_avg_latency = (
            sum([r.observation.latency_seconds for r in config_results]) / config_total
            if config_total > 0
            else 0
        )
        config_avg_tokens = (
            sum([r.observation.metrics.total_tokens for r in config_results])
            / config_total
            if config_total > 0
            else 0
        )
        config_avg_turns = (
            sum([r.observation.metrics.agent_turns for r in config_results])
            / config_total
            if config_total > 0
            else 0
        )
        config_cost = sum([r.estimated_cost_usd or 0.0 for r in config_results])

        configs_breakdown[config] = {
            "Total cases": config_total,
            "Passed": config_passed,
            "Failed": config_failed,
            "Pass rate [%]": f"{config_pass_rate:.2f}",
            "Avg latency [seconds]": f"{config_avg_latency:.2f}",
            "Avg tokens per case": f"{config_avg_tokens:.2f}",
            "Avg agent turns per case": f"{config_avg_turns:.2f}",
            "Estimated cost [USD]": f"{config_cost:.6f}",
        }

    summary = {
        "Global totals": {
            "Total cases": total_cases_run,
            "Total Passed": total_passed,
            "Total Failures": total_failures,
            "Total tokens used": total_tokens,
            "Total agent turns": total_agent_turns,
            "Estimated model cost [USD]": f"{total_estimated_cost:.6f}",
            "Avg run latency [seconds]": f"{avg_latency:.2f}",
            "Avg tokens per case": f"{avg_tokens_per_case:.2f}",
            "Avg agent turns per case": f"{avg_turns_per_case:.2f}",
            "Failed case run(s)": failures,
        },
        "Per-configuration breakdown": configs_breakdown,
    }

    print(json.dumps(summary, indent=2))


async def main() -> None:
    configure_agents()
    trace_processor = EvalTraceProcessor()
    add_trace_processor(trace_processor)
    results = await evaluation_orchestration(_load_cases(), trace_processor)
    _save_results(results)
    _print_summary_report(results)


if __name__ == "__main__":
    asyncio.run(main())
