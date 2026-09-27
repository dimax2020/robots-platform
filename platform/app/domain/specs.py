"""Нормализация характеристик с сохранением исходных значений и происхождения.

Неоднозначный текст не превращается в первое встретившееся число.
Алиасы остаются в attrs для совместимости формул, но не дублируются в карточках.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
import json
import math
from pathlib import Path
import re


@lru_cache(maxsize=1)
def definitions() -> dict[str, dict]:
    path = Path(__file__).resolve().parents[2] / 'seed' / 'attributes.json'
    return {row['key']: row for row in json.loads(path.read_text(encoding='utf-8'))['attributes']}


CANON_LABELS = {key: row['label'] for key, row in definitions().items()}
# Единицы алиасов — часть контракта, а не предположение по величине числа.
ALIASES = {
    'charge_min': ('charge_time_h', 'мин'),
    'charge_time_min': ('charge_time_h', 'мин'),
    'charging_time_min': ('charge_time_h', 'мин'),
    'charging_time_h': ('charge_time_h', 'ч'),
    'work_time_min': ('work_time_h', 'мин'),
    'max_speed_attr': ('max_speed_ms', ''),
    'max_speed': ('max_speed_ms', ''),
    'max_speed_kmh': ('max_speed_ms', 'км/ч'),
    'lift_height_m': ('lift_height_mm', 'м'),
}
NUMERIC_UNITS = {
    'charge_time_h': 'ч', 'work_time_h': 'ч', 'battery_swap_min': 'мин',
    'max_speed_ms': 'м/с', 'speed_loaded_ms': 'м/с', 'speed_empty_ms': 'м/с',
    'speed_vertical_ms': 'м/с', 'payload_kg': 'кг', 'mass_kg': 'кг',
    'min_aisle_width_m': 'м', 'lift_height_mm': 'мм', 'reach_mm': 'мм',
    'power_watt': 'Вт', 'work_time_general_h': 'ч',
    **{k: row['unit'] for k, row in definitions().items() if k in {'work_time_empty_h', 'payload_per_level_kg', 'speed_travel_ms', 'charge_time_to_90_h', 'payload_static_kg', 'speed_cleaning_ms', 'slope_max_deg', 'work_time_at_20kg_h', 'work_time_motion_h', 'dirty_water_tank_l', 'clean_water_tank_l', 'work_time_cleaning_h', 'water_tank_l', 'work_time_dust_h', 'work_time_loaded_h'}},
}
UNIT_GROUPS = {
    'time': {'ч': 3600, 'мин': 60, 'с': 1},
    'speed': {'м/с': 1, 'км/ч': 1/3.6, 'м/мин': 1/60},
    'mass': {'кг': 1, 'г': .001, 'т': 1000},
    'length': {'м': 1, 'см': .01, 'мм': .001},
    'power': {'Вт': 1, 'кВт': 1000},
    'volume': {'л': 1, 'мл': .001},
    'angle': {'°': 1},
}
UNIT_NAMES = {
    'ч': 'ч', 'час': 'ч', 'часа': 'ч', 'часов': 'ч', 'h': 'ч', 'hr': 'ч', 'hours': 'ч',
    'мин': 'мин', 'минута': 'мин', 'минут': 'мин', 'минуты': 'мин', 'min': 'мин',
    'с': 'с', 'сек': 'с', 'секунд': 'с', 's': 'с', 'sec': 'с',
    'м/с': 'м/с', 'м/c': 'м/с', 'm/s': 'м/с', 'м/сек': 'м/с', 'км/ч': 'км/ч', 'km/h': 'км/ч',
    'м/мин': 'м/мин', 'm/min': 'м/мин',
    'кг': 'кг', 'kg': 'кг', 'г': 'г', 'g': 'г', 'т': 'т', 'тонн': 'т', 't': 'т',
    'м': 'м', 'm': 'м', 'см': 'см', 'cm': 'см', 'мм': 'мм', 'mm': 'мм',
    'л': 'л', 'l': 'л', 'литров': 'л', 'мл': 'мл', '°': '°',
    'вт': 'Вт', 'w': 'Вт', 'квт': 'кВт', 'kw': 'кВт',
}
UNIT_RE = re.compile(r'(?<![а-яa-z])(' + '|'.join(re.escape(k) for k in sorted(UNIT_NAMES, key=len, reverse=True)) + r')(?![а-яa-z])', re.I)


def canonical_key(key: str, label: str = '') -> str | None:
    if key in definitions():
        return key
    if key in ALIASES:
        return ALIASES[key][0]
    text = (label or key).casefold().replace('ё', 'е').strip()
    if re.fullmatch(r'(?:габариты|размеры)(?: робота)?(?:[, (].*(?:мм|см|д[×xх]ш[×xх]в)\)?)?', text):
        return 'dimensions_mm'
    if text.startswith('грузоподъемность'):
        return 'payload_kg'
    if 'ширина проезда' in text or text.startswith('минимальная ширина прохода'):
        return 'min_aisle_width_m'
    if text.startswith(('максимальная скорость', 'макс. скорость')):
        return 'max_speed_ms'
    if text.startswith('скорость с грузом'):
        return 'speed_loaded_ms'
    if text.startswith('скорость без груза'):
        return 'speed_empty_ms'
    if text.startswith(('время работы', 'автономность')):
        return 'work_time_h'
    if text.startswith(('время зарядки', 'время заряда', 'время полной зарядки')):
        return 'charge_time_h'
    if re.match(r'^(вес|масса)(?:\s|,|\(|$)', text):
        return 'mass_kg'
    if 'высота подъема' in text or 'высота подьема' in text:
        return 'lift_height_mm'
    return None


def display_label(key: str, label: str | None = None) -> str:
    if label and label != key:
        return label
    canon = canonical_key(key)
    return CANON_LABELS.get(canon or key, label or key)


def _unit(text: str) -> str | None:
    units = {UNIT_NAMES[m.group(0).lower()] for m in UNIT_RE.finditer(text.lower())}
    return next(iter(units)) if len(units) == 1 else None


_NUMBER_TEXT = r'[+]?(?:\d{1,3}(?: \d{3})+|\d+)(?:[.,]\d+)?'
_UNIT_TEXT = r'[a-zа-я/ .]*?'


def upper_bound_text(text: str) -> str:
    """Явная верхняя граница/диапазон → одна величина, до пересчёта единиц."""
    text = text.strip().replace('\u00a0', ' ').replace('\u202f', ' ')
    limit = re.fullmatch(rf'(?:до\s+|не более\s+|up to\s+|≤\s*|<=\s*)({_NUMBER_TEXT})\s*({_UNIT_TEXT})', text, re.I)
    if limit:
        return f'{limit[1]} {limit[2]}'.strip()
    interval = re.fullmatch(rf'(?:от\s+)?({_NUMBER_TEXT})\s*({_UNIT_TEXT})\s*(?:-|–|—|~|…|до)\s*({_NUMBER_TEXT})\s*({_UNIT_TEXT})', text, re.I)
    if not interval:
        return text
    left, right = (float(interval[i].replace(' ', '').replace(',', '.')) for i in (1, 3))
    left_suffix, right_suffix = (interval[i].strip().rstrip('.').casefold() for i in (2, 4))
    left_unit, right_unit = UNIT_NAMES.get(left_suffix), UNIT_NAMES.get(right_suffix)
    if (left_suffix and not left_unit) or (right_suffix and not right_unit):
        return text
    # Единица в конце распространяется на весь диапазон; разные единицы
    # приводятся к единице правой границы перед выбором максимума.
    left_unit = left_unit or right_unit
    right_unit = right_unit or left_unit
    if left_unit != right_unit:
        group = next((g for g in UNIT_GROUPS.values() if left_unit in g and right_unit in g), None)
        if group is None:
            return text
        left *= group[left_unit] / group[right_unit]
    return f'{max(left, right):.12g} {right_unit or ""}'.strip()


def _normalize_scalar(key: str, value: object, label: str = '', unit: str | None = None) -> tuple[str, object, str | None] | None:
    canon = canonical_key(key, label)
    if canon is None:
        return None
    definition = definitions()[canon]
    target = NUMERIC_UNITS.get(canon)
    if canon == 'dimensions_mm':
        match = re.fullmatch(r'\s*(\d+(?:[.,]\d+)?)\s*[xх×*]\s*(\d+(?:[.,]\d+)?)\s*[xх×*]\s*(\d+(?:[.,]\d+)?)\s*([а-яa-z]*)\s*', str(value), re.I)
        if not match:
            return None
        source = _unit(match[4]) if match[4] else (_unit(unit or '') or _unit(label) or ('мм' if key == canon else None))
        if source not in UNIT_GROUPS['length']:
            return None
        factor = UNIT_GROUPS['length'][source] / .001
        numbers = [format(round(float(match[i].replace(',', '.')) * factor, 8), 'g') for i in (1, 2, 3)]
        return canon, ' × '.join(numbers), 'мм'
    if target is None:
        # Не интерпретируем произвольные текстовые поля как числа.
        return (canon, value, definition.get('unit')) if key == canon else None
    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip().replace('\u00a0', ' ').replace('\u202f', ' ')
    # По согласованному правилу берём верхнюю границу диапазона.
    text = upper_bound_text(text)
    # Несколько режимов, 24/7 и произвольные пояснения по-прежнему не угадываем.
    match = re.fullmatch(r'([+]?(?:\d{1,3}(?: \d{3})+|\d+)(?:[.,]\d+)?)\s*([a-zа-яА-Я/ .°]*)', text, re.I)
    if not match:
        return None
    number = float(match[1].replace(' ', '').replace(',', '.'))
    suffix = match[2].strip().rstrip('.').casefold()
    if suffix and suffix not in UNIT_NAMES:
        return None
    source_unit = UNIT_NAMES.get(suffix) if suffix else None
    if source_unit is None:
        source_unit = _unit(unit or '') or _unit(label) or ALIASES.get(key, ('', ''))[1] or (target if key == canon else None)
    if not source_unit:
        return None
    group = next((g for g in UNIT_GROUPS.values() if target in g and source_unit in g), None)
    if group is None or not math.isfinite(number):
        return None
    number = round(number * group[source_unit] / group[target], 10)
    return canon, int(number) if number.is_integer() else number, target


def _normalize_attrs_basic(attrs: dict[str, dict], labels: dict[str, str], units: dict[str, str | None] | None = None) -> tuple[dict[str, dict], list[dict]]:
    """Нормализует packed attrs. Сохраняет source_id/quote и все исходные поля.

    Совпадающие алиасы помечаются alias_of; конфликтующие остаются видимыми.
    Для старого автоматически выведенного значения восстановление допускается
    только при том же источнике, отсутствии ручного подтверждения/цитаты и
    совпадении с результатом старого извлечения первого числа.
    """
    result = deepcopy(attrs)
    issues = []
    units = units or {}
    # Старый expand_known_specs выдавал первое число диапазона за точное и
    # максимальную скорость за скорость с грузом. Сохраняем ошибочное значение
    # в provenance, исключая его из расчётов; ручные данные не трогаем.
    for key, original in attrs.items():
        label = labels.get(key, key)
        canon = canonical_key(key, label)
        if key == canon or canon not in NUMERIC_UNITS or original.get('status') != 'known':
            continue
        converted = _normalize_scalar(key, original.get('value'), label, original.get('unit') or units.get(key))
        old_key = 'speed_loaded_ms' if canon == 'max_speed_ms' else canon
        if converted is not None and old_key == canon:
            continue
        current = attrs.get(old_key) or {}
        number = re.search(r'\d+(?:[.,]\d+)?', str(original.get('value')).replace(' ', ''))
        if (current.get('status') == 'known' and not current.get('confirmed') and not current.get('quote')
                and not current.get('normalization_original') and not current.get('normalized_from')
                and current.get('source_id') is not None and current.get('source_id') == original.get('source_id')
                and number and str(current.get('value')) in {number[0].replace(',', '.'), str(float(number[0].replace(',', '.')))}):
            result[old_key] = {**current, 'status': 'unknown', 'value': None,
                               'normalization_previous': deepcopy(current),
                               'note': 'Старое автоматическое извлечение неоднозначно; требуется проверка источника.'}
            issues.append({'key': key, 'canonical_key': old_key, 'reason': 'invalidated_legacy_inference', 'previous': current.get('value')})
    for key, original in sorted(attrs.items(), key=lambda pair: (canonical_key(pair[0], labels.get(pair[0], pair[0])) != pair[0], pair[0])):
        if original.get('status') == 'not_applicable':
            canon = canonical_key(key, labels.get(key, key))
            if canon and canon != key:
                current = result.get(canon)
                if current is None or current.get('status') in {'unknown', 'not_applicable'}:
                    result[canon] = {**original, 'value': None, 'unit': definitions()[canon].get('unit'), 'normalized_from': key}
                    result[canon].pop('alias_of', None)
                    result[key]['alias_of'] = canon
                else:
                    result[key].pop('alias_of', None)
                    issues.append({'key': key, 'canonical_key': canon, 'reason': 'status_conflict'})
            continue
        if result.get(key, {}).get('status') != 'known' or original.get('status') != 'known' or original.get('value') in (None, ''):
            continue
        label = labels.get(key, key)
        converted = _normalize_scalar(key, original['value'], label, original.get('unit') or units.get(key))
        if converted is None:
            if canonical_key(key, label) in NUMERIC_UNITS:
                issues.append({'key': key, 'reason': 'ambiguous_value_or_unit', 'value': original['value']})
            continue
        canon, value, unit = converted
        bounded = upper_bound_text(str(original['value'])) != str(original['value']).strip().replace('\u00a0', ' ').replace('\u202f', ' ')
        if canon == key:
            if canon not in NUMERIC_UNITS and canon != 'dimensions_mm':
                continue
            result[key] = {**result[key], 'value': value, 'unit': unit}
            if bounded:
                result[key]['normalization_rule'] = 'upper_bound'
            if value != original['value'] or original.get('unit') != unit:
                result[key].setdefault('normalization_original', deepcopy(original))
            continue
        candidate = {**original, 'value': value, 'unit': unit, 'normalized_from': key}
        candidate.pop('alias_of', None)
        if bounded:
            candidate['normalization_rule'] = 'upper_bound'
        current = result.get(canon)
        usable = current and current.get('status') == 'known' and current.get('value') not in (None, '')
        if usable:
            current_value = _normalize_scalar(canon, current['value'], labels.get(canon, ''), current.get('unit'))
            same = current_value and current_value[1] == value
            legacy_number = re.search(r'\d+(?:[.,]\d+)?', str(original['value']).replace(' ', ''))
            legacy_current = attrs.get(canon, current)
            legacy = (not legacy_current.get('confirmed') and not legacy_current.get('quote') and not legacy_current.get('normalized_from')
                      and not legacy_current.get('normalization_original')
                      and current.get('source_id') == original.get('source_id') and legacy_number
                      and str(current['value']) in {legacy_number[0].replace(',', '.'), str(float(legacy_number[0].replace(',', '.')))})
            derived = current.get('normalized_from') == key and current.get('source_id') == original.get('source_id') and not current.get('confirmed')
            if not same and not legacy and not derived:
                result[key].pop('alias_of', None)
                issues.append({'key': key, 'canonical_key': canon, 'reason': 'conflict', 'value': original['value'], 'canonical_value': current['value']})
                continue
            if same:
                result[key]['alias_of'] = canon
                continue
            candidate['normalization_previous'] = deepcopy(current)
            issues.append({'key': key, 'canonical_key': canon, 'reason': 'repaired_legacy_conversion', 'previous': current['value'], 'value': value})
        elif current and current.get('status') == 'not_applicable':
            result[key].pop('alias_of', None)
            issues.append({'key': key, 'canonical_key': canon, 'reason': 'status_conflict'})
            continue
        result[canon] = candidate
        result[key]['alias_of'] = canon
    return result, issues


def expand_known_specs(attributes: dict[str, str], labels: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    """Совместимость для клиентов старой функции; запись БД использует normalize_attrs."""
    packed, _ = normalize_attrs({key: {'status': 'known', 'value': value} for key, value in attributes.items()}, labels)
    return ({key: str(item['value']) for key, item in packed.items()},
            {key: display_label(key, labels.get(key)) for key in packed})


def normalize_value(key: str, value: object, label: str = '', unit: str | None = None) -> tuple[str, object, str | None] | None:
    from app.domain.spec_details import details
    simple = _normalize_scalar(key, value, label, unit)
    if simple is not None:
        return simple
    values, _ = details(key, value, label, unit)
    canon = canonical_key(key, label)
    if canon in values:
        return canon, values[canon]['value'], values[canon]['unit']
    return None


def normalize_attrs(attrs: dict[str, dict], labels: dict[str, str], units: dict[str, str | None] | None = None) -> tuple[dict[str, dict], list[dict]]:
    from app.domain.spec_details import details
    result, issues = _normalize_attrs_basic(attrs, labels, units)
    units = units or {}
    for key, original in attrs.items():
        if original.get('status') != 'known' or original.get('value') in (None, ''):
            continue
        # Числовой результат уже нормализован. Его метаданные не теряются.
        if not isinstance(original['value'], str):
            continue
        if _normalize_scalar(key, original['value'], labels.get(key, key), original.get('unit') or units.get(key)) is not None:
            continue
        values, reason = details(key, original['value'], labels.get(key, key), original.get('unit') or units.get(key))
        if not values:
            if reason:
                for issue in issues:
                    if issue.get('key') == key and issue['reason'] == 'ambiguous_value_or_unit':
                        issue['reason'] = reason
            continue
        success = True
        for target, parsed in values.items():
            current = result.get(target)
            same = current and current.get('status') == 'known' and current.get('value') == parsed['value']
            owned = current and current.get('normalized_from') == key and current.get('source_id') == original.get('source_id') and not current.get('confirmed')
            # Не подменяем смысл равного числа (например 12 ч с нагрузкой/без).
            blocked = current and target != key and not owned and (
                current.get('confirmed') or current.get('status') == 'not_applicable'
                or (current.get('status') == 'known' and not same))
            if blocked:
                issues.append({'key': key, 'canonical_key': target, 'reason': 'conflict', 'value': original['value'], 'canonical_value': current.get('value')})
                success = False
                continue
            if same and target != key and not owned:
                continue
            candidate = {k: v for k, v in original.items() if k not in {'alias_of', 'normalized_fields'}}
            candidate.update(parsed)
            candidate['status'] = 'known'
            candidate['normalized_from'] = key
            candidate['normalization_input'] = original['value']
            if target == key:
                candidate.setdefault('normalization_original', deepcopy(original))
            if current:
                for history in ('normalization_previous', 'normalization_original'):
                    if history in current:
                        candidate.setdefault(history, current[history])
                if not same and current.get('status') == 'known' and 'normalization_previous' not in candidate:
                    candidate['normalization_previous'] = deepcopy(current)
            result[target] = candidate
        if success:
            issues = [i for i in issues if not (i.get('key') == key and i['reason'] in {'ambiguous_value_or_unit', 'conflict'})]
            if key not in values:
                result[key]['alias_of'] = next(iter(values))
                result[key]['normalized_fields'] = sorted(values)
        else:
            result[key].pop('alias_of', None)
    return result, issues
