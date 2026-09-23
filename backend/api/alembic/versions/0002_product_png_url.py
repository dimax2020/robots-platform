"""Добавить ссылку на изображение продукта.

Revision ID: 0002
Revises: 0001
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("product", sa.Column("png_url", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("product", "png_url")
