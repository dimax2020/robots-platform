"""Иерархия каталога: отрасль → объект → процесс → тип решения → продукт."""

from __future__ import annotations

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.domain.csv_parse import slugify
from app.domain.solution_types import raw_key
from app.infrastructure.db.models import (
    EconomyNormOverrideRow,
    IndustryRow,
    ObjectIndustryRow,
    ObjectProcessRow,
    ObjectTypeRow,
    ProcessRow,
    ProductProcessRow,
    ProductRow,
    SolutionTypeRow,
    SolutionTypeRuleRow,
    SourceRow,
)


def make_code(name: str, taken: set[str]) -> str:
    return slugify(name, {item.replace("_", "-") for item in taken}).replace("-", "_")


def untyped_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(ProductRow).where(ProductRow.solution_type_id.is_(None))) or 0


def _type_counts(db: Session) -> dict[int, int]:
    rows = db.execute(
        select(ProductRow.solution_type_id, func.count()).where(ProductRow.solution_type_id.is_not(None)).group_by(ProductRow.solution_type_id)
    ).all()
    return {type_id: count for type_id, count in rows}


def hierarchy(db: Session) -> dict:
    """Дерево со счётчиками. Тип под процессом выводится из продуктов процесса, отдельной связи нет."""
    types = {row.id: row for row in db.scalars(select(SolutionTypeRow))}
    per_process: dict[int, dict[int | None, int]] = {}
    rows = db.execute(
        select(ProductProcessRow.process_id, ProductRow.solution_type_id, func.count())
        .join(ProductRow, ProductRow.id == ProductProcessRow.product_id)
        .group_by(ProductProcessRow.process_id, ProductRow.solution_type_id)
    ).all()
    for process_id, type_id, count in rows:
        per_process.setdefault(process_id, {})[type_id] = count
    processes = {}
    for proc in db.scalars(select(ProcessRow).order_by(ProcessRow.name)):
        counts = per_process.get(proc.id, {})
        branch = [
            {
                "code": types[type_id].code if type_id in types else "",
                "name": types[type_id].name if type_id in types else "Тип не задан",
                "products": count,
            }
            for type_id, count in counts.items()
        ]
        branch.sort(key=lambda item: (item["code"] == "", -item["products"], item["name"]))
        processes[proc.id] = {"code": proc.code, "name": proc.name, "products": sum(counts.values()), "types": branch}
    objects = {}
    for obj in db.scalars(select(ObjectTypeRow).order_by(ObjectTypeRow.name)):
        process_ids = list(db.scalars(select(ObjectProcessRow.process_id).where(ObjectProcessRow.object_type_id == obj.id)))
        items = sorted((processes[pid] for pid in process_ids if pid in processes), key=lambda item: item["name"])
        objects[obj.id] = {"code": obj.code, "name": obj.name, "in_match": obj.in_match, "processes": items}
    linked: set[int] = set()
    industries = []
    for industry in db.scalars(select(IndustryRow).order_by(IndustryRow.name)):
        object_ids = list(db.scalars(select(ObjectIndustryRow.object_type_id).where(ObjectIndustryRow.industry_id == industry.id)))
        linked.update(object_ids)
        industries.append({
            "code": industry.code,
            "name": industry.name,
            "objects": sorted((objects[oid] for oid in object_ids if oid in objects), key=lambda item: item["name"]),
        })
    loose = [item for oid, item in objects.items() if oid not in linked]
    if loose:
        industries.append({"code": "", "name": "Без отрасли", "objects": loose})
    attached = set(db.scalars(select(ObjectProcessRow.process_id)))
    orphan = [item for pid, item in processes.items() if pid not in attached]
    return {
        "industries": industries,
        "orphan_processes": orphan,
        "totals": {
            "products": db.scalar(select(func.count()).select_from(ProductRow)) or 0,
            "untyped": untyped_count(db),
            "without_process": db.scalar(
                select(func.count()).select_from(ProductRow).where(~ProductRow.id.in_(select(ProductProcessRow.product_id)))
            ) or 0,
            "types": len(types),
        },
    }


def industries(db: Session) -> list[dict]:
    result = []
    for industry in db.scalars(select(IndustryRow).order_by(IndustryRow.name)):
        codes = list(db.scalars(
            select(ObjectTypeRow.code)
            .join(ObjectIndustryRow, ObjectIndustryRow.object_type_id == ObjectTypeRow.id)
            .where(ObjectIndustryRow.industry_id == industry.id)
            .order_by(ObjectTypeRow.name)
        ))
        result.append({"code": industry.code, "name": industry.name, "objects": codes})
    return result


def save_industry(db: Session, *, code: str | None, name: str, objects: list[str]) -> dict:
    name = name.strip()
    if not name:
        raise ValueError("Нужно название отрасли")
    row = db.scalar(select(IndustryRow).where(IndustryRow.code == code)) if code else None
    if row is None:
        row = IndustryRow(code=make_code(name, set(db.scalars(select(IndustryRow.code)))), name=name)
        db.add(row)
        db.flush()
    else:
        row.name = name
    db.execute(delete(ObjectIndustryRow).where(ObjectIndustryRow.industry_id == row.id))
    for object_code in dict.fromkeys(objects):
        obj = db.scalar(select(ObjectTypeRow).where(ObjectTypeRow.code == object_code))
        if obj is not None:
            db.add(ObjectIndustryRow(object_type_id=obj.id, industry_id=row.id))
    db.commit()
    return {"code": row.code, "name": row.name, "objects": list(dict.fromkeys(objects))}


def delete_industry(db: Session, code: str) -> None:
    row = db.scalar(select(IndustryRow).where(IndustryRow.code == code))
    if row is None:
        raise KeyError(code)
    db.execute(delete(ObjectIndustryRow).where(ObjectIndustryRow.industry_id == row.id))
    db.delete(row)
    db.commit()


def solution_types(db: Session) -> list[dict]:
    counts = _type_counts(db)
    rows = db.scalars(select(SolutionTypeRow).order_by(SolutionTypeRow.group_name, SolutionTypeRow.name))
    return [
        {"code": row.code, "name": row.name, "group": row.group_name, "family": row.family, "products": counts.get(row.id, 0)}
        for row in rows
    ]


def save_solution_type(db: Session, *, code: str | None, name: str, group: str, family: str) -> dict:
    name = name.strip()
    if not name:
        raise ValueError("Нужно название типа")
    row = db.scalar(select(SolutionTypeRow).where(SolutionTypeRow.code == code)) if code else None
    if row is None:
        row = SolutionTypeRow(code=make_code(name, set(db.scalars(select(SolutionTypeRow.code)))), name=name)
        db.add(row)
    row.name = name
    row.group_name = group.strip()
    row.family = family.strip()
    db.commit()
    return {"code": row.code, "name": row.name, "group": row.group_name, "family": row.family}


def delete_solution_type(db: Session, code: str) -> None:
    row = db.scalar(select(SolutionTypeRow).where(SolutionTypeRow.code == code))
    if row is None:
        raise KeyError(code)
    db.execute(delete(SolutionTypeRuleRow).where(SolutionTypeRuleRow.solution_type_id == row.id))
    db.execute(delete(EconomyNormOverrideRow).where(EconomyNormOverrideRow.solution_type_id == row.id))
    for product in db.scalars(select(ProductRow).where(ProductRow.solution_type_id == row.id)):
        product.solution_type_id = None
    db.delete(row)
    db.commit()


def _raw(product: ProductRow, key: str) -> str:
    item = (product.attrs or {}).get(key) or {}
    return str(item.get("value") or "") if item.get("status") == "known" else ""


def untyped_groups(db: Session) -> list[dict]:
    """Продукты без типа, сгруппированные по категории источника: так тип назначается сразу всей категории."""
    groups: dict[str, dict] = {}
    for product in db.scalars(select(ProductRow).where(ProductRow.solution_type_id.is_(None)).order_by(ProductRow.name)):
        robot_class, subtype, kind = _raw(product, "robot_class"), _raw(product, "subtype"), _raw(product, "robot_kind")
        key = raw_key(robot_class, subtype, kind)
        group = groups.get(key)
        if group is None:
            label = " / ".join(part for part in (robot_class, subtype, kind) if part) or "Категория не указана"
            group = groups[key] = {"raw_key": key, "label": label, "products": []}
        group["products"].append({"slug": product.slug, "name": product.name, "manufacturer": product.manufacturer})
    result = sorted(groups.values(), key=lambda item: (-len(item["products"]), item["label"]))
    for item in result:
        item["count"] = len(item["products"])
    return result


def assign_type(db: Session, *, code: str | None, slugs: list[str], raw: str | None, remember: bool) -> int:
    type_row = None
    if code:
        type_row = db.scalar(select(SolutionTypeRow).where(SolutionTypeRow.code == code))
        if type_row is None:
            raise KeyError(code)
    changed = 0
    if slugs:
        for product in db.scalars(select(ProductRow).where(ProductRow.slug.in_(slugs))):
            product.solution_type_id = type_row.id if type_row else None
            changed += 1
    if raw is not None and type_row is not None:
        for product in db.scalars(select(ProductRow).where(ProductRow.solution_type_id.is_(None))):
            if raw_key(_raw(product, "robot_class"), _raw(product, "subtype"), _raw(product, "robot_kind")) == raw:
                product.solution_type_id = type_row.id
                changed += 1
        if remember and raw.strip("|"):
            rule = db.get(SolutionTypeRuleRow, raw)
            if rule is None:
                db.add(SolutionTypeRuleRow(raw_key=raw, solution_type_id=type_row.id))
            else:
                rule.solution_type_id = type_row.id
    db.commit()
    return changed


def type_rules(db: Session) -> list[dict]:
    names = {row.id: (row.code, row.name) for row in db.scalars(select(SolutionTypeRow))}
    result = []
    for rule in db.scalars(select(SolutionTypeRuleRow).order_by(SolutionTypeRuleRow.raw_key)):
        code, name = names.get(rule.solution_type_id, ("", ""))
        label = " / ".join(part for part in rule.raw_key.split("|") if part)
        result.append({"raw_key": rule.raw_key, "label": label, "type_code": code, "type_name": name})
    return result


def source_registry(db: Session) -> list[dict]:
    """Реестр источников: сколько значений и карточек на каждый ссылается и когда карточки последний раз обновлялись."""
    values = dict(db.execute(text(
        "select (item.value->>'source_id')::int, count(*)::int from product, jsonb_each(attrs) as item "
        "where item.value ? 'source_id' and jsonb_typeof(item.value->'source_id') = 'number' group by 1"
    )).all())
    columns = dict(db.execute(text(
        "select item.value::int, count(*)::int from product, jsonb_each_text(column_sources) as item "
        "where item.value ~ '^[0-9]+$' group by 1"
    )).all())
    stats = {
        source_id: (products, updated)
        for source_id, products, updated in db.execute(text(
            "select sid, count(distinct id)::int, max(updated_at) from ("
            " select p.id, p.updated_at, (item.value->>'source_id')::int as sid from product p, jsonb_each(p.attrs) as item"
            "  where jsonb_typeof(item.value->'source_id') = 'number'"
            " union all"
            " select p.id, p.updated_at, item.value::int from product p, jsonb_each_text(p.column_sources) as item"
            "  where item.value ~ '^[0-9]+$'"
            ") as refs group by sid"
        )).all()
    }
    result = []
    for row in db.scalars(select(SourceRow).order_by(SourceRow.kind, SourceRow.publisher)):
        products, updated = stats.get(row.id, (0, None))
        result.append({
            "id": row.id,
            "kind": row.kind,
            "publisher": row.publisher,
            "url": row.url or None,
            "title": row.title,
            "parser_code": row.parser_code or None,
            "values": int(values.get(row.id, 0)) + int(columns.get(row.id, 0)),
            "products": products,
            "updated_at": updated.isoformat() if updated else None,
        })
    return result


def delete_type_rule(db: Session, raw: str) -> None:
    db.execute(delete(SolutionTypeRuleRow).where(SolutionTypeRuleRow.raw_key == raw))
    db.commit()
