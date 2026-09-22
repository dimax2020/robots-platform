"""Шаг 4. RANK — объяснимый скоринг и сборка трёх сценариев (§6.4, §4.4).

Скоринг только для verdict == "pass". Candidate.score мутируется на месте.
Нормировка dir — min-max среди кандидатов того же процесса.
Экономика не считается: baseline и optimal пустые, economics у всех None.
"""

from __future__ import annotations

import ast
import math
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal
from uuid import UUID

from pydantic import ValidationError

from .models import (
    CalcNorm,
    CalcRequest,
    Candidate,
    Catalog,
    Product,
    Scenario,
    SizedOption,
    SolutionType,
    TraceStep,
)
from .resolve import Resolved, Resolver
from .rules import RuleSpec, UnsafeExpression, validate_rule_spec

_PSEUDO_LABELS: dict[str, str] = {
    "trl": "УГТ",
    "availability": "Статус зрелости",
    "reliability": "Достоверность данных",
    "has_case": "Кейс на таком же процессе",
    "data_completeness": "Полнота данных",
}

_AVAIL_RU = {
    "operation": "в эксплуатации",
    "piloting": "пилотирование",
    "rnd": "НИОКР",
}

_RELIABILITY_RANK = {"A": 0, "B": 1, "C": 2, "D": 3}

_SCENARIO_NAMES: dict[str, str] = {
    "baseline": "Без роботизации",
    "per_task": "Подбор по задачам",
    "optimal": "Оптимальный состав парка",
}


@dataclass
class _Factor:
    field: str
    label: str
    weight: float
    kind: Literal["dir", "map"]
    direction: Literal["max", "min"] | None
    raw_num: float | None
    raw_key: str | None
    missing: bool
    unknown_map: bool
    display: str
    source: str | None
    norm: float = 0.0
    contrib: float = 0.0
    spread_zero: bool = False
    process_n: int = 1


@dataclass
class _Prepared:
    cand: Candidate
    product: Product
    spec: RuleSpec
    factors: list[_Factor] = field(default_factory=list)
    score: float = 0.0


def run(
    req: CalcRequest,
    candidates: list[Candidate],
    options: list[SizedOption],
    catalog: Catalog,
    norms: list[CalcNorm],
) -> tuple[list[Scenario], list[TraceStep]]:
    resolver = Resolver(catalog, norms)
    products = {p.id: p for p in catalog.products}
    types: dict[str, SolutionType] = {st.code: st for st in catalog.solution_types}
    labels = {d.key: d.label for d in catalog.attribute_defs}

    prepared: list[_Prepared] = []
    trace: list[TraceStep] = []

    for cand in candidates:
        if cand.verdict != "pass":
            continue
        item, errors = _prepare_one(cand, products, types, labels, catalog, resolver)
        if errors:
            trace.extend(errors)
            continue
        if item is not None:
            prepared.append(item)

    _normalize_dir(prepared)
    for item in prepared:
        item.score = 0.0
        for fac in item.factors:
            fac.contrib = fac.weight * fac.norm
            item.score += fac.contrib
        item.cand.score = item.score
        for fac in item.factors:
            trace.append(_factor_trace(item, fac))
        trace.append(_total_trace(item))

    scenarios = _build_scenarios(req, prepared, options, products)
    trace.extend(_scenario_stubs())
    return scenarios, trace


def _prepare_one(
    cand: Candidate,
    products: dict[UUID, Product],
    types: dict[str, SolutionType],
    labels: dict[str, str],
    catalog: Catalog,
    resolver: Resolver,
) -> tuple[_Prepared | None, list[TraceStep]]:
    product = products.get(cand.product_id)
    if product is None:
        return None, [
            TraceStep(
                step="rank",
                product_id=cand.product_id,
                verdict="unknown",
                message="Продукт из кандидатов отсутствует в каталоге — балл не считаем.",
            )
        ]
    st = types.get(product.solution_type_code)
    if st is None:
        return None, [
            TraceStep(
                step="rank",
                product_id=product.id,
                verdict="unknown",
                message=(
                    f"Для продукта «{product.name}» нет типа решения "
                    f"{product.solution_type_code} в каталоге — балл не считаем."
                ),
            )
        ]
    try:
        spec = validate_rule_spec(st.rule_spec)
    except (ValidationError, ValueError, SyntaxError, UnsafeExpression) as exc:
        return None, [
            TraceStep(
                step="rank",
                product_id=product.id,
                verdict="unknown",
                message=(
                    f"Правила типа решения {product.solution_type_code} для «{product.name}» "
                    f"некорректны: {exc}."
                ),
            )
        ]

    factors = [_eval_factor(rule, product, cand.process_code, spec, labels, catalog, resolver) for rule in spec.soft]
    return _Prepared(cand=cand, product=product, spec=spec, factors=factors), []


def _eval_factor(
    rule,
    product: Product,
    process_code: str,
    spec: RuleSpec,
    labels: dict[str, str],
    catalog: Catalog,
    resolver: Resolver,
) -> _Factor:
    label = _PSEUDO_LABELS.get(rule.field) or labels.get(rule.field) or rule.field
    kind: Literal["dir", "map"] = "map" if rule.map is not None else "dir"
    direction: Literal["max", "min"] | None = None if kind == "map" else (rule.dir or "max")

    raw_num: float | None = None
    raw_key: str | None = None
    missing = False
    display = ""
    source: str | None = None
    resolved: Resolved | None = None

    if rule.field == "trl":
        raw_num = float(product.trl) if product.trl is not None else 0.0
        display = _fmt_display(raw_num)
    elif rule.field == "availability":
        raw_key = product.availability
        display = f"«{_AVAIL_RU.get(raw_key, raw_key)}»"
    elif rule.field == "reliability":
        raw_key = _worst_reliability(product, spec, resolver)
        display = raw_key
    elif rule.field == "has_case":
        raw_num = 1.0 if process_code in product.case_process_codes else 0.0
        display = "есть" if raw_num == 1.0 else "нет"
    elif rule.field == "data_completeness":
        raw_num = _data_completeness(product, catalog)
        display = _fmt_display(raw_num)
    else:
        resolved = resolver.robot(product, rule.field)
        if resolved is None:
            missing = True
            display = ""
        else:
            raw_num = resolved.value
            raw_key = _fmt_display(resolved.value).replace(",", ".")
            display = _fmt_display(resolved.value)
            source = resolved.source_label

    unknown_map = False
    norm = 0.0
    if kind == "map":
        key = raw_key if raw_key is not None else ""
        if missing or key not in rule.map:
            unknown_map = not missing
            norm = 0.0
        else:
            norm = float(rule.map[key])

    return _Factor(
        field=rule.field,
        label=label,
        weight=rule.weight,
        kind=kind,
        direction=direction,
        raw_num=raw_num,
        raw_key=raw_key,
        missing=missing,
        unknown_map=unknown_map,
        display=display,
        source=source,
        norm=norm,
    )


def _worst_reliability(product: Product, spec: RuleSpec, resolver: Resolver) -> str:
    keys = _robot_keys([*spec.sizing.vars.values(), spec.sizing.formula])
    if not keys:
        return "D"
    letters: list[str] = []
    for key in keys:
        resolved = resolver.robot(product, key)
        if resolved is not None:
            letters.append(resolved.reliability)
    if not letters:
        return "D"
    return max(letters, key=lambda letter: _RELIABILITY_RANK.get(letter, 99))


def _data_completeness(product: Product, catalog: Catalog) -> float:
    defs = catalog.attribute_defs
    if not defs:
        return 0.0
    filled = 0
    for d in defs:
        attr = product.attrs.get(d.key)
        if attr is not None and attr.status in ("known", "not_applicable"):
            filled += 1
    return filled / len(defs)


def _robot_keys(exprs: list[str]) -> list[str]:
    """Ключи robot.X из выражений sizing — без зашитого списка, как в size.py."""
    keys: list[str] = []
    seen: set[str] = set()
    for expr in exprs:
        try:
            tree = ast.parse(expr, mode="eval")
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "robot"
                and node.attr not in seen
            ):
                seen.add(node.attr)
                keys.append(node.attr)
    return keys


def _normalize_dir(prepared: list[_Prepared]) -> None:
    buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    sizes: dict[str, int] = defaultdict(int)
    for item in prepared:
        sizes[item.cand.process_code] += 1
        for fac in item.factors:
            if fac.kind != "dir" or fac.missing or fac.raw_num is None:
                continue
            buckets[(item.cand.process_code, fac.field)].append(fac.raw_num)

    ranges = {key: (min(vals), max(vals)) for key, vals in buckets.items()}

    for item in prepared:
        n = sizes[item.cand.process_code]
        for fac in item.factors:
            fac.process_n = n
            if fac.kind == "map":
                continue
            if fac.missing or fac.raw_num is None:
                fac.norm = 0.0
                fac.spread_zero = False
                continue
            lo, hi = ranges.get((item.cand.process_code, fac.field), (fac.raw_num, fac.raw_num))
            if hi == lo:
                fac.norm = 1.0
                fac.spread_zero = True
            elif fac.direction == "min":
                fac.norm = (hi - fac.raw_num) / (hi - lo)
                fac.spread_zero = False
            else:
                fac.norm = (fac.raw_num - lo) / (hi - lo)
                fac.spread_zero = False


def _factor_trace(item: _Prepared, fac: _Factor) -> TraceStep:
    verdict = "unknown" if fac.missing else "pass"
    return TraceStep(
        step="rank",
        product_id=item.product.id,
        verdict=verdict,
        formula=f"{fac.weight:.2f} * {fac.norm:.2f} = {fac.contrib:.3f}",
        value=fac.contrib,
        source=fac.source,
        message=_factor_message(fac),
    )


def _factor_message(fac: _Factor) -> str:
    w_ru = _ru_trim(fac.weight)
    c_ru = _fmt_ru(fac.contrib, 3)
    if fac.missing:
        return (
            f"«{fac.label}» не найдена ни в паспорте, ни среди аналогов, ни в нормативах "
            f"— фактор даёт 0"
        )
    if fac.kind == "map" and fac.unknown_map:
        shown = fac.display if fac.display.startswith("«") else f"«{fac.display}»"
        return f"{fac.label} {shown} нет в шкале, вклад {c_ru} из {w_ru}"
    if fac.kind == "map":
        return f"{fac.label} {fac.display} — вклад {c_ru} из {w_ru}"
    if fac.spread_zero and fac.process_n <= 1:
        rank_phrase = "единственный кандидат процесса"
    elif fac.spread_zero:
        rank_phrase = "все кандидаты процесса равны"
    elif fac.norm >= 1.0 - 1e-12:
        rank_phrase = "лучший среди кандидатов процесса"
    elif fac.norm <= 1e-12:
        rank_phrase = "худший среди кандидатов процесса"
    else:
        rank_phrase = "среди кандидатов процесса"
    return f"{fac.label} {fac.display} — {rank_phrase}, вклад {c_ru} из {w_ru}"


def _total_trace(item: _Prepared) -> TraceStep:
    if item.factors:
        parts = " + ".join(f"{fac.contrib:.3f}" for fac in item.factors)
        formula = f"{parts} = {item.score:.3f}"
    else:
        formula = f"0 = {item.score:.3f}"
    return TraceStep(
        step="rank",
        product_id=item.product.id,
        verdict="pass",
        formula=formula,
        value=item.score,
        message=(
            f"Итоговый балл «{item.product.name}» на процессе {item.cand.process_code}: "
            f"{_fmt_ru(item.score, 3)}"
        ),
    )


def _build_scenarios(
    req: CalcRequest,
    prepared: list[_Prepared],
    options: list[SizedOption],
    products: dict[UUID, Product],
) -> list[Scenario]:
    by_process: dict[str, list[_Prepared]] = defaultdict(list)
    for item in prepared:
        by_process[item.cand.process_code].append(item)

    order: list[str] = []
    seen: set[str] = set()
    for task in req.tasks:
        if task.process_code not in seen:
            seen.add(task.process_code)
            order.append(task.process_code)
    for item in prepared:
        if item.cand.process_code not in seen:
            seen.add(item.cand.process_code)
            order.append(item.cand.process_code)

    picked: list[SizedOption] = []
    entered_ids: list[UUID] = []
    for process_code in order:
        group = by_process.get(process_code)
        if not group:
            continue
        best = max(group, key=lambda it: it.score)
        opt = next(
            (
                o
                for o in options
                if o.product_id == best.product.id and o.process_code == process_code
            ),
            None,
        )
        if opt is None:
            continue
        picked.append(opt)
        entered_ids.append(best.product.id)

    raas = any(_raas_available(products.get(pid)) for pid in entered_ids)
    return [
        Scenario(code="baseline", name=_SCENARIO_NAMES["baseline"]),
        Scenario(
            code="per_task",
            name=_SCENARIO_NAMES["per_task"],
            options=picked,
            raas_available=raas,
        ),
        Scenario(code="optimal", name=_SCENARIO_NAMES["optimal"]),
    ]


def _raas_available(product: Product | None) -> bool:
    if product is None:
        return False
    attr = product.attrs.get("raas_available")
    return attr is not None and attr.value is True


def _scenario_stubs() -> list[TraceStep]:
    return [
        TraceStep(
            step="rank",
            message=(
                "Сценарий «Без роботизации»: состав парка и экономика появятся на шаге экономики. "
                "Сейчас это заглушка — в E3 экономика не считается."
            ),
        ),
        TraceStep(
            step="rank",
            message=(
                "Сценарий «Оптимальный состав парка»: состав и экономика появятся на шаге экономики. "
                "Сейчас это заглушка — оптимизатор и экономика отложены на E4."
            ),
        ),
    ]


def _fmt_display(value: float) -> str:
    if not math.isfinite(value):
        return str(value)
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    cleaned = float(format(value, ".12g"))
    text = f"{cleaned:.4f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _fmt_ru(value: float, decimals: int) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def _ru_trim(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")
