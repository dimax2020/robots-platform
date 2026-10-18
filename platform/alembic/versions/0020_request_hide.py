"""Скрытие заявки из списка владельца и из списка администратора."""

import sqlalchemy as sa
from alembic import op

revision = "0020_request_hide"
down_revision = "0019_vendor_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vendor_request", sa.Column("owner_hidden", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("vendor_request", sa.Column("admin_hidden", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("vendor_request", "admin_hidden")
    op.drop_column("vendor_request", "owner_hidden")
