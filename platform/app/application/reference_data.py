"""Справочники из seed/*.json: типы решений, поля площадки, группы характеристик. Повторный вызов ничего не дублирует."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.orm import Session

from app.domain.solution_types import Mapping, classify, read_mapping
from app.infrastructure.db.models import (
    AppUserRow,
    AttributeDefRow,
    ObjectFieldRow,
    ObjectInputBindingRow,
    ObjectTypeRow,
    ProductRow,
    SiteFieldRow,
    SolutionTypeRow,
    SolutionTypeRuleRow,
)

DEMO_PASSWORD = "demo-2026"
DEMO_USERS = (("guest", "guest"), ("user", "user"), ("admin", "admin"))

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"
EXTRA_GROUP = "Дополнительно"


def _read(name: str) -> dict:
    path = SEED_DIR / name
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def type_mapping() -> Mapping:
    return read_mapping(_read("solution_types.json"))


def seed_users(db: Session) -> None:
    """Три демо-учётки. Повторный запуск уже записанный пароль не меняет."""
    from uuid import uuid4

    from argon2 import PasswordHasher

    bind = db.get_bind()
    if bind is None or not sa_inspect(bind).has_table("app_user"):
        return
    known = set(db.scalars(select(AppUserRow.login)))
    hasher = PasswordHasher()
    for login, role in DEMO_USERS:
        if login in known:
            continue
        db.add(AppUserRow(id=uuid4(), login=login, password_hash=hasher.hash(DEMO_PASSWORD), role=role))
    db.flush()


def seed_reference(db: Session) -> None:
    seed_users(db)
    _seed_types(db)
    _seed_site_fields(db)
    _seed_object_fields(db)
    _seed_attribute_meta(db)
    db.flush()
    assign_missing_types(db)
    db.commit()


def _seed_types(db: Session) -> None:
    known = set(db.scalars(select(SolutionTypeRow.code)))
    for spec in type_mapping().types:
        if spec.code not in known:
            db.add(SolutionTypeRow(code=spec.code, name=spec.name, group_name=spec.group, family=spec.family))
    db.flush()


def _seed_site_fields(db: Session) -> None:
    known = set(db.scalars(select(SiteFieldRow.key)))
    for row in _read("site_fields.json").get("fields") or []:
        if row["key"] in known:
            continue
        db.add(SiteFieldRow(
            key=row["key"],
            label=row["label"],
            unit=row.get("unit") or "",
            kind=row.get("kind") or "number",
            min_value=row.get("min"),
            max_value=row.get("max"),
            hint=row.get("hint") or "",
            sort=row.get("sort") or 0,
        ))
    db.flush()


def _seed_object_fields(db: Session) -> None:
    """Поля заводятся только объекту без полей: удалённое админом поле при рестарте не вернётся, пока у объекта есть другие."""
    plan = _read("site_fields.json").get("objects") or {}
    fields = set(db.scalars(select(SiteFieldRow.key)))
    for obj in db.scalars(select(ObjectTypeRow)):
        if db.scalar(select(ObjectFieldRow).where(ObjectFieldRow.object_type_id == obj.id).limit(1)) is not None:
            continue
        taken: set[str] = set()
        sort = 0
        for row in plan.get(obj.code) or []:
            if row["key"] not in fields or row["key"] in taken:
                continue
            taken.add(row["key"])
            sort = row.get("sort") or sort + 10
            db.add(ObjectFieldRow(
                object_type_id=obj.id,
                field_key=row["key"],
                group_name=row.get("group") or "",
                label=row.get("label"),
                required=bool(row.get("required")),
                default_value=row.get("default"),
                source=row.get("source") or "",
                sort=sort,
            ))
        bound = db.scalars(select(ObjectInputBindingRow.site_key).where(ObjectInputBindingRow.object_type_id == obj.id))
        for key in sorted(set(bound)):
            if key in taken or key not in fields:
                continue
            taken.add(key)
            sort += 10
            db.add(ObjectFieldRow(object_type_id=obj.id, field_key=key, group_name=EXTRA_GROUP, sort=sort))
    db.flush()


def _seed_attribute_meta(db: Session) -> None:
    from app.domain.specs import definitions
    for row in definitions().values():
        item = db.get(AttributeDefRow, row["key"])
        if item is None:
            item = AttributeDefRow(key=row["key"], label=row["label"], usage="pending",
                                   group_code=row.get("group_code", ""), datatype=row.get("datatype", "text"),
                                   sort=row.get("sort", 1000), unit=row.get("unit"))
            db.add(item)
            continue
        if not item.group_code:
            item.group_code = row.get("group_code") or ""
            item.datatype = row.get("datatype") or "text"
            item.sort = row.get("sort") or 1000
        if row.get("unit") and not item.unit:
            item.unit = row["unit"]
        if item.label in ("", item.key):
            item.label = row["label"]
    db.flush()


def type_rules(db: Session) -> dict[str, str]:
    codes = {row.id: row.code for row in db.scalars(select(SolutionTypeRow))}
    return {row.raw_key: codes[row.solution_type_id] for row in db.scalars(select(SolutionTypeRuleRow)) if row.solution_type_id in codes}


def product_type_code(product: ProductRow, mapping: Mapping, rules: dict[str, str]) -> str | None:
    attrs = product.attrs or {}

    def value(key: str) -> object:
        item = attrs.get(key) or {}
        return item.get("value") if item.get("status") == "known" else ""

    return classify(
        mapping,
        rules,
        robot_class=value("robot_class"),
        subtype=value("subtype"),
        system_class=value("system_class"),
        robot_kind=value("robot_kind"),
    )


def assign_missing_types(db: Session) -> int:
    ids = {row.code: row.id for row in db.scalars(select(SolutionTypeRow))}
    if not ids:
        return 0
    mapping = type_mapping()
    rules = type_rules(db)
    changed = 0
    for product in db.scalars(select(ProductRow).where(ProductRow.solution_type_id.is_(None))):
        code = product_type_code(product, mapping, rules)
        if code and code in ids:
            product.solution_type_id = ids[code]
            changed += 1
    db.flush()
    return changed
