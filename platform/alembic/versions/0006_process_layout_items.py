"""Объекты процесса на схеме: станции, зоны и точки, которые нужны роботу для работы."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006_process_layout_items"
down_revision = "0005_project_layout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("process", sa.Column("layout_items", JSONB(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("process", "layout_items")
