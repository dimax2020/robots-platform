"""Необязательные дополнения/исправления и настройки требований, без допуска reviewed."""
from sqlalchemy import select
from app.domain.assessment import validate_metadata
from app.infrastructure.db.models import ProductRow, ProcessRow, ProductAssessmentRow, ProcessAssessmentRow


def metadata_maps(db):
    return ({str(r.product_id): r.data for r in db.scalars(select(ProductAssessmentRow))},
            {r.process_id: r.data for r in db.scalars(select(ProcessAssessmentRow))})


def read_policy(db, kind: str, key: str) -> dict:
    subject = db.scalar(select(ProductRow).where(ProductRow.slug == key)) if kind == 'product' else db.scalar(select(ProcessRow).where(ProcessRow.code == key))
    if subject is None:
        raise KeyError(key)
    cls = ProductAssessmentRow if kind == 'product' else ProcessAssessmentRow
    row = db.get(cls, subject.id)
    return row.data if row else {}


def save_policy(db, kind: str, key: str, data: dict) -> dict:
    data = validate_metadata(data, product=kind == 'product')
    subject = db.scalar(select(ProductRow).where(ProductRow.slug == key)) if kind == 'product' else db.scalar(select(ProcessRow).where(ProcessRow.code == key))
    if subject is None:
        raise KeyError(key)
    cls = ProductAssessmentRow if kind == 'product' else ProcessAssessmentRow
    row = db.get(cls, subject.id)
    if row is None:
        row = cls(**{'product_id' if kind == 'product' else 'process_id':subject.id}, data=data)
        db.add(row)
    else:
        row.data = data
    db.commit()
    return data
