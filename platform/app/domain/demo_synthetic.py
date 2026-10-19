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
MODE_UNITS = {'uroven_shuma': 'дБА', 'temp_min_c': '°C',
              'working_speed_loaded_ms': 'м/с', 'working_speed_empty_ms': 'м/с',
              'effective_cleaning_rate_m2_h': 'м²/ч'}
TASK_LABELS = dict(flow_per_day='Суточный поток тележек', route_len_m='Маршрут в одну сторону', t_load_s='Сцепка и загрузка',
    t_unload_s='Расцепка и выгрузка', batch_size='Тележек в составе', cart_tare_kg='Масса тары тележки',
    working_speed_loaded_ms='Рабочая скорость с грузом', working_speed_empty_ms='Рабочая скорость возврата',
    availability='Техническая доступность', reserve_count='Резерв парка', staff_fte_now='Исходная численность операции',
    clean_area_m2='Площадь участка уборки', cleaning_passes_per_day='Проходов уборки в сутки',
    cleaning_window_h='Окно уборки', effective_cleaning_rate_m2_h='Полезная производительность уборки')


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
    for code, process in plan['processes'].items():
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
        for key, entry in process['task'].items():
            # Ставка конкретной роли задачи отличается от средней ставки объекта.
            # Сохранённая ставка самой задачи всегда имеет приоритет.
            role_rate = key == 'staff_salary_year_rub' and bool(entry.get('labor_role'))
            if task.get(key) is None and (site.get(key) is None or role_rate):
                task[key] = deepcopy(entry['value'])
                fields.append({'key': key, 'label': TASK_LABELS.get(key, key), **deepcopy(entry), 'category': 'site', 'vendor_confirmed': False, 'requires_vendor_confirmation': False})
        applied.append({'process_code': code, 'process_name': process['name'], 'product_id': '', 'name': 'Допущения задачи', 'fields': fields})
    return site, tasks, applied


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
        applied.append(item)
        if entry.get('process_codes'):
            item['process_codes'] = list(entry['process_codes'])
        catalog.provenance[('fact.' if key in FACT_FIELDS else '') + key] = {
            **deepcopy(item), 'status': ORIGIN,
            'source': {'kind': ORIGIN, 'publisher': 'DEV · допущение хакатона', 'url': None},
        }
    return applied
