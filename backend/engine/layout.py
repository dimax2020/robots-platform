"""Шаг 5. LAYOUT — зоны, маршруты, расстановка (§10)."""

from __future__ import annotations

from .models import CalcRequest, Plan, Route, Scenario, TraceStep, Zone


def run(req: CalcRequest, scenario: Scenario) -> tuple[Plan, list[TraceStep]]:
    # TODO(E5): контур из параметров или пресет, автотрассировка по манхэттенской метрике.
    plan = Plan(
        width_m=60,
        height_m=40,
        zones=[
            Zone(id="receiving", kind="receiving", x=2, y=2, w=12, h=8, label="Приёмка"),
            Zone(id="storage", kind="storage", x=20, y=2, w=36, h=26, label="Хранение"),
            Zone(id="shipping", kind="shipping", x=2, y=30, w=12, h=8, label="Отгрузка"),
            Zone(id="charging", kind="charging", x=20, y=32, w=8, h=6, label="Зарядка"),
        ],
        routes=[
            Route(
                id="r1",
                from_zone="receiving",
                to_zone="storage",
                points=[(8, 6), (38, 6), (38, 15)],
                length_m=39,
            ),
        ],
        charging_points=[(22, 35), (26, 35)],
    )
    return plan, [
        TraceStep(step="layout", message="План построен по пресету «склад» (заглушка)")
    ]
