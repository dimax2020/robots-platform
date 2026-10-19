"""Проверенные факты и профили допуска; исходные карточки и назначения сохраняются."""
import json
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from alembic import op

revision = '0024_assessment_profiles'
down_revision = '0023_process_description'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('product_assessment',
                    sa.Column('product_id', UUID(as_uuid=True), sa.ForeignKey('product.id', ondelete='CASCADE'), primary_key=True),
                    sa.Column('data', JSONB, nullable=False))
    op.create_table('process_assessment',
                    sa.Column('process_id', sa.Integer(), sa.ForeignKey('process.id', ondelete='CASCADE'), primary_key=True),
                    sa.Column('data', JSONB, nullable=False))
    # Фиксированные данные именно этой миграции. Никаких runtime-зависимостей от reports/.
    payload = json.loads(Path(__file__).with_name('0024_assessment_seed.json').read_text())
    conn = op.get_bind()
    for item in payload['products']:
        conn.execute(sa.text('INSERT INTO product_assessment (product_id, data) SELECT id, CAST(:data AS jsonb) FROM product WHERE id=CAST(:id AS uuid)'),
                     {'id': item['id'], 'data': json.dumps(item['data'], ensure_ascii=False)})
    for item in payload['processes']:
        conn.execute(sa.text('INSERT INTO process_assessment (process_id, data) SELECT id, CAST(:data AS jsonb) FROM process WHERE code=:code'),
                     {'code': item['code'], 'data': json.dumps(item['data'], ensure_ascii=False)})


def downgrade():
    op.drop_table('process_assessment')
    op.drop_table('product_assessment')
