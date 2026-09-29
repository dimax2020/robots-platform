"""Объект можно выключить из подбора: без галочки его не выбрать в новом проекте."""

import sqlalchemy as sa
from alembic import op

revision = "0013_object_in_match"
down_revision = "0012_process_disabled_reason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "object_type",
        sa.Column("in_match", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column("object_type", "in_match")
