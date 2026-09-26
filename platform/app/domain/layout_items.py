"""Объекты, которые процесс требует на схеме. Роли читает симуляция, подписи — пользователь."""

from __future__ import annotations

ROLES = {
    "pickup": "Откуда робот берёт груз",
    "dropoff": "Куда робот везёт груз",
    "charge": "Зарядка",
    "waypoint": "Точка обхода",
    "work_zone": "Зона работы",
    "obstacle": "Стационарное препятствие",
}

SHAPES = {"point": "Точка", "area": "Площадь"}
COUNT_RULES = {
    "fixed": "Ровно столько, сколько указано",
    "by_flow": "По потоку: станций хватает на поток площадки",
    "by_charge": "По доле времени на зарядке",
}


def item(key: str, label: str, role: str, shape: str = "point", count: int = 1, rule: str = "fixed", hint: str = "") -> dict:
    return {"key": key, "label": label, "role": role, "shape": shape, "min_count": count, "count_rule": rule, "hint": hint}


def _transport(pickup: str, dropoff: str, pickup_hint: str, dropoff_hint: str) -> list[dict]:
    return [
        item("pickup", pickup, "pickup", count=1, rule="by_flow", hint=pickup_hint),
        item("dropoff", dropoff, "dropoff", count=1, rule="by_flow", hint=dropoff_hint),
        item("charge", "Зарядка", "charge", count=1, rule="by_charge", hint="Место, где робот восстанавливает заряд. Ставьте в стороне от проезда."),
    ]


def _coverage(zone: str, zone_hint: str) -> list[dict]:
    return [
        item("zone", zone, "work_zone", shape="area", hint=zone_hint),
        item("charge", "База", "charge", count=1, rule="by_charge", hint="База, куда робот возвращается заряжаться и заливать воду."),
    ]


_PATROL = [
    item("waypoint", "Точка обхода", "waypoint", count=2, hint="Минимум две точки. Робот обходит их по кругу и делает остановку на каждой."),
    item("charge", "Зарядка", "charge", count=1, rule="by_charge", hint="Пост зарядки рядом с маршрутом."),
]

_PALLET = _transport("Приёмка", "Отгрузка", "Ворота или буфер, где робот забирает паллету.", "Место, куда паллету отвозят. Расстояние между приёмкой и отгрузкой — маршрут рейса.")

DEFAULT_ITEMS: dict[str, list[dict]] = {
    "pallet_transport": _PALLET,
    "pallet_storage": _transport("Приёмка", "Зона хранения", "Буфер приёмки паллет.", "Ряд хранения, куда паллету ставят."),
    "auto_pallet_storage": _transport("Приёмка", "Ячейки хранения", "Буфер перед автоматическим складом.", "Вход в ячейки хранения."),
    "rack_placement": _transport("Приёмка", "Ярусы стеллажей", "Буфер приёмки.", "Стеллаж, на ярусы которого ставят паллеты."),
    "cart_towing": _transport("Сцепка тележек", "Расцепка", "Где робот подцепляет тележки.", "Где тележки отцепляют."),
    "packing": _transport("Упаковка", "Паллетирование", "Стол упаковки.", "Место сборки паллеты."),
    "pallet_handling": _transport("Паллетирование", "Погрузка", "Готовые паллеты.", "Ворота погрузки."),
    "palletizing": _transport("Паллетирование", "Погрузка", "Готовые паллеты.", "Ворота погрузки."),
    "order_picking": _transport("Зона хранения", "Станция комплектации", "Полки, откуда робот везёт товар или полку.", "Станция, где человек собирает заказ."),
    "box_transport": _transport("Подача коробов", "Сортировка коробов", "Откуда идут короба.", "Куда короба разбирают."),
    "parcel_sorting": _transport("Вход сортировки", "Выход сортировки", "Индукция: посылку кладут на робота.", "Ячейка назначения."),
    "tote_delivery": _transport("Выдача тары", "Приём тары", "Откуда робот забирает тару.", "Куда тару привозят."),
    "apron_transport": _transport("Терминал", "Перрон", "Точка в терминале.", "Стоянка на перроне."),
    "baggage_transport": _transport("Приём багажа", "Выдача багажа", "Стойки приёма.", "Лента выдачи."),
    "passenger_service": _transport("Стойка", "Выход на посадку", "Стойка регистрации.", "Выход на посадку."),
    "medicine_delivery": _transport("Аптека", "Отделение", "Аптека или склад.", "Пост отделения."),
    "biomaterial_delivery": _transport("Отделение", "Лаборатория", "Пост, где берут пробы.", "Приём лаборатории."),
    "ward_service": _transport("Пост", "Палата", "Пост медсестры.", "Палата."),
    "floor_cleaning": _coverage("Зона уборки", "Площадь, которую робот убирает. Стеллажи внутри зоны он объезжает."),
    "floor_washing": _coverage("Зона мойки", "Площадь пола, которую робот моет."),
    "inventory": [
        item("zone", "Зона стеллажей", "work_zone", shape="area", hint="Стеллажи, которые робот сканирует. Ряды внутри отметьте препятствиями."),
        item("charge", "Зарядка", "charge", count=1, rule="by_charge", hint="Пост зарядки у края зоны."),
    ],
    "warehouse_inventory": [
        item("zone", "Зона стеллажей", "work_zone", shape="area", hint="Стеллажи, которые робот сканирует."),
        item("charge", "Зарядка", "charge", count=1, rule="by_charge", hint="Пост зарядки у края зоны."),
    ],
    "perimeter_security": _PATROL,
    "roof_inspection": _PATROL,
    "territory_inspection": _PATROL,
    "facade_washing": [item("zone", "Фасад", "work_zone", shape="area", hint="Участок фасада на схеме. Модели движения для мойки фасадов нет, роботы на схему не выходят.")],
}


def default_items(code: str) -> list[dict]:
    return [dict(row) for row in DEFAULT_ITEMS.get(code, [])]


def clean_items(rows: list[dict]) -> list[dict]:
    out = []
    seen = set()
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "").strip()
        label = str(row.get("label") or "").strip()
        role = str(row.get("role") or "")
        if not key or not label or role not in ROLES or key in seen:
            continue
        seen.add(key)
        shape = row.get("shape") if row.get("shape") in SHAPES else ("area" if role in {"work_zone", "obstacle"} else "point")
        rule = row.get("count_rule") if row.get("count_rule") in COUNT_RULES else "fixed"
        try:
            count = max(0, int(row.get("min_count") or 0))
        except (TypeError, ValueError):
            count = 1
        out.append({"key": key, "label": label, "role": role, "shape": shape, "min_count": count, "count_rule": rule, "hint": str(row.get("hint") or "")})
    return out
