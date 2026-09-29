"""Общие фильтры подбора: правила, которые действуют на все процессы сразу, начиная с готовности робота."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0014_match_settings"
down_revision = "0013_object_in_match"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_setting",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("value", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("match_setting")
