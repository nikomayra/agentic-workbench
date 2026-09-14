import uuid
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from app.agents.workers import WorkExecution
from app.orchestration.worktrees import Worktree
from app.schemas.schemas import ApprovalRequest, ReviewOutput, Workstream


class CoordinatorStages(StrEnum):
    # Init
    CREATED = "created"

    # Processing
    AWAITING_APPROVALS = "awaiting_approvals"
    WORK_COMPLETED = "work_completed"
    INTEGRATING = "integrating"
    MERGE_CONFLICT = "merge_conflict"
    MERGE_REPAIR_AWAITING_APPROVALS = "merge_repair_awaiting_approvals"
    MERGE_REPAIR_COMPLETED = "merge_repair_completed"
    INTEGRATED = "integrated"
    REVIEW_FINDINGS = "review_findings"
    REVIEW_FIX_AWAITING_APPROVALS = "review_fix_awaiting_approvals"
    REVIEW_FIX_COMPLETED = "review_fix_completed"
    AWAITING_FINAL_APPROVAL = "awaiting_final_approval"

    # TERMINAL
    COMPLETED = "completed"
    REJECTED = "rejected"


class WorkRecordStatus(StrEnum):
    NOT_MERGED = "not_merged"
    MERGED = "merged"


class WorkRecord(BaseModel):
    work_id: uuid.UUID
    status: WorkRecordStatus
    workstream: Workstream
    worktree: Worktree
    work_execution: WorkExecution | None = None


class MergeConflict(BaseModel):
    work_id: uuid.UUID
    file_paths: list[Path]
    repair_execution: WorkExecution | None = None


class ReviewFindings(BaseModel):
    review_output: ReviewOutput
    fix_attempts: int = 0
    fix_execution: WorkExecution | None = None


class CoordinatorExecution(BaseModel):
    stage: CoordinatorStages
    work_records: list[WorkRecord]
    integration_worktree: Worktree | None = None
    merge_conflict: MergeConflict | None = None
    review_findings: ReviewFindings | None = None


def pending_approval_requests(
    execution: CoordinatorExecution,
) -> list[ApprovalRequest]:
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
