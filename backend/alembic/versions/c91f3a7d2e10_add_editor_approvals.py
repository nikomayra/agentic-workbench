"""Add editor approval persistence.

Revision ID: c91f3a7d2e10
Revises: 2987b87c7bbd
Create Date: 2026-08-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c91f3a7d2e10"
down_revision: str | Sequence[str] | None = "2987b87c7bbd"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workflow_run", sa.Column("agent_state", sa.JSON(), nullable=True))
    op.add_column(
        "workflow_run",
        sa.Column(
            "revision_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.create_table(
        "approval",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("workflow_run_id", sa.Uuid(), nullable=False),
        sa.Column("call_id", sa.String(length=255), nullable=False),
        sa.Column("tool_name", sa.String(length=255), nullable=False),
        sa.Column("operation", sa.JSON(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("rejection_message", sa.TEXT(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["workflow_run_id"], ["workflow_run.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("call_id"),
    )


def downgrade() -> None:
    op.drop_table("approval")
    op.drop_column("workflow_run", "revision_count")
    op.drop_column("workflow_run", "agent_state")
