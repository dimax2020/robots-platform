"""Шаг 1. MATCH — жёсткие ограничения, трёхзначно (§7.1)."""

from __future__ import annotations

from .models import CalcRequest, Candidate, Catalog, TraceStep


def run(req: CalcRequest, catalog: Catalog) -> tuple[list[Candidate], list[TraceStep]]:
    # TODO(E3): прогон rule_spec.hard по продуктам, привязанным к процессам задач.
    return [], []
