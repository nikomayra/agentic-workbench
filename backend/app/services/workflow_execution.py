import asyncio
import datetime
import uuid
from typing import NoReturn

from fastapi import HTTPException, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_db_ctx
from app.models.models import (
    Approval,
    ApprovalDecision,
    WorkflowRun,
    WorkflowRunStatus,
)
from app.orchestration.coordinator import (
    resume_coordinator,
    start_coordinator,
)
from app.orchestration.state import (
    CoordinatorExecution,
    CoordinatorStages,
    pending_approval_requests,
)
from app.schemas.schemas import (
    ApprovalResolution,
    Plan,
    WorkflowRunResponse,
)

WORKFLOW_TIMEOUT_SECONDS = 120


def _saved_plan(workflow_run: WorkflowRun) -> Plan:
    if workflow_run.plan is None:
        raise HTTPException(status_code=409, detail="Workflow has no saved plan.")
    return Plan.model_validate(workflow_run.plan)


def _saved_coordinator_execution(workflow_run: WorkflowRun) -> CoordinatorExecution:
    if workflow_run.agent_state is None:
        raise HTTPException(
            status_code=409, detail="Workflow has no saved coordinator execution."
        )
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
    await db.commit()
    raise HTTPException(status_code=502, detail=error_message) from exc


async def _save_coordinator_execution(
    workflow_run: WorkflowRun,
    execution: CoordinatorExecution,
    db: AsyncSession,
) -> None:
    workflow_run.agent_state = execution.model_dump(mode="json")
    workflow_run.error = None

    if execution.stage == CoordinatorStages.COMPLETED:
        workflow_run.status = WorkflowRunStatus.Completed
        await db.commit()
        return

    if execution.stage == CoordinatorStages.REJECTED:
        workflow_run.status = WorkflowRunStatus.Cancelled
        await db.commit()
        return

    if execution.stage in (
        CoordinatorStages.AWAITING_APPROVALS,
        CoordinatorStages.MERGE_REPAIR_AWAITING_APPROVALS,
        CoordinatorStages.REVIEW_FIX_AWAITING_APPROVALS,
    ):
        workflow_run.status = WorkflowRunStatus.PendingToolApproval
    elif execution.stage == CoordinatorStages.AWAITING_FINAL_APPROVAL:
        workflow_run.status = WorkflowRunStatus.PendingFinalApproval
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
    *,
    resolutions: dict[str, ApprovalResolution] | None = None,
) -> None:
    try:
        async with asyncio.timeout(WORKFLOW_TIMEOUT_SECONDS):
            saved_plan = _saved_plan(workflow_run)
            if resolutions is not None:
                saved_state = _saved_coordinator_execution(workflow_run)
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
    except HTTPException as exc:
        await _fail_workflow(workflow_run, db, exc, message=str(exc.detail))
    # This route boundary records unexpected workflow failures instead of leaving
    # a durable run stuck in the Processing state.
    except Exception as exc:  # noqa: BLE001
        await _fail_workflow(workflow_run, db, exc)


async def _decide_approval(
    approval_id: uuid.UUID,
    decision: ApprovalDecision,
    rejection_message: str | None,
    response: Response,
    db: AsyncSession,
) -> WorkflowRunResponse:
    approval = await db.get(Approval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found.")
    if approval.decision != ApprovalDecision.Pending:
        raise HTTPException(status_code=409, detail="Approval already has a decision.")

    workflow_run = await db.get(WorkflowRun, approval.workflow_run_id)
    if not workflow_run:
        raise HTTPException(status_code=404, detail="Workflow run not found.")
    if workflow_run.status != WorkflowRunStatus.PendingToolApproval:
        raise HTTPException(
            status_code=409, detail="Workflow is not awaiting tool approval."
        )

    approval.decision = decision
    approval.rejection_message = rejection_message
    approval.decided_at = datetime.datetime.now(datetime.UTC)
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
        response.status_code = 202
        return WorkflowRunResponse.model_validate(workflow_run, from_attributes=True)

    workflow_run.status = WorkflowRunStatus.Queued
    await db.commit()
    response.status_code = 202

    return WorkflowRunResponse.model_validate(workflow_run, from_attributes=True)


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
        .values(status=WorkflowRunStatus.Processing, error=None)
        .returning(WorkflowRun.id)
    )
    await db.commit()

    if claimed_id is not None:
        return await db.get(WorkflowRun, claimed_id)

    existing_id = await db.scalar(
        select(WorkflowRun.id).where(WorkflowRun.id == run_id)
    )
    if existing_id is None:
        raise RuntimeError(f"Workflow run {run_id} was not found.")

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
        raise RuntimeError("Workflow still has pending approval decisions.")

    return {
        approval.call_id: ApprovalResolution(
            decision=approval.decision,
            rejection_message=approval.rejection_message,
        )
        for approval in approvals
    }


async def advance_workflow(run_id: uuid.UUID) -> bool:
    """Claim and advance a queued workflow until its next durable pause."""

    async with get_async_db_ctx() as db:
        workflow_run = await _claim_queued_workflow(run_id, db)
        if workflow_run is None:
            return False

        resolutions = None
        if workflow_run.agent_state is not None:
            resolutions = await _saved_approval_resolutions(workflow_run, db)

        await _continue_workflow(workflow_run, db, resolutions=resolutions)
        return True
