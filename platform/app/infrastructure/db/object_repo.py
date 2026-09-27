"""Объекты: поля площадки для формы проекта и справочник этих полей."""

from __future__ import annotations

import re

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.infrastructure.db.catalog_repo import make_code
from app.infrastructure.db.models import (
    IndustryRow,
    ObjectFieldRow,
    ObjectIndustryRow,
    ObjectInputBindingRow,
    ObjectProcessRow,
    ObjectTypeRow,
    ProcessFilterRow,
    ProcessRow,
    ProjectRow,
    SiteFieldRow,
)

KINDS = {"number", "int", "bool", "text"}


def _num(value) -> float | None:
    return None if value is None else float(value)


def site_field_view(row: SiteFieldRow) -> dict:
    return {
        "key": row.key,
        "label": row.label,
        "unit": row.unit,
        "kind": row.kind,
        "min": _num(row.min_value),
        "max": _num(row.max_value),
        "hint": row.hint,
    }


def site_fields(db: Session) -> list[dict]:
    used = dict(db.execute(select(ObjectFieldRow.field_key, func.count()).group_by(ObjectFieldRow.field_key)).all())
    return [
        {**site_field_view(row), "objects": int(used.get(row.key, 0))}
        for row in db.scalars(select(SiteFieldRow).order_by(SiteFieldRow.sort, SiteFieldRow.label))
    ]


def save_site_field(db: Session, payload: dict) -> dict:
    label = (payload.get("label") or "").strip()
    if not label:
        raise ValueError("Нужна подпись поля")
    kind = payload.get("kind") or "number"
    if kind not in KINDS:
        raise ValueError("Тип поля: number, int, bool или text")
    key = (payload.get("key") or "").strip()
    row = db.get(SiteFieldRow, key) if key else None
    if row is None:
        if key and not re.fullmatch(r"[a-z][a-z0-9_]*", key):
            raise ValueError("Ключ: латиница, цифры и подчёркивание, с буквы")
        key = key or make_code(label, set(db.scalars(select(SiteFieldRow.key))))
        if not re.match(r"[a-z]", key):
            key = f"f_{key}"
        top = db.scalar(select(func.max(SiteFieldRow.sort))) or 0
        row = SiteFieldRow(key=key, label=label, sort=top + 10)
        db.add(row)
    row.label = label
    row.unit = (payload.get("unit") or "").strip()
    row.kind = kind
    row.min_value = payload.get("min")
    row.max_value = payload.get("max")
    row.hint = (payload.get("hint") or "").strip()
    db.commit()
    return site_field_view(row)


def delete_site_field(db: Session, key: str) -> None:
    row = db.get(SiteFieldRow, key)
    if row is None:
        raise KeyError(key)
    in_objects = db.scalar(select(func.count()).select_from(ObjectFieldRow).where(ObjectFieldRow.field_key == key)) or 0
    in_bindings = db.scalar(select(func.count()).select_from(ObjectInputBindingRow).where(ObjectInputBindingRow.site_key == key)) or 0
    if in_objects or in_bindings:
        raise ValueError("Поле используется в объектах или привязках процессов. Сначала уберите его оттуда.")
    db.delete(row)
    db.commit()


def object_fields(db: Session, object_id: int) -> list[dict]:
    stmt = (
        select(ObjectFieldRow, SiteFieldRow)
        .join(SiteFieldRow, SiteFieldRow.key == ObjectFieldRow.field_key)
        .where(ObjectFieldRow.object_type_id == object_id)
        .order_by(ObjectFieldRow.sort, SiteFieldRow.sort)
    )
    return [
        {
            **site_field_view(meta),
            "base_label": meta.label,
            "label": link.label or meta.label,
            "group": link.group_name,
            "required": link.required,
            "default": link.default_value,
            "source": link.source,
        }
        for link, meta in db.execute(stmt)
    ]


def form_fields(db: Session, object_code: str) -> dict:
    obj = db.scalar(select(ObjectTypeRow).where(ObjectTypeRow.code == object_code))
    if obj is None:
        raise KeyError(object_code)
    return {"code": obj.code, "name": obj.name, "fields": object_fields(db, obj.id)}


def replace_object_fields(db: Session, obj: ObjectTypeRow, rows: list[dict]) -> None:
    known = set(db.scalars(select(SiteFieldRow.key)))
    db.execute(delete(ObjectFieldRow).where(ObjectFieldRow.object_type_id == obj.id))
    db.flush()
    taken: set[str] = set()
    for index, row in enumerate(rows):
        key = row.get("key") or ""
        if key not in known or key in taken:
            continue
        taken.add(key)
        label = (row.get("label") or "").strip()
        db.add(ObjectFieldRow(
            object_type_id=obj.id,
            field_key=key,
            group_name=(row.get("group") or "").strip(),
            label=label or None,
            required=bool(row.get("required")),
            default_value=row.get("default"),
            source=(row.get("source") or "").strip(),
            sort=(index + 1) * 10,
        ))


def objects_overview(db: Session) -> list[dict]:
    result = []
    for obj in db.scalars(select(ObjectTypeRow).order_by(ObjectTypeRow.name)):
        fields = db.scalar(select(func.count()).select_from(ObjectFieldRow).where(ObjectFieldRow.object_type_id == obj.id)) or 0
        processes = db.scalar(select(func.count()).select_from(ObjectProcessRow).where(ObjectProcessRow.object_type_id == obj.id)) or 0
        projects = db.scalar(select(func.count()).select_from(ProjectRow).where(ProjectRow.object_type_id == obj.id)) or 0
        result.append({
            "code": obj.code,
            "name": obj.name,
            "fields": fields,
            "processes": processes,
            "unbound": len(unbound_inputs(db, obj.id)),
            "projects": projects,
        })
    return result


def process_inputs(db: Session, process: ProcessRow) -> list[dict]:
    """Величины процесса: у фильтров и у формулы количества. Какое поле площадки в них подставить, решает объект."""
    inputs: list[dict] = []
    seen: set[str] = set()
    for item in db.scalars(select(ProcessFilterRow).where(ProcessFilterRow.process_id == process.id).order_by(ProcessFilterRow.id)):
        for row in item.inputs or []:
            if not isinstance(row, dict):
                continue
            key = str(row.get("key") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            inputs.append({"key": key, "label": row.get("label") or key, "kind": "filter", "filter": item.name})
    for row in process.count_inputs or []:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        inputs.append({"key": key, "label": row.get("label") or key, "kind": "count", "filter": ""})
    return inputs


def unbound_inputs(db: Session, object_id: int) -> list[tuple[str, str]]:
    missing = []
    process_ids = list(db.scalars(select(ObjectProcessRow.process_id).where(ObjectProcessRow.object_type_id == object_id)))
    for process in db.scalars(select(ProcessRow).where(ProcessRow.id.in_(process_ids))):
        bound = set(db.scalars(select(ObjectInputBindingRow.input_key).where(
            ObjectInputBindingRow.object_type_id == object_id,
            ObjectInputBindingRow.process_id == process.id,
        )))
        for item in process_inputs(db, process):
            if item["key"] not in bound:
                missing.append((process.code, item["key"]))
    return missing


def create_object(db: Session, *, name: str, industries: list[str], copy_from: str | None) -> str:
    name = name.strip()
    if not name:
        raise ValueError("Нужно название объекта")
    code = make_code(name, set(db.scalars(select(ObjectTypeRow.code))))
    obj = ObjectTypeRow(code=code, name=name)
    db.add(obj)
    db.flush()
    for industry_code in dict.fromkeys(industries):
        industry = db.scalar(select(IndustryRow).where(IndustryRow.code == industry_code))
        if industry is not None:
            db.add(ObjectIndustryRow(object_type_id=obj.id, industry_id=industry.id))
    if copy_from:
        source = db.scalar(select(ObjectTypeRow).where(ObjectTypeRow.code == copy_from))
        if source is not None:
            for link in db.scalars(select(ObjectFieldRow).where(ObjectFieldRow.object_type_id == source.id)):
                db.add(ObjectFieldRow(
                    object_type_id=obj.id,
                    field_key=link.field_key,
                    group_name=link.group_name,
                    label=link.label,
                    required=link.required,
                    default_value=None,
                    source="",
                    sort=link.sort,
                ))
    db.commit()
    return code


def set_object_identity(db: Session, obj: ObjectTypeRow, *, name: str | None, industries: list[str] | None) -> None:
    if name is not None and name.strip():
        obj.name = name.strip()
    if industries is None:
        return
    db.execute(delete(ObjectIndustryRow).where(ObjectIndustryRow.object_type_id == obj.id))
    for industry_code in dict.fromkeys(industries):
        industry = db.scalar(select(IndustryRow).where(IndustryRow.code == industry_code))
        if industry is not None:
            db.add(ObjectIndustryRow(object_type_id=obj.id, industry_id=industry.id))


def object_industries(db: Session, object_id: int) -> list[str]:
    return list(db.scalars(
        select(IndustryRow.code)
        .join(ObjectIndustryRow, ObjectIndustryRow.industry_id == IndustryRow.id)
        .where(ObjectIndustryRow.object_type_id == object_id)
    ))
