"""Задачи демо аэропорта и медучреждения: без численности экономика не считает эффект."""

from alembic import op
from sqlalchemy.orm import Session

revision = "0015_demo_object_tasks"
down_revision = "0014_match_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.application.reference_data import attach_demo_tasks

    with Session(bind=op.get_bind()) as db:
        attach_demo_tasks(db)
        db.commit()


def downgrade() -> None:
    # Численность — данные демо, а не схема. Откат миграции её не стирает.
    pass
