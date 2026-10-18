"""Отметка, что принятая заявка уже записана в каталог."""

import sqlalchemy as sa
from alembic import op

revision = "0021_catalog_apply"
down_revision = "0020_request_hide"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Уже принятые строки в каталоге есть, поэтому для них флаг сразу true.
    op.add_column("vendor_request", sa.Column("catalog_applied", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.alter_column("vendor_request", "catalog_applied", server_default=sa.false())


def downgrade() -> None:
    op.drop_column("vendor_request", "catalog_applied")
