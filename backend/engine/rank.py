"""Шаг 4. RANK — объяснимый скоринг и сборка трёх сценариев (§7.2, §8.2)."""

from __future__ import annotations

from .models import CalcNorm, CalcRequest, Candidate, Catalog, Scenario, SizedOption, TraceStep


def run(
    req: CalcRequest,
    candidates: list[Candidate],
    options: list[SizedOption],
    catalog: Catalog,
    norms: list[CalcNorm],
) -> tuple[list[Scenario], list[TraceStep]]:
    # TODO(E4): rule_spec.soft → нормировка [0,1] → взвешенная сумма; вклад каждого фактора в trace.
    scenarios = [
        Scenario(code="baseline", name="Без роботизации"),
        Scenario(code="per_task", name="Подбор по задачам"),
        Scenario(code="optimal", name="Оптимальный состав парка"),
    ]
    return scenarios, []
