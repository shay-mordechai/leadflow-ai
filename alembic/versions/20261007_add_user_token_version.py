"""Add per-user token version for session revocation after password changes."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261007_token_version"
down_revision: Union[str, Sequence[str], None] = "4d8b8a62e7d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
