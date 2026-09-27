"""Пользователи платформы и владелец проекта."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

revision = "0008_users"
down_revision = "0007_admin_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_user",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("login", sa.Text(), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
    )
    op.add_column(
        "project",
        sa.Column("owner_id", UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="SET NULL"), nullable=True),
    )

    from app.application.reference_data import seed_users

    with Session(bind=op.get_bind()) as db:
        seed_users(db)
        db.commit()


def downgrade() -> None:
    op.drop_column("project", "owner_id")
    op.drop_table("app_user")
