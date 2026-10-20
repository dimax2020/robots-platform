"""Исполняемые требования процессов, без административного разрешения reviewed.

Существующие правила БД всегда сохраняются. Нет правил — нет доказанного pass:
это недостающая инженерная спецификация, а не очередь модерации карточек.
"""
from app.domain.assessment import checked, reason

INDOOR = frozenset('warehouse_inventory floor_cleaning pallet_transport rack_placement cart_towing pallet_storage order_picking medicine_delivery biomaterial_delivery tote_delivery baggage_transport parcel_sorting packing palletizing passenger_service ward_service'.split())
OUTDOOR = frozenset('aerial_survey apron_transport crop_monitoring field_spraying harvesting lawn_mowing outdoor_delivery perimeter_security ploughing road_works street_cleaning territory_inspection'.split())


def compile_requirements(code, rules, metadata=None, site=None):
    from app.domain.match import FilterRule
    supplied, errors = checked(metadata, product=False)
    policy = {'allowed_kinds': ['robot', 'cell', 'system'], 'allowed_controls': ['autonomous'],
              'environments': ['indoor'] if code in INDOOR else ['outdoor'] if code in OUTDOOR else [],
              'critical_robot_keys': [], 'critical_site_keys': [], 'required_checks': [], 'required_equipment': []}
    extra, bindings = [], {}
    if code == 'warehouse_inventory':
        # Сканирующий комплекс с тягачом технически допустим; труд/комплект считаются отдельно.
        policy.update(allowed_kinds=['robot', 'system', 'operator_equipment'], allowed_controls=['autonomous', 'operator', 'teleoperated'])
        extra = [
            FilterRule('Высота сканирования', (), (), 'formula', 'hard',
                       (('inventory_height', 'Высота хранения, м'),), 'robot.lift_height_mm >= inventory_height * 1000'),
            FilterRule('Проход инвентаризатора', ('aisle_width_m',), ('min_aisle_width_m',), '<=', 'hard'),
        ]
        bindings['inventory_height'] = 'storage_height_m'
    if not any(r.mode == 'hard' for r in (*rules, *extra)):
        errors.append(reason('process_checks_missing', 'Для процесса не заданы обязательные технические проверки'))
    for key, op, name in [('temp_min_c', '<=', 'Минимальная температура'), ('temp_max_c', '>=', 'Максимальная температура')]:
        if (site or {}).get(key) not in (None, ''):
            extra.append(FilterRule(name, (key,), (key,), op, 'hard'))
    effective = list(rules)
    for rule in extra:
        if rule not in effective:
            effective.append(rule)
    # Служебные отметки этапа 1 не являются требованиями процесса.
    for key, value in supplied.items():
        if key not in {'reviewed', 'requirements_reviewed', 'evidence', 'version'}:
            policy[key] = value
    # Нельзя потерять обязательные системные проверки при пустом legacy required_checks.
    policy['required_checks'] = list(dict.fromkeys([*policy.get('required_checks', []), *(r.name for r in extra)]))
    return policy, tuple(effective), bindings, errors
