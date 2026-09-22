"""run_pipeline(req, catalog, norms) -> CalcResponse (§4, §6.5).

Каждый шаг — чистая функция (input, catalog, norms) -> (result, list[TraceStep]).
Без обращений к БД, без сайд-эффектов, без чтения настроек.
vendor_queries приходят из match.
"""

from __future__ import annotations

from . import ENGINE_VERSION, cost, layout, match, rank, sim, size
from .models import CalcNorm, CalcRequest, CalcResponse, Catalog
from .prepare import prepare
from .resolve import Resolver


def _apply_overrides(norms: list[CalcNorm], overrides: dict[str, float]) -> list[CalcNorm]:
    """ТЗ 3.5.3: пользователь меняет редактируемые допущения."""
    if not overrides:
        return norms
    return [
        n.model_copy(update={"value": overrides[n.key]}) if n.editable and n.key in overrides else n
        for n in norms
    ]


def run_pipeline(req: CalcRequest, catalog: Catalog, norms: list[CalcNorm] | None = None) -> CalcResponse:
    norms = _apply_overrides(norms if norms is not None else catalog.norms, req.overrides)
    resolver = Resolver(catalog, norms)
    req, trace = prepare(req, resolver)

    candidates, vendor_queries, t = match.run(req, catalog, norms)
    trace += t

    options, t = size.run(req, candidates, catalog, norms)
    trace += t

    _econ, t = cost.run(req, options, catalog, norms)
    trace += t

    scenarios, t = rank.run(req, candidates, options, catalog, norms)
    trace += t

    target = next((s for s in scenarios if s.code == "per_task"), scenarios[0])
    plan, t = layout.run(req, target)
    trace += t

    shift, t = sim.run(req, target, plan)
    trace += t

    return CalcResponse(
        engine_version=ENGINE_VERSION,
        catalog_version_id=catalog.version_id,
        candidates=candidates,
        options=options,
        scenarios=scenarios,
        vendor_queries=vendor_queries,
        plan=plan,
        sim=shift,
        trace=trace,
    )
