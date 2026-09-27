"""Назначения по смыслу карточек и объединение дублирующих процессов."""

import logging

from alembic import op
from sqlalchemy.orm import Session

revision = "0011_review_process_assignments"
down_revision = "0011_demo_projects"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.application.assign_processes import assign_all

    with Session(bind=op.get_bind()) as db:
        counts = assign_all(db, commit=False)
        logging.getLogger("alembic.runtime.migration").info(
            "Связи роботов пересмотрены: %s; без установленных задач: %s",
            sum(v for k, v in counts.items() if k != "unassigned"), counts["unassigned"],
        )


def downgrade() -> None:
    # Возвращать заведомо ошибочные связи и стирать ручные исправления нельзя.
    pass
