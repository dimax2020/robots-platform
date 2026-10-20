"""Отдельный фиксированный слой DEV-допущений. Не пишет в исходный каталог.

Данные подключаются только в явно разрешённой DEV-среде и выбранных демопроектах.
Любые опубликованные значения, конфликты и not_applicable имеют приоритет.
"""
from copy import deepcopy
from functools import lru_cache
import json
from math import isfinite
from pathlib import Path

from app.domain.assessment import validate_metadata
from app.domain.specs import NUMERIC_UNITS, display_label, normalize_value
from app.config import get_settings

ORIGIN = 'demo_synthetic'
NOTICE = 'В оценке присутствуют синтетические допущения DEV для хакатона. Они не подтверждены вендором; технический результат условен до проверки этих данных.'
FACT_FIELDS = {'solution_kind', 'control_mode', 'execution_class', 'environments', 'capabilities', 'equipment', 'configuration_complete', 'price_complete'}
FACT_LABELS = {'solution_kind': 'Вид решения', 'control_mode': 'Управление', 'environments': 'Среда эксплуатации',
               'capabilities': 'Выполняемые операции', 'execution_class': 'Класс исполнения'}
MODE_UNITS = {'uroven_shuma': 'дБА', 'temp_min_c': '°C', 'temp_max_c': '°C',
              'inspection_height_m': 'м', 'facade_reach_m': 'м', 'wind_max_ms': 'м/с',
              'working_time_h': 'ч', 'working_inventory_rate_h': 'мест/ч',
              'working_speed_loaded_ms': 'м/с', 'working_speed_empty_ms': 'м/с',
              'effective_cleaning_rate_m2_h': 'м²/ч'}
TASK_LABELS = dict(flow_per_day='Суточный поток', route_len_m='Маршрут в одну сторону', t_load_s='Сцепка и загрузка',
    t_unload_s='Расцепка и выгрузка', batch_size='Единиц в партии или составе', cart_tare_kg='Масса тары тележки',
    working_speed_loaded_ms='Рабочая скорость с грузом', working_speed_empty_ms='Рабочая скорость возврата',
    availability='Техническая доступность', reserve_count='Резерв парка', staff_fte_now='Исходная численность операции',
    clean_area_m2='Площадь участка уборки', cleaning_passes_per_day='Проходов уборки в сутки',
    cleaning_window_h='Окно уборки', effective_cleaning_rate_m2_h='Полезная производительность уборки')
TASK_LABELS['working_time_h'] = 'Оценочное время работы выбранного режима'
TASK_LABELS['working_inventory_rate_h'] = 'Оценочная производительность инвентаризации'
TASK_LABELS.update(inspection_height_m='Высота фотоосмотра', facade_reach_m='Досягаемость фасадной мойки',
                   wind_max_ms='Допустимый рабочий ветер')


@lru_cache(maxsize=1)
def manifest() -> dict:
    path = Path(__file__).resolve().parents[2] / 'seed' / 'demo_synthetic.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('version') != 2:
        raise ValueError('Неизвестная версия синтетических дополнений')
    return data


def enabled():
    return get_settings().demo_synthetic_enabled


def project_plan(project):
    # Контур определяется сервером, а не переданными клиентом site/preview.
    return deepcopy(manifest()['projects'].get(project.slug)) if enabled() and project.is_demo else None


def project_inputs(plan, site, tasks):
    site, tasks = deepcopy(site), deepcopy(tasks)
    applied = []
    fields = []
    for key, entry in plan.get('site', {}).items():
        if site.get(key) in (None, ''):
            site[key] = deepcopy(entry['value'])
            fields.append({'key': key, 'label': entry.get('label', key), **deepcopy(entry),
                           'category': 'site', 'vendor_confirmed': False, 'requires_vendor_confirmation': False})
    if fields:
        applied.append({'process_code': '', 'process_name': 'Недостающие входы демоплощадки',
                        'product_id': '', 'name': 'Допущения площадки', 'fields': fields})
    # Для технических демонстраций сохраняем входы, даже когда процесс пока
    # не входит в рассчитываемую программу (несовместим или нет модели).
    for code, process in {**plan.get('technical_processes', {}), **plan['processes']}.items():
        matches = [t for t in tasks if t.get('process_code') == code]
        if len(matches) > 1:
            # Несколько независимых потоков нельзя молча заменить последним.
            for task in matches:
                task['__demo_input_conflict'] = True
            continue
        if matches:
            task = matches[0]
        else:
            task = {'process_code': code, 'name': process['name']}
            tasks.append(task)
        fields = []
        for key, entry in process.get('task', {}).items():
            # Ставка конкретной роли задачи отличается от средней ставки объекта.
            # Сохранённая ставка самой задачи всегда имеет приоритет.
            role_rate = key == 'staff_salary_year_rub' and bool(entry.get('labor_role'))
            if task.get(key) is None and (site.get(key) is None or role_rate):
                task[key] = deepcopy(entry['value'])
                fields.append({'key': key, 'label': TASK_LABELS.get(key, key), **deepcopy(entry), 'category': 'site', 'vendor_confirmed': False, 'requires_vendor_confirmation': False})
        # Условия операции — отдельная область, а не изменение требований объекта.
        # Явные входы задачи (включая 0/False) сильнее DEV-сценария.
        for key, entry in process.get('operation', {}).get('fields', {}).items():
            if task.get(key) is None:
                task[key] = deepcopy(entry['value'])
                fields.append({'key': key, **deepcopy(entry), 'category': 'operation',
                               'scope': code, 'base_site_value': deepcopy(site.get(key)),
                               'vendor_confirmed': False, 'requires_vendor_confirmation': False})
        applied.append({'process_code': code, 'process_name': process['name'], 'product_id': '', 'name': 'Допущения задачи', 'fields': fields})
    return site, tasks, applied


def operation_context(process, site, task, profile, rules, bindings):
    """Только явно зарегистрированная DEV-операция; обычный подбор не меняется."""
    from app.domain.match import FilterRule
    operation = (process or {}).get('operation')
    if not enabled() or not operation:
        return site, profile, rules, bindings
    values = deepcopy(site)
    # Здесь уже подготовленные входы задачи, включая What-if нагрузки.
    values.update({key: value for key, value in (task or {}).items()
                   if value is not None and not key.startswith('__')})
    settings = operation.get('engineering', {})
    profile = {**deepcopy(profile), **deepcopy(settings.get('profile', {}))}
    validate_metadata(profile, product=False)
    omitted = settings.get('omit_rules', {})
    if any(not explanation.strip() for explanation in omitted.values()):
        raise ValueError('Удаление проверки требует инженерного обоснования')
    rules = tuple(rule for rule in rules if rule.name not in omitted)
    if settings.get('bindings', {}).get('shift') == 'autonomy_required_h':
        from dataclasses import replace
        rules = tuple(replace(rule, name='Работа между зарядками и обслуживанием')
                      if rule.formula == 'robot.work_time_h >= shift' else rule for rule in rules)
    for definition in settings.get('checks', []):
        if definition['op'] not in {'>=', '<=', '=='}:
            raise ValueError('DEV-проверка должна сравнивать характеристики, а не задавать модель количества')
        rules += (FilterRule(definition['name'], (definition['site_key'],),
                             (definition['robot_key'],), definition['op'], 'hard'),)
    return values, profile, rules, {**bindings, **settings.get('bindings', {})}


def operation_links(process):
    """Адресные связи существующих карточек с обоснованием, без записи в БД."""
    if not enabled():
        return []
    links = (process or {}).get('operation', {}).get('product_links', [])
    for entry in links:
        if entry.get('origin') != ORIGIN or not entry.get('explanation') or not entry.get('references'):
            raise ValueError('DEV-связь требует назначения и источника')
    return deepcopy(links)


@lru_cache(maxsize=1)
def supplements() -> dict:
    data = manifest()
    result = {}
    for product in data['products']:
        if product['product_id'] in result:
            raise ValueError('Повтор product_id в синтетических дополнениях')
        for key, entry in product['fields'].items():
            if entry.get('origin') != ORIGIN or not entry.get('explanation') or not isinstance(entry.get('unit'), str):
                raise ValueError(f'Нет происхождения/единиц/пояснения для {key}')
            if key in FACT_FIELDS:
                validate_metadata({key: entry['value']}, product=True)
            elif key in NUMERIC_UNITS:
                if normalize_value(key, entry['value'], unit=entry['unit']) is None:
                    raise ValueError(f'Некорректные единицы дополнения {key}')
            elif (key not in MODE_UNITS or entry['unit'] != MODE_UNITS[key]
                  or type(entry['value']) not in (int, float) or not isfinite(entry['value'])):
                raise ValueError(f'Неизвестная характеристика дополнения {key}')
        result[product['product_id']] = product['fields']
    return result


def apply_supplements(row, catalog, *, entries=None, process_code='') -> list[dict]:
    if not enabled():
        return []
    entries = supplements().get(str(row.id), {}) if entries is None else entries
    applied = []
    for key, entry in entries.items():
        if entry.get('process_codes') and process_code not in entry['process_codes']:
            continue
        raw = (row.attrs or {}).get(key) or {}
        # Не устраняем синтетикой противоречие, неприменимость или явно заданное
        # исходное значение, даже если его не смог разобрать нормализатор.
        if (key in catalog.issues or any(r.field == key or r.code == 'configuration_error' for r in catalog.reasons)
                or raw.get('status') == 'not_applicable' or raw.get('conflict')
                or raw.get('status') == 'conflict'
                or raw.get('status') == 'known' and raw.get('value') not in (None, '', [])):
            continue
        target = catalog.facts if key in FACT_FIELDS else catalog.values
        if target.get(key) not in (None, '', []):
            continue
        value = deepcopy(entry['value'])
        unit = entry['unit']
        if key in NUMERIC_UNITS:
            _, value, unit = normalize_value(key, value, unit=unit)
        target[key] = value
        item = {'key': key, 'label': FACT_LABELS.get(key, TASK_LABELS.get(key, display_label(key, 'Уровень шума' if key == 'uroven_shuma' else None))),
                'value': value, 'unit': unit, 'origin': ORIGIN, 'explanation': entry['explanation'],
                'vendor_confirmed': False, 'requires_vendor_confirmation': True}
        # Ссылки объясняют выбор диапазона/аналога, не превращают синтетику в паспорт.
        for extra in ('references', 'scope'):
            if extra in entry:
                item[extra] = deepcopy(entry[extra])
        applied.append(item)
        if entry.get('process_codes'):
            item['process_codes'] = list(entry['process_codes'])
        catalog.provenance[('fact.' if key in FACT_FIELDS else '') + key] = {
            **deepcopy(item), 'status': ORIGIN,
            'source': {'kind': ORIGIN, 'publisher': 'DEV · допущение хакатона', 'url': None},
        }
    return applied


def technical_mode_values(catalog):
    """Оценочный режим отдельно от опубликованной верхней границы автономности.

    Известное рабочее значение не заменяется. Режим разрешает лишь неопределённость
    «до N часов», не конфликт, диапазон, особые условия или not_applicable.
    """
    import re
    from app.domain.formula import _number
    values = dict(catalog.values)
    mode = catalog.provenance.get('working_time_h', {})
    published = catalog.provenance.get('work_time_h', {})
    original = published.get('normalization_original') or published
    text = str(original.get('value', '')) + ' ' + str(published.get('quote') or '')
    estimate = _number(values.get('working_time_h'))
    limit = _number(published.get('normalized_value', published.get('value')))
    if (mode.get('origin') == ORIGIN and 'work_time_h' not in values
            and published.get('status') == 'known' and not published.get('conflict') and not published.get('conditions')
            and catalog.issues.get('work_time_h', '').startswith('Указана граница, диапазон или отдельный режим')
            and (published.get('normalization_rule') == 'upper_bound' or re.search(r'\bдо\s+\d|up to\s+\d', text, re.I))
            and estimate is not None and limit is not None and 0 < estimate <= limit):
        values['work_time_h'] = estimate
    return values


def catalog_inventory_quantity(catalog, site, context):
    """Вызывает сохранённую формулу инвентаризации через прежний robot_count.

    Не переносит транспортный цикл на сканер, AS/RS или манипулятор. Формулу,
    резерв и коэффициенты берёт целиком из ProcessRow; новых выражений здесь нет.
    """
    from app.domain.assessment import reason
    from app.domain.formula import _number, build_env, identifiers
    from app.domain.match import robot_count
    from app.domain.sizing import SizingResult
    model = 'process.count_formula/warehouse_inventory'
    if (not context or context.get('process_code') != 'warehouse_inventory'
            or catalog.facts.get('execution_class') != 'inventory_scanner'
            or context.get('flow_unit') != 'locations/hour'):
        return SizingResult(None, (reason('sizing_incompatible', 'Для оценки количества нужен подтверждённый тип инвентаризатора и единицы его производительности', stage='sizing'),), model)
    from app.domain.assessment import valid_count
    stock, hours, shifts = (_number(site.get(key)) for key in ('pallet_places', 'shift_hours', 'shifts_per_day'))
    if (any(isinstance(site.get(key), bool) for key in ('pallet_places', 'shift_hours', 'shifts_per_day'))
            or not valid_count(stock) or hours is None or shifts is None
            or hours <= 0 or shifts <= 0 or hours * shifts > 24):
        return SizingResult(None, (reason('sizing_input_invalid', 'Уточните число мест хранения и сменность: число мест должно быть целым неотрицательным, рабочее время — от 0 до 24 часов в сутки', stage='sizing'),), model)
    robot = dict(catalog.values)
    if str(robot.get('throughput_unit', '')).casefold() not in {'палето-мест/ч', 'паллето-мест/ч', 'мест/ч'}:
        return SizingResult(None, (reason('sizing_unit_incompatible', 'Для оценки количества нужна производительность в местах хранения за час', stage='sizing'),), model)
    mode = catalog.provenance.get('working_inventory_rate_h', {})
    rate = _number(robot.get('working_inventory_rate_h'))
    published = catalog.provenance.get('throughput', {})
    limit = _number(published.get('normalized_value', published.get('value')))
    # Это отдельная оценка рабочего режима ниже опубликованного предела;
    # карточка, scalar/диапазон источника и его происхождение остаются прежними.
    use_mode = (mode.get('origin') == ORIGIN and rate is not None and limit is not None and 0 < rate <= limit
            and published.get('status') == 'known' and not published.get('conflict') and not published.get('conditions')
            and catalog.issues.get('throughput', '').startswith('Указана граница, диапазон или отдельный режим'))
    if use_mode:
        robot['throughput'] = rate
    formula = context.get('formula', '')
    inputs = tuple(context.get('inputs') or ())
    bindings = context.get('bindings') or {}
    count, note = robot_count(formula, inputs, bindings, site, robot)
    if count is None:
        return SizingResult(None, (reason('sizing_input_missing', 'Для оценки количества уточните число мест хранения и рабочую производительность сканирования. ' + note, stage='sizing'),), model)
    status, env, _ = build_env(formula, {key for key, _ in inputs}, bindings, site, robot)
    details = {key.removeprefix('robot.'): env[key] for key in identifiers(formula) if key in env} if status == 'ok' else {}
    return SizingResult(count, (), model, {'inputs': details, 'formula': formula,
        'throughput_parameter': 'working_inventory_rate_h' if use_mode else 'throughput',
        'formula_source': 'process.count_formula', 'flow_unit': 'locations/hour', 'quantity_unit': 'machines'})


def catalog_process_quantity(catalog, site, context, robot, task):
    """Привязка сохранённых моделей к их физическим операциям, без новых формул."""
    from app.domain.assessment import reason, valid_count
    from app.domain.formula import _number, build_env, identifiers
    from app.domain.match import robot_count, formula_with_task
    from app.domain.sizing import SizingResult
    if context.get('process_code') == 'warehouse_inventory':
        return catalog_inventory_quantity(catalog, site, context)
    code = context.get('process_code')
    expected = {'perimeter_security': 'ground_patrol', 'territory_inspection': 'ground_patrol',
                'passenger_service': 'indoor_visitor_service'}
    model = 'process.count_formula/' + str(code)
    if (code not in expected or catalog.facts.get('execution_class') != expected[code]
            or context.get('flow_unit') != 'missions/day' or not context.get('formula')):
        return SizingResult(None, (reason('sizing_incompatible', 'Сохранённая модель не соответствует типу решения и рабочей операции', stage='sizing'),), model)
    hours, shifts = (_number(site.get(k)) for k in ('shift_hours', 'shifts_per_day'))
    if (hours is None or shifts is None or hours <= 0 or shifts <= 0 or hours * shifts > 24
            or any(isinstance(site.get(k), bool) for k in ('shift_hours', 'shifts_per_day'))):
        return SizingResult(None, (reason('sizing_input_invalid', 'Уточните рабочее время операции: от 0 до 24 часов в сутки', stage='sizing'),), model)
    if code == 'passenger_service':
        # Существующая функция подстановки входов задачи, без изменения выражения.
        if any(_number((task or {}).get(k)) is None or isinstance((task or {}).get(k), bool)
               or _number((task or {}).get(k)) < 0 for k in ('flow_per_day', 'route_len_m')):
            return SizingResult(None, (reason('sizing_input_missing', 'Уточните число сопровождений и длину маршрута', stage='sizing'),), model)
        formula = formula_with_task(context['formula'], task)
    else:
        # В сохранённой модели 24 обхода и геометрия периметра через площадь.
        # Это не произвольный поток и не модель полёта.
        if _number(site.get('area_m2')) is None or _number(site['area_m2']) <= 0:
            return SizingResult(None, (reason('sizing_input_missing', 'Уточните площадь патрулируемого участка', stage='sizing'),), model)
        formula = context['formula']
    count, note = robot_count(formula, context['inputs'], context['bindings'], site, robot)
    if count is None or not valid_count(count):
        return SizingResult(None, (reason('sizing_input_missing', 'Уточните рабочую скорость и параметры маршрута. ' + note, stage='sizing'),), model)
    status, env, _ = build_env(formula, {k for k, _ in context['inputs']}, context['bindings'], site, robot)
    inputs = {key.removeprefix('robot.'): env[key] for key in identifiers(formula) if key in env} if status == 'ok' else {}
    return SizingResult(count, (), model, {'inputs': inputs, 'formula': formula,
        'formula_source': 'process.count_formula', 'flow_unit': 'missions/day', 'quantity_unit': 'machines',
        'operating_hours_per_day': hours * shifts})
