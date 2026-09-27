import pytest

from app.domain.specs import normalize_attrs, normalize_value, display_label
from app.domain.csv_parse import parse_manual_csv


@pytest.mark.parametrize('key,label,value,unit,target,expected', [
    ('charge_min', '', '90', None, 'charge_time_h', 1.5),
    ('charge_time_h', '', '90 мин', None, 'charge_time_h', 1.5),
    ('vremya', 'Время зарядки, мин', '90', None, 'charge_time_h', 1.5),
    ('vremya', 'Время заряда батареи, час.', '1,5', None, 'charge_time_h', 1.5),
    ('vremya', 'Время работы', '7200 сек', None, 'work_time_h', 2),
    ('max_speed_attr', '', '3,6 км/ч', None, 'max_speed_ms', 1),
    ('speed', 'Максимальная скорость', '60 м/мин', None, 'max_speed_ms', 1),
    ('payload_kg', '', '1,5 т', None, 'payload_kg', 1500),
    ('weight', 'Масса, г', '500', None, 'mass_kg', .5),
    ('lift_height_m', '', '2.5', None, 'lift_height_mm', 2500),
    ('aisle', 'Минимальная ширина прохода', '700 мм', None, 'min_aisle_width_m', .7),
    ('charge_time_h', '', '120', 'мин', 'charge_time_h', 2),
    ('charge_time_h', '', '1.5 ч', 'мин', 'charge_time_h', 1.5),
])
def test_units(key, label, value, unit, target, expected):
    result = normalize_value(key, value, label, unit)
    assert result is not None
    assert result[0] == target
    assert result[1] == expected


@pytest.mark.parametrize('value', ['24/7', '1 ч 30 мин', 'нет данных', True, '2 кг', '-1 ч'])
def test_ambiguous_values_are_not_guessed(value):
    assert normalize_value('charge_time_h', value) is None


def packed(value, source=10, **extra):
    return dict(status='known', value=value, source_id=source, quote=None, **extra)


def test_preserves_source_and_quote_and_hides_only_equivalent_alias():
    original = {'charge_min': {**packed('90'), 'quote': 'Документация: 90 мин'}}
    result, issues = normalize_attrs(original, {})
    assert not issues
    assert result['charge_time_h']['value'] == 1.5
    assert result['charge_time_h']['source_id'] == 10
    assert result['charge_time_h']['quote'] == 'Документация: 90 мин'
    assert result['charge_min']['alias_of'] == 'charge_time_h'
    assert 'alias_of' not in original['charge_min']
    assert normalize_attrs(result, {})[0] == result


def test_conflicting_sources_survive_visible():
    original = {'charge_min': packed('90'), 'charge_time_h': packed('2', source=20)}
    result, issues = normalize_attrs(original, {})
    assert result['charge_time_h']['value'] == 2
    assert 'alias_of' not in result['charge_min']
    assert any(i['reason'] == 'conflict' for i in issues)


def test_fix_legacy_minutes_with_same_source():
    original = {'charge_min': packed('90'), 'charge_time_h': packed('90.0')}
    result, issues = normalize_attrs(original, {})
    assert result['charge_time_h']['value'] == 1.5
    assert any(i['reason'] == 'repaired_legacy_conversion' for i in issues)
    assert normalize_attrs(result, {})[0] == result


def test_manual_value_never_overwritten():
    original = {'charge_min': packed('90'), 'charge_time_h': packed('90.0', confirmed=True)}
    result, issues = normalize_attrs(original, {})
    assert result['charge_time_h']['value'] == 90
    assert any(i['reason'] == 'conflict' for i in issues)


def test_max_speed_is_not_loaded_speed():
    result, _ = normalize_attrs({'max_speed_attr': packed('3.6 км/ч')}, {})
    assert result['max_speed_ms']['value'] == 1
    assert 'speed_loaded_ms' not in result
    assert display_label('max_speed_attr') == 'Максимальная скорость'


def test_manual_csv_label_and_unit():
    row = parse_manual_csv('product_slug,attr_key,label,value,unit\nr,charge_time_h,Время зарядки,90,мин\n')[0]
    assert normalize_value(row.attr_key, row.value, row.label, row.unit)[1] == 1.5


def test_dimensions_cm_to_mm():
    assert normalize_value('gabarity', '10 × 20 × 30 см', 'Габариты') == ('dimensions_mm', '100 × 200 × 300', 'мм')


def test_parser_refresh_updates_derived_value():
    attrs, _ = normalize_attrs({'charge_min': packed('90')}, {})
    attrs['charge_min'] = packed('120')
    result, _ = normalize_attrs(attrs, {})
    assert result['charge_time_h']['value'] == 2


def test_legacy_range_uses_upper_bound():
    attrs = {'vremya': packed('2-4 ч'), 'charge_time_h': packed('2.0')}
    result, _ = normalize_attrs(attrs, {'vremya': 'Время зарядки'})
    assert result['charge_time_h']['value'] == 4
    assert result['charge_time_h']['normalization_rule'] == 'upper_bound'
    assert result['vremya']['value'] == '2-4 ч'
    assert normalize_attrs(result, {'vremya': 'Время зарядки'})[0] == result


def test_legacy_max_speed_does_not_remain_loaded_speed():
    attrs = {'max_speed_attr': packed('3.6 км/ч'), 'speed_loaded_ms': packed('3.6')}
    result, _ = normalize_attrs(attrs, {})
    assert result['max_speed_ms']['value'] == 1
    assert result['speed_loaded_ms']['status'] == 'unknown'


def test_not_applicable_is_preserved_under_canonical_key():
    result, issues = normalize_attrs({'charge_min': {'status': 'not_applicable', 'value': None, 'source_id': 10}}, {})
    assert not issues
    assert result['charge_time_h']['status'] == 'not_applicable'
    assert result['charge_time_h']['source_id'] == 10
    assert normalize_attrs(result, {})[0] == result


@pytest.mark.parametrize('value', ['1 час 30 мин', '24/7'])
def test_formula_rejects_ambiguous_numbers(value):
    from app.domain.formula import build_env
    assert build_env('robot.charge_time_h > 1', set(), {}, {}, {'charge_time_h': value})[0] == 'bad'


def test_formula_preserves_negative_numbers():
    from app.domain.formula import build_env
    status, env, _ = build_env('robot.temp_min_c < 0', set(), {}, {}, {'temp_min_c': '-20'})
    assert status == 'ok'
    assert env['robot.temp_min_c'] == -20


def test_formula_does_not_choose_between_productivity_modes():
    from app.domain.formula import build_env
    status, _, _ = build_env('robot.proizvoditelnost > 1', set(), {}, {},
                            {'proizvoditelnost': '1 200 м²/ч (макс), 700 м²/ч (при высоком трафике)'})
    assert status == 'bad'


@pytest.mark.parametrize('label', ['Габариты подносов', 'Габариты проезда', 'Габариты отсеков'])
def test_dimensions_of_parts_are_not_robot_dimensions(label):
    assert normalize_value('custom', '10 x 20 x 30 см', label) is None


@pytest.mark.parametrize('value,expected', [
    ('до 3 часов', 3), ('2-4 часа', 4), ('2–4 ч', 4), ('2—4 ч', 4),
    ('от 2 до 4 часов', 4), ('2~4 ч', 4), ('не более 3 ч', 3), ('≤ 3 ч', 3),
    ('120–240 мин', 4), ('до 90 минут', 1.5), ('1,5–2,5 ч', 2.5),
    ('2 ч - 4 ч', 4), ('90 мин - 2 ч', 2), ('4-2 ч', 4),
])
def test_upper_bound(value, expected):
    assert normalize_value('charge_time_h', value)[1] == expected
    result, _ = normalize_attrs({'charge_time_h': packed(value)}, {})
    assert result['charge_time_h']['value'] == expected
    assert result['charge_time_h']['normalization_original']['value'] == value
    assert normalize_attrs(result, {})[0] == result


def test_formula_uses_upper_bound_and_converts_minutes():
    from app.domain.formula import build_env
    status, env, _ = build_env('robot.charge_time_h > 1', set(), {}, {}, {'charge_time_h': '120-240 мин'})
    assert status == 'ok'
    assert env['robot.charge_time_h'] == 4
