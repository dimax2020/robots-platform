"""Начальные задачи и объекты из рассмотренного справочника, без дублирующих процессов."""

from sqlalchemy.orm import Session

from app.application.assign_processes import seed_taxonomy
from app.infrastructure.db.models import ParserSettingRow
from app.parsers import PARSERS


def seed(db: Session) -> None:
    seed_taxonomy(db)
    for code in PARSERS:
        if db.get(ParserSettingRow, code) is None:
            db.add(ParserSettingRow(code=code, enabled=True, hour=3))
    db.commit()
