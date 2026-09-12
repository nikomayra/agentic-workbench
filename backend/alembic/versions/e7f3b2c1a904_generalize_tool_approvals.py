"""Generalize tool approval display data.

Revision ID: e7f3b2c1a904
Revises: c91f3a7d2e10
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e7f3b2c1a904"
down_revision: str | Sequence[str] | None = "c91f3a7d2e10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("approval", sa.Column("summary", sa.TEXT(), nullable=True))
    op.add_column("approval", sa.Column("details", sa.JSON(), nullable=True))
    op.execute(
        "UPDATE approval SET summary = tool_name, details = operation"
    )
    op.alter_column("approval", "summary", nullable=False)
    op.alter_column("approval", "details", nullable=False)
    op.drop_column("approval", "operation")


def downgrade() -> None:
    op.add_column("approval", sa.Column("operation", sa.JSON(), nullable=True))
    op.execute("UPDATE approval SET operation = details")
    op.alter_column("approval", "operation", nullable=False)
    op.drop_column("approval", "details")
    op.drop_column("approval", "summary")
