"""RuleSpec и безопасный вычислитель выражений (§4.2).

Никакого eval() от строки из БД: разбор через ast.parse(mode="eval") с белым списком узлов.
"""

from __future__ import annotations

import ast
import math
from typing import Any, Literal

from pydantic import BaseModel, Field


class HardRule(BaseModel):
    field: str
    op: Literal[">=", "<=", ">", "<", "==", "!=", "in"]
    ref: str  # "task.max_load_kg", "site.aisle_width_m"


class SoftRule(BaseModel):
    field: str
    weight: float
    dir: Literal["max", "min"] | None = None
    map: dict[str, float] | None = None


class Sizing(BaseModel):
    family: Literal["flow_cycle", "area_window", "station_robots", "count_window", "perimeter_rounds"]
    vars: dict[str, str] = Field(default_factory=dict)
    formula: str


class RuleSpec(BaseModel):
    solution_type: str
    hard: list[HardRule] = Field(default_factory=list)
    soft: list[SoftRule] = Field(default_factory=list)
    sizing: Sizing


_ALLOWED_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Compare,
    ast.Name,
    ast.Constant,
    ast.Call,
    ast.Attribute,
    ast.Load,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.USub,
    ast.UAdd,
    ast.Gt,
    ast.GtE,
    ast.Lt,
    ast.LtE,
    ast.Eq,
    ast.NotEq,
)

_ALLOWED_FUNCS: dict[str, Any] = {
    "ceil": math.ceil,
    "floor": math.floor,
    "min": min,
    "max": max,
    "abs": abs,
}


class UnsafeExpression(ValueError):
    pass


def _validate(tree: ast.AST) -> None:
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise UnsafeExpression(f"Недопустимый узел выражения: {type(node).__name__}")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
                raise UnsafeExpression("Разрешены только вызовы ceil/floor/min/max/abs")


def _resolve(node: ast.AST, ctx: dict[str, Any]) -> Any:
    if isinstance(node, ast.Expression):
        return _resolve(node.body, ctx)
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in ctx:
            return ctx[node.id]
        raise KeyError(f"Неизвестная переменная: {node.id}")
    if isinstance(node, ast.Attribute):
        base = _resolve(node.value, ctx)
        if isinstance(base, dict):
            return base[node.attr]
        return getattr(base, node.attr)
    if isinstance(node, ast.UnaryOp):
        v = _resolve(node.operand, ctx)
        return -v if isinstance(node.op, ast.USub) else +v
    if isinstance(node, ast.BinOp):
        a, b = _resolve(node.left, ctx), _resolve(node.right, ctx)
        ops = {
            ast.Add: lambda: a + b,
            ast.Sub: lambda: a - b,
            ast.Mult: lambda: a * b,
            ast.Div: lambda: a / b,
            ast.FloorDiv: lambda: a // b,
            ast.Mod: lambda: a % b,
            ast.Pow: lambda: a**b,
        }
        return ops[type(node.op)]()
    if isinstance(node, ast.Compare):
        left = _resolve(node.left, ctx)
        for op, comp in zip(node.ops, node.comparators, strict=True):
            right = _resolve(comp, ctx)
            ok = {
                ast.Gt: left > right,
                ast.GtE: left >= right,
                ast.Lt: left < right,
                ast.LtE: left <= right,
                ast.Eq: left == right,
                ast.NotEq: left != right,
            }[type(op)]
            if not ok:
                return False
            left = right
        return True
    if isinstance(node, ast.Call):
        args = [_resolve(a, ctx) for a in node.args]
        return _ALLOWED_FUNCS[node.func.id](*args)  # type: ignore[attr-defined]
    raise UnsafeExpression(f"Не обрабатывается: {type(node).__name__}")


def evaluate(expr: str, ctx: dict[str, Any]) -> Any:
    """Вычислить выражение из RuleSpec в контексте {task, site, robot, norm, ...}."""
    tree = ast.parse(expr, mode="eval")
    _validate(tree)
    return _resolve(tree, ctx)


def validate_rule_spec(raw: dict) -> RuleSpec:
    """Разобрать RuleSpec и проверить все выражения на безопасность — вызывается при старте (§11.1)."""
    spec = RuleSpec.model_validate(raw)
    for expr in [*spec.sizing.vars.values(), spec.sizing.formula]:
        _validate(ast.parse(expr, mode="eval"))
    return spec
