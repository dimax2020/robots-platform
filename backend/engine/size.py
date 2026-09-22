"""Шаг 2. SIZE — сколько штук и по какой формуле, пять семейств (§6.3, §4.5).

Вход уже подготовлен в prepare.py (суточный поток, t_load/t_unload, поля площадки).
Здесь только расчёт количества по sizing RuleSpec.
"""

from __future__ import annotations

import ast
import math
from typing import Any

from pydantic import ValidationError

from .models import CalcNorm, CalcRequest, Candidate, Catalog, Product, SizedOption, Task, TraceStep
from .resolve import Resolved, Resolver
from .rules import Sizing, UnsafeExpression, evaluate, validate_rule_spec

_BINOPS = {
    ast.Add: "+",
    ast.Sub: "-",
    ast.Mult: "*",
    ast.Div: "/",
    ast.FloorDiv: "//",
    ast.Mod: "%",
    ast.Pow: "**",
}
_PREC = {
    ast.Pow: 4,
    ast.Mult: 2,
    ast.Div: 2,
    ast.FloorDiv: 2,
    ast.Mod: 2,
    ast.Add: 1,
    ast.Sub: 1,
}
_UNARY_PREC = 3


def run(
    req: CalcRequest, candidates: list[Candidate], catalog: Catalog, norms: list[CalcNorm]
) -> tuple[list[SizedOption], list[TraceStep]]:
    resolver = Resolver(catalog, norms)
    products = {p.id: p for p in catalog.products}
    types = {st.code: st for st in catalog.solution_types}

    options: list[SizedOption] = []
    trace: list[TraceStep] = []

    for cand in candidates:
        if cand.verdict != "pass":
            continue
        product = products.get(cand.product_id)
        if product is None:
            trace.append(
                TraceStep(
                    step="size",
                    product_id=cand.product_id,
                    verdict="unknown",
                    message="Продукт из кандидатов отсутствует в каталоге — количество не считаем.",
                )
            )
            continue
        task = next((t for t in req.tasks if t.process_code == cand.process_code), None)
        if task is None:
            trace.append(
                TraceStep(
                    step="size",
                    product_id=product.id,
                    verdict="unknown",
                    message=(
                        f"Задача процесса {cand.process_code} для «{product.name}» "
                        f"не найдена — количество не считаем."
                    ),
                )
            )
            continue
        st = types.get(product.solution_type_code)
        if st is None:
            trace.append(
                TraceStep(
                    step="size",
                    product_id=product.id,
                    verdict="unknown",
                    message=(
                        f"Для продукта «{product.name}» нет типа решения "
                        f"{product.solution_type_code} в каталоге — количество не считаем."
                    ),
                )
            )
            continue
        try:
            spec = validate_rule_spec(st.rule_spec)
        except (ValidationError, ValueError, SyntaxError, UnsafeExpression) as exc:
            trace.append(
                TraceStep(
                    step="size",
                    product_id=product.id,
                    verdict="unknown",
                    message=(
                        f"Правила типа решения {product.solution_type_code} для «{product.name}» "
                        f"некорректны: {exc}."
                    ),
                )
            )
            continue

        option, steps = _size_one(req, cand, product, task, spec.sizing, resolver, norms)
        trace.extend(steps)
        if option is not None:
            options.append(option)

    return options, trace


def _size_one(
    req: CalcRequest,
    cand: Candidate,
    product: Product,
    task: Task,
    sizing: Sizing,
    resolver: Resolver,
    norms: list[CalcNorm],
) -> tuple[SizedOption | None, list[TraceStep]]:
    task_dict = task.model_dump()
    site_dict = req.site.model_dump()
    norm_dict = _flat_norms(norms, product.solution_type_code)

    robot_keys = _robot_keys([*sizing.vars.values(), sizing.formula])
    robot_dict: dict[str, float] = {}
    ladder: list[Resolved] = []
    for key in robot_keys:
        resolved = resolver.robot(product, key)
        if resolved is None:
            return None, [
                TraceStep(
                    step="size",
                    product_id=product.id,
                    verdict="unknown",
                    message=(
                        f"Характеристика «{key}» продукта «{product.name}» не найдена "
                        f"ни в паспорте, ни среди аналогов, ни в нормативах — количество не считаем."
                    ),
                )
            ]
        robot_dict[key] = resolved.value
        if resolved.origin in ("analogue_median", "assumption_norm"):
            ladder.append(resolved)

    eval_ctx: dict[str, Any] = {
        "task": task_dict,
        "site": site_dict,
        "robot": robot_dict,
        "norm": norm_dict,
    }
    vars_values: dict[str, Any] = {}
    for name, expr in sizing.vars.items():
        value, err = _safe_eval(expr, eval_ctx, product=product, label=f"переменной «{name}»")
        if err is not None:
            return None, [err]
        vars_values[name] = value
        eval_ctx[name] = value

    result, err = _safe_eval(sizing.formula, eval_ctx, product=product, label="формулы")
    if err is not None:
        return None, [err]

    if isinstance(result, bool) or not isinstance(result, (int, float)):
        return None, [
            TraceStep(
                step="size",
                product_id=product.id,
                verdict="unknown",
                message=(
                    f"Формула семейства {sizing.family} для «{product.name}» "
                    f"вернула не число ({result!r}) — продукт пропущен."
                ),
            )
        ]

    count = int(result)
    if count <= 0:
        return None, [
            TraceStep(
                step="size",
                product_id=product.id,
                verdict="unknown",
                formula=_fmt_num(result),
                value=float(result),
                unit="шт",
                message=(
                    f"Формула семейства {sizing.family} для «{product.name}» дала {count} — "
                    f"признак незаполненного правила, количество не считаем."
                ),
            )
        ]

    substituted = _substitute(sizing.formula, eval_ctx)
    formula_text = f"{substituted} = {count}"
    steps = [
        TraceStep(
            step="size",
            product_id=product.id,
            value=resolved.value,
            unit=resolved.unit,
            source=resolved.source_label,
            message=resolved.message,
        )
        for resolved in ladder
    ]
    steps.append(
        TraceStep(
            step="size",
            product_id=product.id,
            verdict="pass",
            formula=formula_text,
            value=count,
            unit="шт",
            message=_summary_message(sizing.family, count, task_dict, site_dict, vars_values, norm_dict),
        )
    )
    return (
        SizedOption(
            product_id=product.id,
            process_code=cand.process_code,
            count=count,
            formula=formula_text,
            family=sizing.family,
        ),
        steps,
    )


def _flat_norms(norms: list[CalcNorm], solution_type_code: str) -> dict[str, float]:
    """Плоские ключи без точек; норматив типа решения перекрывает общий с тем же ключом."""
    general: dict[str, float] = {}
    typed: dict[str, float] = {}
    for n in norms:
        if "." in n.key:
            continue
        if n.solution_type_code is None:
            general[n.key] = n.value
        elif n.solution_type_code == solution_type_code:
            typed[n.key] = n.value
    return {**general, **typed}


def _robot_keys(exprs: list[str]) -> list[str]:
    """Ключи robot.X из выражений sizing — без зашитого списка."""
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


def _safe_eval(
    expr: str, ctx: dict[str, Any], *, product: Product, label: str
) -> tuple[Any, TraceStep | None]:
    try:
        return evaluate(expr, ctx), None
    except ZeroDivisionError:
        return None, TraceStep(
            step="size",
            product_id=product.id,
            verdict="unknown",
            formula=expr,
            message=(
                f"Расчёт {label} для «{product.name}» прерван: деление на ноль. "
                f"Количество не считаем."
            ),
        )
    except TypeError:
        return None, TraceStep(
            step="size",
            product_id=product.id,
            verdict="unknown",
            formula=expr,
            message=(
                f"Расчёт {label} для «{product.name}» прерван: во входе формулы есть пустое значение. "
                f"Количество не считаем."
            ),
        )
    except (KeyError, AttributeError) as exc:
        return None, TraceStep(
            step="size",
            product_id=product.id,
            verdict="unknown",
            formula=expr,
            message=(
                f"Расчёт {label} для «{product.name}» прерван: нет значения «{exc}». "
                f"Количество не считаем."
            ),
        )


def _fmt_num(value: Any) -> str:
    if value is None:
        return "None"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        cleaned = float(format(value, ".12g"))
        if abs(cleaned - round(cleaned)) < 1e-9:
            return str(int(round(cleaned)))
        if cleaned == 0:
            return "0"
        exp = math.floor(math.log10(abs(cleaned)))
        decimals = max(0, 3 - exp)
        rounded = round(cleaned, decimals)
        if abs(rounded - round(rounded)) < 1e-9:
            return str(int(round(rounded)))
        return f"{rounded:.{decimals}f}".rstrip("0").rstrip(".")
    return str(value)


def _fmt_ru(value: Any) -> str:
    return _fmt_num(value).replace(".", ",")


def _substitute(expr: str, ctx: dict[str, Any]) -> str:
    tree = ast.parse(expr, mode="eval")
    return _render(tree.body, ctx)


def _render(node: ast.AST, ctx: dict[str, Any], parent_prec: int = 0, *, is_right: bool = False) -> str:
    if isinstance(node, ast.Constant):
        return _fmt_num(node.value)
    if isinstance(node, ast.Name):
        if node.id in ctx:
            value = ctx[node.id]
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return _fmt_num(value)
        return node.id
    if isinstance(node, ast.Attribute):
        value = _attr_value(node, ctx)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return _fmt_num(value)
        if value is not None:
            return _fmt_num(value)
        return f"{_render(node.value, ctx)}.{node.attr}"
    if isinstance(node, ast.UnaryOp):
        inner = _render(node.operand, ctx, _UNARY_PREC)
        op = "-" if isinstance(node.op, ast.USub) else "+"
        text = f"{op}{inner}"
        return f"({text})" if _UNARY_PREC < parent_prec else text
    if isinstance(node, ast.BinOp):
        prec = _PREC.get(type(node.op), 0)
        op = _BINOPS[type(node.op)]
        left = _render(node.left, ctx, prec, is_right=False)
        right = _render(node.right, ctx, prec, is_right=True)
        text = f"{left} {op} {right}"
        right_assoc = isinstance(node.op, ast.Pow)
        wrap = prec < parent_prec or (prec == parent_prec and prec != 0 and (not is_right if right_assoc else is_right))
        return f"({text})" if wrap else text
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        args = ", ".join(_render(a, ctx) for a in node.args)
        return f"{node.func.id}({args})"
    if isinstance(node, ast.Compare):
        parts = [_render(node.left, ctx)]
        op_map = {ast.Gt: ">", ast.GtE: ">=", ast.Lt: "<", ast.LtE: "<=", ast.Eq: "==", ast.NotEq: "!="}
        for op, comp in zip(node.ops, node.comparators, strict=True):
            parts.append(op_map[type(op)])
            parts.append(_render(comp, ctx))
        return " ".join(parts)
    return ast.unparse(node)


def _attr_value(node: ast.Attribute, ctx: dict[str, Any]) -> Any:
    if isinstance(node.value, ast.Name):
        base = ctx.get(node.value.id)
        if isinstance(base, dict):
            return base.get(node.attr)
        if base is not None:
            return getattr(base, node.attr, None)
        return None
    if isinstance(node.value, ast.Attribute):
        inner = _attr_value(node.value, ctx)
        if isinstance(inner, dict):
            return inner.get(node.attr)
        if inner is not None:
            return getattr(inner, node.attr, None)
    return None


def _summary_message(
    family: str,
    count: int,
    task: dict[str, Any],
    site: dict[str, Any],
    vars_values: dict[str, Any],
    norm: dict[str, float],
) -> str:
    reserve = _fmt_ru(norm.get("n_reserve", 1))
    k_util = _fmt_ru(norm.get("k_util"))
    if family == "flow_cycle":
        return (
            f"Для потока {_fmt_ru(task.get('flow_per_hour'))} паллет/ч нужно {count} единиц: "
            f"цикл {_fmt_ru(vars_values.get('t_cycle'))} с, "
            f"доступность {_fmt_ru(vars_values.get('uptime'))}, "
            f"загрузка {k_util}, плюс резерв {reserve}"
        )
    if family == "area_window":
        return (
            f"Для площади {_fmt_ru(site.get('clean_area_m2'))} м² нужно {count} единиц: "
            f"производительность {_fmt_ru(vars_values.get('q'))} м²/ч, "
            f"окно {_fmt_ru(vars_values.get('t_window'))} ч, "
            f"проходов {_fmt_ru(norm.get('f_passes'))}, плюс резерв {reserve}"
        )
    if family == "count_window":
        return (
            f"Для {_fmt_ru(site.get('pallet_places'))} паллетомест нужно {count} единиц: "
            f"производительность {_fmt_ru(vars_values.get('q'))} мест/ч, "
            f"окно {_fmt_ru(vars_values.get('t_window'))} ч, "
            f"частота {_fmt_ru(norm.get('f_frequency'))}, плюс резерв {reserve}"
        )
    if family == "station_robots":
        return (
            f"Для потока {_fmt_ru(task.get('flow_per_hour'))} операций/ч нужно {count} единиц: "
            f"{_fmt_ru(vars_values.get('stations'))} станций, плюс резерв {reserve}"
        )
    if family == "perimeter_rounds":
        return (
            f"Для {_fmt_ru(norm.get('rounds_required'))} обходов нужно {count} единиц: "
            f"обход {_fmt_ru(vars_values.get('t_round'))} с, "
            f"окно {_fmt_ru(vars_values.get('t_window'))} с, "
            f"загрузка {k_util}, плюс резерв {reserve}"
        )
    return f"Для этой задачи нужно {count} единиц, плюс резерв {reserve}"
