"""Демо-объекты как обычные проекты: флаг демо, публикация и постоянный адрес."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

revision = "0011_demo_projects"
down_revision = "0010_attribute_upper_bounds"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("project", sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("project", sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("project", sa.Column("slug", sa.Text(), nullable=True))
    op.create_unique_constraint("uq_project_slug", "project", ["slug"])

    from app.application.reference_data import seed_demo_projects

    with Session(bind=op.get_bind()) as db:
        seed_demo_projects(db)
        db.commit()


def downgrade() -> None:
    op.drop_constraint("uq_project_slug", "project", type_="unique")
    op.drop_column("project", "slug")
    op.drop_column("project", "published")
    op.drop_column("project", "is_demo")
