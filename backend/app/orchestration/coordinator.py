"""Coordinate planning and isolated worker execution."""

import asyncio
import uuid
from typing import Any

from app.agents.planning import invoke_decomposer
from app.agents.reviewer import invoke_reviewer
from app.agents.workers import (
    WorkerInput,
    WorkExecution,
    WorkExecutionStatus,
    invoke_worker,
    resume_worker,
)
from app.orchestration.repository_checks import git_diff, run_tests
from app.orchestration.state import (
    CoordinatorExecution,
    CoordinatorStages,
    MergeConflict,
    ReviewFindings,
    WorkRecord,
    WorkRecordStatus,
)
from app.orchestration.worktrees import (
    commit_worktree_changes,
    complete_merge_after_conflict,
    create_worktree,
    delete_generated_branch,
    merge_worktree_changes,
    remove_worktree_checkout,
)
from app.repository.operations import SAMPLE_REPOSITORY_ROOT
from app.schemas.schemas import (
    ApprovalResolution,
    ExecutionPlan,
    Plan,
    ReviewInput,
    ReviewOutput,
    ReviewStatus,
    Workstream,
)

MAX_REVIEW_FIX_CYCLES = 1


def prepare_work(execution_plan: ExecutionPlan) -> list[WorkRecord]:
    """Create one unexecuted work record and worktree per workstream."""
    prepared_work: list[WorkRecord] = []

    try:
        for workstream in execution_plan.workstreams:
            work_id = uuid.uuid4()
            worktree = create_worktree(str(work_id))
            prepared_work.append(
                WorkRecord(
                    work_id=work_id,
                    status=WorkRecordStatus.NOT_MERGED,
                    workstream=workstream,
                    worktree=worktree,
                )
            )
    except Exception:
        # If preparation fails halfway through, remove resources already created.
        for worker in reversed(prepared_work):
            remove_worktree_checkout(worker.worktree, force=True)
            delete_generated_branch(worker.worktree)
        raise

    return prepared_work


async def execute_new_work(
    work_records: list[WorkRecord],
) -> list[WorkRecord]:
    """Execute every newly prepared work record concurrently."""
    tasks_by_work_id: dict[uuid.UUID, asyncio.Task[WorkExecution]] = {}

    async with asyncio.TaskGroup() as group:
        for work in work_records:
            if work.work_execution is not None:
                raise RuntimeError("New work cannot already have an execution.")

            worker_input = WorkerInput(workstream=work.workstream)
            tasks_by_work_id[work.work_id] = group.create_task(
                invoke_worker(work.worktree.path, worker_input),
                name=str(work.work_id),
            )

    return [
        _replace_work_execution(
            work,
            tasks_by_work_id[work.work_id].result(),
        )
        for work in work_records
    ]


async def resume_pending_work(
    work_records: list[WorkRecord],
    approval_resolutions: dict[str, ApprovalResolution],
) -> list[WorkRecord]:
    """Resume pending work concurrently while preserving completed work."""
    pending_work: list[tuple[WorkRecord, dict[str, Any]]] = []

    for work in work_records:
        execution = work.work_execution
        if execution is None:
            raise RuntimeError("Saved work must have an execution.")
        if execution.status == WorkExecutionStatus.PENDING_APPROVAL:
            if execution.run_state is None:
                raise RuntimeError("Pending work must have a saved run state.")
            pending_work.append((work, execution.run_state))

    if not pending_work:
        raise RuntimeError("No pending work is available to resume.")

    tasks_by_work_id: dict[uuid.UUID, asyncio.Task[WorkExecution]] = {}
    async with asyncio.TaskGroup() as group:
        for work, run_state in pending_work:
            tasks_by_work_id[work.work_id] = group.create_task(
                resume_worker(
                    work.worktree.path,
                    run_state,
                    resolutions=approval_resolutions,
                ),
                name=str(work.work_id),
            )

    updated_executions = {
        work_id: task.result() for work_id, task in tasks_by_work_id.items()
    }
    return [
        _replace_work_execution(work, updated_executions[work.work_id])
        if work.work_id in updated_executions
        else work
        for work in work_records
    ]


def _replace_work_execution(
    work: WorkRecord,
    execution: WorkExecution,
) -> WorkRecord:
    """Return the same durable work identity with an updated execution."""
    return WorkRecord(
        work_id=work.work_id,
        status=work.status,
        workstream=work.workstream,
        worktree=work.worktree,
        work_execution=execution,
    )


def _state_from_work_results(work_records: list[WorkRecord]) -> CoordinatorExecution:
    """Validate work results and derive the coordinator's next stage."""
    if not work_records:
        raise RuntimeError("Coordinator execution requires at least one work record.")

    has_pending_work = False
    for work in work_records:
        execution = work.work_execution
        if execution is None:
            raise RuntimeError("Returned work must have an execution.")
        if execution.status == WorkExecutionStatus.PENDING_APPROVAL:
            if execution.run_state is None:
                raise RuntimeError("Pending work must have a saved run state.")
            has_pending_work = True
        elif execution.output is None:
            raise RuntimeError("Completed work must have an output.")

    stage = (
        CoordinatorStages.AWAITING_APPROVALS
        if has_pending_work
        else CoordinatorStages.WORK_COMPLETED
    )

    return CoordinatorExecution(stage=stage, work_records=work_records)


async def advance_until_pause(
    plan: Plan, state: CoordinatorExecution
) -> CoordinatorExecution:
    """Dispatcher method for transitions in coordinator state-machine"""
    while True:
        match state.stage:
            case CoordinatorStages.WORK_COMPLETED:
                _commit_completed_work(state)
                state = _create_integration_worktree(state)

            case CoordinatorStages.INTEGRATING:
                state = _merge_worktrees_into_integration(state)

            case CoordinatorStages.MERGE_CONFLICT:
                state = await start_merge_conflict_repair(state)

            case CoordinatorStages.MERGE_REPAIR_COMPLETED:
                state = _state_from_merge_repair_completed(state)

            case (
                CoordinatorStages.AWAITING_APPROVALS
                | CoordinatorStages.MERGE_REPAIR_AWAITING_APPROVALS
                | CoordinatorStages.REVIEW_FIX_AWAITING_APPROVALS
                | CoordinatorStages.AWAITING_FINAL_APPROVAL
            ):
                return state

            case CoordinatorStages.INTEGRATED:
                state = await _review_integration_worktree(plan, state)

            case CoordinatorStages.REVIEW_FINDINGS:
                state = await start_attempt_fix_review_findings(state)

            case CoordinatorStages.REVIEW_FIX_COMPLETED:
                state = _state_from_review_findings_fix_completed(state)

            case _:
                raise RuntimeError("Unsupported state detected")


async def _review_integration_worktree(
    plan: Plan,
    state: CoordinatorExecution,
) -> CoordinatorExecution:
    if state.stage != CoordinatorStages.INTEGRATED or not state.integration_worktree:
        raise RuntimeError("Not ready for review cycle yet.")

    test_outcome = run_tests(state.integration_worktree.path)
    actual_diff = git_diff(state.integration_worktree.path)
    test_report = (
        f"Combined tests: {'PASSED' if test_outcome.passed else 'FAILED'}\n"
        f"{test_outcome.output}"
    )

    combined_work_notes = [
        work_record.work_execution.output.work_notes
        for work_record in state.work_records
        if work_record.work_execution and work_record.work_execution.output
    ]

    review_input = ReviewInput(
        original_plan=plan,
        executed_workstreams=[
            work_record.workstream for work_record in state.work_records
        ],
        implementation_notes=("\n".join(combined_work_notes)),
        actual_diff=actual_diff.output,
        test_output=test_report,
    )

    review_output = await invoke_reviewer(
        state.integration_worktree.path, review_input=review_input
    )

    if not test_outcome.passed and review_output.status == ReviewStatus.SUCCESS:
        review_output = ReviewOutput(
            status=ReviewStatus.CHANGES_REQUIRED,
            repair_task="Fix the failing combined test suite.",
            acceptance_criteria=["The combined test suite passes."],
        )

    if state.review_findings:
        review_findings = ReviewFindings(
            review_output=review_output,
            fix_attempts=state.review_findings.fix_attempts,
        )
    else:
        review_findings = ReviewFindings(
            review_output=review_output,
        )

    if review_output.status == ReviewStatus.SUCCESS:
        return CoordinatorExecution(
            stage=CoordinatorStages.AWAITING_FINAL_APPROVAL,
            work_records=state.work_records,
            integration_worktree=state.integration_worktree,
        )
    else:
        return CoordinatorExecution(
            stage=CoordinatorStages.REVIEW_FINDINGS,
            work_records=state.work_records,
            integration_worktree=state.integration_worktree,
            review_findings=review_findings,
        )


def _state_from_review_findings_fix_completed(
    state: CoordinatorExecution,
) -> CoordinatorExecution:
    if (
        not state.review_findings
        or not state.review_findings.review_output.repair_task
        or not state.integration_worktree
        or state.stage != CoordinatorStages.REVIEW_FIX_COMPLETED
    ):
        raise RuntimeError(
            "Review findings fix not complete, failed to resolve state transition."
        )

    commit_outcome = commit_worktree_changes(
        state.integration_worktree,
        f"Review findings fix completed: {state.review_findings.review_output.repair_task[:200]}",
    )
    if not commit_outcome.committed or not commit_outcome.commit_hash:
        raise RuntimeError("Completed review fix did not produce a commit.")

    return CoordinatorExecution(
        stage=CoordinatorStages.INTEGRATED,
        work_records=state.work_records,
        integration_worktree=state.integration_worktree,
        review_findings=state.review_findings,
    )


def _state_from_fix_review_findings_attempt(
    state: CoordinatorExecution, fix_execution: WorkExecution
) -> CoordinatorExecution:
    if state.review_findings is None:
        raise RuntimeError("Review findings fix requires active review findings.")

    if fix_execution.status == WorkExecutionStatus.PENDING_APPROVAL:
        if fix_execution.run_state is None:
            raise RuntimeError(
                "Pending review findings fix must have a saved run state."
            )
        stage = CoordinatorStages.REVIEW_FIX_AWAITING_APPROVALS
        new_fix_attempts = state.review_findings.fix_attempts
    else:
        if fix_execution.output is None:
            raise RuntimeError("Completed review findings fix must have output.")
        stage = CoordinatorStages.REVIEW_FIX_COMPLETED
        new_fix_attempts = state.review_findings.fix_attempts + 1

    updated_review_findings = state.review_findings.model_copy(
        update={"fix_execution": fix_execution, "fix_attempts": new_fix_attempts}
    )
    return state.model_copy(
        update={"stage": stage, "review_findings": updated_review_findings}
    )


async def start_attempt_fix_review_findings(
    state: CoordinatorExecution,
) -> CoordinatorExecution:

    if not state.review_findings or state.stage != CoordinatorStages.REVIEW_FINDINGS:
        raise RuntimeError("Must have review findings before attempting fix.")

    if (
        state.review_findings
        and state.review_findings.fix_attempts >= MAX_REVIEW_FIX_CYCLES
    ):
        raise RuntimeError("Exceeded max allowed review fix attempts.")

    if not state.integration_worktree:
        raise RuntimeError(
            "Missing integration worktree. Failed to fix review findings."
        )

    if not state.review_findings.review_output.repair_task:
        raise RuntimeError("Review output without review task. Failed to fix findings.")

    repair_assignment = Workstream(
        name="repair-review-findings",
        task=(
            f"Resolve the reviewer's findings: {state.review_findings.review_output.repair_task}"
        ),
        intended_paths=state.review_findings.review_output.affected_paths or [],
        acceptance_criteria=state.review_findings.review_output.acceptance_criteria
        or [],
    )
    repair_execution = await invoke_worker(
        state.integration_worktree.path,
        WorkerInput(workstream=repair_assignment),
    )

    return _state_from_fix_review_findings_attempt(state, repair_execution)


async def resume_attempt_fix_review_findings(
    state: CoordinatorExecution,
    decisions: dict[str, ApprovalResolution],
) -> CoordinatorExecution:
    if (
        state.stage != CoordinatorStages.REVIEW_FIX_AWAITING_APPROVALS
        or state.integration_worktree is None
        or state.review_findings is None
        or state.review_findings.fix_execution is None
        or state.review_findings.fix_execution.run_state is None
    ):
        raise RuntimeError("Review findings fix is not ready to resume.")

    repair_execution = await resume_worker(
        state.integration_worktree.path,
        state.review_findings.fix_execution.run_state,
        decisions,
    )
    return _state_from_fix_review_findings_attempt(state, repair_execution)


def finalize_coordinator(
    saved_state: CoordinatorExecution, approved: bool
) -> CoordinatorExecution:
    """Apply the final human decision and remove temporary Git resources."""
    if saved_state.stage != CoordinatorStages.AWAITING_FINAL_APPROVAL:
        raise RuntimeError("Not ready to finalize coordinator.")

    if not saved_state.integration_worktree:
        raise RuntimeError("Missing integration worktree; cannot finalize coordinator.")

    for work_record in saved_state.work_records:
        remove_worktree_checkout(work_record.worktree, force=True)
        delete_generated_branch(work_record.worktree)

    remove_worktree_checkout(saved_state.integration_worktree, force=True)
    if not approved:
        delete_generated_branch(saved_state.integration_worktree)

    stage = CoordinatorStages.COMPLETED if approved else CoordinatorStages.REJECTED
    return saved_state.model_copy(update={"stage": stage})


async def resume_coordinator(
    plan: Plan,
    saved_state: CoordinatorExecution,
    decisions: dict[str, ApprovalResolution],
) -> CoordinatorExecution:
    """Resume paused coordinator execution"""
    updated_state = None
    if saved_state.stage == CoordinatorStages.AWAITING_APPROVALS:
        updated_state = await resume_work(saved_state, decisions=decisions)
    elif saved_state.stage == CoordinatorStages.MERGE_REPAIR_AWAITING_APPROVALS:
        updated_state = await resume_merge_conflict_repair(
            saved_state, decisions=decisions
        )
    elif saved_state.stage == CoordinatorStages.REVIEW_FIX_AWAITING_APPROVALS:
        updated_state = await resume_attempt_fix_review_findings(
            saved_state, decisions=decisions
        )

    if updated_state:
        return await advance_until_pause(plan, updated_state)
    else:
        raise RuntimeError("Failed to resume coordinator")


async def start_coordinator(plan: Plan) -> CoordinatorExecution:
    """Start coordinator execution for an approved plan."""
    execution_plan = await invoke_decomposer(SAMPLE_REPOSITORY_ROOT, plan)
    initial_state = await _start_work(execution_plan)
    return await advance_until_pause(plan, initial_state)


async def _start_work(execution_plan: ExecutionPlan) -> CoordinatorExecution:
    prepared_work = prepare_work(execution_plan)

    try:
        executed_work = await execute_new_work(prepared_work)
        return _state_from_work_results(executed_work)
    except Exception as exc:
        for work in reversed(prepared_work):
            remove_worktree_checkout(work.worktree, force=True)
            delete_generated_branch(work.worktree)
        raise RuntimeError("Failed to start work") from exc


async def resume_work(
    saved_state: CoordinatorExecution,
    decisions: dict[str, ApprovalResolution],
) -> CoordinatorExecution:
    """Resume a coordinator paused for worker tool approvals."""
    validated_state = _state_from_work_results(saved_state.work_records)
    if validated_state.stage != saved_state.stage:
        raise RuntimeError("Saved coordinator stage does not match its work records.")
    if validated_state.stage != CoordinatorStages.AWAITING_APPROVALS:
        raise RuntimeError("Only work awaiting approvals can be resumed.")

    updated_work = await resume_pending_work(validated_state.work_records, decisions)
    return _state_from_work_results(updated_work)


def _commit_completed_work(state: CoordinatorExecution) -> None:
    if state.stage != CoordinatorStages.WORK_COMPLETED:
        raise RuntimeError("All work must be complete before committing.")

    for work in state.work_records:
        output = commit_worktree_changes(
            work.worktree, f"Completed work_record: {work.work_id}"
        )
        if output.committed and not output.commit_hash:
            raise RuntimeError("Completed work committed but no commit hash saved.")

        # NOTE: Successfully completed no-change workstreams allowed.
        # if not output.committed:
        #     raise RuntimeError("Completed work failed to commit.")


def _create_integration_worktree(state: CoordinatorExecution) -> CoordinatorExecution:

    if state.stage != CoordinatorStages.WORK_COMPLETED:
        raise RuntimeError(
            "Work must be completed before creating integration worktree."
        )

    integration_id = uuid.uuid4()
    integration_worktree = create_worktree(f"integration_{integration_id}")

    updated_state = CoordinatorExecution(
        stage=CoordinatorStages.INTEGRATING,
        work_records=state.work_records,
        integration_worktree=integration_worktree,
    )
    return updated_state


def _merge_worktrees_into_integration(
    state: CoordinatorExecution,
) -> CoordinatorExecution:

    if not state.integration_worktree or state.stage != CoordinatorStages.INTEGRATING:
        raise RuntimeError("Not ready to merge changes yet.")

    updated_work_records: list[WorkRecord] = state.work_records.copy()
    for idx, work_record in enumerate(updated_work_records):
        if work_record.status == WorkRecordStatus.MERGED:
            continue

        if work_record.work_execution:
            merge_output = merge_worktree_changes(
                work_record.worktree, state.integration_worktree
            )

            if merge_output.conflicts:
                if not merge_output.conflict_file_paths:
                    raise RuntimeError(
                        "Merge conflict must include affected file paths"
                    )
                merge_conflict = MergeConflict(
                    work_id=work_record.work_id,
                    file_paths=list(merge_output.conflict_file_paths),
                )
                return CoordinatorExecution(
                    stage=CoordinatorStages.MERGE_CONFLICT,
                    work_records=updated_work_records,
                    integration_worktree=state.integration_worktree,
                    merge_conflict=merge_conflict,
                )
            updated_work_records[idx] = work_record.model_copy(
                update={"status": WorkRecordStatus.MERGED}
            )
        else:
            raise RuntimeError("Work must have execution for merging.")

    return CoordinatorExecution(
        stage=CoordinatorStages.INTEGRATED,
        work_records=updated_work_records,
        integration_worktree=state.integration_worktree,
    )


def _state_from_merge_repair_completed(
    state: CoordinatorExecution,
) -> CoordinatorExecution:
    if (
        not state.merge_conflict
        or not state.integration_worktree
        or state.stage != CoordinatorStages.MERGE_REPAIR_COMPLETED
    ):
        raise RuntimeError(
            "Merge repair not complete, failed to resolve state transition."
        )

    complete_merge_after_conflict(state.integration_worktree)

    if not any(
        work_record.work_id == state.merge_conflict.work_id
        for work_record in state.work_records
    ):
        raise RuntimeError(
            "Can't find original merge conflict work record; failed to complete merge repair."
        )

    updated_work_records = [
        work_record.model_copy(update={"status": WorkRecordStatus.MERGED})
        if work_record.work_id == state.merge_conflict.work_id
        else work_record
        for work_record in state.work_records
    ]

    return CoordinatorExecution(
        stage=CoordinatorStages.INTEGRATING,
        work_records=updated_work_records,
        integration_worktree=state.integration_worktree,
        merge_conflict=None,
    )


def _state_from_merge_repair_result(
    state: CoordinatorExecution,
    repair_execution: WorkExecution,
) -> CoordinatorExecution:
    """Attach a merge-repair result and derive its next coordinator stage."""
    if state.merge_conflict is None:
        raise RuntimeError("Merge repair requires an active conflict.")

    if repair_execution.status == WorkExecutionStatus.PENDING_APPROVAL:
        if repair_execution.run_state is None:
            raise RuntimeError("Pending merge repair must have a saved run state.")
        stage = CoordinatorStages.MERGE_REPAIR_AWAITING_APPROVALS
    else:
        if repair_execution.output is None:
            raise RuntimeError("Completed merge repair must have output.")
        stage = CoordinatorStages.MERGE_REPAIR_COMPLETED

    updated_conflict = state.merge_conflict.model_copy(
        update={"repair_execution": repair_execution}
    )
    return state.model_copy(update={"stage": stage, "merge_conflict": updated_conflict})


async def start_merge_conflict_repair(
    state: CoordinatorExecution,
) -> CoordinatorExecution:
    """Start an agent repair for the active conflict in the integration tree."""

    if (
        not state.integration_worktree
        or not state.merge_conflict
        or state.stage != CoordinatorStages.MERGE_CONFLICT
    ):
        raise RuntimeError("Not ready for merge conflict resolution.")

    if state.merge_conflict.repair_execution is not None:
        raise RuntimeError("Merge conflict repair has already started.")

    original_work = next(
        (
            work
            for work in state.work_records
            if work.work_id == state.merge_conflict.work_id
        ),
        None,
    )
    if original_work is None:
        raise ValueError(
            "Original conflicting work was not found. Merge repair failed."
        )

    conflict_paths = [path.as_posix() for path in state.merge_conflict.file_paths]
    repair_assignment = Workstream(
        name=f"merge-repair-{original_work.workstream.name}",
        task=(
            "Resolve the active Git merge conflicts in these files: "
            f"{', '.join(conflict_paths)}. Preserve compatible changes from both "
            "branches and remove all conflict markers."
        ),
        intended_paths=conflict_paths,
        acceptance_criteria=[
            "All listed merge conflicts are resolved without conflict markers.",
            *original_work.workstream.acceptance_criteria,
        ],
        shared_contracts=original_work.workstream.shared_contracts,
    )
    repair_execution = await invoke_worker(
        state.integration_worktree.path,
        WorkerInput(workstream=repair_assignment),
    )
    return _state_from_merge_repair_result(state, repair_execution)


async def resume_merge_conflict_repair(
    state: CoordinatorExecution,
    decisions: dict[str, ApprovalResolution],
) -> CoordinatorExecution:
    """Resume an interrupted merge-repair agent after approval decisions."""
    if (
        state.stage != CoordinatorStages.MERGE_REPAIR_AWAITING_APPROVALS
        or state.integration_worktree is None
        or state.merge_conflict is None
        or state.merge_conflict.repair_execution is None
        or state.merge_conflict.repair_execution.run_state is None
    ):
        raise RuntimeError("Merge conflict repair is not ready to resume.")

    repair_execution = await resume_worker(
        state.integration_worktree.path,
        state.merge_conflict.repair_execution.run_state,
        decisions,
    )
    return _state_from_merge_repair_result(state, repair_execution)
