"""Add per-user token version for session revocation after password changes."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20261007_token_version"
down_revision: str | Sequence[str] | None = "4d8b8a62e7d1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column(
                "token_version",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("token_version")
