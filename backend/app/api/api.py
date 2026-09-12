import asyncio
import datetime
import json
import uuid
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.planning import PlannerError, invoke_planner
from app.agents.reviewer import ReviewerError
from app.agents.workers import WorkerError
from app.db import get_async_db_session
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
from app.orchestration.state import CoordinatorExecution, CoordinatorStages
from app.repository.operations import SAMPLE_REPOSITORY_ROOT
from app.schemas.schemas import (
    ApprovalRejectRequest,
    ApprovalRequest,
    ApprovalResolution,
    ApprovalResponse,
    FinalApprovalRequest,
    Plan,
    WorkflowRunCreate,
    WorkflowRunResponse,
)

router = APIRouter()

WORKFLOW_ERRORS = (PlannerError, ReviewerError, WorkerError, RuntimeError)
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
        requests = _extract_approvals(execution)
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


def _extract_approvals(execution: CoordinatorExecution) -> list[ApprovalRequest]:
    """Return approvals from only the execution that caused the current pause."""
    requests: list[ApprovalRequest] = []

    if execution.stage == CoordinatorStages.AWAITING_APPROVALS:
        for work_record in execution.work_records:
            if work_record.work_execution:
                requests.extend(work_record.work_execution.approval_requests)
    elif (
        execution.stage == CoordinatorStages.MERGE_REPAIR_AWAITING_APPROVALS
        and execution.merge_conflict
        and execution.merge_conflict.repair_execution
    ):
        requests.extend(execution.merge_conflict.repair_execution.approval_requests)
    elif (
        execution.stage == CoordinatorStages.REVIEW_FIX_AWAITING_APPROVALS
        and execution.review_findings
        and execution.review_findings.fix_execution
    ):
        requests.extend(execution.review_findings.fix_execution.approval_requests)

    return requests


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
    except HTTPException:
        raise
    # This route boundary records unexpected workflow failures instead of leaving
    # a durable run stuck in the Processing state.
    except Exception as exc:  # noqa: BLE001
        await _fail_workflow(workflow_run, db, exc)


@router.post("/runs")
async def create_run(
    payload: WorkflowRunCreate,
    db: AsyncSession = Depends(get_async_db_session),
) -> WorkflowRunResponse:
    workflow_run = WorkflowRun(
        objective=payload.objective,
        status=WorkflowRunStatus.Processing,
    )
    db.add(workflow_run)
    await db.commit()

    try:
        plan = await invoke_planner(SAMPLE_REPOSITORY_ROOT, payload.objective)
    except PlannerError as exc:
        await _fail_workflow(workflow_run, db, exc)

    workflow_run.plan = plan.model_dump(mode="json")
    workflow_run.status = WorkflowRunStatus.PendingPlanApproval
    workflow_run.error = None
    await db.commit()

    return WorkflowRunResponse.model_validate(workflow_run, from_attributes=True)


@router.get("/runs/{run_id}")
async def find_run(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> WorkflowRunResponse:
    workflow_run = await db.get(WorkflowRun, run_id)
    if not workflow_run:
        raise HTTPException(status_code=404, detail="Workflow run not found.")

    return WorkflowRunResponse.model_validate(workflow_run, from_attributes=True)


# TODO add pagination...
@router.get("/runs")
async def list_runs(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[WorkflowRunResponse]:
    workflow_runs = (
        await db.scalars(select(WorkflowRun).order_by(WorkflowRun.created_at.desc()))
    ).all()
    if not workflow_runs:
        raise HTTPException(status_code=404, detail="No workflow run not found.")

    for w in workflow_runs:
        attrs = {c.key: getattr(w, c.key) for c in inspect(w).mapper.column_attrs}
        # handles datetime, uuid, and nested json formatting safely
        print(json.dumps(attrs, default=str, indent=2))

    return [
        WorkflowRunResponse.model_validate(workflow_run, from_attributes=True)
        for workflow_run in workflow_runs
    ]


@router.post("/runs/{run_id}/approve")
async def approve_plan(
    run_id: uuid.UUID,
    response: Response,
    db: AsyncSession = Depends(get_async_db_session),
) -> WorkflowRunResponse:
    workflow_run = await db.get(WorkflowRun, run_id)
    if not workflow_run:
        raise HTTPException(status_code=404, detail="Workflow run not found.")
    if workflow_run.status != WorkflowRunStatus.PendingPlanApproval:
        raise HTTPException(status_code=409, detail="Plan is not awaiting approval.")

    workflow_run.status = WorkflowRunStatus.Processing
    await db.commit()
    await _continue_workflow(workflow_run, db)

    if workflow_run.status in (
        WorkflowRunStatus.PendingToolApproval,
        WorkflowRunStatus.PendingFinalApproval,
    ):
        response.status_code = 202

    return WorkflowRunResponse.model_validate(workflow_run, from_attributes=True)


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

    approvals = (
        await db.scalars(
            select(Approval).where(Approval.workflow_run_id == workflow_run.id)
        )
    ).all()
    resolutions = {
        item.call_id: ApprovalResolution(
            decision=item.decision,
            rejection_message=item.rejection_message,
        )
        for item in approvals
    }

    workflow_run.status = WorkflowRunStatus.Processing
    await db.commit()
    await _continue_workflow(workflow_run, db, resolutions=resolutions)

    if workflow_run.status in (
        WorkflowRunStatus.PendingToolApproval,
        WorkflowRunStatus.PendingFinalApproval,
    ):
        response.status_code = 202

    return WorkflowRunResponse.model_validate(workflow_run, from_attributes=True)


@router.post("/runs/{run_id}/finalize")
async def finalize_run(
    run_id: uuid.UUID,
    payload: FinalApprovalRequest,
    db: AsyncSession = Depends(get_async_db_session),
) -> WorkflowRunResponse:
    """Apply the human's final decision and clean up temporary worktrees."""
    workflow_run = await db.get(WorkflowRun, run_id)
    if not workflow_run:
        raise HTTPException(status_code=404, detail="Workflow run not found.")
    if workflow_run.status != WorkflowRunStatus.PendingFinalApproval:
        raise HTTPException(
            status_code=409, detail="Workflow is not awaiting final approval."
        )

    try:
        execution = finalize_coordinator(
            _saved_coordinator_execution(workflow_run),
            approved=payload.approved,
        )
        await _save_coordinator_execution(workflow_run, execution, db)
    except WORKFLOW_ERRORS as exc:
        await _fail_workflow(workflow_run, db, exc)

    return WorkflowRunResponse.model_validate(workflow_run, from_attributes=True)


@router.post("/approvals/{approval_id}/approve")
async def approve_tool(
    approval_id: uuid.UUID,
    response: Response,
    db: AsyncSession = Depends(get_async_db_session),
) -> WorkflowRunResponse:
    return await _decide_approval(
        approval_id,
        ApprovalDecision.Approved,
        None,
        response,
        db,
    )


@router.post("/approvals/{approval_id}/reject")
async def reject_tool(
    approval_id: uuid.UUID,
    payload: ApprovalRejectRequest,
    response: Response,
    db: AsyncSession = Depends(get_async_db_session),
) -> WorkflowRunResponse:
    return await _decide_approval(
        approval_id,
        ApprovalDecision.Rejected,
        payload.rejection_message,
        response,
        db,
    )


@router.get("/approvals/{approval_id}")
async def find_approval(
    approval_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> ApprovalResponse:
    approval = await db.get(Approval, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval not found.")

    return ApprovalResponse.model_validate(approval, from_attributes=True)


@router.get("/runs/{run_id}/approvals")
async def list_approvals(
    run_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> list[ApprovalResponse]:
    workflow_run = await db.get(WorkflowRun, run_id)
    if not workflow_run:
        raise HTTPException(status_code=404, detail="Workflow run not found.")

    approvals = (
        await db.scalars(
            select(Approval)
            .where(Approval.workflow_run_id == run_id)
            .order_by(Approval.created_at.desc())
        )
    ).all()
    return [
        ApprovalResponse.model_validate(approval, from_attributes=True)
        for approval in approvals
    ]
