import asyncio
import datetime
import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_async_db_ctx, get_async_db_session
from app.models.models import (
    Approval,
    ApprovalDecision,
    WorkflowRun,
    WorkflowRunStatus,
)
from app.schemas.schemas import (
    ApprovalRejectRequest,
    ApprovalResponse,
    FinalApprovalRequest,
    WorkflowRunCreate,
    WorkflowRunResponse,
)
from app.services.workflow_execution import (
    WorkflowExecutionError,
    WorkflowNotFoundError,
    decide_approval,
    finalize_workflow,
)
from app.tasks.workflow_tasks import enqueue_workflow

router = APIRouter()


@router.post("/runs")
async def create_run(
    payload: WorkflowRunCreate,
    response: Response,
    db: AsyncSession = Depends(get_async_db_session),
) -> WorkflowRunResponse:
    workflow_run = WorkflowRun(
        objective=payload.objective,
        status=WorkflowRunStatus.Queued,
    )
    db.add(workflow_run)
    await db.commit()

    enqueue_workflow(workflow_run.id)
    response.status_code = 202

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
    workflow_run.updated_at = datetime.datetime.now(datetime.UTC)
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
        await finalize_workflow(workflow_run, payload.approved, db)
    except WorkflowExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return WorkflowRunResponse.model_validate(workflow_run, from_attributes=True)


async def _decide_tool_approval(
    approval_id: uuid.UUID,
    decision: ApprovalDecision,
    rejection_message: str | None,
    response: Response,
    db: AsyncSession,
) -> WorkflowRunResponse:
    try:
        workflow_run = await decide_approval(
            approval_id,
            decision,
            rejection_message,
            db,
        )
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowExecutionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if workflow_run.status == WorkflowRunStatus.Queued:
        enqueue_workflow(workflow_run.id)

    response.status_code = 202
    return WorkflowRunResponse.model_validate(workflow_run, from_attributes=True)


@router.post("/approvals/{approval_id}/approve")
async def approve_tool(
    approval_id: uuid.UUID,
    response: Response,
    db: AsyncSession = Depends(get_async_db_session),
) -> WorkflowRunResponse:
    return await _decide_tool_approval(
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
    return await _decide_tool_approval(
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


TERMINAL_WORKFLOW_STATUSES = {
    WorkflowRunStatus.Cancelled,
    WorkflowRunStatus.Completed,
    WorkflowRunStatus.Failed,
}
SSE_HEARTBEAT_SECONDS = 15.0
SSE_POLL_SECONDS = 1.0


@router.get("/runs/{run_id}/events")
async def stream_run_status(run_id: uuid.UUID, request: Request) -> StreamingResponse:
    # Validate before opening a successful streaming response. The generator uses
    # short-lived sessions so one browser connection does not hold a DB session.
    async with get_async_db_ctx() as db:
        if await db.get(WorkflowRun, run_id) is None:
            raise HTTPException(status_code=404, detail="Workflow run not found.")

    return StreamingResponse(
        _workflow_status_events(run_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _workflow_status_events(run_id: uuid.UUID, request: Request):
    last_snapshot: str | None = None
    last_send_time = time.monotonic()

    while not await request.is_disconnected():
        async with get_async_db_ctx() as db:
            workflow_run = await db.get(WorkflowRun, run_id)

        if workflow_run is None:
            return

        response = WorkflowRunResponse.model_validate(
            workflow_run,
            from_attributes=True,
        )
        snapshot = response.model_dump_json()

        if snapshot != last_snapshot:
            yield _format_sse(snapshot, event="workflow")
            last_snapshot = snapshot
            last_send_time = time.monotonic()
        elif time.monotonic() - last_send_time >= SSE_HEARTBEAT_SECONDS:
            yield ": heartbeat\n\n"
            last_send_time = time.monotonic()

        if workflow_run.status in TERMINAL_WORKFLOW_STATUSES:
            return

        await asyncio.sleep(SSE_POLL_SECONDS)


def _format_sse(data: str, event: str | None = None) -> str:
    """Format one named or unnamed Server-Sent Event."""
    sse_lines: list[str] = []
    if event:
        sse_lines.append(f"event: {event}")

    for line in data.splitlines():
        sse_lines.append(f"data: {line}")

    return "\n".join(sse_lines) + "\n\n"
