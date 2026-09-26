"""Схема объекта проекта: этажи, стены, препятствия, станции и переходы между этажами."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_project_layout"
down_revision = "0004_economy_norms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("project", sa.Column("layout", JSONB(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("project", "layout")
