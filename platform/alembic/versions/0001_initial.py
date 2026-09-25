"""Схема каталога, таксономии и очереди прогонов."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("publisher", sa.Text(), nullable=False),
        sa.Column("url", sa.Text()),
        sa.Column("parser_code", sa.Text()),
        sa.Column("title", sa.Text()),
    )
    op.create_index("ix_source_identity", "source", ["kind", "publisher", "url", "parser_code"], unique=True)

    op.create_table(
        "attribute_def",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("unit", sa.Text()),
        sa.Column("usage", sa.Text(), nullable=False, server_default="pending"),
    )

    op.create_table(
        "product",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("manufacturer", sa.Text()),
        sa.Column("availability", sa.Text()),
        sa.Column("trl", sa.Integer()),
        sa.Column("price_rub", sa.Numeric()),
        sa.Column("image_url", sa.Text()),
        sa.Column("summary", sa.Text()),
        sa.Column("raw_catalog", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("attrs", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("column_sources", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_product_name_id", "product", ["name", "id"])

    op.create_table(
        "product_origin",
        sa.Column("platform", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product.id"), nullable=False),
        sa.PrimaryKeyConstraint("platform", "external_id"),
    )
    op.create_index("ix_product_origin_product", "product_origin", ["product_id"])

    op.create_table(
        "industry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
    )
    op.create_table(
        "object_type",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
    )
    op.create_table(
        "process",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
    )
    op.create_table(
        "object_industry",
        sa.Column("object_type_id", sa.Integer(), sa.ForeignKey("object_type.id"), nullable=False),
        sa.Column("industry_id", sa.Integer(), sa.ForeignKey("industry.id"), nullable=False),
        sa.PrimaryKeyConstraint("object_type_id", "industry_id"),
    )
    op.create_table(
        "object_process",
        sa.Column("object_type_id", sa.Integer(), sa.ForeignKey("object_type.id"), nullable=False),
        sa.Column("process_id", sa.Integer(), sa.ForeignKey("process.id"), nullable=False),
        sa.PrimaryKeyConstraint("object_type_id", "process_id"),
    )
    op.create_table(
        "product_process",
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product.id"), nullable=False),
        sa.Column("process_id", sa.Integer(), sa.ForeignKey("process.id"), nullable=False),
        sa.PrimaryKeyConstraint("product_id", "process_id"),
    )
    op.create_index("ix_product_process_process", "product_process", ["process_id", "product_id"])

    op.create_table(
        "process_filter",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("process_id", sa.Integer(), sa.ForeignKey("process.id"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("object_keys", postgresql.JSONB(), nullable=False),
        sa.Column("robot_keys", postgresql.JSONB(), nullable=False),
        sa.Column("op", sa.Text(), nullable=False),
        sa.Column("mode", sa.Text(), nullable=False),
    )

    op.create_table(
        "project",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("object_type_id", sa.Integer(), sa.ForeignKey("object_type.id"), nullable=False),
        sa.Column("site", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_table(
        "project_process",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project.id"), nullable=False),
        sa.Column("process_id", sa.Integer(), sa.ForeignKey("process.id"), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("project_id", "process_id"),
    )

    op.create_table(
        "parser_setting",
        sa.Column("code", sa.Text(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("hour", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_enqueued_on", sa.Date()),
    )

    op.create_table(
        "job",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("parser_code", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text()),
        sa.Column("error", sa.Text()),
        sa.Column("counters", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "uq_job_live",
        "job",
        ["kind", "parser_code"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending', 'running')"),
    )


def downgrade() -> None:
    op.drop_table("job")
    op.drop_table("parser_setting")
    op.drop_table("project_process")
    op.drop_table("project")
    op.drop_table("process_filter")
    op.drop_table("product_process")
    op.drop_table("object_process")
    op.drop_table("object_industry")
    op.drop_table("process")
    op.drop_table("object_type")
    op.drop_table("industry")
    op.drop_table("product_origin")
    op.drop_table("product")
    op.drop_table("attribute_def")
    op.drop_table("source")
