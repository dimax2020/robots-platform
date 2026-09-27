"""Типы решений, поля площадки по объектам, группы характеристик, источники нормативов и нормативы по типам."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

revision = "0007_admin_catalog"
down_revision = "0006_process_layout_items"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "solution_type",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("group_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("family", sa.Text(), nullable=False, server_default=""),
    )
    op.create_table(
        "solution_type_rule",
        sa.Column("raw_key", sa.Text(), primary_key=True),
        sa.Column("solution_type_id", sa.Integer(), sa.ForeignKey("solution_type.id", ondelete="CASCADE"), nullable=False),
    )
    op.add_column("product", sa.Column("solution_type_id", sa.Integer(), sa.ForeignKey("solution_type.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_product_solution_type", "product", ["solution_type_id"])

    op.create_table(
        "site_field",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False, server_default=""),
        sa.Column("kind", sa.Text(), nullable=False, server_default="number"),
        sa.Column("min_value", sa.Numeric(), nullable=True),
        sa.Column("max_value", sa.Numeric(), nullable=True),
        sa.Column("hint", sa.Text(), nullable=False, server_default=""),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "object_field",
        sa.Column("object_type_id", sa.Integer(), sa.ForeignKey("object_type.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("field_key", sa.Text(), sa.ForeignKey("site_field.key", ondelete="CASCADE"), primary_key=True),
        sa.Column("group_name", sa.Text(), nullable=False, server_default=""),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("default_value", JSONB(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False, server_default=""),
        sa.Column("sort", sa.Integer(), nullable=False, server_default="0"),
    )

    op.add_column("attribute_def", sa.Column("group_code", sa.Text(), nullable=False, server_default=""))
    op.add_column("attribute_def", sa.Column("datatype", sa.Text(), nullable=False, server_default="text"))
    op.add_column("attribute_def", sa.Column("sort", sa.Integer(), nullable=False, server_default="1000"))

    op.add_column("economy_norm", sa.Column("rationale", sa.Text(), nullable=True))
    op.add_column("economy_norm", sa.Column("origin", sa.Text(), nullable=True))
    op.add_column("economy_norm", sa.Column("url", sa.Text(), nullable=True))
    op.add_column("economy_norm_log", sa.Column("origin", sa.Text(), nullable=True))
    op.create_table(
        "economy_norm_override",
        sa.Column("norm_key", sa.Text(), primary_key=True),
        sa.Column("solution_type_id", sa.Integer(), sa.ForeignKey("solution_type.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("value", sa.Numeric(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False, server_default=""),
        sa.Column("origin", sa.Text(), nullable=False, server_default=""),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    from app.application.reference_data import seed_reference

    with Session(bind=op.get_bind()) as db:
        seed_reference(db)


def downgrade() -> None:
    op.drop_table("economy_norm_override")
    op.drop_column("economy_norm_log", "origin")
    op.drop_column("economy_norm", "url")
    op.drop_column("economy_norm", "origin")
    op.drop_column("economy_norm", "rationale")
    op.drop_column("attribute_def", "sort")
    op.drop_column("attribute_def", "datatype")
    op.drop_column("attribute_def", "group_code")
    op.drop_table("object_field")
    op.drop_table("site_field")
    op.drop_index("ix_product_solution_type", table_name="product")
    op.drop_column("product", "solution_type_id")
    op.drop_table("solution_type_rule")
    op.drop_table("solution_type")
