"""Оптимальный состав парка — CP-SAT (§8.5).

CP-SAT работает только с целыми коэффициентами: цены в копейках, производительность и эффект ×100.
"""

from __future__ import annotations

from .models import CalcNorm, CalcRequest, Candidate, Catalog, SizedOption


def optimize_fleet(
    req: CalcRequest, candidates: list[Candidate], catalog: Catalog, norms: list[CalcNorm]
) -> list[SizedOption]:
    # TODO(E6):
    #   from ortools.sat.python import cp_model
    #   покрыть пиковый поток каждого процесса; ограничения по бюджету и площади; max Σ эффекта.
    raise NotImplementedError("Оптимизатор реализуется на этапе E6")
