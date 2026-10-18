"""Профиль вендора и очередь его заявок. Каталог эта миграция не трогает."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Session

revision = "0019_vendor_requests"
down_revision = "0018_warehouse_roles_back"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vendor_profile",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("manufacturer", sa.Text(), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("about", sa.Text(), nullable=False, server_default=""),
        sa.Column("website", sa.Text(), nullable=False, server_default=""),
        sa.Column("email", sa.Text(), nullable=False, server_default=""),
        sa.Column("phone", sa.Text(), nullable=False, server_default=""),
        sa.Column("city", sa.Text(), nullable=False, server_default=""),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("documents", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.create_table(
        "vendor_request",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("admin_comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_vendor_request_user", "vendor_request", ["user_id", "created_at"])

    from app.application.reference_data import seed_users

    with Session(bind=op.get_bind()) as db:
        seed_users(db)
        db.commit()


def downgrade() -> None:
    op.drop_index("ix_vendor_request_user", table_name="vendor_request")
    op.drop_table("vendor_request")
    op.drop_table("vendor_profile")
