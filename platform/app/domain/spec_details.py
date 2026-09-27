"""Разбор условий и режимов без смешивания разных физических величин."""
from __future__ import annotations

import re


def clean_text(value: object) -> str:
    text = re.sub('[\u200b-\u200f\ufeff]', '', str(value))
    text = text.replace('\u00a0', ' ').replace('\u202f', ' ')
    text = re.sub(r'\s*/\s*', '/', text)
    text = re.sub(r'км/(?:час(?:а|ов)?|ч\.)\b', 'км/ч', text, flags=re.I)
    return re.sub(r'\s+', ' ', text).strip()


def details(key: str, value: object, label: str = '', unit: str | None = None) -> tuple[dict[str, dict], str | None]:
    from app.domain.specs import canonical_key, _normalize_scalar, NUMERIC_UNITS
    canon = canonical_key(key, label)
    if canon not in NUMERIC_UNITS or not isinstance(value, str):
        return {}, None
    text = clean_text(value)

    def scalar(target: str, raw: str, condition: str = '', *, default_unit: bool = True) -> dict | None:
        approximate = bool(re.match(r'^(?:[~≈]|около\b|примерно\b)', raw, re.I))
        stripped = re.sub(r'^(?:[~≈]\s*|(?:около|примерно)\s+)', '', raw, flags=re.I)
        stripped = re.sub(r'^<\s*(?![=])', 'до ', stripped)
        # Для неизвестного алиаса единица по-прежнему обязательна.
        parsed = _normalize_scalar(target if default_unit else key, stripped, label, unit)
        if parsed is None:
            return None
        result = {'value': parsed[1], 'unit': parsed[2]}
        if approximate:
            result['approximate'] = True
        if condition:
            result['condition'] = condition
        return result

    def pair(pattern: str, first: str, second: str, conditions: tuple[str, str], primary: str | None = None):
        match = re.fullmatch(pattern, text, re.I)
        if not match:
            return None
        a, b = scalar(first, match[1], conditions[0]), scalar(second, match[2], conditions[1])
        if a is None or b is None:
            return {}, 'unparsed_modes'
        result = {first: a, second: b}
        if primary:
            result[canon] = dict(result[primary])
        return result, None

    if canon == 'payload_kg':
        if match := re.fullmatch(r'Бак чистой воды (.+?),?\s+бак грязной воды (.+)', text, re.I):
            a, b = scalar('clean_water_tank_l', match[1]), scalar('dirty_water_tank_l', match[2])
            return ({'clean_water_tank_l': a, 'dirty_water_tank_l': b}, None) if a and b else ({}, 'unparsed_tank')
        if match := re.fullmatch(r'Бак (?:для )?воды (.+)', text, re.I):
            a = scalar('water_tank_l', match[1])
            return ({'water_tank_l': a}, None) if a else ({}, 'unparsed_tank')
        parsed = pair(r'(.+?)\s*\(стоя\)\s*/\s*(.+?)\s*\(в движении\)', 'payload_static_kg', 'payload_kg', ('стоя', 'в движении'))
        if parsed:
            return parsed
        if match := re.fullmatch(r'(.+?)/(?:ярус|уровень)', text, re.I):
            a = scalar('payload_per_level_kg', match[1], 'на один ярус; общая грузоподъёмность не задана')
            return ({'payload_per_level_kg': a}, None) if a else ({}, 'unparsed_per_level')
    if canon == 'work_time_h':
        parsed = pair(r'(.+?)\s*\(без нагрузки\)\s*[/,]\s*(.+?)\s*\(полная(?: нагрузка)?\)', 'work_time_empty_h', 'work_time_loaded_h', ('без нагрузки', 'полная нагрузка'), 'work_time_loaded_h')
        if parsed:
            return parsed
        parsed = pair(r'(.+?)\s*\(без нагрузки\)\s*/\s*(.+?)\s*\(с 20 кг\)', 'work_time_empty_h', 'work_time_at_20kg_h', ('без нагрузки', 'нагрузка 20 кг'), 'work_time_at_20kg_h')
        if parsed:
            return parsed
        parsed = pair(r'(.+?)[,;]?\s+Зарядка\s+(.+)', 'work_time_h', 'charge_time_h', ('', ''))
        if parsed:
            return parsed
        parsed = pair(r'(.+?)\s+Непрерывное движение\s+(.+)', 'work_time_h', 'work_time_motion_h', ('общая автономность; режим не уточнён', 'непрерывное движение'))
        if parsed:
            # Для общего расчёта выбирается подтверждённая автономность движения.
            values, reason = parsed
            if values:
                values['work_time_h'] = dict(values['work_time_motion_h'])
                values['work_time_general_h'] = scalar('work_time_general_h', re.split(r'\s+Непрерывное', text, flags=re.I)[0], 'режим не уточнён')
            return values, reason
        parsed = pair(r'(.+?)\s+Уборка пыли:\s*(.+)', 'work_time_cleaning_h', 'work_time_dust_h', ('основная уборка', 'уборка пыли'), 'work_time_cleaning_h')
        if parsed:
            return parsed
    if canon == 'max_speed_ms':
        parsed = pair(r'(.+?)\s+при обычной езде\s+и\s+(.+?)\s+при уборке', 'speed_travel_ms', 'speed_cleaning_ms', ('обычная езда', 'уборка'), 'speed_travel_ms')
        if parsed:
            return parsed
        parsed = pair(r'(.+?),\s*Угол подъема\s+(.+)', 'max_speed_ms', 'slope_max_deg', ('', ''))
        if parsed:
            return parsed

    # Одинаковые повторённые величины склеиваем, разные варианты не усредняем.
    tokens = re.findall(r'(?:от\s+)?\d+(?:[.,]\d+)?(?:\s*[-–—~]\s*\d+(?:[.,]\d+)?)?\s*(?:км/ч|м/с|кг|часов|часа|час|ч|мин|min)\.?', text, re.I)
    if len(tokens) > 1 and re.sub(r'\s+', '', ''.join(tokens)) == re.sub(r'\s+', '', text):
        parsed = [scalar(canon, token) for token in tokens]
        if all(parsed) and all(item == parsed[0] for item in parsed):
            return {canon: {**parsed[0], 'normalization_rule': 'deduplicated'}}, None
        return {}, 'different_variants'

    # Условие относится к ведущей величине, а не заменяется первым числом скобок.
    condition = ''
    raw = text
    if match := re.fullmatch(r'([^()]+?)\s*\((.+)\)', text):
        raw, condition = match[1].strip(), match[2].strip()
    elif match := re.fullmatch(r'(.+?)\s+при активной ходьбе', text, re.I):
        raw, condition = match[1], 'активная ходьба'
    parsed = scalar(canon, raw, condition, default_unit=key == canon)
    if parsed:
        if canon == 'charge_time_h' and re.search(r'90\s*%', condition):
            return {'charge_time_to_90_h': parsed}, None
        return {canon: parsed}, None
    if re.match(r'^(?:свыше|более|≥|>)', text, re.I):
        return {}, 'lower_bound_only'
    if re.fullmatch(r'\d+(?:[.,]\d+)?', text):
        return {}, 'missing_unit'
    if not re.search(r'\d', text):
        return {}, 'no_numeric_value'
    return {}, 'unparsed_description'
