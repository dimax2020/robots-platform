"""Назначение процессов роботам по названию и классу. Фильтры процессов очищает."""

from __future__ import annotations

import re

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import (
    IndustryRow,
    ObjectTypeRow,
    ProcessRow,
    ProductProcessRow,
    ProductRow,
    ProjectProcessRow,
    ProjectRow,
)
from app.infrastructure.db.taxonomy_repo import add_process, save_object

WAREHOUSE = [
    "pallet_transport",
    "rack_placement",
    "auto_pallet_storage",
    "order_picking",
    "tote_delivery",
    "cart_towing",
    "parcel_sorting",
    "palletizing",
    "floor_cleaning",
    "inventory",
    "facade_washing",
    "roof_inspection",
    "perimeter_security",
]
AIRPORT = [
    "floor_cleaning",
    "facade_washing",
    "roof_inspection",
    "perimeter_security",
    "territory_inspection",
    "baggage_transport",
    "apron_transport",
    "passenger_service",
    "tote_delivery",
]
HOSPITAL = [
    "floor_cleaning",
    "medicine_delivery",
    "biomaterial_delivery",
    "ward_service",
    "inventory",
    "facade_washing",
    "perimeter_security",
]

PROCESSES = [
    ("pallet_transport", "Перевозка паллет"),
    ("rack_placement", "Размещение на ярусах"),
    ("auto_pallet_storage", "Автоматическое хранение паллет"),
    ("order_picking", "Комплектация"),
    ("tote_delivery", "Доставка тары"),
    ("cart_towing", "Буксировка тележек"),
    ("parcel_sorting", "Сортировка посылок"),
    ("palletizing", "Погрузка и паллетирование"),
    ("floor_cleaning", "Уборка пола / территории"),
    ("inventory", "Инвентаризация"),
    ("facade_washing", "Мойка фасадов"),
    ("roof_inspection", "Осмотр кровли"),
    ("perimeter_security", "Охрана периметра"),
    ("territory_inspection", "Осмотр территории"),
    ("baggage_transport", "Перевозка багажа"),
    ("apron_transport", "Транспорт на перроне"),
    ("passenger_service", "Сервис в терминале"),
    ("medicine_delivery", "Доставка лекарств и материалов"),
    ("biomaterial_delivery", "Доставка биоматериалов"),
    ("ward_service", "Сервис в отделениях"),
]


def assign_all(db: Session) -> dict[str, int]:
    for code, name in PROCESSES:
        add_process(db, code=code, name=name)
    save_object(db, code="warehouse", name="Склад", industries=["logistics"], processes=WAREHOUSE)
    _industry(db, "transport", "Транспорт")
    _industry(db, "medicine", "Медицина")
    save_object(db, code="airport", name="Аэропорт", industries=["transport"], processes=AIRPORT)
    save_object(db, code="hospital", name="Медучреждение", industries=["medicine"], processes=HOSPITAL)

    codes = {row.code: row.id for row in db.scalars(select(ProcessRow))}
    counts = {code: 0 for code, _name in PROCESSES}
    unassigned = 0
    for product in db.scalars(select(ProductRow)):
        chosen = classify(_blob(product), _payload(product))
        db.execute(delete(ProductProcessRow).where(ProductProcessRow.product_id == product.id))
        if not chosen:
            unassigned += 1
            continue
        for code in chosen:
            process_id = codes.get(code)
            if process_id is None:
                continue
            db.add(ProductProcessRow(product_id=product.id, process_id=process_id))
            counts[code] += 1
    _sync_projects(db)
    db.commit()
    counts["unassigned"] = unassigned
    return counts


def classify(text: str, payload: float | None) -> set[str]:
    raw = text.casefold().replace("ё", "е")
    if _excluded(raw):
        return set()
    found: set[str] = set()
    if _floor(raw):
        found.add("floor_cleaning")
        found.add("floor_washing")
    if _facade(raw):
        found.add("facade_washing")
    if _roof(raw):
        found.add("roof_inspection")
    if _territory(raw):
        found.add("territory_inspection")
    if _security(raw):
        found.add("perimeter_security")
    if _inventory(raw):
        found.add("inventory")
        found.add("warehouse_inventory")
    if _storage(raw):
        found.add("auto_pallet_storage")
        found.add("pallet_storage")
    if _rack(raw):
        found.add("rack_placement")
    if _pallet_move(raw, payload):
        found.add("pallet_transport")
        found.add("baggage_transport")
    if _tow(raw):
        found.add("cart_towing")
        found.add("apron_transport")
    if _sort(raw):
        found.add("parcel_sorting")
        found.add("box_transport")
    if _pick(raw):
        found.add("order_picking")
    if _palletize(raw):
        found.add("palletizing")
        found.add("pallet_handling")
        found.add("packing")
    if _indoor_delivery(raw, payload):
        found.update({"tote_delivery", "medicine_delivery", "biomaterial_delivery"})
    if _service_person(raw):
        found.update({"ward_service", "passenger_service"})
    return found


def _blob(product: ProductRow) -> str:
    parts = [product.name or "", product.summary or ""]
    for key in ("robot_class", "subtype", "robot_kind", "scenario"):
        value = (product.attrs or {}).get(key, {})
        if isinstance(value, dict) and value.get("value"):
            parts.append(str(value["value"]))
    return " ".join(parts)


def _payload(product: ProductRow) -> float | None:
    for key in ("payload_kg", "gruzopodemnost_maksimalnaya", "gruzopodemnost"):
        raw = (product.attrs or {}).get(key, {})
        if not isinstance(raw, dict) or raw.get("value") in (None, ""):
            continue
        match = re.search(r"\d+(?:[.,]\d+)?", str(raw["value"]).replace(" ", ""))
        if match:
            return float(match.group(0).replace(",", "."))
    return None


def _excluded(text: str) -> bool:
    words = (
        "катер", "подвод", "тнпа", "катамаран", "трактор", "агро", "доиль", "плод", "ягод", "томат",
        "бульдозер", "каток", "асфальт", "трамвай", "метро", "такси", "автобус", "свар",
        "демонтаж", "расцеп", "вагон",
    )
    return any(re.search(rf"(?<!\w){re.escape(word)}", text) for word in words) or "3d-принтер" in text or "3d принтер" in text


def _floor(text: str) -> bool:
    if any(word in text for word in ("фасад", "кровл", "тротуар", "улиц", "снег")):
        return False
    return any(word in text for word in ("убор", "поломо", "пылесос", "клинер", "cleaner", "kleenbot", "cleanbot", "scrub"))


def _facade(text: str) -> bool:
    return any(word in text for word in ("фасад", "мойк окон", "мойка окон", "робот-паук", "октокоптер"))


def _roof(text: str) -> bool:
    if any(word in text for word in ("агро", "посев", "геодез")):
        return False
    return any(word in text for word in ("кровл", "крыш", "бпла", "бвс", "дрон", "мультиротор", "vtol", "гескан", "supercam", "инспекц"))


def _territory(text: str) -> bool:
    if any(word in text for word in ("агро", "посев")):
        return False
    return any(word in text for word in ("инспекц", "бпла", "бвс", "дрон", "мультиротор", "vtol"))


def _security(text: str) -> bool:
    return any(word in text for word in ("охран", "патрул", "security"))


def _inventory(text: str) -> bool:
    return "инвентар" in text


def _storage(text: str) -> bool:
    return any(word in text for word in ("шаттл", "shuttle", "as-rs", "кран-штабел", "smartcube", "кубическ", "система хранения"))


def _rack(text: str) -> bool:
    return any(word in text for word in ("штабел", "вилоч", "погрузчик", "fmr", "ярус"))


def _pallet_move(text: str, payload: float | None) -> bool:
    if any(word in text for word in ("шаттл", "shuttle", "кран-штабел")):
        return False
    if any(word in text for word in ("паллет", "поддон", "amr", "fmr", "складск", "погрузчик", "штабел")):
        return True
    return payload is not None and payload >= 200


def _tow(text: str) -> bool:
    return any(word in text for word in ("тягач", "буксир", "tug"))


def _sort(text: str) -> bool:
    return any(word in text for word in ("сортир", "посыл"))


def _pick(text: str) -> bool:
    return any(word in text for word in ("комплект", "pick by", "отбор", "picker", "воркер"))


def _palletize(text: str) -> bool:
    if any(word in text for word in ("свар", "плод", "томат")):
        return False
    return any(word in text for word in ("паллетир", "уклад", "кобот", "cobot", "манипулятор", "дельта-робот"))


def _indoor_delivery(text: str, payload: float | None) -> bool:
    if any(word in text for word in ("бпла", "бвс", "дрон", "катер")):
        return False
    if any(word in text for word in ("достав", "курьер", "butler", "holabot", "flashbot", "сервисн")):
        return True
    return payload is not None and payload < 200


def _service_person(text: str) -> bool:
    if any(word in text for word in ("убор", "поломо", "кафе", "кофе")):
        return False
    return any(word in text for word in ("сервисн", "гуманоид", "антропоморф", "промобот"))


def _industry(db: Session, code: str, name: str) -> None:
    if db.scalar(select(IndustryRow).where(IndustryRow.code == code)) is None:
        db.add(IndustryRow(code=code, name=name))
        db.commit()


def _sync_projects(db: Session) -> None:
    objects = {row.id: row.code for row in db.scalars(select(ObjectTypeRow))}
    wanted = {"warehouse": WAREHOUSE, "airport": AIRPORT, "hospital": HOSPITAL}
    codes = {row.code: row.id for row in db.scalars(select(ProcessRow))}
    for project in db.scalars(select(ProjectRow)):
        object_code = objects.get(project.object_type_id)
        allowed = {codes[code] for code in wanted.get(object_code or "", []) if code in codes}
        for link in list(db.scalars(select(ProjectProcessRow).where(ProjectProcessRow.project_id == project.id))):
            if link.process_id not in allowed:
                db.delete(link)
        for process_id in allowed:
            if db.get(ProjectProcessRow, (project.id, process_id)) is None:
                db.add(ProjectProcessRow(project_id=project.id, process_id=process_id, enabled=True))
