"""Причина, по которой процесс выключили в проекте: невыгоден по экономике."""

import sqlalchemy as sa
from alembic import op

revision = "0012_process_disabled_reason"
down_revision = "0011_review_process_assignments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("project_process", sa.Column("disabled_reason", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("project_process", "disabled_reason")
