"""Единые характеристики, единицы и подписи; исходные значения сохраняются."""
import logging
from alembic import op
from sqlalchemy.orm import Session

revision = '0009_normalize_attributes'
down_revision = '0008_users'
branch_labels = None
depends_on = None


def upgrade() -> None:
    from app.infrastructure.db.ingest import normalize_stored
    with Session(bind=op.get_bind()) as db:
        report = normalize_stored(db)
        logging.getLogger('alembic.runtime.migration').info(
            'Нормализация: %s карточек изменено, %s замечаний; подробный аудит: python -m app.normalize_catalog --report report.json',
            report['changed'], len(report['issues']))
        db.commit()


def downgrade() -> None:
    # Миграция данных не удаляет исходные поля. Автоматически отменять последующие
    # ручные изменения нельзя; для полного отката используется резервная копия.
    pass
