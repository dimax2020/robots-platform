"""Численность в уже созданных демо и возврат процессов, выключенных старым расчётом."""

from alembic import op
from sqlalchemy.orm import Session

revision = "0016_refresh_demo_tasks"
down_revision = "0015_demo_object_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.application.reference_data import attach_demo_tasks

    with Session(bind=op.get_bind()) as db:
        attach_demo_tasks(db)
        db.commit()


def downgrade() -> None:
    pass
