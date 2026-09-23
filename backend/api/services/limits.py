"""Проверка числовых полей площадки и задач по data/field_limits.json (E4 §7)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from pydantic_core import InitErrorDetails, PydanticCustomError

from api.config import get_settings
from engine.models import SiteProfile, Task


@dataclass(frozen=True, slots=True)
class LimitViolation:
    """Одно нарушение диапазона с путём для FastAPI loc."""

    loc: tuple[str | int, ...]
    field: str
    value: float
    min: float
    max: float
    message: str


def _fmt_number(value: float | int) -> str:
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, float) and value == int(value):
        return str(int(value))
    return str(value)


def _unit_suffix(unit: str | None) -> str:
    if not unit:
        return ""
    return f" {unit}"


def _format_message(
    *,
    label: str,
    value: float,
    min_v: float,
    max_v: float,
    unit: str | None,
) -> str:
    suffix = _unit_suffix(unit)
    return (
        f"{label} {_fmt_number(value)}{suffix} выходит за границу "
        f"{_fmt_number(min_v)}-{_fmt_number(max_v)}{suffix}"
    )


@lru_cache
def _load_field_limits(data_dir: str) -> dict[str, Any]:
    path = Path(data_dir) / "field_limits.json"
    if not path.is_file():
        raise FileNotFoundError(f"Файл границ полей не найден: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"field_limits.json: ожидается объект, получено {type(raw).__name__}")
    return raw


def load_field_limits() -> dict[str, Any]:
    """Загрузить field_limits.json через get_settings().data_dir с кэшем."""
    return _load_field_limits(str(get_settings().data_dir.resolve()))


def clear_limits_cache() -> None:
    """Сброс кэша — для тестов с подменой data_dir."""
    _load_field_limits.cache_clear()


def _as_mapping(obj: SiteProfile | Task | dict[str, Any]) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    return obj.model_dump()


def _check_section(
    *,
    section: dict[str, Any],
    values: dict[str, Any],
    loc_prefix: tuple[str | int, ...],
) -> list[LimitViolation]:
    violations: list[LimitViolation] = []
    for field, rule in section.items():
        if field.startswith("_") or not isinstance(rule, dict):
            continue
        if "min" not in rule or "max" not in rule:
            continue
        raw = values.get(field)
        if raw is None:
            continue
        if isinstance(raw, bool):
            continue
        if not isinstance(raw, (int, float)):
            continue
        min_v = float(rule["min"])
        max_v = float(rule["max"])
        if min_v <= float(raw) <= max_v:
            continue
        label = str(rule.get("label") or field)
        unit = rule.get("unit")
        if unit is not None:
            unit = str(unit)
        message = _format_message(
            label=label, value=float(raw), min_v=min_v, max_v=max_v, unit=unit
        )
        violations.append(
            LimitViolation(
                loc=(*loc_prefix, field),
                field=field,
                value=float(raw),
                min=min_v,
                max=max_v,
                message=message,
            )
        )
    return violations


def check_site(site: SiteProfile | dict[str, Any] | None) -> list[LimitViolation]:
    """Проверить числовые поля площадки. None — без нарушений."""
    if site is None:
        return []
    limits = load_field_limits()
    section = limits.get("site") or {}
    if not isinstance(section, dict):
        raise ValueError("field_limits.json: раздел site должен быть объектом")
    return _check_section(section=section, values=_as_mapping(site), loc_prefix=("site",))


def check_tasks(tasks: list[Task] | list[dict[str, Any]] | None) -> list[LimitViolation]:
    """Проверить числовые поля задач. None — без нарушений."""
    if tasks is None:
        return []
    limits = load_field_limits()
    section = limits.get("task") or {}
    if not isinstance(section, dict):
        raise ValueError("field_limits.json: раздел task должен быть объектом")
    violations: list[LimitViolation] = []
    for index, task in enumerate(tasks):
        violations.extend(
            _check_section(
                section=section,
                values=_as_mapping(task),
                loc_prefix=("tasks", index),
            )
        )
    return violations


def check_site_and_tasks(
    site: SiteProfile | dict[str, Any] | None = None,
    tasks: list[Task] | list[dict[str, Any]] | None = None,
) -> list[LimitViolation]:
    """Проверить site и/или tasks; вернуть список нарушений."""
    return [*check_site(site), *check_tasks(tasks)]


def violations_to_validation_error(
    title: str, violations: list[LimitViolation]
) -> ValidationError:
    """Собрать ValidationError с loc, совместимым с FastAPI body."""
    line_errors: list[InitErrorDetails] = [
        {
            "type": PydanticCustomError("field_limits", "{message}", {"message": v.message}),
            "loc": v.loc,
            "input": v.value,
        }
        for v in violations
    ]
    return ValidationError.from_exception_data(title, line_errors)
