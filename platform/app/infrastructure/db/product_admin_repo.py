"""Продукты в админке: список с фильтрами, покрытие данных по процессу, ручная правка карточки."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.domain.csv_parse import slugify
from app.domain.formula import identifiers
from app.domain.specs import CANON_LABELS
from app.infrastructure.db.models import (
    AttributeDefRow,
    ProcessFilterRow,
    ProcessRow,
    ProductProcessRow,
    ProductRow,
    SolutionTypeRow,
    SourceRow,
)

ECONOMY_KEYS = (("price_rub", "Цена"), ("power_watt", "Мощность"), ("raas_available", "Аренда (RaaS)"))
COLUMNS = ("name", "manufacturer", "availability", "trl", "price_rub", "image_url", "summary")
MANUAL_PARSER = "manual"


def _known(attrs: dict, key: str) -> bool:
    item = attrs.get(key) or {}
    return item.get("status") == "known" and item.get("value") not in (None, "")


def _filled(product: ProductRow, key: str) -> bool:
    if key == "price_rub":
        return product.price_rub is not None
    return _known(product.attrs or {}, key)


def _labels(db: Session) -> dict[str, str]:
    labels = {}
    for row in db.scalars(select(AttributeDefRow)):
        labels[row.key] = row.label if row.label and row.label != row.key else CANON_LABELS.get(row.key, row.key)
    return labels


def _tz_keys(db: Session) -> list[str]:
    return list(db.scalars(select(AttributeDefRow.key).where(AttributeDefRow.group_code.not_in(["", "identification", "data_quality"]))))


def _processes_by_product(db: Session) -> dict:
    result: dict = {}
    rows = db.execute(select(ProductProcessRow.product_id, ProcessRow.code, ProcessRow.name).join(ProcessRow, ProcessRow.id == ProductProcessRow.process_id))
    for product_id, code, name in rows:
        result.setdefault(product_id, []).append({"code": code, "name": name})
    return result


def admin_products(db: Session, *, q: str = "", process: str = "", solution_type: str = "", limit: int = 0) -> list[dict]:
    types = {row.id: {"code": row.code, "name": row.name} for row in db.scalars(select(SolutionTypeRow))}
    by_product = _processes_by_product(db)
    tz_keys = _tz_keys(db)
    stmt = select(ProductRow).order_by(ProductRow.name)
    if solution_type == "-":
        stmt = stmt.where(ProductRow.solution_type_id.is_(None))
    elif solution_type:
        stmt = stmt.join(SolutionTypeRow, SolutionTypeRow.id == ProductRow.solution_type_id).where(SolutionTypeRow.code == solution_type)
    if process == "-":
        stmt = stmt.where(~ProductRow.id.in_(select(ProductProcessRow.product_id)))
    elif process:
        stmt = stmt.join(ProductProcessRow, ProductProcessRow.product_id == ProductRow.id).join(ProcessRow, ProcessRow.id == ProductProcessRow.process_id).where(ProcessRow.code == process)
    text = q.strip().lower()
    result = []
    for row in db.scalars(stmt):
        if text and text not in f"{row.name} {row.manufacturer or ''} {row.slug}".lower():
            continue
        filled = sum(1 for key in tz_keys if _known(row.attrs or {}, key))
        result.append({
            "id": str(row.id),
            "slug": row.slug,
            "name": row.name,
            "manufacturer": row.manufacturer,
            "availability": row.availability,
            "trl": row.trl,
            "price_rub": None if row.price_rub is None else float(row.price_rub),
            "image_url": row.image_url,
            "solution_type": types.get(row.solution_type_id),
            "processes": by_product.get(row.id, []),
            "completeness": round(filled / len(tz_keys), 3) if tz_keys else 0,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        })
        if limit and len(result) >= limit:
            break
    return result


def required_keys(db: Session, process: ProcessRow) -> list[dict]:
    """Что нужно роботу процесса для расчёта: характеристики из условий, формулы количества, ранжирования и экономики."""
    labels = _labels(db)
    wanted: dict[str, str] = {}
    for item in db.scalars(select(ProcessFilterRow).where(ProcessFilterRow.process_id == process.id)):
        inputs = {row.get("key") for row in (item.inputs or []) if isinstance(row, dict)}
        for name in identifiers(item.formula or ""):
            bare = name.split(".", 1)[1] if name.startswith("robot.") else name
            if bare not in inputs and bare not in wanted:
                wanted[bare] = "условие"
        for key in item.robot_keys or []:
            wanted.setdefault(key, "условие")
    count_inputs = {row.get("key") for row in (process.count_inputs or []) if isinstance(row, dict)}
    for name in identifiers(process.count_formula or ""):
        if name.startswith("robot."):
            wanted.setdefault(name.split(".", 1)[1], "количество")
        elif name not in count_inputs:
            wanted.setdefault(name, "количество")
    if process.rank_key:
        wanted.setdefault(process.rank_key, "лучший")
    for key, _label in ECONOMY_KEYS:
        wanted.setdefault(key, "экономика")
    names = dict(ECONOMY_KEYS)
    return [{"key": key, "label": names.get(key) or labels.get(key) or CANON_LABELS.get(key, key), "used_in": used} for key, used in wanted.items()]


def coverage(db: Session, process_code: str) -> dict:
    process = db.scalar(select(ProcessRow).where(ProcessRow.code == process_code))
    if process is None:
        raise KeyError(process_code)
    keys = required_keys(db, process)
    types = {row.id: row.name for row in db.scalars(select(SolutionTypeRow))}
    tz_keys = _tz_keys(db)
    rows = list(db.scalars(
        select(ProductRow).join(ProductProcessRow, ProductProcessRow.product_id == ProductRow.id)
        .where(ProductProcessRow.process_id == process.id).order_by(ProductRow.name)
    ))
    missing_count: dict[str, int] = {item["key"]: 0 for item in keys}
    robots = []
    for row in rows:
        missing = [item["key"] for item in keys if not _filled(row, item["key"])]
        for key in missing:
            missing_count[key] += 1
        robots.append({
            "slug": row.slug,
            "name": row.name,
            "manufacturer": row.manufacturer,
            "image_url": row.image_url,
            "solution_type": types.get(row.solution_type_id),
            "ready": round((len(keys) - len(missing)) / len(keys), 3) if keys else 1,
            "completeness": round(sum(1 for key in tz_keys if _known(row.attrs or {}, key)) / len(tz_keys), 3) if tz_keys else 0,
            "missing": missing,
        })
    robots.sort(key=lambda item: (item["ready"], item["name"]))
    return {
        "code": process.code,
        "name": process.name,
        "keys": [{**item, "missing": missing_count[item["key"]]} for item in keys],
        "robots": robots,
        "total": len(robots),
        "ready": sum(1 for item in robots if not item["missing"]),
    }


def set_process_products(db: Session, process_code: str, *, add: list[str], remove: list[str]) -> int:
    process = db.scalar(select(ProcessRow).where(ProcessRow.code == process_code))
    if process is None:
        raise KeyError(process_code)
    changed = 0
    for product in db.scalars(select(ProductRow).where(ProductRow.slug.in_(add or ["-"]))):
        if db.get(ProductProcessRow, (product.id, process.id)) is None:
            db.add(ProductProcessRow(product_id=product.id, process_id=process.id))
            changed += 1
    ids = list(db.scalars(select(ProductRow.id).where(ProductRow.slug.in_(remove or ["-"]))))
    if ids:
        changed += db.execute(delete(ProductProcessRow).where(ProductProcessRow.process_id == process.id, ProductProcessRow.product_id.in_(ids))).rowcount or 0
    db.commit()
    return changed


def _source_view(source: SourceRow | None) -> dict | None:
    if source is None:
        return None
    return {"id": source.id, "kind": source.kind, "publisher": source.publisher, "url": source.url or None, "title": source.title, "parser_code": source.parser_code or None}


def product_detail(db: Session, slug: str) -> dict:
    row = db.scalar(select(ProductRow).where(ProductRow.slug == slug))
    if row is None:
        raise KeyError(slug)
    sources = {item.id: item for item in db.scalars(select(SourceRow))}
    defs = {item.key: item for item in db.scalars(select(AttributeDefRow))}
    labels = _labels(db)
    attrs = []
    for key, raw in (row.attrs or {}).items():
        if raw.get("alias_of"):
            continue
        meta = defs.get(key)
        attrs.append({
            "key": key,
            "label": labels.get(key, key),
            "unit": meta.unit if meta else None,
            "group": meta.group_code if meta else "",
            "datatype": meta.datatype if meta else "text",
            "sort": meta.sort if meta else 1000,
            "status": raw.get("status") or "unknown",
            "value": raw.get("value"),
            "quote": raw.get("quote"),
            "approximate": bool(raw.get("approximate")),
            "condition": raw.get("condition"),
            "fetched_at": raw.get("fetched_at"),
            "confirmed": bool(raw.get("confirmed")),
            "source": _source_view(sources.get(raw.get("source_id"))),
        })
    attrs.sort(key=lambda item: (item["sort"], item["label"]))
    columns = {field: _source_view(sources.get(source_id)) for field, source_id in (row.column_sources or {}).items()}
    raw_rows = (row.raw_catalog or {}).get("rows") or []
    head = raw_rows[0] if raw_rows and isinstance(raw_rows[0], dict) else {}
    used_sources = {raw.get("source_id") for raw in (row.attrs or {}).values()} | set((row.column_sources or {}).values())
    tz_keys = _tz_keys(db)
    return {
        "id": str(row.id),
        "slug": row.slug,
        "name": row.name,
        "manufacturer": row.manufacturer,
        "availability": row.availability,
        "trl": row.trl,
        "price_rub": None if row.price_rub is None else float(row.price_rub),
        "image_url": row.image_url,
        "summary": row.summary,
        "solution_type": db.scalar(select(SolutionTypeRow.code).where(SolutionTypeRow.id == row.solution_type_id)) if row.solution_type_id else None,
        "processes": [item["code"] for item in _processes_by_product(db).get(row.id, [])],
        "legal_entity": head.get("компания") or row.manufacturer,
        "region": (row.attrs or {}).get("region", {}).get("value"),
        "market_potential": (row.attrs or {}).get("market_potential", {}).get("value"),
        "columns": columns,
        "attrs": attrs,
        "quality": {
            "completeness": round(sum(1 for key in tz_keys if _known(row.attrs or {}, key)) / len(tz_keys), 3) if tz_keys else 0,
            "filled": sum(1 for key in tz_keys if _known(row.attrs or {}, key)),
            "total": len(tz_keys),
            "sources": len({item for item in used_sources if item}),
        },
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _manual_source(db: Session, source: dict) -> int:
    kind = source.get("kind") or "vendor"
    publisher = (source.get("publisher") or "").strip() or "Администратор"
    url = (source.get("url") or "").strip()
    title = (source.get("title") or "").strip() or None
    rationale = (source.get("rationale") or "").strip()
    if kind in {"analogue", "assumption"} and not rationale:
        raise ValueError("Для оценки по аналогу и допущения нужно обоснование")
    if rationale:
        title = f"{title} — {rationale}" if title else rationale
    row = db.scalar(select(SourceRow).where(
        SourceRow.kind == kind, SourceRow.publisher == publisher, SourceRow.url == url,
        SourceRow.parser_code == MANUAL_PARSER, SourceRow.title == title,
    ))
    if row is None:
        row = SourceRow(kind=kind, publisher=publisher, url=url, parser_code=MANUAL_PARSER, title=title)
        db.add(row)
        db.flush()
    return row.id


def patch_product(db: Session, slug: str, payload: dict) -> dict:
    """Ручная правка. Поле получает ручной источник, поэтому следующий импорт его не затрёт (ingest._owned)."""
    row = db.scalar(select(ProductRow).where(ProductRow.slug == slug))
    if row is None:
        raise KeyError(slug)
    columns = payload.get("columns") or {}
    attrs_in = payload.get("attrs") or {}
    touched = bool(columns) or bool(attrs_in)
    source_id = _manual_source(db, payload.get("source") or {}) if touched else None
    today = datetime.now(timezone.utc).date().isoformat()
    sources = dict(row.column_sources or {})
    for field, value in columns.items():
        if field not in COLUMNS:
            continue
        if field == "trl" and value not in (None, ""):
            value = int(value)
        if field == "price_rub" and value not in (None, ""):
            value = float(value)
        if field == "name" and not str(value or "").strip():
            raise ValueError("Название не может быть пустым")
        setattr(row, field, value if value != "" else None)
        sources[field] = source_id
    row.column_sources = sources
    attrs = dict(row.attrs or {})
    for key, item in attrs_in.items():
        if item is None:
            attrs.pop(key, None)
            attrs = {k: v for k, v in attrs.items() if v.get("alias_of") != key}
            continue
        status = item.get("status") or "known"
        value = item.get("value")
        if status != "known":
            value = None
        attrs[key] = {
            "status": status,
            "value": value,
            "source_id": source_id,
            "quote": (item.get("quote") or None),
            "fetched_at": today,
            "confirmed": bool(item.get("confirmed")),
            **({"unit": item["unit"]} if item.get("unit") else {}),
        }
        from app.infrastructure.db.ingest import _ensure_attrs
        _ensure_attrs(db, {key: value}, {key: item.get("label") or key})
        definition = db.get(AttributeDefRow, key)
        if item.get("unit") and not definition.unit:
            definition.unit = item["unit"]
    for key, flag in (payload.get("confirm") or {}).items():
        if key in attrs:
            attrs[key] = {**attrs[key], "confirmed": bool(flag)}
    from app.infrastructure.db.ingest import _normalized
    row.attrs = _normalized(db, attrs, {key: item.get("label", key) for key, item in attrs_in.items() if item})
    if "solution_type" in payload:
        code = payload.get("solution_type")
        row.solution_type_id = db.scalar(select(SolutionTypeRow.id).where(SolutionTypeRow.code == code)) if code else None
    if payload.get("processes") is not None:
        db.execute(delete(ProductProcessRow).where(ProductProcessRow.product_id == row.id))
        for code in dict.fromkeys(payload["processes"]):
            process_id = db.scalar(select(ProcessRow.id).where(ProcessRow.code == code))
            if process_id is not None:
                db.add(ProductProcessRow(product_id=row.id, process_id=process_id))
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return product_detail(db, row.slug)


def create_product(db: Session, *, name: str, manufacturer: str | None, solution_type: str | None, source: dict) -> str:
    name = name.strip()
    if not name:
        raise ValueError("Нужно название продукта")
    taken = set(db.scalars(select(ProductRow.slug)))
    source_id = _manual_source(db, source)
    row = ProductRow(
        id=uuid4(),
        slug=slugify(name, taken),
        name=name,
        manufacturer=(manufacturer or "").strip() or None,
        attrs={},
        raw_catalog={},
        column_sources={"name": source_id, **({"manufacturer": source_id} if manufacturer else {})},
        solution_type_id=db.scalar(select(SolutionTypeRow.id).where(SolutionTypeRow.code == solution_type)) if solution_type else None,
    )
    db.add(row)
    db.commit()
    return row.slug


def set_image(db: Session, slug: str, url: str) -> None:
    row = db.scalar(select(ProductRow).where(ProductRow.slug == slug))
    if row is None:
        raise KeyError(slug)
    row.image_url = url
    sources = dict(row.column_sources or {})
    sources["image_url"] = _manual_source(db, {"kind": "vendor", "publisher": "Администратор", "title": "Фото загружено вручную"})
    row.column_sources = sources
    row.updated_at = datetime.now(timezone.utc)
    db.commit()


def attribute_dictionary(db: Session) -> list[dict]:
    counts = dict(db.execute(text(
        "select key, count(*)::int from product, lateral jsonb_object_keys(attrs) as key group by key"
    )).all())
    labels = _labels(db)
    return [
        {
            "key": row.key,
            "label": labels.get(row.key, row.key),
            "unit": row.unit,
            "usage": row.usage,
            "group": row.group_code,
            "datatype": row.datatype,
            "sort": row.sort,
            "products": int(counts.get(row.key, 0)),
        }
        for row in db.scalars(select(AttributeDefRow).order_by(AttributeDefRow.sort, AttributeDefRow.key))
    ]


def save_attribute(db: Session, key: str, payload: dict) -> dict:
    row = db.get(AttributeDefRow, key)
    if row is None:
        raise KeyError(key)
    if payload.get("label") is not None:
        row.label = payload["label"].strip() or row.key
    if payload.get("unit") is not None:
        row.unit = payload["unit"].strip() or None
    if payload.get("group") is not None:
        row.group_code = payload["group"]
    if payload.get("datatype") is not None:
        row.datatype = payload["datatype"]
    if payload.get("sort") is not None:
        row.sort = int(payload["sort"])
    db.commit()
    return {"key": row.key, "label": row.label, "unit": row.unit, "group": row.group_code, "datatype": row.datatype, "sort": row.sort, "usage": row.usage}


def product_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(ProductRow)) or 0
