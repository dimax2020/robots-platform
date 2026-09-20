"""Шаг 2. SIZE — сколько штук и по какой формуле, пять семейств (§7.3)."""

from __future__ import annotations

from .models import CalcNorm, CalcRequest, Candidate, Catalog, SizedOption, TraceStep


def run(
    req: CalcRequest, candidates: list[Candidate], catalog: Catalog, norms: list[CalcNorm]
) -> tuple[list[SizedOption], list[TraceStep]]:
    # TODO(E3): flow_cycle / area_window / station_robots / count_window / perimeter_rounds.
    return [], []
