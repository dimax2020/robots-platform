"""Стандартные коэффициенты экономики, история их правок и значения проекта."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004_economy_norms"
down_revision = "0003_process_formula"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "economy_norm",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "economy_norm_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("old_value", sa.Numeric()),
        sa.Column("new_value", sa.Numeric(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.add_column("project", sa.Column("economy_overrides", JSONB(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("project", "economy_overrides")
    op.drop_table("economy_norm_log")
    op.drop_table("economy_norm")
