"""Границы допуска: независимые функции и публичный API на отдельной тестовой БД."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from app.domain.assessment import functional_reasons, select_hit, validate_metadata
from app.domain.match import FilterRule, RobotView, match_robots, robot_count
from app.domain.formula import evaluate, FormulaError
from app.domain.sizing import size_equipment
from app.domain.economy import calculate

FACTS = {'version': 1, 'reviewed': True, 'evidence': ['Паспорт тестовой конфигурации'],
         'solution_kind': 'robot', 'control_mode': 'autonomous', 'execution_class': 'mobile_transport',
         'configuration_complete': True, 'price_complete': True, 'environments': ['indoor'], 'capabilities': ['move'], 'equipment': ['tray']}
PROFILE = {'version': 1, 'reviewed': True, 'evidence': ['Проверенный тестовый профиль'],
           'allowed_kinds': ['robot'], 'allowed_controls': ['autonomous'], 'environments': ['indoor'],
           'critical_site_keys': ['load', 'aisle'], 'critical_robot_keys': ['payload_kg', 'min_aisle_width_m'],
           'required_checks': ['Груз', 'Проезд'], 'required_equipment': ['tray'],
           'sizing': {'model': 'mobile_cycle_v1', 'flow_unit': 'items/day', 'quantity_unit': 'machines'}}
RULES = (FilterRule('Груз', ('load',), ('payload_kg',), '>=', 'hard'),
         FilterRule('Проезд', ('aisle',), ('min_aisle_width_m',), '<=', 'hard'))
ATTRS = {'payload_kg': 100, 'min_aisle_width_m': 1, 'speed_loaded_ms': 1, 'speed_empty_ms': 2}
SITE = {'load': 50, 'aisle': 2, 'flow_per_day': 1000, 'route_len_m': 100,
        't_load_s': 30, 't_unload_s': 30, 'batch_size': 1, 'availability': .8,
        'reserve_count': 0, 'shift_hours': 8, 'shifts_per_day': 1}


def run(site=None, attrs=None, facts=None, profile=None, rules=RULES):
    return match_robots(process_code='move', process_name='Перевозка', site=SITE if site is None else site,
                        rules=rules, robots=(RobotView('a', 'Тест', 'a', ATTRS if attrs is None else attrs,
                                                      assessment=FACTS if facts is None else facts),),
                        profile=PROFILE if profile is None else profile)[0]


def codes(hit):
    return {r.code for r in hit.reasons}


def test_reviewed_complete_candidate_can_pass():
    assert run().verdict == 'pass'


def test_empty_site_never_passes():
    hit = run(site={})
    assert hit.verdict == 'unknown'
    assert 'site_input_missing' in codes(hit)


def test_missing_bindings_do_not_skip_checks():
    rule = FilterRule('Груз', (), (), 'formula', 'hard', (('load', 'Груз'),), 'robot.payload_kg >= load')
    hit = run(rules=(rule,))
    assert hit.verdict == 'unknown'
    assert 'site_binding_missing' in codes(hit)


@pytest.mark.parametrize('profile,rules', [(PROFILE, ()),
                                             ({**PROFILE, 'required_checks': ['Несуществующая проверка']}, RULES)])
def test_insufficient_process_profile(profile, rules):
    assert run(profile=profile, rules=rules).verdict == 'unknown'


def test_unknown_critical_attribute():
    hit = run(attrs={'min_aisle_width_m': 1})
    assert hit.verdict == 'unknown'
    assert 'robot_attribute_missing' in codes(hit)


@pytest.mark.parametrize('missing', ['solution_kind', 'control_mode', 'environments'])
def test_unknown_identity_or_control_is_not_compatibility(missing):
    f = deepcopy(FACTS); f.pop(missing)
    assert run(facts=f).verdict == 'unknown'


def test_editorial_review_does_not_gate_published_facts():
    assert run(facts={**FACTS, 'reviewed': False}, profile={**PROFILE, 'reviewed': False}).verdict == 'pass'
    assert run(facts={**FACTS, 'reviewed': False, 'environments': ['outdoor']}).verdict == 'fail'
    assert run(profile={}).verdict == 'pass'  # Рабочие правила не требуют отдельного разрешения.
    f = deepcopy(FACTS); f.pop('execution_class'); f.pop('configuration_complete')
    assert run(facts=f).verdict == 'pass'  # Эти сведения нужны количеству/экономике.


def test_uav_outside_is_incompatible_with_corridor_regardless_of_numbers():
    hit = run(facts={**FACTS, 'execution_class': 'aerial_mission', 'environments': ['outdoor']})
    assert hit.verdict == 'fail'
    assert 'environment_incompatible' in codes(hit)


@pytest.mark.parametrize('kind', ['software', 'component', 'operator_equipment'])
def test_incomplete_solution_cannot_be_a_robot(kind):
    hit = run(facts={**FACTS, 'solution_kind': kind, 'control_mode': 'operator'})
    assert hit.verdict == 'fail'
    assert 'incomplete_solution' in codes(hit)


def test_family_or_missing_module_is_not_ready():
    assert run(facts={**FACTS, 'solution_kind': 'family', 'configuration_complete': False}).verdict != 'pass'
    assert 'equipment_missing' in codes(run(facts={**FACTS, 'equipment': []}))


def test_sizing_has_explicit_units_no_mandatory_reserve():
    sized = size_equipment(PROFILE, FACTS, SITE, ATTRS)
    assert sized.count == 10
    assert size_equipment(PROFILE, FACTS, {**SITE, 'reserve_count': 2}, ATTRS).count == 12
    assert size_equipment(PROFILE, FACTS, {**SITE, 'flow_per_day': 0}, ATTRS).count == 0


def test_asrs_never_uses_mobile_sizing():
    result = size_equipment(PROFILE, {**FACTS, 'execution_class': 'automated_storage'}, SITE, ATTRS)
    assert result.count is None
    assert result.reasons[0].code == 'sizing_incompatible'


def test_unknown_models_and_capacity_units():
    assert size_equipment({}, FACTS, SITE, ATTRS).count is None
    assert size_equipment({'sizing': {'model': 'unknown'}}, FACTS, SITE, ATTRS).count is None
    p = {**PROFILE, 'sizing': {**PROFILE['sizing'], 'flow_unit': 'm2/h'}}
    assert size_equipment(p, FACTS, SITE, ATTRS).reasons[0].code == 'sizing_unit_incompatible'


@pytest.mark.parametrize('key,value', [('batch_size', 0), ('batch_size', 1.5), ('reserve_count', -.5),
    ('availability', 0), ('route_len_m', -1), ('shift_hours', float('nan')), ('speed_loaded_ms', float('inf'))])
def test_bad_sizing_inputs_are_diagnostic(key, value):
    result = size_equipment(PROFILE, FACTS, {**SITE, key: value}, {**ATTRS, key: value})
    assert result.count is None and result.reasons


@pytest.mark.parametrize('formula', ['-1', '1.5', '1 / 0', 'sqrt(-1)', '1' + '0' * 400])
def test_count_rejects_invalid_or_nonfinite_result(formula):
    count, note = robot_count(formula, (), {}, {}, {})
    assert count is None and note


@pytest.mark.parametrize('formula,value', [('1 == 1 or 2 == 2', True), ('1 == 0 and 2 == 2', False),
                                          ('min(1,2)', 1), ('max(1, 2)', 2), ('round(1.234,2)', 1.23)])
def test_formula_boolean_and_argument_parsing(formula, value):
    assert evaluate(formula, {}) == value


@pytest.mark.parametrize('formula', ['sqrt(-1)', 'ceil(1/0)', 'round(1,1.2)', 'min()', '1e900'])
def test_formula_errors_are_formula_errors(formula):
    with pytest.raises(FormulaError):
        evaluate(formula, {})


@pytest.mark.parametrize('count', [None, -1, 1.1, float('nan'), float('inf'), True])
def test_unknown_count_takes_one_marked_robot_and_marks_report_incomplete(count):
    # Решение команды: количество не посчитано — в расчёте 1 робот с пометкой, пользователь задаёт своё число.
    # Расчёт при этом неполный, и причина видна в blockers.
    report = calculate([{'process_code': 'move', 'price_rub': 100, 'count': count}])
    assert report['status'] == 'incomplete'
    assert report['fleet'][0]['count_used'] == 1
    assert report['fleet'][0]['count_source'] == 'default'
    assert any(item['code'] == 'count_default' for item in report['blockers'])


def test_confirmed_fleet_with_independent_labor_can_have_complete_economy():
    e = calculate([{'process_code': 'move', 'price_rub': 100, 'count': 2}],
                  {'staff_salary_year_rub': 1000000}, tasks=[{'process_code': 'move', 'staff_fte_now': 1}])
    assert e['complete'] is True


def test_human_baseline_does_not_follow_robot_number():
    def report(n):
        return calculate([{'process_code': 'move', 'price_rub': 100, 'count': n}],
                         {'staff_salary_year_rub': 1000000, 'shift_hours': 8, 'shifts_per_day': 1, 'days_year': 365},
                         tasks=[{'process_code': 'different', 'staff_fte_now': 1}])
    assert report(1)['payroll']['value'] == report(100)['payroll']['value'] == 0
    assert report(1)['status'] == report(100)['status'] == 'incomplete'
    assert report(1)['scenarios'][1]['payback']['value'] is None


def test_partial_project_is_incomplete_but_keeps_calculated_numbers():
    e = calculate([{'process_code': 'move', 'price_rub': 100, 'count': 2}],
                  blockers=[{'code': 'process_not_selected', 'message': 'Одна операция не рассчитана'}])
    assert not e['complete']
    assert any(item['code'] == 'process_not_selected' for item in e['blockers'])
    # Посчитанное не прячется: пользователь видит, что уже есть, и что нужно дозаполнить.
    assert e['scenarios'][1]['capex']['value'] is not None


def test_no_auto_unknown_conditional_or_stale_choice():
    for verdict in ('unknown', 'conditional', 'fail'):
        group = {'best_product_id': 'a', 'hits': [{'product_id': 'a', 'verdict': verdict, 'count': 1, 'economic_ready': True}]}
        assert select_hit(group)[0] is None
        assert select_hit(group, 'a', explicit=True)[0] is None
    assert select_hit({'hits': []}, 'deleted', explicit=True)[1][0]['code'] == 'selection_invalid'


def test_python_and_frontend_selection_contract():
    fixtures = json.loads((Path(__file__).parent / 'fixtures/fleet-selection.json').read_text())
    for case in fixtures:
        hit, _ = select_hit(case['group'], case.get('chosen_id'), explicit=case.get('explicit', False))
        assert (hit or {}).get('product_id') == case['expected'], case['name']


def test_only_reviewed_metadata_with_evidence_can_be_saved():
    with pytest.raises(ValueError):
        validate_metadata({'reviewed': True}, product=True)
    with pytest.raises(ValueError):
        validate_metadata({'environments': 'indoor'}, product=True)
    with pytest.raises(ValueError):
        validate_metadata({'control_mode': 'guess'}, product=True)


def test_process_requirements_apply_without_editorial_review():
    hit = run(facts={**FACTS, 'environments': ['outdoor']}, profile={**PROFILE, 'reviewed': False})
    assert hit.verdict == 'fail'
    assert 'environment_incompatible' in codes(hit)


def test_capacity_input_units_cannot_be_smuggled_as_another_measure():
    result = size_equipment(PROFILE, FACTS, {**SITE, 'flow_per_day': '100 кг'}, ATTRS)
    assert result.count is None


def test_missing_labor_price_cannot_produce_savings():
    report = calculate([{'process_code': 'move', 'price_rub': 100, 'count': 2}],
                       tasks=[{'process_code': 'move', 'staff_fte_now': 1}])
    assert report['status'] == 'incomplete'
    assert not report['labor_baseline_complete']
    assert report['scenarios'][1]['payback']['value'] is None
    assert report['scenarios'][1]['effect']['value'] <= 0


@pytest.mark.parametrize('field,value', [('solution_kind', []), ('control_mode', {}), ('version', True)])
def test_malformed_metadata_is_validation_error(field, value):
    with pytest.raises(ValueError):
        validate_metadata({field: value}, product=True)


@pytest.mark.parametrize('site', [dict(SITE, flow_per_day=1e308), dict(SITE, shift_hours=1e-300, shifts_per_day=1e-300), dict(SITE, flow_per_day=10**400)])
def test_sizing_overflow_and_underflow_are_diagnostic(site):
    result = size_equipment(PROFILE, FACTS, site, ATTRS)
    assert result.count is None and result.reasons


def test_zero_robots_do_not_claim_personnel_savings():
    e = calculate([{'process_code': 'move', 'price_rub': 100, 'count': 0}],
                  {'staff_salary_year_rub': 1000000}, tasks=[{'process_code': 'move', 'staff_fte_now': 1}])
    assert e['status'] == 'incomplete'
    assert not e['fleet'][0]['included']
    assert e['fleet'][0]['count_used'] == 0
    assert not e['scenarios'][1]['effect']['value']
