"""Чистые типы. Без ввода-вывода."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.formula import FormulaError, MissingName, build_env, evaluate
from app.domain.specs import CANON_LABELS

_LABELS = {
    **CANON_LABELS,
    "proizvoditelnost": "Производительность",
    "uroven_shuma": "Уровень шума",
}


def _label(name: str) -> str:
    return _LABELS.get(name, name)


@dataclass(frozen=True)
class ParsedRecord:
    platform: str
    external_id: str
    source_kind: str
    source_publisher: str
    source_url: str | None
    parser_code: str | None
    name: str
    manufacturer: str | None = None
    price_rub: float | None = None
    availability: str | None = None
    trl: int | None = None
    image_url: str | None = None
    summary: str | None = None
    attributes: dict[str, str] = field(default_factory=dict)
    attribute_labels: dict[str, str] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OverlayRow:
    product_slug: str
    attr_key: str
    label: str
    value: str
    status: str
    source_kind: str
    source_url: str | None
    quote: str | None


@dataclass(frozen=True)
class FilterRule:
    name: str
    object_keys: tuple[str, ...]
    robot_keys: tuple[str, ...]
    op: str
    mode: str
    inputs: tuple[tuple[str, str], ...] = ()
    formula: str = ""


@dataclass(frozen=True)
class RobotView:
    id: str
    name: str
    slug: str
    attrs: dict[str, Any]
    image_url: str | None = None


@dataclass(frozen=True)
class MatchHit:
    product_id: str
    name: str
    slug: str
    process_code: str
    process_name: str
    verdict: str
    notes: tuple[str, ...]
    image_url: str | None = None


def match_robots(
    *,
    process_code: str,
    process_name: str,
    site: dict[str, Any],
    rules: tuple[FilterRule, ...],
    robots: tuple[RobotView, ...],
    bindings: dict[str, str] | None = None,
) -> list[MatchHit]:
    """Вердикт по каждому роботу процесса. Базы здесь нет."""
    linked = bindings or {}
    return [
        _one(process_code, process_name, site, rules, robot, linked)
        for robot in robots
    ]


def _one(
    process_code: str,
    process_name: str,
    site: dict[str, Any],
    rules: tuple[FilterRule, ...],
    robot: RobotView,
    bindings: dict[str, str],
) -> MatchHit:
    fails: list[str] = []
    unknowns: list[str] = []
    conditions: list[str] = []
    for rule in rules:
        if rule.formula:
            _formula_rule(rule, site, bindings, robot, fails, unknowns, conditions)
            continue
        pairs = _pairs(rule)
        for object_key, robot_key in pairs:
            site_value = site.get(object_key)
            if site_value is None or site_value == "":
                continue
            robot_value = robot.attrs.get(robot_key)
            if robot_value is None or robot_value == "":
                unknowns.append(f"{rule.name}: нет «{robot_key}»")
                continue
            ok, detail = _compare(rule.op, robot_value, site_value)
            if ok is None:
                unknowns.append(f"{rule.name}: {detail}")
                continue
            if ok:
                continue
            note = f"{rule.name}: {robot_key} {rule.op} {object_key} не выполнено ({detail})"
            if rule.mode == "conditional":
                conditions.append(note)
            else:
                fails.append(note)
    if fails:
        verdict, notes = "fail", tuple(fails + unknowns + conditions)
    elif unknowns:
        verdict, notes = "unknown", tuple(unknowns + conditions)
    elif conditions:
        verdict, notes = "conditional", tuple(conditions)
    else:
        verdict, notes = "pass", ()
    return MatchHit(robot.id, robot.name, robot.slug, process_code, process_name, verdict, notes, robot.image_url)


def _formula_rule(rule: FilterRule, site: dict, bindings: dict[str, str], robot: RobotView, fails: list[str], unknowns: list[str], conditions: list[str]) -> None:
    input_keys = {key for key, _label in rule.inputs}
    status, env, detail = build_env(rule.formula, input_keys, bindings, site, robot.attrs)
    if status == "skip":
        return
    if status == "missing":
        unknowns.append(f"{rule.name}: нет «{_label(detail)}»")
        return
    if status != "ok":
        unknowns.append(f"{rule.name}: «{_label(detail)}» не число")
        return
    try:
        result = evaluate(rule.formula, env)
    except MissingName as exc:
        unknowns.append(f"{rule.name}: нет «{exc.name}»")
        return
    except FormulaError as exc:
        unknowns.append(f"{rule.name}: {exc}")
        return
    if not isinstance(result, bool):
        unknowns.append(f"{rule.name}: формула должна отвечать да или нет")
        return
    if result:
        return
    note = f"{rule.name}: условие не выполнено"
    if rule.mode == "conditional":
        conditions.append(note)
    else:
        fails.append(note)


def _pairs(rule: FilterRule) -> list[tuple[str, str]]:
    if not rule.robot_keys:
        return []
    if len(rule.object_keys) == len(rule.robot_keys):
        return list(zip(rule.object_keys, rule.robot_keys, strict=True))
    if len(rule.object_keys) == 1:
        return [(rule.object_keys[0], key) for key in rule.robot_keys]
    width = min(len(rule.object_keys), len(rule.robot_keys))
    return list(zip(rule.object_keys[:width], rule.robot_keys[:width], strict=True))


def _compare(op: str, robot_value: Any, site_value: Any) -> tuple[bool | None, str]:
    if op == "==":
        left = str(robot_value).strip().casefold()
        right = str(site_value).strip().casefold()
        return left == right, f"{robot_value} и {site_value}"
    try:
        left = float(str(robot_value).replace(",", ".").replace(" ", ""))
        right = float(str(site_value).replace(",", ".").replace(" ", ""))
    except (TypeError, ValueError):
        return None, "значение не число"
    detail = f"{left:g} {op} {right:g}"
    if op == "<=":
        return left <= right, detail
    if op == ">=":
        return left >= right, detail
    if op == "<":
        return left < right, detail
    if op == ">":
        return left > right, detail
    return None, f"оператор {op} не поддерживается"


def robot_count(formula: str, inputs: tuple[tuple[str, str], ...], bindings: dict[str, str], site: dict, robot: dict) -> tuple[float | None, str]:
    if not formula.strip():
        return None, ""
    status, env, detail = build_env(formula, {key for key, _label in inputs}, bindings, site, robot)
    if status == "skip":
        return None, "параметр объекта не задан"
    if status == "missing":
        return None, f"нет «{_label(detail)}»"
    if status != "ok":
        return None, f"«{_label(detail)}» не число"
    try:
        value = evaluate(formula, env)
    except MissingName as exc:
        return None, f"нет «{exc.name}»"
    except FormulaError as exc:
        return None, str(exc)
    if isinstance(value, bool):
        return None, "формула количества должна давать число"
    return float(value), ""


def usage_for(key: str, *, unused: bool, referenced: set[str]) -> str:
    if unused:
        return "unused"
    if key in referenced:
        return "active"
    return "pending"
