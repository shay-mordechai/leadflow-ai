"""align leads summary_message_count server_default

Revision ID: 20261123_align_default
Revises: 20261122_enforce_rls_all
Create Date: 2026-11-23 18:05:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20261123_align_default"
down_revision: str | Sequence[str] | None = "20261122_enforce_rls_all"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "leads",
        "summary_message_count",
        existing_type=sa.Integer(),
        server_default="0",
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "leads",
        "summary_message_count",
        existing_type=sa.Integer(),
        server_default=None,
        existing_nullable=False,
    )
