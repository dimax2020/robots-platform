"""Демо-склад снова считает ФОТ по ролям площадки: убираем две задачи, записанные в 0016."""

from alembic import op
from sqlalchemy import select
from sqlalchemy.orm import Session

revision = "0018_warehouse_roles_back"
down_revision = "0017_medicine_staff"
branch_labels = None
depends_on = None

# Ровно те строки, что записала 0016. Задачи, которые админ завёл сам, не трогаем.
_SEEDED = {("order_picking", 100, 1_562_400), ("pallet_transport", 25, 1_874_880)}


def upgrade() -> None:
    from app.infrastructure.db.models import ProjectRow

    with Session(bind=op.get_bind()) as db:
        project = db.scalar(select(ProjectRow).where(ProjectRow.slug == "demo-warehouse"))
        if project is None:
            return
        site = dict(project.site or {})
        tasks = site.get("__tasks")
        if not isinstance(tasks, list):
            return
        kept = [
            task for task in tasks
            if not (isinstance(task, dict) and (task.get("process_code"), task.get("staff_fte_now"), task.get("staff_salary_year_rub")) in _SEEDED)
        ]
        if len(kept) != len(tasks):
            site["__tasks"] = kept
            project.site = site
            db.commit()


def downgrade() -> None:
    pass
