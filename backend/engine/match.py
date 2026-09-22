"""Шаг 1. MATCH — жёсткие ограничения, трёхзначно (§6.2 E3_SPEC).

Лестницу достоверности не применяем: в hard участвует только паспорт продукта.
Если характеристики нет — unknown, а не fail. Если правая часть правила
не вычисляется (поля площадки нет) — правило пропускается без вердикта (§4.6).
"""

from __future__ import annotations

from uuid import UUID

from .models import (
    AttributeDef,
    AttrValue,
    CalcNorm,
    CalcRequest,
    Candidate,
    Catalog,
    Product,
    Source,
    Task,
    TraceStep,
    VendorQuery,
    Verdict,
)
from .resolve import _parse_number, _reliability_of_source, _vendor_source_label
from .rules import HardRule, RuleSpec, UnsafeExpression, evaluate

_SKIP = object()

_OPS = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


def run(
    req: CalcRequest, catalog: Catalog, norms: list[CalcNorm]
) -> tuple[list[Candidate], list[VendorQuery], list[TraceStep]]:
    types_by_code = {st.code: st for st in catalog.solution_types}
    products_by_type: dict[str, list[Product]] = {}
    for product in catalog.products:
        products_by_type.setdefault(product.solution_type_code, []).append(product)

    sources = {s.id: s for s in catalog.sources}
    labels = {d.key: d for d in catalog.attribute_defs}
    trl_min = _norm_value(norms, "trl_min_automatch")
    norm_ctx = {n.key: n.value for n in norms if "." not in n.key}
    manual = set(req.manual_product_ids)

    candidates: list[Candidate] = []
    vendor_queries: list[VendorQuery] = []
    seen_queries: set[tuple[UUID, str]] = set()
    trace: list[TraceStep] = []

    for task in req.tasks:
        if task.process_code not in catalog.process_solutions:
            name = task.name or task.process_code
            trace.append(
                TraceStep(
                    step="match",
                    message=(
                        f"Процесс «{name}» отсутствует в карте типов решений — "
                        "задача пропущена, кандидаты не подбирались."
                    ),
                )
            )
            continue

        type_codes = catalog.process_solutions[task.process_code]
        seen_products: set[UUID] = set()
        ctx = {"task": task, "site": req.site, "norm": norm_ctx}

        for type_code in type_codes:
            spec = _rule_spec(types_by_code.get(type_code), type_code)
            for product in products_by_type.get(type_code, []):
                if product.id in seen_products:
                    continue
                seen_products.add(product.id)

                blocked = _automatch_block(product, trl_min)
                if blocked is not None:
                    if product.id not in manual:
                        continue
                    trace.append(
                        TraceStep(
                            step="match",
                            product_id=product.id,
                            message=(
                                f"«{product.name}» добавлен вручную и допущен к подбору, "
                                f"хотя не проходит порог автоподбора: {blocked}."
                            ),
                        )
                    )

                candidate, steps = _match_product(product, task, spec, ctx, labels, sources)
                candidates.append(candidate)
                trace.extend(steps)

                if candidate.verdict == "unknown":
                    url = _any_source_url(product, sources)
                    for field in candidate.unknown:
                        key = (product.id, field)
                        if key in seen_queries:
                            continue
                        seen_queries.add(key)
                        vendor_queries.append(
                            VendorQuery(
                                product_id=product.id,
                                product_name=product.name,
                                manufacturer=product.manufacturer,
                                field=field,
                                source_url=url,
                            )
                        )

    return candidates, vendor_queries, trace


def _match_product(
    product: Product,
    task: Task,
    spec: RuleSpec,
    ctx: dict,
    labels: dict[str, AttributeDef],
    sources: dict[int, Source],
) -> tuple[Candidate, list[TraceStep]]:
    failed: list[str] = []
    unknown: list[str] = []
    steps: list[TraceStep] = []

    for rule in spec.hard:
        steps.append(
            _eval_hard(product, rule, ctx, labels, sources, failed, unknown)
        )

    if failed:
        verdict: Verdict = "fail"
    elif unknown:
        verdict = "unknown"
    else:
        verdict = "pass"

    steps.append(
        TraceStep(
            step="match",
            product_id=product.id,
            verdict=verdict,
            message=_verdict_message(product, task, verdict, failed, unknown, labels),
        )
    )
    return (
        Candidate(
            product_id=product.id,
            process_code=task.process_code,
            verdict=verdict,
            failed=failed,
            unknown=unknown,
            score=None,
        ),
        steps,
    )


def _eval_hard(
    product: Product,
    rule: HardRule,
    ctx: dict,
    labels: dict[str, AttributeDef],
    sources: dict[int, Source],
    failed: list[str],
    unknown: list[str],
) -> TraceStep:
    label = _label(rule.field, labels)
    unit = _unit(rule.field, labels, product.attrs.get(rule.field))

    if rule.op not in _OPS:
        return TraceStep(
            step="match",
            product_id=product.id,
            formula=rule.ref,
            unit=unit,
            message=f"Правило «{label}» пропущено: оператор «{rule.op}» не поддерживается.",
        )

    ref = _eval_ref(rule.ref, ctx)
    if ref is _SKIP:
        return TraceStep(
            step="match",
            product_id=product.id,
            formula=rule.ref,
            unit=unit,
            message=(
                f"Правило «{label}» пропущено: в профиле площадки нет данных "
                f"для выражения {rule.ref}, ограничивать нечем."
            ),
        )

    attr = product.attrs.get(rule.field)
    if attr is None or attr.status == "unknown":
        unknown.append(rule.field)
        return TraceStep(
            step="match",
            product_id=product.id,
            verdict="unknown",
            unit=unit,
            source=_attr_source(attr, sources),
            message=(
                f"«{label}» не опубликована в паспорте «{product.name}» — "
                "требуется уточнение у вендора."
            ),
        )

    if attr.status == "not_applicable":
        return TraceStep(
            step="match",
            product_id=product.id,
            verdict="pass",
            unit=unit,
            source=_attr_source(attr, sources),
            message=f"«{label}» не применима к «{product.name}» — ограничение не действует.",
        )

    parsed = _parse_number(attr.value)
    if parsed is None:
        unknown.append(rule.field)
        return TraceStep(
            step="match",
            product_id=product.id,
            verdict="unknown",
            unit=unit,
            source=_attr_source(attr, sources),
            message=(
                f"«{label}» у «{product.name}» задана, но значение не приводится к числу — "
                "нарушение не доказано, требуется уточнение у вендора."
            ),
        )

    left, _ = parsed
    ok = _OPS[rule.op](left, ref)
    if not ok:
        failed.append(rule.field)
        verdict: Verdict = "fail"
    else:
        verdict = "pass"

    return TraceStep(
        step="match",
        product_id=product.id,
        verdict=verdict,
        formula=f"{_fmt(left)} {rule.op} {_fmt(ref)}",
        value=left,
        unit=unit,
        source=_attr_source(attr, sources),
        message=_compare_message(ok, label, left, ref, unit, rule.op),
    )


def _eval_ref(expr: str, ctx: dict) -> object:
    try:
        value = evaluate(expr, ctx)
    except (TypeError, KeyError, AttributeError, ZeroDivisionError, OverflowError, UnsafeExpression):
        return _SKIP
    if value is None:
        return _SKIP
    if isinstance(value, bool):
        return _SKIP
    if isinstance(value, (int, float)):
        return float(value)
    parsed = _parse_number(value)
    if parsed is None:
        return _SKIP
    return parsed[0]


def _automatch_block(product: Product, trl_min: float | None) -> str | None:
    reasons: list[str] = []
    if product.availability == "rnd":
        reasons.append("доступность «НИОКР»")
    if product.trl is None:
        reasons.append("уровень готовности (УГТ) не указан")
    elif trl_min is not None and product.trl < trl_min:
        reasons.append(f"УГТ {product.trl} ниже порога автоподбора {_fmt(trl_min)}")
    return "; ".join(reasons) if reasons else None


def _rule_spec(st, type_code: str) -> RuleSpec:
    if st is None:
        return RuleSpec(
            solution_type=type_code,
            sizing={"family": "flow_cycle", "formula": "1"},
        )
    return RuleSpec.model_validate(st.rule_spec)


def _norm_value(norms: list[CalcNorm], key: str) -> float | None:
    for n in norms:
        if n.key == key:
            return n.value
    return None


def _label(key: str, labels: dict[str, AttributeDef]) -> str:
    defn = labels.get(key)
    return defn.label if defn is not None and defn.label else key


def _unit(key: str, labels: dict[str, AttributeDef], attr: AttrValue | None) -> str | None:
    if attr is not None and attr.unit:
        return attr.unit
    defn = labels.get(key)
    return defn.unit if defn is not None else None


def _attr_source(attr: AttrValue | None, sources: dict[int, Source]) -> str | None:
    if attr is None or attr.source_id is None:
        return None
    src = sources.get(attr.source_id)
    return _vendor_source_label(_reliability_of_source(src), src)


def _any_source_url(product: Product, sources: dict[int, Source]) -> str | None:
    for attr in product.attrs.values():
        if attr.source_id is None:
            continue
        src = sources.get(attr.source_id)
        if src is not None and src.url:
            return src.url
    return None


def _verdict_message(
    product: Product,
    task: Task,
    verdict: Verdict,
    failed: list[str],
    unknown: list[str],
    labels: dict[str, AttributeDef],
) -> str:
    task_name = task.name or task.process_code
    if verdict == "fail":
        fields = ", ".join(_label(k, labels) for k in failed)
        return f"«{product.name}» исключён из задачи «{task_name}»: не выполнены ограничения по полям {fields}."
    if verdict == "unknown":
        fields = ", ".join(_label(k, labels) for k in unknown)
        return f"«{product.name}» требует проверки по задаче «{task_name}»: не опубликованы {fields}."
    return f"«{product.name}» подходит для задачи «{task_name}»: все жёсткие ограничения выполнены."


def _compare_message(ok: bool, label: str, left: float, right: float, unit: str | None, op: str) -> str:
    u = f" {unit}" if unit else ""
    a, b = _fmt(left), _fmt(right)
    if op == ">=":
        return (
            f"{label} {a}{u} покрывает требуемые {b}{u}"
            if ok
            else f"{label} {a}{u} не покрывает требуемые {b}{u}"
        )
    if op == "<=":
        return (
            f"{label} {a}{u} укладывается в ограничение площадки {b}{u}"
            if ok
            else f"{label} {a}{u} превышает ограничение площадки {b}{u}"
        )
    if op == ">":
        return f"{label} {a}{u} больше {b}{u}" if ok else f"{label} {a}{u} не больше {b}{u}"
    if op == "<":
        return f"{label} {a}{u} меньше {b}{u}" if ok else f"{label} {a}{u} не меньше {b}{u}"
    if op == "==":
        return f"{label} {a}{u} совпадает с {b}{u}" if ok else f"{label} {a}{u} не совпадает с {b}{u}"
    return f"{label} {a}{u} отличается от {b}{u}" if ok else f"{label} {a}{u} равна {b}{u}, хотя должна отличаться"


def _fmt(value: float) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return f"{value:g}"
