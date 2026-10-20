"""Кабинет интегратора: профиль, запросы заказчиков и переписка."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0026_integrator"
down_revision = "0025_match_journal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integrator_profile",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=False),
        sa.Column("brand", sa.Text(), nullable=False, server_default=""),
        sa.Column("about", sa.Text(), nullable=False, server_default=""),
        sa.Column("website", sa.Text(), nullable=False, server_default=""),
        sa.Column("email", sa.Text(), nullable=False, server_default=""),
        sa.Column("phone", sa.Text(), nullable=False, server_default=""),
        sa.Column("city", sa.Text(), nullable=False, server_default=""),
        sa.Column("address", sa.Text(), nullable=False, server_default=""),
        sa.Column("inn", sa.Text(), nullable=False, server_default=""),
        sa.Column("ogrn", sa.Text(), nullable=False, server_default=""),
        sa.Column("regions", sa.Text(), nullable=False, server_default=""),
        sa.Column("contact_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("experience_years", sa.Integer(), nullable=True),
        sa.Column("specializations", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("documents", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("nda_accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_table(
        "integration_request",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("integrator_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="sent"),
        sa.Column("user_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("feedback", sa.Text(), nullable=False, server_default=""),
        sa.Column("decline_comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["integrator_user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "integrator_user_id", name="uq_integration_request_pair"),
    )
    op.create_index("ix_integration_request_integrator", "integration_request", ["integrator_user_id"])
    op.create_index("ix_integration_request_owner", "integration_request", ["owner_user_id"])
    op.create_table(
        "integration_message",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("files", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["request_id"], ["integration_request.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_integration_message_request", "integration_message", ["request_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_integration_message_request", table_name="integration_message")
    op.drop_table("integration_message")
    op.drop_index("ix_integration_request_owner", table_name="integration_request")
    op.drop_index("ix_integration_request_integrator", table_name="integration_request")
    op.drop_table("integration_request")
    op.drop_table("integrator_profile")
