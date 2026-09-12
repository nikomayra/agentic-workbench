import datetime
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.models import ApprovalDecision, WorkflowRunStatus


class PlanStep(BaseModel):
    title: str
    description: str
    acceptance_criteria: str


class Workstream(BaseModel):
    """One unit of independent work assigned to worker derived from plan"""

    name: str
    task: str
    intended_paths: list[str]
    acceptance_criteria: list[str]
    shared_contracts: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    summary: str
    steps: list[PlanStep]


class ExecutionPlan(BaseModel):
    """Machine-facing decomposition of one approved plan."""

    workstreams: list[Workstream] = Field(min_length=1)


class ReviewInput(BaseModel):
    original_plan: Plan
    executed_workstreams: list[Workstream]
    implementation_notes: str
    actual_diff: str
    test_output: str


class ReviewStatus(StrEnum):
    SUCCESS = "pass"
    CHANGES_REQUIRED = "changes_required"


class ReviewOutput(BaseModel):
    status: ReviewStatus
    repair_task: str | None = Field(
        default=None,
        description="None on success status, or actionable corrections when changes are required.",
    )
    affected_paths: list[str] = Field(
        default_factory=list,
        description="Best-effort affected file paths when changes are required.",
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Clear acceptance criteria when changes are required.",
    )

    @model_validator(mode="after")
    def validate_required_repair_details(self) -> ReviewOutput:
        """Require enough information to create repair work after a failed review."""
        if self.status == ReviewStatus.CHANGES_REQUIRED and (
            not self.repair_task or not self.acceptance_criteria
        ):
            raise ValueError(
                "Changes-required review must include a repair task and acceptance criteria."
            )
        return self


class ApprovalRequest(BaseModel):
    """One SDK tool interruption that needs a human decision."""

    call_id: str
    tool_name: str
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class ApprovalResolution(BaseModel):
    """A saved human decision used when resuming an SDK RunState."""

    decision: ApprovalDecision
    rejection_message: str | None = None


class WorkflowRunCreate(BaseModel):
    objective: str


class FinalApprovalRequest(BaseModel):
    approved: bool


class WorkflowRunResponse(BaseModel):
    id: uuid.UUID
    objective: str
    status: WorkflowRunStatus
    plan: Plan | None
    error: str | None
    created_at: datetime.datetime


class ApprovalRejectRequest(BaseModel):
    rejection_message: str | None = None


class ApprovalResponse(BaseModel):
    id: uuid.UUID
    workflow_run_id: uuid.UUID
    call_id: str
    tool_name: str
    summary: str
    details: dict[str, Any]
    decision: ApprovalDecision
    rejection_message: str | None
    created_at: datetime.datetime
    decided_at: datetime.datetime | None
