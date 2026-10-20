"""Журнал подбора: итог, параметры площадки и причины, без данных заказчика."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0025_match_journal"
down_revision = ("0024_assessment_profiles", "0024_analytics")
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "match_journal",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("object_code", sa.Text(), nullable=False, server_default=""),
        sa.Column("object_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.Text(), nullable=False, server_default="project"),
        sa.Column("outcome", sa.Text(), nullable=False, server_default="empty"),
        sa.Column("site", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_match_journal_created", "match_journal", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_match_journal_created", table_name="match_journal")
    op.drop_table("match_journal")
