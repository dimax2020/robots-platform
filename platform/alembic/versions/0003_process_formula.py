"""Колонки формулы фильтра, расчёта количества и привязки величин к параметрам объекта."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_process_formula"
down_revision = "0002_parser_minute"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("process", sa.Column("count_formula", sa.Text(), nullable=False, server_default=""))
    op.add_column("process", sa.Column("count_inputs", JSONB(), nullable=False, server_default="[]"))
    op.add_column("process", sa.Column("rank_key", sa.Text(), nullable=False, server_default=""))
    op.add_column("process", sa.Column("rank_order", sa.Text(), nullable=False, server_default="asc"))
    op.add_column("process_filter", sa.Column("inputs", JSONB(), nullable=False, server_default="[]"))
    op.add_column("process_filter", sa.Column("formula", sa.Text(), nullable=False, server_default=""))
    op.create_table(
        "object_input_binding",
        sa.Column("object_type_id", sa.Integer(), sa.ForeignKey("object_type.id"), primary_key=True),
        sa.Column("process_id", sa.Integer(), sa.ForeignKey("process.id"), primary_key=True),
        sa.Column("input_key", sa.Text(), primary_key=True),
        sa.Column("site_key", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("object_input_binding")
    op.drop_column("process_filter", "formula")
    op.drop_column("process_filter", "inputs")
    op.drop_column("process", "rank_order")
    op.drop_column("process", "rank_key")
    op.drop_column("process", "count_inputs")
    op.drop_column("process", "count_formula")
