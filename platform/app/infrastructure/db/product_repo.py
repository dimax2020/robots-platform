import base64
import json
from uuid import UUID

from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session

from app.infrastructure.db.models import (
    ObjectProcessRow,
    ObjectTypeRow,
    ProcessRow,
    ProductProcessRow,
    ProductRow,
    SolutionTypeRow,
    SourceRow,
)


def list_products(
    db: Session,
    *,
    cursor: str | None,
    limit: int,
    solution_type: str | None = None,
    process: str | None = None,
    object_code: str | None = None,
) -> dict:
    types = _types(db)
    scope = []
    if solution_type:
        type_id = next((type_id for type_id, (code, _name) in types.items() if code == solution_type), -1)
        scope.append(ProductRow.solution_type_id == type_id)
    if process:
        scope.append(ProductRow.id.in_(
            select(ProductProcessRow.product_id).join(ProcessRow, ProcessRow.id == ProductProcessRow.process_id).where(ProcessRow.code == process)
        ))
    if object_code:
        scope.append(ProductRow.id.in_(
            select(ProductProcessRow.product_id)
            .join(ProcessRow, ProcessRow.id == ProductProcessRow.process_id)
            .join(ObjectProcessRow, ObjectProcessRow.process_id == ProcessRow.id)
            .join(ObjectTypeRow, ObjectTypeRow.id == ObjectProcessRow.object_type_id)
            .where(ObjectTypeRow.code == object_code)
        ))
    total = db.scalar(select(func.count()).select_from(ProductRow).where(*scope)) or 0
    stmt = select(ProductRow).where(*scope).order_by(ProductRow.name, ProductRow.id).limit(limit + 1)
    if cursor:
        name, product_id = _decode(cursor)
        stmt = stmt.where(tuple_(ProductRow.name, ProductRow.id) > tuple_(name, product_id))
    rows = list(db.scalars(stmt))
    page = rows[:limit]
    next_cursor = _encode(page[-1].name, page[-1].id) if len(rows) > limit and page else None
    return {"items": [_card(row, types) for row in page], "next_cursor": next_cursor, "total": total}


def public_solution_types(db: Session) -> list[dict]:
    rows = db.execute(
        select(SolutionTypeRow.code, SolutionTypeRow.name, SolutionTypeRow.group_name, func.count(ProductRow.id))
        .join(ProductRow, ProductRow.solution_type_id == SolutionTypeRow.id)
        .group_by(SolutionTypeRow.id)
        .order_by(func.count(ProductRow.id).desc(), SolutionTypeRow.name)
    ).all()
    return [{"code": code, "name": name, "group": group, "products": count} for code, name, group, count in rows]


def _types(db: Session) -> dict[int, tuple[str, str]]:
    return {row.id: (row.code, row.name) for row in db.scalars(select(SolutionTypeRow))}


def get_product(db: Session, slug: str) -> dict | None:
    row = db.scalar(select(ProductRow).where(ProductRow.slug == slug))
    if row is None:
        return None
    from app.infrastructure.db.models import AttributeDefRow

    sources = {item.id: item for item in db.scalars(select(SourceRow))}
    meta = {item.key: item for item in db.scalars(select(AttributeDefRow))}
    attrs = []
    for key, raw in (row.attrs or {}).items():
        source = sources.get(raw.get("source_id"))
        field = meta.get(key)
        attrs.append({
            "key": key,
            "label": field.label if field else key,
            "group": field.group_code if field else "",
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
    card = _card(row, _types(db))
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


def _card(row: ProductRow, types: dict[int, tuple[str, str]] | None = None) -> dict:
    price = None if row.price_rub is None else float(row.price_rub)
    solution = (types or {}).get(row.solution_type_id) if row.solution_type_id else None
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
        "solution_type": None if solution is None else {"code": solution[0], "name": solution[1]},
    }


def _encode(name: str, product_id: UUID) -> str:
    raw = json.dumps({"name": name, "id": str(product_id)}, ensure_ascii=False).encode()
    return base64.urlsafe_b64encode(raw).decode()


def _decode(cursor: str) -> tuple[str, UUID]:
    payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
    return payload["name"], UUID(payload["id"])
