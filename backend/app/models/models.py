from __future__ import annotations

import datetime
import uuid
from enum import StrEnum

from sqlalchemy import JSON, TEXT, TIMESTAMP, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


def _utcnow() -> datetime.datetime:
    """Timezone-aware UTC timestamp for SQLAlchemy column defaults."""
    return datetime.datetime.now(datetime.UTC)


class WorkflowRunStatus(StrEnum):
    Cancelled = "cancelled"
    Processing = "processing"
    PendingPlanApproval = "pending_plan_approval"
    PendingToolApproval = "pending_tool_approval"
    PendingFinalApproval = "pending_final_approval"
    Completed = "completed"
    Failed = "failed"


class ApprovalDecision(StrEnum):
    Pending = "pending"
    Approved = "approved"
    Rejected = "rejected"


class WorkflowRun(Base):
    __tablename__ = "workflow_run"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    objective: Mapped[str] = mapped_column(TEXT(), nullable=False)
    status: Mapped[WorkflowRunStatus] = mapped_column(
        String(128), nullable=False, default=WorkflowRunStatus.Processing
    )
    plan: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(TEXT(), nullable=True)
    agent_state: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    revision_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow
    )

    approvals: Mapped[list[Approval]] = relationship(
        back_populates="workflow_run",
        cascade="all, delete-orphan",
    )


class Approval(Base):
    __tablename__ = "approval"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_run.id"), nullable=False
    )
    call_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    tool_name: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(TEXT(), nullable=False)
    details: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    decision: Mapped[ApprovalDecision] = mapped_column(
        String(32), nullable=False, default=ApprovalDecision.Pending
    )
    rejection_message: Mapped[str | None] = mapped_column(TEXT(), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, default=_utcnow
    )
    decided_at: Mapped[datetime.datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    workflow_run: Mapped[WorkflowRun] = relationship(back_populates="approvals")
