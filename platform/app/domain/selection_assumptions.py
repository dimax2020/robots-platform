"""Обоснования оценочных входов. Только проекция, без изменения исходных карточек."""
from copy import deepcopy

from app.domain.specs import NUMERIC_UNITS, display_label


def assumption(key, value, explanation, *, origin, **extra):
    return {'key': key, 'label': display_label(key), 'value': deepcopy(value),
            'unit': NUMERIC_UNITS.get(key, ''), 'origin': origin, 'explanation': explanation,
            'requires_vendor_confirmation': True, 'vendor_confirmed': False, **extra}


def catalog_assumptions(catalog):
    return [assumption(key, data.get('normalized_value', data.get('value')), data['explanation'],
                       origin=data['origin'], source_id=data.get('source_id'), source=data.get('source'),
                       derived_from=data.get('derived_from', []), unit=data.get('normalized_unit', data.get('unit', NUMERIC_UNITS.get(key, ''))))
            for key, data in catalog.provenance.items()
            if data.get('origin') in {'catalog_assumption', 'derived_assumption'} and key in catalog.values]


def assume_return_speed(row, catalog):
    """Консервативный режим возврата с той же скоростью, что и движение с грузом.

    Используем рабочее значение, не паспортный максимум/диапазон. Не исправляем
    конфликты, условия, явно заданные значения или not_applicable.
    """
    from app.domain.formula import _number
    key = 'speed_empty_ms'
    raw = (row.attrs or {}).get(key) or {}
    loaded = _number(catalog.values.get('speed_loaded_ms'))
    if (catalog.facts.get('execution_class') != 'mobile_transport' or loaded is None or loaded <= 0
            or key in catalog.values or key in catalog.issues
            or raw.get('status') in {'known', 'not_applicable', 'conflict'} or raw.get('conflict')):
        return
    catalog.values[key] = loaded
    catalog.provenance[key] = {
        **assumption(key, loaded, 'Скорость возврата без груза принята равной известной рабочей скорости с грузом. Более быстрый возврат не предполагается; режим требует проверки у вендора.', origin='derived_assumption'),
        'derived_from': ['speed_loaded_ms'], 'source': deepcopy(catalog.provenance.get('speed_loaded_ms', {}).get('source')),
        'source_id': catalog.provenance.get('speed_loaded_ms', {}).get('source_id'),
    }


def sizing_profile(profile, code, facts):
    """Выбор из действующего реестра по операции и установленному классу исполнения."""
    if profile.get('sizing'):
        return profile
    model = None
    if facts.get('execution_class') == 'mobile_transport':
        if code == 'cart_towing':
            model = 'towing_cycle_v1'
        elif code in {'pallet_transport', 'tote_delivery', 'baggage_transport', 'medicine_delivery', 'biomaterial_delivery'}:
            model = 'mobile_cycle_v1'
    elif code == 'floor_cleaning' and facts.get('execution_class') == 'mobile_cleaning':
        model = 'cleaning_area_v1'
    if not model:
        return profile
    return {**profile, 'sizing': {'model': model, 'quantity_unit': 'machines',
            'flow_unit': 'm2/day' if model == 'cleaning_area_v1' else 'items/day',
            **({'rate_basis': 'robot_mode'} if model == 'cleaning_area_v1' else {})}}


def commercial_assumptions(facts, price):
    """Базовый комплект отдельного робота можно оценивать, не объявляя цену полной.

    Явно неполная комплектация, семейства, ячейки и системы требуют уточнения.
    """
    if facts.get('solution_kind') != 'robot' or not price or price <= 0:
        return []
    labels = {'configuration_complete': 'Комплектация', 'price_complete': 'Состав цены'}
    explanations = {
        'configuration_complete': 'Оценивается базовая комплектация отдельного робота для указанной операции. Состав поставки и дополнительную оснастку необходимо уточнить у вендора.',
        'price_complete': 'Опубликованная цена используется как цена базового робота. Полнота поставки и стоимость дополнительных опций требуют уточнения у вендора; итоговая экономика предварительная.',
    }
    return [assumption(key, 'базовая поставка', explanations[key], origin='selection_policy', label=labels[key])
            for key in labels if facts.get(key) is None]
