import asyncio
import datetime
import uuid
from typing import NoReturn

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.planning import PlannerError, invoke_planner
from app.db import get_async_db_ctx
from app.models.models import (
    Approval,
    ApprovalDecision,
    WorkflowRun,
    WorkflowRunStatus,
)
from app.orchestration.coordinator import (
    finalize_coordinator,
    resume_coordinator,
    start_coordinator,
)
from app.orchestration.state import (
    CoordinatorExecution,
    CoordinatorStages,
    pending_approval_requests,
)
from app.repository.operations import SAMPLE_REPOSITORY_ROOT
from app.schemas.schemas import (
    ApprovalResolution,
    Plan,
)

WORKFLOW_TIMEOUT_SECONDS = 120


class WorkflowExecutionError(Exception):
    """Workflow execution service failed."""


class WorkflowNotFoundError(WorkflowExecutionError):
    """A requested workflow or approval does not exist."""


def _utcnow() -> datetime.datetime:
    """Timezone-aware UTC timestamp"""
    return datetime.datetime.now(datetime.UTC)


def _saved_plan(workflow_run: WorkflowRun) -> Plan:
    if workflow_run.plan is None:
        raise WorkflowExecutionError("Workflow has no saved plan.")
    return Plan.model_validate(workflow_run.plan)


def _saved_coordinator_execution(workflow_run: WorkflowRun) -> CoordinatorExecution:
    if workflow_run.agent_state is None:
        raise WorkflowExecutionError("Workflow has no saved coordinator execution.")
    return CoordinatorExecution.model_validate(workflow_run.agent_state)


async def _fail_workflow(
    workflow_run: WorkflowRun,
    db: AsyncSession,
    exc: Exception,
    *,
    message: str | None = None,
) -> NoReturn:
    error_message = message or str(exc)
    workflow_run.status = WorkflowRunStatus.Failed
    workflow_run.error = error_message
    workflow_run.claimed_at = None
    workflow_run.updated_at = _utcnow()
    await db.commit()
    raise WorkflowExecutionError(error_message) from exc


async def _save_coordinator_execution(
    workflow_run: WorkflowRun,
    execution: CoordinatorExecution,
    db: AsyncSession,
) -> None:
    workflow_run.agent_state = execution.model_dump(mode="json")
    workflow_run.error = None

    if execution.stage == CoordinatorStages.COMPLETED:
        workflow_run.status = WorkflowRunStatus.Completed
        workflow_run.claimed_at = None
        workflow_run.updated_at = _utcnow()
        await db.commit()
        return

    if execution.stage == CoordinatorStages.REJECTED:
        workflow_run.status = WorkflowRunStatus.Cancelled
        workflow_run.claimed_at = None
        workflow_run.updated_at = _utcnow()
        await db.commit()
        return

    if execution.stage in (
        CoordinatorStages.AWAITING_APPROVALS,
        CoordinatorStages.MERGE_REPAIR_AWAITING_APPROVALS,
        CoordinatorStages.REVIEW_FIX_AWAITING_APPROVALS,
    ):
        workflow_run.status = WorkflowRunStatus.PendingToolApproval
        workflow_run.claimed_at = None
        workflow_run.updated_at = _utcnow()

    elif execution.stage == CoordinatorStages.AWAITING_FINAL_APPROVAL:
        workflow_run.status = WorkflowRunStatus.PendingFinalApproval
        workflow_run.claimed_at = None
        workflow_run.updated_at = _utcnow()
    else:
        raise RuntimeError(
            f"Coordinator returned a non-pausable stage: {execution.stage}."
        )

    if workflow_run.status == WorkflowRunStatus.PendingToolApproval:
        requests = pending_approval_requests(execution)
        if not requests:
            raise RuntimeError("Paused coordinator has no approval requests.")

        for request in requests:
            db.add(
                Approval(
                    workflow_run_id=workflow_run.id,
                    call_id=request.call_id,
                    tool_name=request.tool_name,
                    summary=request.summary,
                    details=request.details,
                )
            )

    await db.commit()


async def _continue_workflow(
    workflow_run: WorkflowRun,
    db: AsyncSession,
) -> None:
    try:
        async with asyncio.timeout(WORKFLOW_TIMEOUT_SECONDS):
            saved_plan = _saved_plan(workflow_run)
            if workflow_run.agent_state is not None:
                saved_state = _saved_coordinator_execution(workflow_run)
                resolutions = await _saved_approval_resolutions(workflow_run, db)
                execution = await resume_coordinator(
                    saved_plan, saved_state, resolutions
                )
            else:
                execution = await start_coordinator(saved_plan)
            await _save_coordinator_execution(workflow_run, execution, db)
    except TimeoutError as exc:
        await _fail_workflow(
            workflow_run,
            db,
            exc,
            message=f"Workflow timed out after {WORKFLOW_TIMEOUT_SECONDS} seconds.",
        )
    except WorkflowExecutionError as exc:
        await _fail_workflow(workflow_run, db, exc)
    # Record unexpected workflow failures instead of leaving durable state stuck
    # in Processing.
    except Exception as exc:  # noqa: BLE001
        await _fail_workflow(workflow_run, db, exc)


async def decide_approval(
    approval_id: uuid.UUID,
    decision: ApprovalDecision,
    rejection_message: str | None,
    db: AsyncSession,
) -> WorkflowRun:
    """Persist one tool decision and queue the run when all are decided."""
    approval = await db.get(Approval, approval_id)
    if not approval:
        raise WorkflowNotFoundError("Approval not found.")
    if approval.decision != ApprovalDecision.Pending:
        raise WorkflowExecutionError("Approval already has a decision.")

    workflow_run = await db.get(WorkflowRun, approval.workflow_run_id)
    if not workflow_run:
        raise WorkflowNotFoundError("Workflow run not found.")
    if workflow_run.status != WorkflowRunStatus.PendingToolApproval:
        raise WorkflowExecutionError("Workflow is not awaiting tool approval.")

    approval.decision = decision
    approval.rejection_message = rejection_message
    approval.decided_at = datetime.datetime.now(datetime.UTC)
    workflow_run.updated_at = _utcnow()
    await db.flush()

    pending_count = await db.scalar(
        select(func.count())
        .select_from(Approval)
        .where(
            Approval.workflow_run_id == workflow_run.id,
            Approval.decision == ApprovalDecision.Pending,
        )
    )
    if pending_count:
        await db.commit()
        return workflow_run

    workflow_run.status = WorkflowRunStatus.Queued
    workflow_run.claimed_at = None
    await db.commit()
    return workflow_run


async def _claim_queued_workflow(
    run_id: uuid.UUID,
    db: AsyncSession,
) -> WorkflowRun | None:
    """Atomically claim one queued run; return None when another task won."""
    claimed_id = await db.scalar(
        update(WorkflowRun)
        .where(
            WorkflowRun.id == run_id,
            WorkflowRun.status == WorkflowRunStatus.Queued,
        )
        .values(
            status=WorkflowRunStatus.Processing,
            error=None,
            claimed_at=_utcnow(),
            updated_at=_utcnow(),
        )
        .returning(WorkflowRun.id)
    )
    await db.commit()

    if claimed_id is not None:
        return await db.get(WorkflowRun, claimed_id)

    existing_id = await db.scalar(
        select(WorkflowRun.id).where(WorkflowRun.id == run_id)
    )
    if existing_id is None:
        raise WorkflowNotFoundError(f"Workflow run {run_id} was not found.")

    return None


async def _saved_approval_resolutions(
    workflow_run: WorkflowRun,
    db: AsyncSession,
) -> dict[str, ApprovalResolution]:
    approvals = (
        await db.scalars(
            select(Approval).where(Approval.workflow_run_id == workflow_run.id)
        )
    ).all()
    if any(approval.decision == ApprovalDecision.Pending for approval in approvals):
        raise WorkflowExecutionError("Workflow still has pending approval decisions.")

    return {
        approval.call_id: ApprovalResolution(
            decision=approval.decision,
            rejection_message=approval.rejection_message,
        )
        for approval in approvals
    }


async def _save_workflow_plan(workflow_run: WorkflowRun, db: AsyncSession) -> None:
    try:
        async with asyncio.timeout(WORKFLOW_TIMEOUT_SECONDS):
            plan = await invoke_planner(
                SAMPLE_REPOSITORY_ROOT,
                workflow_run.objective,
            )
    except TimeoutError as exc:
        await _fail_workflow(
            workflow_run,
            db,
            exc,
            message=f"Planning timed out after {WORKFLOW_TIMEOUT_SECONDS} seconds.",
        )
    except PlannerError as exc:
        await _fail_workflow(workflow_run, db, exc)
    except Exception as exc:  # noqa: BLE001
        await _fail_workflow(workflow_run, db, exc)

    workflow_run.plan = plan.model_dump(mode="json")
    workflow_run.status = WorkflowRunStatus.PendingPlanApproval
    workflow_run.error = None
    workflow_run.claimed_at = None
    workflow_run.updated_at = _utcnow()
    await db.commit()


async def requeue_stale_workflows(before: datetime.datetime) -> list[uuid.UUID]:
    """Release stale database claims and return the runs that need new tasks."""
    async with get_async_db_ctx() as db:
        run_ids = list(
            (
                await db.scalars(
                    update(WorkflowRun)
                    .where(
                        WorkflowRun.status == WorkflowRunStatus.Processing,
                        WorkflowRun.claimed_at.is_not(None),
                        WorkflowRun.claimed_at <= before,
                    )
                    .values(
                        status=WorkflowRunStatus.Queued,
                        claimed_at=None,
                        updated_at=_utcnow(),
                    )
                    .returning(WorkflowRun.id)
                )
            ).all()
        )
        await db.commit()
        return run_ids


async def finalize_workflow(
    workflow_run: WorkflowRun,
    approved: bool,
    db: AsyncSession,
) -> WorkflowRun:
    """Apply the final human decision and persist the terminal state."""
    try:
        execution = finalize_coordinator(
            _saved_coordinator_execution(workflow_run),
            approved=approved,
        )
        await _save_coordinator_execution(workflow_run, execution, db)
    except Exception as exc:  # noqa: BLE001
        await _fail_workflow(workflow_run, db, exc)

    return workflow_run


async def advance_workflow(run_id: uuid.UUID) -> bool:
    """Claim and advance a queued workflow until its next durable pause."""

    async with get_async_db_ctx() as db:
        workflow_run = await _claim_queued_workflow(run_id, db)
        if workflow_run is None:
            return False

        if workflow_run.plan is None:
            await _save_workflow_plan(workflow_run, db)
            return True

        await _continue_workflow(workflow_run, db)
        return True
