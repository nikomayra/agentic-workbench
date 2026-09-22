import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import inspect, select
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
)
from app.repository.operations import SAMPLE_REPOSITORY_ROOT
from app.schemas.schemas import (
    ApprovalRejectRequest,
    ApprovalResponse,
    FinalApprovalRequest,
    WorkflowRunCreate,
    WorkflowRunResponse,
)
from app.services.workflow_execution import (
    _decide_approval,
    _fail_workflow,
    _save_coordinator_execution,
    _saved_coordinator_execution,
)
from app.tasks.workflow_tasks import enqueue_workflow

router = APIRouter()

WORKFLOW_ERRORS = (PlannerError, ReviewerError, WorkerError, RuntimeError)


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

    workflow_run.status = WorkflowRunStatus.Queued
    await db.commit()
    enqueue_workflow(workflow_run.id)
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
    workflow_run = await _decide_approval(
        approval_id,
        ApprovalDecision.Approved,
        None,
        response,
        db,
    )
    if workflow_run.status == WorkflowRunStatus.Queued:
        enqueue_workflow(workflow_run.id)
    return workflow_run


@router.post("/approvals/{approval_id}/reject")
async def reject_tool(
    approval_id: uuid.UUID,
    payload: ApprovalRejectRequest,
    response: Response,
    db: AsyncSession = Depends(get_async_db_session),
) -> WorkflowRunResponse:
    workflow_run = await _decide_approval(
        approval_id,
        ApprovalDecision.Rejected,
        payload.rejection_message,
        response,
        db,
    )
    if workflow_run.status == WorkflowRunStatus.Queued:
        enqueue_workflow(workflow_run.id)
    return workflow_run


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
