"""baseline (no models yet)

Revision ID: b5cf6a780cd8
Revises:
Create Date: 2026-08-13 14:50:25.610887

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "b5cf6a780cd8"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""


def downgrade() -> None:
    """Downgrade schema."""
