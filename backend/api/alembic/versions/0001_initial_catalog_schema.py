"""initial catalog schema

Revision ID: 0001
Revises: 
Create Date: 2026-09-21 22:23:08.309881
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Поиск по каталогу — pg_trgm по названию и производителю (§3.1, §9.6)
    op.execute("create extension if not exists pg_trgm")

    op.create_table('app_user',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('login', sa.Text(), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('role', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('login')
    )
    op.create_table('attribute_def',
    sa.Column('key', sa.Text(), nullable=False),
    sa.Column('group_code', sa.Text(), nullable=False),
    sa.Column('label', sa.Text(), nullable=False),
    sa.Column('unit', sa.Text(), nullable=True),
    sa.Column('datatype', sa.Text(), nullable=False),
    sa.Column('enum_values', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('required_for', postgresql.ARRAY(sa.Text()), nullable=True),
    sa.Column('sort', sa.SmallInteger(), nullable=True),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('catalog_version',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('published_by', sa.Text(), nullable=True),
    sa.Column('note', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('industry',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_table('object_type',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_table('process',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_table('refresh_run',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('stats', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('error', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('solution_type',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('family', sa.Text(), nullable=False),
    sa.Column('rule_spec', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('code')
    )
    op.create_table('industry_object',
    sa.Column('industry_id', sa.Integer(), nullable=False),
    sa.Column('object_type_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['industry_id'], ['industry.id'], ),
    sa.ForeignKeyConstraint(['object_type_id'], ['object_type.id'], ),
    sa.PrimaryKeyConstraint('industry_id', 'object_type_id')
    )
    op.create_table('object_process',
    sa.Column('object_type_id', sa.Integer(), nullable=False),
    sa.Column('process_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['object_type_id'], ['object_type.id'], ),
    sa.ForeignKeyConstraint(['process_id'], ['process.id'], ),
    sa.PrimaryKeyConstraint('object_type_id', 'process_id')
    )
    op.create_table('process_solution',
    sa.Column('process_id', sa.Integer(), nullable=False),
    sa.Column('solution_type_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['process_id'], ['process.id'], ),
    sa.ForeignKeyConstraint(['solution_type_id'], ['solution_type.id'], ),
    sa.PrimaryKeyConstraint('process_id', 'solution_type_id')
    )
    op.create_table('product',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('solution_type_id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('manufacturer', sa.Text(), nullable=False),
    sa.Column('legal_entity', sa.Text(), nullable=True),
    sa.Column('country', sa.Text(), nullable=True),
    sa.Column('availability', sa.Text(), nullable=False),
    sa.Column('trl', sa.SmallInteger(), nullable=True),
    sa.Column('market_potential', sa.SmallInteger(), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('attrs', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('valid_from', sa.BigInteger(), nullable=False),
    sa.Column('valid_to', sa.BigInteger(), nullable=True),
    sa.ForeignKeyConstraint(['solution_type_id'], ['solution_type.id'], ),
    sa.ForeignKeyConstraint(['valid_from'], ['catalog_version.id'], ),
    sa.ForeignKeyConstraint(['valid_to'], ['catalog_version.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    op.create_index('ix_product_attrs', 'product', ['attrs'], unique=False, postgresql_using='gin', postgresql_ops={'attrs': 'jsonb_path_ops'})
    op.create_index('ix_product_solution_type_current', 'product', ['solution_type_id'], unique=False, postgresql_where=sa.text('valid_to IS NULL'))
    op.create_table('project',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('owner_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('object_type_id', sa.Integer(), nullable=False),
    sa.Column('site', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('tasks', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('overrides', postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['object_type_id'], ['object_type.id'], ),
    sa.ForeignKeyConstraint(['owner_id'], ['app_user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('attr_proposal',
    sa.Column('id', sa.BigInteger(), nullable=False),
    sa.Column('product_id', sa.UUID(), nullable=True),
    sa.Column('key', sa.Text(), nullable=False),
    sa.Column('new_value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('origin', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), server_default=sa.text("'pending'"), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('reviewed_by', sa.Text(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('calc_run',
    sa.Column('id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
    sa.Column('project_id', sa.UUID(), nullable=False),
    sa.Column('catalog_version_id', sa.BigInteger(), nullable=False),
    sa.Column('engine_version', sa.Text(), nullable=False),
    sa.Column('request', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('response', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['catalog_version_id'], ['catalog_version.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('source',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('url', sa.Text(), nullable=True),
    sa.Column('publisher', sa.Text(), nullable=True),
    sa.Column('title', sa.Text(), nullable=True),
    sa.Column('captured_at', sa.Date(), nullable=False),
    sa.Column('rationale', sa.Text(), nullable=True),
    sa.Column('ref_product_id', sa.UUID(), nullable=True),
    sa.Column('content_hash', sa.Text(), nullable=True),
    sa.Column('last_checked_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("kind not in ('analogue', 'assumption') or rationale is not null", name='reasoned'),
    sa.ForeignKeyConstraint(['ref_product_id'], ['product.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('calc_norm',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('solution_type_id', sa.Integer(), nullable=True),
    sa.Column('key', sa.Text(), nullable=False),
    sa.Column('value', sa.Numeric(), nullable=False),
    sa.Column('unit', sa.Text(), nullable=True),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('editable', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.ForeignKeyConstraint(['solution_type_id'], ['solution_type.id'], ),
    sa.ForeignKeyConstraint(['source_id'], ['source.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('solution_type_id', 'key')
    )
    op.create_table('product_case',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.UUID(), nullable=False),
    sa.Column('object_type_id', sa.Integer(), nullable=True),
    sa.Column('process_id', sa.Integer(), nullable=True),
    sa.Column('customer', sa.Text(), nullable=True),
    sa.Column('summary', sa.Text(), nullable=True),
    sa.Column('source_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['object_type_id'], ['object_type.id'], ),
    sa.ForeignKeyConstraint(['process_id'], ['process.id'], ),
    sa.ForeignKeyConstraint(['product_id'], ['product.id'], ),
    sa.ForeignKeyConstraint(['source_id'], ['source.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Триграммный индекс по выражению — в модели не выражается, только сырым SQL (§6.2)
    op.execute(
        "create index ix_product_search on product "
        "using gin ((name || ' ' || manufacturer) gin_trgm_ops)"
    )


def downgrade() -> None:
    op.execute("drop index if exists ix_product_search")
    op.drop_table('product_case')
    op.drop_table('calc_norm')
    op.drop_table('source')
    op.drop_table('calc_run')
    op.drop_table('attr_proposal')
    op.drop_table('project')
    op.drop_index('ix_product_solution_type_current', table_name='product', postgresql_where=sa.text('valid_to IS NULL'))
    op.drop_index('ix_product_attrs', table_name='product', postgresql_using='gin', postgresql_ops={'attrs': 'jsonb_path_ops'})
    op.drop_table('product')
    op.drop_table('process_solution')
    op.drop_table('object_process')
    op.drop_table('industry_object')
    op.drop_table('solution_type')
    op.drop_table('refresh_run')
    op.drop_table('process')
    op.drop_table('object_type')
    op.drop_table('industry')
    op.drop_table('catalog_version')
    op.drop_table('attribute_def')
    op.drop_table('app_user')
