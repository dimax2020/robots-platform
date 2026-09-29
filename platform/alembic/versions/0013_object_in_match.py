"""Объект можно выключить из подбора: без галочки его не выбрать в новом проекте."""

from alembic import op

revision = "0013_object_in_match"
down_revision = "0012_process_disabled_reason"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Колонку уже могла завести 0007_admin_catalog, чтобы сид справочника не падал.
    op.execute("ALTER TABLE object_type ADD COLUMN IF NOT EXISTS in_match boolean NOT NULL DEFAULT true")


def downgrade() -> None:
    op.drop_column("object_type", "in_match")
