"""Реестр моделей мощности. Старые строковые формулы не имеют неявного допуска."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import ceil, floor, isfinite
import re

from app.domain.assessment import Reason, reason, valid_count
from app.domain.formula import _number
from app.domain.specs import display_label

SIZING_LABELS = {
    'flow_per_day': 'Суточный поток', 'route_len_m': 'Длина маршрута',
    't_load_s': 'Время загрузки', 't_unload_s': 'Время выгрузки', 'batch_size': 'Размер партии',
    'availability': 'Техническая доступность', 'reserve_count': 'Резерв парка',
    'shift_hours': 'Длительность смены', 'shifts_per_day': 'Смен в сутки',
    'clean_area_m2': 'Площадь уборки', 'cleaning_passes_per_day': 'Проходов уборки в сутки',
    'cleaning_window_h': 'Рабочее окно уборки', 'effective_cleaning_rate_m2_h': 'Рабочая производительность уборки',
    'cart_tare_kg': 'Масса тары тележки', 'pallet_mass_kg': 'Масса груза',
    'working_speed_loaded_ms': 'Рабочая скорость с грузом', 'working_speed_empty_ms': 'Рабочая скорость возврата',
    'sizing_window_h': 'Рабочее окно операции', 'handling_cycle_s': 'Такт обработки',
    'work_units_per_cycle': 'Единиц работы за цикл', 'module_storage_places': 'Мест в модуле AS/RS',
    'surface_area_m2': 'Площадь одного обследования', 'surface_rate_m2_h': 'Производительность обработки поверхности',
    'turnaround_h': 'Обслуживание между вылетами',
    'lines_per_presentation': 'Строк заказа за выдачу тары',
}


def input_label(key):
    return SIZING_LABELS.get(key, display_label(key))


@dataclass(frozen=True)
class SizingResult:
    count: float | None
    reasons: tuple[Reason, ...] = ()
    model: str | None = None
    details: dict = field(default_factory=dict)


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
        return SizingResult(None, (reason('sizing_model_missing', 'Для оценки количества уточните у поставщика производительность решения для выбранной операции и рабочий режим на объекте', stage='sizing'),))
    if not isinstance(model, str):
        return SizingResult(None, (reason('sizing_configuration_error', 'Некорректный идентификатор модели количества', stage='sizing'),))
    if model in {'asrs_capacity_v1', 'stationary_cycle_v1', 'aerial_surface_v1'}:
        return _engineering_model(model, policy, facts, {**site, **(task or {})}, robot)
    if model in {'towing_cycle_v1', 'cleaning_area_v1'}:
        return _operational_model(model, policy, facts, {**site, **(task or {})}, robot)
    if model != 'mobile_cycle_v1':
        return SizingResult(None, (reason('sizing_model_unknown', 'Для оценки количества требуется инженерная проверка производительности и рабочего режима решения', stage='sizing'),), model)
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
            problems.append(reason('sizing_input_missing' if raw in (None, '') else 'sizing_input_invalid', f'Для расчёта количества требуется «{input_label(k)}»', field=k, stage='sizing'))
        else:
            env[k] = n
    for k in ('speed_loaded_ms', 'speed_empty_ms'):
        raw = robot.get(k)
        n = _quantity(raw)
        if n is None:
            problems.append(reason('sizing_attribute_missing', f'Для расчёта количества требуется «{input_label(k)}»', field=k, stage='sizing'))
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
    return SizingResult(float(count), (), model, {'inputs': env, 'cycle_s': cycle,
        'daily_capacity_per_machine_items': env['batch_size'] * window / cycle,
        'working_count': ceil(demand), 'reserve_count': env['reserve_count'],
        'operating_hours_per_day': env['shift_hours'] * env['shifts_per_day']})


def _operational_model(model, policy, facts, inputs, robot):
    """Два физических процесса: цикл состава и площадная уборка с зарядкой."""
    cleaning = model == 'cleaning_area_v1'
    expected = 'mobile_cleaning' if cleaning else 'mobile_transport'
    if facts.get('execution_class') != expected:
        return SizingResult(None, (reason('sizing_incompatible', 'Модель несовместима с классом исполнения', stage='sizing'),), model)
    if policy.get('quantity_unit') != 'machines' or policy.get('flow_unit') != ('m2/day' if cleaning else 'items/day'):
        return SizingResult(None, (reason('sizing_unit_incompatible', 'Некорректные единицы модели', stage='sizing'),), model)
    keys = ('clean_area_m2', 'cleaning_passes_per_day', 'cleaning_window_h', 'effective_cleaning_rate_m2_h') if cleaning else (
        'flow_per_day', 'route_len_m', 't_load_s', 't_unload_s', 'batch_size', 'cart_tare_kg',
        'working_speed_loaded_ms', 'working_speed_empty_ms', 'pallet_mass_kg', 'shift_hours', 'shifts_per_day')
    required = {k: inputs.get(k) for k in (*keys, 'availability', 'reserve_count')}
    required.update({k: robot.get(k) for k in ('work_time_h', 'charge_time_h')})
    if not cleaning:
        required['payload_kg'] = robot.get('payload_kg')
    values = {k: _quantity(v) for k, v in required.items()}
    problems = [reason('sizing_input_missing' if required[k] in (None, '') else 'sizing_input_invalid',
                       f'Для оценки количества уточните «{input_label(k)}»', field=k, stage='sizing') for k, v in values.items() if v is None]
    if problems:
        return SizingResult(None, tuple(problems), model)
    v = values
    def invalid(message):
        return SizingResult(None, (reason('sizing_input_invalid', message, stage='sizing'),), model)
    if (any(x < 0 for x in v.values()) or not 0 < v['availability'] <= 1
            or not valid_count(v['reserve_count']) or v['work_time_h'] <= 0):
        return invalid('Доступность, резерв и длительности должны быть конечными и находиться в допустимых границах')
    battery = v['work_time_h'] / (v['work_time_h'] + v['charge_time_h'])
    availability = v['availability'] * battery
    if cleaning:
        window = v['cleaning_window_h']
        if not 0 < window <= 24 or v['effective_cleaning_rate_m2_h'] <= 0:
            return invalid('Окно уборки должно быть 0…24 ч, производительность положительна')
        area = _quantity(inputs.get('area_m2'))
        if area is not None and v['clean_area_m2'] > area:
            return invalid('Убираемая площадь превышает площадь объекта')
        # Сохраняем опубликованный диапазон, не превращая его в паспортный scalar.
        limits = re.search(r'(\d+)\s*[-–]\s*(\d+)', str(robot.get('proizvoditelnost', '')))
        if limits and not float(limits[1]) <= v['effective_cleaning_rate_m2_h'] <= float(limits[2]):
            return invalid('Рабочая производительность вне опубликованного диапазона')
        work = v['clean_area_m2'] * v['cleaning_passes_per_day']
        capacity = v['effective_cleaning_rate_m2_h'] * window * availability
        details = {'daily_work_m2': work, 'daily_capacity_per_machine_m2': capacity}
    else:
        window = v['shift_hours'] * v['shifts_per_day']
        if (not 0 < window <= 24 or v['batch_size'] <= 0 or not v['batch_size'].is_integer()
                or min(v['working_speed_loaded_ms'], v['working_speed_empty_ms']) <= 0):
            return invalid('Некорректная сменность, партия или рабочие скорости')
        mass = (v['pallet_mass_kg'] + v['cart_tare_kg']) * v['batch_size']
        if mass > v['payload_kg']:
            return invalid('Масса состава с тарой превышает буксируемую нагрузку')
        for kind in ('loaded', 'empty'):
            limit = _quantity(robot.get(f'speed_{kind}_limit_ms'))
            if limit is not None and v[f'working_speed_{kind}_ms'] > limit:
                return invalid('Рабочая скорость превышает опубликованный предел')
        cycle = v['route_len_m'] / v['working_speed_loaded_ms'] + v['route_len_m'] / v['working_speed_empty_ms'] + v['t_load_s'] + v['t_unload_s']
        if cycle <= 0:
            return invalid('Длительность цикла должна быть положительной')
        work = v['flow_per_day']
        capacity = window * 3600 * availability / cycle * v['batch_size']
        details = {'cycle_s': cycle, 'train_mass_kg': mass, 'daily_capacity_per_machine_items': capacity}
    if not isfinite(capacity) or capacity <= 0 or not isfinite(work) or not isfinite(work / capacity):
        return invalid('Производительность выходит за допустимый числовой диапазон')
    active = ceil(work / capacity)
    count = active + v['reserve_count']
    if not valid_count(count):
        return invalid('Некорректное количество машин')
    return SizingResult(float(count), (), model, {'inputs': v, 'battery_availability': battery,
        'effective_availability': availability, 'working_count': active, 'reserve_count': v['reserve_count'],
        'operating_hours_per_day': window, **details})


def _engineering_model(model, policy, facts, inputs, robot):
    """Ёмкость AS/RS, такт ячейки и площадь вылетов; прежние модели не меняются."""
    asrs = model == 'asrs_capacity_v1'
    aerial = model == 'aerial_surface_v1'
    storage = asrs and policy.get('flow_unit') == 'pallets/day'
    survey = aerial and policy.get('flow_unit') == 'surveys/day'
    classes = ({'automated_storage'} if asrs else
               {'aerial_inspection'} if survey else {'aerial_facade_cleaning'} if aerial else {'stationary_manipulation'})
    units = {'pallets/day', 'lines/day'} if asrs else {'m2/day', 'surveys/day'} if aerial else {'items/day'}
    def error(code, message, field=None):
        return SizingResult(None, (reason(code, message, field=field, stage='sizing'),), model)
    if facts.get('execution_class') not in classes:
        return error('sizing_incompatible', 'Модель несовместима с классом исполнения')
    if policy.get('quantity_unit') != 'machines' or policy.get('flow_unit') not in units:
        return error('sizing_unit_incompatible', 'Не подтверждены единицы потока и количества')
    required = {k: inputs.get(k) for k in ('flow_per_day', 'sizing_window_h', 'availability', 'reserve_count')}
    units_key = 'lines_per_presentation' if asrs and not storage else 'work_units_per_cycle'
    robot_keys = ('surface_rate_m2_h', 'work_time_h', 'turnaround_h') if aerial else (units_key,)
    # Существующая однозначная пропускная способность сильнее оценки такта.
    published_rate = asrs and robot.get('throughput') is not None
    if published_rate:
        robot_keys += ('throughput',)
        if str(robot.get('throughput_unit', '')).casefold() not in {'паллет/ч на кран', 'паллет/ч', 'циклов/ч'}:
            return error('sizing_unit_incompatible', 'Производительность AS/RS требуется в циклах выдачи за час')
    elif not aerial:
        robot_keys += ('handling_cycle_s',)
    if storage:
        required['pallet_places'] = inputs.get('pallet_places')
        robot_keys += ('module_storage_places',)
    if survey:
        required['surface_area_m2'] = inputs.get('surface_area_m2')
    required.update({k: robot.get(k) for k in robot_keys})
    v = {k: _quantity(raw) for k, raw in required.items()}
    problems = tuple(reason('sizing_attribute_missing' if k in robot_keys else 'sizing_input_missing',
                            f'Для расчёта количества требуется «{input_label(k)}»', field=k, stage='sizing')
                     for k, n in v.items() if n is None)
    if problems:
        return SizingResult(None, problems, model)
    if (any(n < 0 for n in v.values()) or not 0 < v['availability'] <= 1
            or not 0 < v['sizing_window_h'] <= 24 or not valid_count(v['reserve_count'])):
        return error('sizing_input_invalid', 'Некорректные нагрузка, рабочее окно, доступность или резерв')
    if storage and (not valid_count(v['pallet_places']) or not valid_count(v['module_storage_places']) or v['module_storage_places'] == 0):
        return error('sizing_input_invalid', 'Число мест должно быть целым, ёмкость модуля положительна')
    details = {}
    window = v['sizing_window_h']
    if aerial:
        if min(v['surface_rate_m2_h'], v['work_time_h']) <= 0 or v['work_time_h'] > 24:
            return error('sizing_input_invalid', 'Производительность и время рабочего вылета должны быть положительными')
        work = v['flow_per_day'] * (v['surface_area_m2'] if survey else 1)
        if survey and v['surface_area_m2'] <= 0:
            return error('sizing_input_invalid', 'Площадь одного обследования должна быть положительной')
        # Только целые вылеты, включая полное обслуживание/зарядку между ними.
        cycle = v['work_time_h'] + v['turnaround_h']
        mission_capacity = window * v['availability'] / cycle
        if not isfinite(mission_capacity):
            return error('sizing_input_invalid', 'Расчёт вылетов выходит за числовой диапазон')
        missions = floor(mission_capacity)
        coverage = v['surface_rate_m2_h'] * v['work_time_h']
        capacity = missions * coverage
        if not isfinite(work) or not isfinite(coverage) or not isfinite(capacity) or coverage <= 0 or capacity <= 0 or not isfinite(work / coverage):
            return error('sizing_input_invalid', 'Рабочее окно не вмещает вылет с обслуживанием или площадь выходит за диапазон')
        sorties = ceil(work / coverage)
        demand = sorties / missions
        details = {'daily_work_m2': work, 'coverage_per_sortie_m2': coverage,
                   'sorties_per_machine_day': missions, 'required_sorties': sorties,
                   'daily_capacity_per_machine_m2': capacity}
        formula = 'ceil(ceil(work_m2 / (surface_rate_m2_h * work_time_h)) / floor(window_h * availability / (work_time_h + turnaround_h))) + reserve'
    else:
        if v[units_key] <= 0 or (published_rate and v['throughput'] <= 0) or (not published_rate and v['handling_cycle_s'] <= 0):
            return error('sizing_input_invalid', 'Такт и единиц работы за цикл должны быть положительными')
        rate = v['throughput'] if published_rate else 3600 / v['handling_cycle_s']
        capacity = rate * v[units_key] * window * v['availability']
        if not isfinite(capacity) or capacity <= 0 or not isfinite(v['flow_per_day'] / capacity):
            return error('sizing_input_invalid', 'Производительность выходит за числовой диапазон')
        demand = v['flow_per_day'] / capacity
        details = {'daily_capacity_per_machine_items': capacity, 'cycles_per_hour': rate,
                   'rate_parameter': 'throughput' if published_rate else 'handling_cycle_s'}
        formula = f'ceil(flow_per_day / (cycles_per_hour * {units_key} * window_h * availability)) + reserve'
        if storage:
            demand = max(demand, v['pallet_places'] / v['module_storage_places'])
            details['capacity_required_modules'] = ceil(v['pallet_places'] / v['module_storage_places'])
            formula = 'ceil(max(flow_per_day / daily_capacity, pallet_places / module_storage_places)) + reserve'
    if not isfinite(demand):
        return error('sizing_result_invalid', 'Расчёт количества выходит за числовой диапазон')
    active = ceil(demand)
    count = active + v['reserve_count'] if active else 0
    if not valid_count(count):
        return error('sizing_result_invalid', 'Некорректное количество оборудования')
    audit_inputs = {**v, **({'throughput_unit': robot['throughput_unit']} if published_rate else {})}
    return SizingResult(float(count), (), model, {'inputs': audit_inputs, **details, 'formula': formula,
        'formula_source': 'engineering_registry', 'flow_unit': policy['flow_unit'], 'quantity_unit': 'machines',
        'working_count': active, 'reserve_count': v['reserve_count'], 'operating_hours_per_day': window})
