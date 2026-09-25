"""Запись карточек. Один источник не затирает чужое заполненное поле."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.csv_parse import slugify
from app.domain.match import OverlayRow, ParsedRecord
from app.domain.specs import expand_known_specs
from app.infrastructure.db.models import AttributeDefRow, ProductOriginRow, ProductRow, SourceRow


@dataclass
class IngestCounters:
    created: int = 0
    updated: int = 0
    skipped: int = 0


def ingest_records(db: Session, records: list[ParsedRecord]) -> IngestCounters:
    counters = IngestCounters()
    taken = set(db.scalars(select(ProductRow.slug)).all())
    by_name = _names(db)
    for record in records:
        attributes, labels = expand_known_specs(record.attributes, record.attribute_labels)
        record = ParsedRecord(**{**record.__dict__, "attributes": attributes, "attribute_labels": labels})
        origin = db.get(ProductOriginRow, (record.platform, record.external_id))
        source_id = _source_id(db, record.source_kind, record.source_publisher, record.source_url, record.parser_code)
        _ensure_attrs(db, record.attributes, record.attribute_labels)
        if origin is None:
            existing = by_name.get(_name_key(record.name))
            if existing is not None and len(existing) == 1:
                product = existing[0]
                _fill_product(product, record, source_id)
                db.add(ProductOriginRow(platform=record.platform, external_id=record.external_id, product_id=product.id))
                counters.updated += 1
                continue
            product_id = _new_id(record)
            product = ProductRow(
                id=product_id,
                slug=slugify(record.name, taken),
                name=record.name,
                manufacturer=record.manufacturer,
                availability=record.availability,
                trl=record.trl,
                price_rub=record.price_rub,
                image_url=record.image_url,
                summary=record.summary,
                raw_catalog=record.raw,
                attrs=_pack_attrs(record.attributes, source_id),
                column_sources=_column_sources(record, source_id),
            )
            db.add(product)
            db.flush()
            db.add(ProductOriginRow(platform=record.platform, external_id=record.external_id, product_id=product_id))
            by_name.setdefault(_name_key(product.name), []).append(product)
            counters.created += 1
            continue
        product = db.get(ProductRow, origin.product_id)
        if product is None:
            counters.skipped += 1
            continue
        _fill_product(product, record, source_id)
        counters.updated += 1
    db.commit()
    return counters


def overlay_rows(db: Session, rows: list[OverlayRow]) -> IngestCounters:
    counters = IngestCounters()
    for row in rows:
        product = db.scalar(select(ProductRow).where(ProductRow.slug == row.product_slug))
        if product is None:
            counters.skipped += 1
            continue
        source_id = _source_id(db, row.source_kind, _publisher(row.source_url), row.source_url, None)
        _ensure_attrs(db, {row.attr_key: row.value}, {row.attr_key: row.label})
        attrs = dict(product.attrs or {})
        current = attrs.get(row.attr_key)
        if current and current.get("status") == "known" and current.get("value") not in (None, ""):
            counters.skipped += 1
            continue
        if row.status != "known" or row.value == "":
            attrs[row.attr_key] = {"status": row.status or "unknown", "value": None, "source_id": source_id, "quote": row.quote}
        else:
            attrs[row.attr_key] = {"status": "known", "value": row.value, "source_id": source_id, "quote": row.quote}
        product.attrs = attrs
        product.updated_at = datetime.now(timezone.utc)
        counters.updated += 1
    db.commit()
    return counters


def _name_key(name: str) -> str:
    cleaned = re.sub(r"\([^)]*\)", " ", name)
    return slugify(cleaned, set()).replace("-", "")


def _names(db: Session) -> dict[str, list[ProductRow]]:
    grouped: dict[str, list[ProductRow]] = {}
    for row in db.scalars(select(ProductRow)):
        grouped.setdefault(_name_key(row.name), []).append(row)
    return grouped


def canonicalize_stored(db: Session) -> int:
    """Дописать канонические поля в уже сохранённые характеристики парсеров."""
    labels = {row.key: row.label for row in db.scalars(select(AttributeDefRow))}
    changed = 0
    for product in db.scalars(select(ProductRow)):
        raw = {
            key: str(item.get("value"))
            for key, item in (product.attrs or {}).items()
            if item.get("status") == "known" and item.get("value") not in (None, "")
        }
        expanded, new_labels = expand_known_specs(raw, labels)
        attrs = dict(product.attrs or {})
        added = False
        for key, value in expanded.items():
            if key in attrs:
                continue
            source_id = next((item.get("source_id") for item in attrs.values() if item.get("source_id")), None)
            attrs[key] = {"status": "known", "value": value, "source_id": source_id, "quote": None}
            added = True
        if not added:
            continue
        _ensure_attrs(db, {key: expanded[key] for key in expanded if key not in labels}, new_labels)
        product.attrs = attrs
        product.updated_at = datetime.now(timezone.utc)
        changed += 1
    db.commit()
    return changed


def _new_id(record: ParsedRecord) -> UUID:
    if record.platform == "fc_bas":
        return UUID(record.external_id)
    return uuid4()


def _publisher(url: str | None) -> str:
    if not url:
        return "Команда проекта"
    host = url.split("/")[2] if "://" in url else url
    return host[4:] if host.startswith("www.") else host


def _source_id(db: Session, kind: str, publisher: str, url: str | None, parser_code: str | None) -> int:
    url = url or ""
    parser_code = parser_code or ""
    stmt = select(SourceRow).where(
        SourceRow.kind == kind,
        SourceRow.publisher == publisher,
        SourceRow.url == url,
        SourceRow.parser_code == parser_code,
    )
    row = db.scalar(stmt)
    if row is None:
        row = SourceRow(kind=kind, publisher=publisher, url=url, parser_code=parser_code, title=publisher)
        db.add(row)
        db.flush()
    return row.id


def _ensure_attrs(db: Session, attributes: dict[str, str], labels: dict[str, str]) -> None:
    for key in attributes:
        if db.get(AttributeDefRow, key) is None:
            db.add(AttributeDefRow(key=key, label=labels.get(key) or key, usage="pending"))
    db.flush()


def _pack_attrs(attributes: dict[str, str], source_id: int) -> dict:
    return {
        key: {"status": "known", "value": value, "source_id": source_id, "quote": None}
        for key, value in attributes.items()
        if value != ""
    }


def _column_sources(record: ParsedRecord, source_id: int) -> dict:
    sources = {}
    for field, value in (
        ("name", record.name),
        ("manufacturer", record.manufacturer),
        ("availability", record.availability),
        ("trl", record.trl),
        ("price_rub", record.price_rub),
        ("image_url", record.image_url),
        ("summary", record.summary),
    ):
        if value is not None and value != "":
            sources[field] = source_id
    return sources


def _owned(product: ProductRow, field: str, source_id: int) -> bool:
    current = (product.column_sources or {}).get(field)
    return current is None or current == source_id


def _fill_product(product: ProductRow, record: ParsedRecord, source_id: int) -> None:
    sources = dict(product.column_sources or {})
    if record.raw:
        product.raw_catalog = record.raw
    pairs = {
        "name": record.name,
        "manufacturer": record.manufacturer,
        "availability": record.availability,
        "trl": record.trl,
        "price_rub": record.price_rub,
        "image_url": record.image_url,
        "summary": record.summary,
    }
    for field, value in pairs.items():
        if value is None or value == "":
            continue
        existing = getattr(product, field)
        if existing not in (None, "") and not _owned(product, field, source_id):
            continue
        setattr(product, field, value)
        sources[field] = source_id
    product.column_sources = sources
    attrs = dict(product.attrs or {})
    for key, value in record.attributes.items():
        current = attrs.get(key)
        if current and current.get("status") == "known" and current.get("value") not in (None, "") and current.get("source_id") != source_id:
            continue
        attrs[key] = {"status": "known", "value": value, "source_id": source_id, "quote": None}
    product.attrs = attrs
    product.updated_at = datetime.now(timezone.utc)
