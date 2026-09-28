"""Причина, по которой процесс выключили в проекте: невыгоден по экономике."""

from alembic import op

revision = "0012_process_disabled_reason"
down_revision = "0011_review_process_assignments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # На чистой базе колонку уже завела 0011_demo_projects.
    op.execute("ALTER TABLE project_process ADD COLUMN IF NOT EXISTS disabled_reason text")


def downgrade() -> None:
    op.execute("ALTER TABLE project_process DROP COLUMN IF EXISTS disabled_reason")
