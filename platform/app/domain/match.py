"""Чистые типы. Без ввода-вывода."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
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
    unit: str | None = None


@dataclass(frozen=True)
class FilterRule:
    name: str
    object_keys: tuple[str, ...]
    robot_keys: tuple[str, ...]
    op: str
    mode: str
    inputs: tuple[tuple[str, str], ...] = ()
    formula: str = ""


STAGES = {"operation": "В эксплуатации", "piloting": "Пилот", "rnd": "Разработка (R&D)"}


@dataclass(frozen=True)
class Readiness:
    """Общий фильтр готовности: незрелый робот не отсеивается, а уходит в «Уточнить»."""

    enabled: bool = True
    min_trl: int = 6
    review_stages: tuple[str, ...] = ("rnd",)
    review_missing_trl: bool = False

    @classmethod
    def from_value(cls, value: dict | None) -> "Readiness":
        data = value or {}
        base = cls()
        try:
            min_trl = int(data.get("min_trl", base.min_trl))
        except (TypeError, ValueError):
            min_trl = base.min_trl
        stages = data.get("review_stages", list(base.review_stages))
        return cls(
            enabled=bool(data.get("enabled", base.enabled)),
            min_trl=max(0, min(9, min_trl)),
            review_stages=tuple(code for code in stages if code in STAGES) if isinstance(stages, list) else base.review_stages,
            review_missing_trl=bool(data.get("review_missing_trl", base.review_missing_trl)),
        )

    def as_value(self) -> dict:
        return {
            "enabled": self.enabled,
            "min_trl": self.min_trl,
            "review_stages": list(self.review_stages),
            "review_missing_trl": self.review_missing_trl,
        }

    def notes(self, trl: int | None, stage: str | None) -> list[str]:
        if not self.enabled:
            return []
        out = []
        if trl is None:
            if self.review_missing_trl:
                out.append("Готовность: УГТ не указан")
        elif self.min_trl and trl < self.min_trl:
            out.append(f"Готовность: УГТ {trl} ниже порога {self.min_trl}")
        if stage in self.review_stages:
            out.append(f"Готовность: стадия «{STAGES[stage]}»")
        return out


@dataclass(frozen=True)
class RobotView:
    id: str
    name: str
    slug: str
    attrs: dict[str, Any]
    image_url: str | None = None
    trl: int | None = None
    stage: str | None = None


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
    trl: int | None = None
    stage: str | None = None


def match_robots(
    *,
    process_code: str,
    process_name: str,
    site: dict[str, Any],
    rules: tuple[FilterRule, ...],
    robots: tuple[RobotView, ...],
    bindings: dict[str, str] | None = None,
    readiness: Readiness | None = None,
) -> list[MatchHit]:
    """Вердикт по каждому роботу процесса. Базы здесь нет."""
    linked = bindings or {}
    return [
        _one(process_code, process_name, site, rules, robot, linked, readiness)
        for robot in robots
    ]


def _one(
    process_code: str,
    process_name: str,
    site: dict[str, Any],
    rules: tuple[FilterRule, ...],
    robot: RobotView,
    bindings: dict[str, str],
    readiness: Readiness | None = None,
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
    immature = readiness.notes(robot.trl, robot.stage) if readiness else []
    if fails:
        verdict, notes = "fail", tuple(fails + unknowns + conditions + immature)
    elif unknowns or immature:
        verdict, notes = "unknown", tuple(immature + unknowns + conditions)
    elif conditions:
        verdict, notes = "conditional", tuple(conditions)
    else:
        verdict, notes = "pass", ()
    return MatchHit(robot.id, robot.name, robot.slug, process_code, process_name, verdict, notes, robot.image_url, robot.trl, robot.stage)


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


# Суточный объём и длина рейса в формулах аэропорта и медучреждения записаны числами.
_HARD_FLOW = re.compile(r"ceil\(\((\d+(?:\.\d+)?)")
_HARD_LEG = re.compile(r"(\d+(?:\.\d+)?)(\s*/\s*robot\.speed_loaded_ms)")
# Доля убираемой площади, если в датасете её нет: у склада активная зона — половина площади.
CLEAN_AREA_SHARE = 0.5


def _plain(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else str(value)


def formula_with_task(formula: str, task: dict | None) -> str:
    """Подставляет объём и маршрут задачи вместо зашитых 420/850/1200 и 584/360.

    В формуле путь уже туда и обратно, поэтому длина маршрута задачи удваивается.
    Формулы склада этой подстановки не касаются: там объём и маршрут — имена полей.
    """
    if not formula or not isinstance(task, dict):
        return formula
    text = formula
    flow = task.get("flow_per_day")
    route = task.get("route_len_m")
    try:
        flow_n = float(flow) if flow not in (None, "") else None
    except (TypeError, ValueError):
        flow_n = None
    try:
        route_n = float(route) if route not in (None, "") else None
    except (TypeError, ValueError):
        route_n = None
    if flow_n is not None:
        text = _HARD_FLOW.sub(lambda match: f"ceil(({_plain(flow_n)}", text, count=1)
    if route_n is not None:
        distance = _plain(route_n * 2)
        text = _HARD_LEG.sub(lambda match: distance + match.group(2), text, count=1)
    return text


def count_site(site: dict | None) -> dict:
    """Площадь уборки из доли общей, если у объекта её нет в датасете."""
    out = dict(site or {})
    if out.get("clean_area_m2") not in (None, ""):
        return out
    try:
        area = float(out.get("area_m2"))
    except (TypeError, ValueError):
        return out
    if area > 0:
        out["clean_area_m2"] = area * CLEAN_AREA_SHARE
    return out


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
