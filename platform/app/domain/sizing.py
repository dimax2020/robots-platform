"""Реестр моделей мощности. Старые строковые формулы не имеют неявного допуска."""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, isfinite
import re

from app.domain.assessment import Reason, reason, valid_count
from app.domain.formula import _number


@dataclass(frozen=True)
class SizingResult:
    count: float | None
    reasons: tuple[Reason, ...] = ()
    model: str | None = None


def _quantity(raw):
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, str) and not re.fullmatch(r'[+-]?\d+(?:[.,]\d+)?', raw.strip()):
        return None
    return _number(raw)


def size_equipment(profile: dict, facts: dict, site: dict, robot: dict, task: dict | None = None) -> SizingResult:
    """Достоверность параметров подтверждает профиль, единицы и классы проверяет реестр."""
    if not isinstance(profile, dict) or not isinstance(facts, dict):
        return SizingResult(None, (reason('sizing_configuration_error', 'Некорректные метаданные модели количества', stage='sizing'),))
    policy = profile.get('sizing') or {}
    model = policy.get('model') if isinstance(policy, dict) else None
    if not model:
        return SizingResult(None, (reason('sizing_model_missing', 'Для этого решения не определена модель количества', stage='sizing'),))
    if not isinstance(model, str):
        return SizingResult(None, (reason('sizing_configuration_error', 'Некорректный идентификатор модели количества', stage='sizing'),))
    if model != 'mobile_cycle_v1':
        return SizingResult(None, (reason('sizing_model_unknown', 'Модель количества не поддерживается', stage='sizing'),), model)
    if facts.get('execution_class') != 'mobile_transport':
        return SizingResult(None, (reason('sizing_incompatible', 'Транспортный цикл применим только к мобильному транспортному роботу', stage='sizing'),), model)
    if policy.get('flow_unit') != 'items/day' or policy.get('quantity_unit') != 'machines':
        return SizingResult(None, (reason('sizing_unit_incompatible', 'Не подтверждены единицы потока и количества', stage='sizing'),), model)
    # Ни 80 секунд, ни 0.82, ни резерв +1 не подставляются по умолчанию.
    values = dict(site)
    values.update(task or {})
    keys = ('flow_per_day', 'route_len_m', 't_load_s', 't_unload_s', 'batch_size', 'availability', 'reserve_count', 'shift_hours', 'shifts_per_day')
    env = {}
    problems = []
    for k in keys:
        raw = values.get(k)
        n = _quantity(raw)
        if n is None:
            problems.append(reason('sizing_input_missing' if raw in (None, '') else 'sizing_input_invalid', f'Для расчёта количества требуется «{k}»', field=k, stage='sizing'))
        else:
            env[k] = n
    for k in ('speed_loaded_ms', 'speed_empty_ms'):
        raw = robot.get(k)
        n = _quantity(raw)
        if n is None:
            problems.append(reason('sizing_attribute_missing', f'Для расчёта количества требуется «{k}»', field=k, stage='sizing'))
        else:
            env[k] = n
    if problems:
        return SizingResult(None, tuple(problems), model)
    if (any(env[k] < 0 for k in keys) or env['batch_size'] <= 0 or not env['batch_size'].is_integer()
            or not valid_count(env['reserve_count']) or not 0 < env['availability'] <= 1
            or any(env[k] <= 0 for k in ('shift_hours', 'shifts_per_day', 'speed_loaded_ms', 'speed_empty_ms'))
            or env['shift_hours'] * env['shifts_per_day'] > 24):
        return SizingResult(None, (reason('sizing_input_invalid', 'Некорректные параметры цикла, сменности или резерва', stage='sizing'),), model)
    cycle = env['route_len_m'] / env['speed_loaded_ms'] + env['route_len_m'] / env['speed_empty_ms'] + env['t_load_s'] + env['t_unload_s']
    if cycle <= 0 or not isfinite(cycle):
        return SizingResult(None, (reason('sizing_input_invalid', 'Длительность цикла должна быть положительной и конечной', stage='sizing'),), model)
    window = env['shift_hours'] * env['shifts_per_day'] * 3600 * env['availability']
    if window <= 0 or not isfinite(window):
        return SizingResult(None, (reason('sizing_input_invalid', 'Некорректное доступное время работы', stage='sizing'),), model)
    demand = env['flow_per_day'] / env['batch_size'] * cycle / window
    if not isfinite(demand):
        return SizingResult(None, (reason('sizing_result_invalid', 'Расчёт количества выходит за числовой диапазон', stage='sizing'),), model)
    count = ceil(demand) + env['reserve_count']
    if not valid_count(count):
        return SizingResult(None, (reason('sizing_result_invalid', 'Некорректное количество машин', stage='sizing'),), model)
    return SizingResult(float(count), (), model)
