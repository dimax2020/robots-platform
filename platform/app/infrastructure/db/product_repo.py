import base64
import json
from uuid import UUID

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from app.infrastructure.db.models import ProductProcessRow, ProductRow, SourceRow


def list_products(db: Session, *, cursor: str | None, limit: int) -> dict:
    total = db.scalar(select(func.count()).select_from(ProductRow)) or 0
    stmt = select(ProductRow).order_by(ProductRow.name, ProductRow.id).limit(limit + 1)
    if cursor:
        name, product_id = _decode(cursor)
        stmt = stmt.where(tuple_(ProductRow.name, ProductRow.id) > tuple_(name, product_id))
    rows = list(db.scalars(stmt))
    page = rows[:limit]
    next_cursor = _encode(page[-1].name, page[-1].id) if len(rows) > limit and page else None
    return {"items": [_card(row) for row in page], "next_cursor": next_cursor, "total": total}


def get_product(db: Session, slug: str) -> dict | None:
    row = db.scalar(select(ProductRow).where(ProductRow.slug == slug))
    if row is None:
        return None
    from app.infrastructure.db.models import AttributeDefRow

    sources = {item.id: item for item in db.scalars(select(SourceRow))}
    labels = {item.key: item.label for item in db.scalars(select(AttributeDefRow))}
    attrs = []
    for key, raw in (row.attrs or {}).items():
        source = sources.get(raw.get("source_id"))
        attrs.append({
            "key": key,
            "label": labels.get(key) or key,
            "status": raw.get("status"),
            "value": raw.get("value"),
            "quote": raw.get("quote"),
            "source": None if source is None else {
                "kind": source.kind,
                "publisher": source.publisher,
                "url": source.url or None,
                "parser_code": source.parser_code or None,
            },
        })
    card = _card(row)
    card["summary"] = row.summary
    card["raw_catalog"] = row.raw_catalog
    card["attrs"] = attrs
    return card


def products_for_process(db: Session, process_id: int) -> list[ProductRow]:
    stmt = (
        select(ProductRow)
        .join(ProductProcessRow, ProductProcessRow.product_id == ProductRow.id)
        .where(ProductProcessRow.process_id == process_id)
        .order_by(ProductRow.name)
    )
    return list(db.scalars(stmt))


_HIGHLIGHTS = (
    ("payload_kg", "Грузоподъёмность", "кг"),
    ("speed_loaded_ms", "Скорость", "м/с"),
    ("min_aisle_width_m", "Проход", "м"),
    ("work_time_h", "Работа", "ч"),
)


def _card(row: ProductRow) -> dict:
    price = None if row.price_rub is None else float(row.price_rub)
    highlights = []
    attrs = row.attrs or {}
    for key, label, unit in _HIGHLIGHTS:
        raw = attrs.get(key) or {}
        if raw.get("status") == "known" and raw.get("value") not in (None, ""):
            highlights.append(f"{label} {raw.get('value')} {unit}")
    return {
        "id": str(row.id),
        "slug": row.slug,
        "name": row.name,
        "manufacturer": row.manufacturer,
        "availability": row.availability,
        "trl": row.trl,
        "price_rub": price,
        "image_url": row.image_url,
        "highlights": highlights,
    }


def _encode(name: str, product_id: UUID) -> str:
    raw = json.dumps({"name": name, "id": str(product_id)}, ensure_ascii=False).encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decode(cursor: str) -> tuple[str, UUID]:
    payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    return payload["name"], UUID(payload["id"])
