"""Первый объект — склад. Связи задаются явно, чужие сценарии каталога не копируются."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import IndustryRow, ParserSettingRow
from app.infrastructure.db.taxonomy_repo import add_process, replace_filters, save_object
from app.parsers import PARSERS

PROCESSES = [
    ("pallet_handling", "Погрузка и паллетирование"),
    ("pallet_storage", "Паллетное хранение"),
    ("order_picking", "Сборка заказов"),
    ("box_transport", "Сортировка и транспорт коробов"),
    ("packing", "Упаковка и паллетирование"),
    ("warehouse_inventory", "Инвентаризация склада"),
    ("floor_washing", "Мойка полов"),
    ("facade_washing", "Мойка фасадов"),
]

FILTERS = {
    "pallet_handling": [
        {"name": "Груз паллеты", "object_keys": ["pallet_mass_kg"], "robot_keys": ["payload_kg"], "op": ">=", "mode": "hard"},
        {"name": "Главный проезд", "object_keys": ["main_aisle_width_m"], "robot_keys": ["min_aisle_width_m"], "op": "<=", "mode": "hard"},
    ],
    "pallet_storage": [
        {"name": "Груз паллеты", "object_keys": ["pallet_mass_kg"], "robot_keys": ["payload_kg"], "op": ">=", "mode": "hard"},
        {"name": "Рабочий проход", "object_keys": ["aisle_width_m"], "robot_keys": ["min_aisle_width_m"], "op": "<=", "mode": "hard"},
        {"name": "Высота хранения", "object_keys": ["storage_height_m"], "robot_keys": ["lift_height_m"], "op": ">=", "mode": "conditional"},
    ],
    "order_picking": [
        {"name": "Масса штуки", "object_keys": ["unit_mass_kg"], "robot_keys": ["payload_kg"], "op": ">=", "mode": "hard"},
        {"name": "Рабочий проход", "object_keys": ["aisle_width_m"], "robot_keys": ["min_aisle_width_m"], "op": "<=", "mode": "hard"},
    ],
    "box_transport": [
        {"name": "Масса короба", "object_keys": ["unit_mass_kg"], "robot_keys": ["payload_kg"], "op": ">=", "mode": "hard"},
        {"name": "Рабочий проход", "object_keys": ["aisle_width_m"], "robot_keys": ["min_aisle_width_m"], "op": "<=", "mode": "hard"},
    ],
    "packing": [
        {"name": "Масса штуки", "object_keys": ["unit_mass_kg"], "robot_keys": ["payload_kg"], "op": ">=", "mode": "hard"},
    ],
    "warehouse_inventory": [
        {"name": "Рабочий проход", "object_keys": ["aisle_width_m"], "robot_keys": ["min_aisle_width_m"], "op": "<=", "mode": "hard"},
        {"name": "Высота сканирования", "object_keys": ["storage_height_m"], "robot_keys": ["lift_height_m"], "op": ">=", "mode": "conditional"},
    ],
    "floor_washing": [
        {"name": "Ширина проезда", "object_keys": ["aisle_width_m"], "robot_keys": ["min_aisle_width_m"], "op": "<=", "mode": "hard"},
        {"name": "Тип пола", "object_keys": ["floor_type"], "robot_keys": ["floor_type"], "op": "==", "mode": "conditional"},
    ],
    "facade_washing": [
        {"name": "Высота фасада", "object_keys": ["facade_height_m"], "robot_keys": ["reach_m"], "op": ">=", "mode": "conditional"},
    ],
}


def seed(db: Session) -> None:
    for code, name in PROCESSES:
        add_process(db, code=code, name=name)
    if db.scalar(select(IndustryRow).where(IndustryRow.code == "logistics")) is None:
        db.add(IndustryRow(code="logistics", name="Логистика"))
        db.commit()
    from app.infrastructure.db.models import ObjectTypeRow

    if db.scalar(select(ObjectTypeRow).where(ObjectTypeRow.code == "warehouse")) is None:
        save_object(
            db,
            code="warehouse",
            name="Склад",
            industries=["logistics"],
            processes=[code for code, _name in PROCESSES],
        )
    for code in PARSERS:
        if db.get(ParserSettingRow, code) is None:
            db.add(ParserSettingRow(code=code, enabled=True, hour=3))
    db.commit()
