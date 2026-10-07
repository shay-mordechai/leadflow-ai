"""Add WhatsApp message idempotency and lead qualification score.

Revision ID: 4d8b8a62e7d1
Revises: bbaf27c9b091
Create Date: 2026-10-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4d8b8a62e7d1"
down_revision: Union[str, Sequence[str], None] = "bbaf27c9b091"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("leads") as batch_op:
        batch_op.add_column(sa.Column("qualification_score", sa.Integer(), nullable=True))

    with op.batch_alter_table("messages") as batch_op:
        batch_op.add_column(sa.Column("external_id", sa.String(), nullable=True))
        batch_op.create_index("ix_messages_external_id", ["external_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("messages") as batch_op:
        batch_op.drop_index("ix_messages_external_id")
        batch_op.drop_column("external_id")

    with op.batch_alter_table("leads") as batch_op:
        batch_op.drop_column("qualification_score")