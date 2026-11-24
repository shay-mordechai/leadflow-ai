"""add FREE value to plantier enum

Revision ID: 20261124_add_free_tier
Revises: 20261123_align_default
Create Date: 2026-11-24 11:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "20261124_add_free_tier"
down_revision: str | Sequence[str] | None = "20261123_align_default"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        with op.get_context().autocommit_block():
            op.execute("ALTER TYPE plantier ADD VALUE IF NOT EXISTS 'FREE'")


def downgrade() -> None:
    # PostgreSQL enums do not support dropping individual values without recreating the type.
    pass
