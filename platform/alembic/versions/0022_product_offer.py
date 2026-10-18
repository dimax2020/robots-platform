"""Счётчик показов карточки в подборе. Без персональных данных."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0022_product_offer"
down_revision = "0021_catalog_apply"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_offer",
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("offers", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["product_id"], ["product.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("product_id"),
    )


def downgrade() -> None:
    op.drop_table("product_offer")
