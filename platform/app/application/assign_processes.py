"""Явные назначения по рассмотренным карточкам, без догадок по классу и весу."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import (
    IndustryRow, ObjectIndustryRow, ObjectInputBindingRow, ObjectProcessRow,
    ObjectTypeRow, ProcessFilterRow, ProcessRow, ProductProcessRow, ProductRow,
    ProjectProcessRow,
)

ASSIGNMENTS_FILE = Path(__file__).resolve().parents[2] / "seed" / "process_assignments.json"


def read_assignments() -> dict:
    data = json.loads(ASSIGNMENTS_FILE.read_text(encoding="utf-8"))
    codes = {p["code"] for p in data["processes"]}
    if len(codes) != len(data["processes"]):
        raise ValueError("Повторяющиеся коды процессов")
    seen = set()
    for row in data["products"]:
        product_id = UUID(row["id"])
        if product_id in seen or not set(row["processes"]) <= codes:
            raise ValueError(f"Некорректное назначение: {row['name']}")
        seen.add(product_id)
    if not set(data["merges"].values()) <= codes or set(data["merges"]) & codes:
        raise ValueError("Некорректные объединения процессов")
    return data


def classify(text: str, payload: float | None = None) -> set[str]:
    """Совместимый интерфейс: только точное имя рассмотренной модели.

    Вес не определяет задачу. Неизвестное или неоднозначное имя не назначается.
    Основное назначение в БД использует UUID, поэтому одноимённые роботы различаются.
    """
    matches = [set(p["processes"]) for p in read_assignments()["products"]
               if p["name"].strip().casefold() == text.strip().casefold()]
    return matches[0] if matches and all(m == matches[0] for m in matches) else set()


def seed_taxonomy(db: Session, data: dict | None = None) -> dict[str, ProcessRow]:
    """Добавить недостающие задачи и объекты; ручные настройки не перезаписывать."""
    data = data or read_assignments()
    industries = {x.code: x for x in db.scalars(select(IndustryRow))}
    for spec in data["industries"]:
        if spec["code"] not in industries:
            row = IndustryRow(code=spec["code"], name=spec["name"])
            db.add(row)
            industries[row.code] = row
    objects = {x.code: x for x in db.scalars(select(ObjectTypeRow))}
    new_objects = set()
    for spec in data["objects"]:
        if spec["code"] not in objects:
            row = ObjectTypeRow(code=spec["code"], name=spec["name"])
            db.add(row)
            objects[row.code] = row
            new_objects.add(row.code)
    processes = {x.code: x for x in db.scalars(select(ProcessRow))}
    new_processes = set()
    for spec in data["processes"]:
        if spec["code"] not in processes:
            row = ProcessRow(code=spec["code"], name=spec["name"])
            db.add(row)
            processes[row.code] = row
            new_processes.add(row.code)
    db.flush()
    for spec in data["objects"]:
        if spec["code"] in new_objects:
            for code in spec["industries"]:
                db.add(ObjectIndustryRow(object_type_id=objects[spec["code"]].id,
                                         industry_id=industries[code].id))
    for spec in data["processes"]:
        for code in spec["objects"]:
            if spec["code"] in new_processes or code in new_objects:
                db.add(ObjectProcessRow(object_type_id=objects[code].id,
                                        process_id=processes[spec["code"]].id))
    db.flush()
    return processes


def _merge_process(db: Session, source: ProcessRow, target: ProcessRow) -> None:
    # Формулы и оформление канонического процесса имеют приоритет. Если их нет,
    # переносим настройки целиком, чтобы не потерять связанные входные параметры.
    if not target.count_formula and source.count_formula:
        target.count_formula = source.count_formula
        target.count_inputs = source.count_inputs
    if not target.rank_key and source.rank_key:
        target.rank_key, target.rank_order = source.rank_key, source.rank_order
    if not target.layout_items and source.layout_items:
        target.layout_items = source.layout_items

    for model, keys in (
        (ObjectProcessRow, ("object_type_id",)),
        (ProductProcessRow, ("product_id",)),
        (ProjectProcessRow, ("project_id",)),
        (ObjectInputBindingRow, ("object_type_id", "input_key")),
    ):
        for link in list(db.scalars(select(model).where(model.process_id == source.id))):
            identity = {key: getattr(link, key) for key in keys} | {"process_id": target.id}
            if db.get(model, identity) is None:
                values = {c.name: getattr(link, c.name) for c in model.__table__.columns}
                values["process_id"] = target.id
                db.add(model(**values))
            db.delete(link)
        db.flush()

    fields = ("name", "object_keys", "robot_keys", "op", "mode", "inputs", "formula")
    def signature(row):
        return json.dumps({k: getattr(row, k) for k in fields}, sort_keys=True)
    existing = {signature(row) for row in db.scalars(
        select(ProcessFilterRow).where(ProcessFilterRow.process_id == target.id))}
    for row in db.scalars(select(ProcessFilterRow).where(ProcessFilterRow.process_id == source.id)):
        if signature(row) in existing:
            db.delete(row)
        else:
            existing.add(signature(row))
            row.process_id = target.id
    db.flush()
    db.delete(source)
    db.flush()


def assign_all(db: Session, *, commit: bool = True) -> dict[str, int]:
    """Однократное исправление каталога; вызывается миграцией, не каждым запуском.

    Обновляются только рассмотренные UUID. Новые карточки и их ручные связи
    не затрагиваются. Импорт новых роботов сам по себе процессы не назначает.
    """
    data = read_assignments()
    processes = seed_taxonomy(db, data)
    for old, new in data["merges"].items():
        if old in processes:
            _merge_process(db, processes.pop(old), processes[new])
    for spec in data["processes"]:
        processes[spec["code"]].name = spec["name"]

    reviewed = {UUID(row["id"]): row for row in data["products"]}
    # У рассмотренных карточек удаляем только связи с системными процессами.
    # Пользовательские процессы вне этого справочника сохраняются.
    managed_ids = [processes[p["code"]].id for p in data["processes"]]
    products = list(db.scalars(select(ProductRow).where(ProductRow.id.in_(reviewed))))
    ids = [p.id for p in products]
    db.execute(delete(ProductProcessRow).where(
        ProductProcessRow.product_id.in_(ids), ProductProcessRow.process_id.in_(managed_ids)))
    counts = {p["code"]: 0 for p in data["processes"]}
    counts["unassigned"] = 0
    for product in products:
        chosen = reviewed[product.id]["processes"]
        if not chosen:
            counts["unassigned"] += 1
        for code in chosen:
            db.add(ProductProcessRow(product_id=product.id, process_id=processes[code].id))
            counts[code] += 1
    db.flush()
    if commit:
        db.commit()
    return counts
