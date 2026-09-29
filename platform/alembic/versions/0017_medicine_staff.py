"""Доставка лекарств получает свою половину численности санитаров в уже созданном демо."""

from alembic import op
from sqlalchemy.orm import Session

revision = "0017_medicine_staff"
down_revision = "0016_refresh_demo_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.application.reference_data import attach_demo_tasks

    with Session(bind=op.get_bind()) as db:
        attach_demo_tasks(db)
        db.commit()


def downgrade() -> None:
    pass
