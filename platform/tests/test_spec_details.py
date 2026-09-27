import pytest
from app.domain.specs import normalize_attrs, normalize_value


def packed(value, source=7, **extra):
    return {'status': 'known', 'value': value, 'source_id': source, 'quote': None, **extra}


@pytest.mark.parametrize('key,label,text,target,value,extra', [
    ('massa', 'Масса', '~35 кг', 'mass_kg', 35, {'approximate': True}),
    ('massa', 'Масса', 'примерно 47 кг', 'mass_kg', 47, {'approximate': True}),
    ('massa', 'Масса', '55 кг\u200b', 'mass_kg', 55, {}),
    ('massa', 'Масса', '35кг 35кг 35кг', 'mass_kg', 35, {}),
    ('massa', 'Масса', '18 кг (из них ~3 кг — голова)', 'mass_kg', 18, {'condition': 'из них ~3 кг — голова'}),
    ('speed', 'Максимальная скорость', '2,9 км / час', 'max_speed_ms', round(2.9/3.6, 10), {}),
    ('speed', 'Максимальная скорость', '0 ~ 3,2 км / ч', 'max_speed_ms', round(3.2/3.6, 10), {}),
    ('work', 'Время работы', '180 min 180 min', 'work_time_h', 3, {}),
    ('work', 'Время работы', '1.5-3 часа 1.5-3 часа', 'work_time_h', 3, {}),
    ('work', 'Время работы', '5~10 ч (Стандартный режим 8 ч)', 'work_time_h', 10, {'condition':'Стандартный режим 8 ч'}),
    ('charge', 'Время зарядки', '< 3 ч', 'charge_time_h', 3, {}),
    ('payload', 'Грузоподъёмность', 'до 40 кг (4 подноса, ~10 кг/уровень)', 'payload_kg', 40, {'condition':'4 подноса, ~10 кг/уровень'}),
    ('aisle', 'Минимальная ширина прохода', '90 см (без поворота)', 'min_aisle_width_m', .9, {'condition':'без поворота'}),
])
def test_cleanup_and_conditions(key, label, text, target, value, extra):
    raw = {key: packed(text)}
    result, issues = normalize_attrs(raw, {key:label})
    assert result[target]['value'] == value
    assert result[target]['source_id'] == 7
    for k,v in extra.items(): assert result[target][k] == v
    assert result[key]['value'] == text
    assert result[key]['alias_of'] == target
    again, _ = normalize_attrs(result, {key:label})
    assert again == result


@pytest.mark.parametrize('key,label,text,expected', [
    ('payload','Грузоподъёмность','120 кг (стоя) / 40 кг (в движении)', {'payload_static_kg':120,'payload_kg':40}),
    ('work','Время работы','12 ч (без нагрузки) / 6 ч (полная)', {'work_time_empty_h':12,'work_time_loaded_h':6,'work_time_h':6}),
    ('work','Время работы','5 ч (без нагрузки) / 4 ч (с 20 кг)', {'work_time_empty_h':5,'work_time_at_20kg_h':4,'work_time_h':4}),
    ('work','Время работы','10 часов, Зарядка 4 часа', {'work_time_h':10,'charge_time_h':4}),
    ('work','Время работы','10 часов Непрерывное движение 2,5 часа', {'work_time_h':2.5,'work_time_motion_h':2.5,'work_time_general_h':10}),
    ('work','Время работы','до 6 часов Уборка пыли: до 10 часов', {'work_time_h':6,'work_time_cleaning_h':6,'work_time_dust_h':10}),
    ('speed','Максимальная скорость','До 1.2 м/с при обычной езде и до 0,8 м/с при уборке', {'max_speed_ms':1.2,'speed_travel_ms':1.2,'speed_cleaning_ms':.8}),
    ('speed','Максимальная скорость','2-4 км/ч, Угол подъема 5°', {'max_speed_ms':round(4/3.6,10),'slope_max_deg':5}),
    ('payload','Грузоподъёмность','Бак чистой воды 28 л, бак грязной воды 30 л', {'clean_water_tank_l':28,'dirty_water_tank_l':30}),
    ('payload','Грузоподъёмность','Бак для воды 60 л', {'water_tank_l':60}),
    ('payload','Грузоподъёмность','10 кг/ярус', {'payload_per_level_kg':10}),
    ('charge','Время зарядки','2 ч (с 0% до 90%)', {'charge_time_to_90_h':2}),
])
def test_split_fields(key,label,text,expected):
    result, _ = normalize_attrs({key:packed(text)}, {key:label})
    for target,value in expected.items():
        assert result[target]['value'] == value
        assert result[target]['source_id'] == 7
    if 'water_tank_l' in expected or 'payload_per_level_kg' in expected or 'clean_water_tank_l' in expected:
        assert 'payload_kg' not in result
    if 'charge_time_to_90_h' in expected:
        assert 'charge_time_h' not in result
    assert normalize_attrs(result, {key:label})[0] == result


def test_canonical_conditional_keeps_original():
    result,_ = normalize_attrs({'mass_kg':packed('~35 кг')}, {})
    assert result['mass_kg']['value']==35
    assert result['mass_kg']['normalization_original']['value']=='~35 кг'
    assert normalize_attrs(result,{})[0]==result


@pytest.mark.parametrize('value,reason', [('120','missing_unit'),('свыше 50 кг','lower_bound_only'),('несколько подносов','no_numeric_value'),('2 кг 3 кг 3 кг','different_variants')])
def test_no_guessed_units_or_variants(value,reason):
    result,issues=normalize_attrs({'payload':packed(value)}, {'payload':'Грузоподъёмность'})
    assert 'payload_kg' not in result
    assert any(i['reason']==reason for i in issues)


def test_confirmed_work_time_is_protected():
    attrs={'work':packed('12 ч (без нагрузки) / 6 ч (полная)'), 'work_time_h':packed(9,source=9,confirmed=True)}
    result,issues=normalize_attrs(attrs,{'work':'Время работы'})
    assert result['work_time_h']['value']==9
    assert not result['work'].get('alias_of')
    assert any(i['reason']=='conflict' for i in issues)
