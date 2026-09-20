"""Шаг 3. COST — CAPEX / OPEX / эффект / окупаемость / ROI / TCO (§8.1)."""

from __future__ import annotations

from .models import CalcNorm, CalcRequest, Catalog, Economics, SizedOption, TraceStep


def run(
    req: CalcRequest, options: list[SizedOption], catalog: Catalog, norms: list[CalcNorm]
) -> tuple[Economics, list[TraceStep]]:
    # TODO(E4): формулы по таблице ТЗ 3.5.2, все коэффициенты [D] — из calc_norm с обоснованием.
    econ = Economics(
        capex_rub=0.0,
        opex_year_rub=0.0,
        effect_year_rub=0.0,
        tco_rub=0.0,
        horizon_years=req.horizon_years,
    )
    return econ, []
