"""Допуск при неполных данных: ограничения, происхождение и границы оценки."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.domain.assessment import select_hit
from app.domain.catalog_assessment import resolve_catalog
from app.domain.match import FilterRule, match_robots
from app.infrastructure.db.taxonomy_repo import _candidate_payload, _robot_view
from test_assessment import ATTRS, FACTS, PROFILE, RULES, SITE


def attributes(**changes):
    return {**{k: {'status': 'known', 'value': v, 'source_id': 1} for k, v in ATTRS.items()}, **changes}


def candidate(*, attrs=None, facts=None, site=None, rules=RULES, profile=PROFILE, sources=None, code='move'):
    facts = deepcopy(FACTS if facts is None else facts)
    facts['capabilities'] = [code]
    row = SimpleNamespace(id='a', name='Робот', slug='a', price_rub=1000, trl=8, availability='operation',
                          image_url=None, summary=None, column_sources={}, attrs=deepcopy(attrs if attrs is not None else attributes()))
    before = deepcopy(row.__dict__)
    site = SITE if site is None else site
    catalog = resolve_catalog(row, facts, process_code=code, site=site, sources=sources)
    hit = match_robots(process_code=code, process_name='Доставка', site=site, rules=rules,
                       robots=(_robot_view(row, catalog=catalog),), profile=profile)[0]
    payload = _candidate_payload(hit, row, facts, profile, site, None, catalog)
    assert before == row.__dict__
    return payload


def test_optional_unset_limit_does_not_block_but_explicit_limit_does():
    noise = FilterRule('Шум', ('noise_limit_dba',), ('uroven_shuma',), '<=', 'conditional')
    hit = candidate(rules=(*RULES, noise))
    assert hit['verdict'] == 'pass' and hit['economic_ready']
    assert hit['significant_reasons'] == []
    assert any(r['field'] == 'noise_limit_dba' for r in hit['clarifications'])
    hit = candidate(rules=(*RULES, noise), site={**SITE, 'noise_limit_dba': 40})
    assert hit['verdict'] == 'unknown' and not hit['economic_ready']
    assert candidate(rules=(*RULES, noise), site={**SITE, 'noise_limit_dba': 40},
                     attrs=attributes(uroven_shuma={'status': 'known', 'value': 60}))['verdict'] == 'fail'


def test_optional_formula_does_not_cancel_explicit_critical_site_key():
    rule = FilterRule('Шум', (), (), 'formula', 'conditional', (('noise', 'Лимит шума'),), 'robot.uroven_shuma <= noise')
    assert candidate(rules=(*RULES, rule))['verdict'] == 'unknown'  # Нет привязки — ошибка настройки.
    profile = {**PROFILE, 'critical_site_keys': ['load', 'aisle', 'noise_limit_dba']}
    assert candidate(rules=RULES, profile=profile)['verdict'] == 'unknown'


def test_noncritical_unknowns_are_only_in_clarifications():
    hit = candidate(attrs=attributes(color={'status': 'unknown', 'value': None, 'label': 'Цвет корпуса'}))
    assert hit['verdict'] == 'pass' and hit['economic_ready']
    assert not hit['significant_reasons']
    assert any(r['field'] == 'color' for r in hit['clarifications'])


def test_explicit_justified_assumption_passes_and_keeps_source():
    attrs = attributes(min_aisle_width_m={'status': 'known', 'value': 1, 'unit': 'м', 'source_id': 2})
    sources = {1: {'kind': 'vendor'}, 2: {'kind': 'assumption', 'publisher': 'Инженер', 'title': 'Оценка проезда для конкретного исполнения; проверить на площадке'}}
    hit = candidate(attrs=attrs, sources=sources)
    assert hit['verdict'] == 'pass' and hit['applicability'] == 'conditional'
    assert hit['count'] == 10 and hit['economic_ready']
    assert hit['assumptions'][0]['source_id'] == 2
    assert hit['assumptions'][0]['explanation'] == sources[2]['title']
    assert 'min_aisle_width_m' in hit['vendor_confirmation_fields']
    assert select_hit({'hits': [hit]}, 'a', explicit=True)[0] == hit


@pytest.mark.parametrize('change', [dict(conflict=True), dict(unit='кг'), dict(conditions={'floor': 'smooth'})])
def test_assumption_cannot_resolve_conflict_wrong_units_or_unmet_conditions(change):
    attrs = attributes(min_aisle_width_m={'status': 'known', 'value': 1, 'unit': 'м', 'source_id': 2, **change})
    hit = candidate(attrs=attrs, sources={2: {'kind': 'assumption', 'title': 'Обоснованная оценка'}})
    assert hit['verdict'] == 'unknown' and not hit['economic_ready']
    assert not any(a['key'] == 'min_aisle_width_m' for a in hit['assumptions'])


def test_unjustified_assumption_is_unknown_and_known_failure_stays_failure():
    attrs = attributes(min_aisle_width_m={'status': 'known', 'value': 1, 'unit': 'м', 'source_id': 2, 'quote': '1 м'})
    assert candidate(attrs=attrs, sources={2: {'kind': 'assumption'}})['verdict'] == 'unknown'
    attrs['min_aisle_width_m']['value'] = 3
    assert candidate(attrs=attrs, sources={2: {'kind': 'assumption', 'title': 'Проверка проезда'}})['verdict'] == 'fail'


def test_return_speed_is_conservative_and_uses_existing_cycle():
    attrs = attributes(speed_empty_ms={'status': 'unknown', 'value': None})
    hit = candidate(attrs=attrs)
    assert hit['applicability'] == 'conditional' and hit['economic_ready']
    assert hit['count'] == 12  # Тот же mobile_cycle_v1, возврат со скоростью 1 м/с.
    assert hit['sizing']['inputs']['speed_empty_ms'] == ATTRS['speed_loaded_ms']
    assert hit['sizing']['input_provenance']['speed_empty_ms']['derived_from'] == ['speed_loaded_ms']
    assert hit['assumptions'][0]['origin'] == 'derived_assumption'
    for status in ['known', 'not_applicable', 'conflict']:
        attrs['speed_empty_ms'] = {'status': status, 'value': 'неоднозначно'}
        assert candidate(attrs=attrs)['count'] is None
    attrs['speed_empty_ms'] = {'status': 'known', 'value': .5}
    known = candidate(attrs=attrs)
    assert known['sizing']['inputs']['speed_empty_ms'] == .5
    assert not known['assumptions']


def test_missing_commercial_flags_do_not_require_confirmation_before_estimate():
    facts = {k: v for k, v in FACTS.items() if k not in {'configuration_complete', 'price_complete'}}
    hit = candidate(facts=facts)
    assert hit['economic_ready'] and hit['applicability'] == 'conditional'
    assert {a['key'] for a in hit['assumptions']} == {'configuration_complete', 'price_complete'}
    assert 'price_complete' not in hit['resolved_facts']
    assert not candidate(facts={**facts, 'price_complete': False})['economic_ready']
    assert not candidate(facts={**facts, 'configuration_complete': False})['economic_ready']
    assert not candidate(facts={**facts, 'solution_kind': 'system'}, profile={**PROFILE, 'allowed_kinds': ['system']})['economic_ready']


def test_existing_model_selected_for_known_operation_without_profile_sizing():
    hit = candidate(code='tote_delivery', profile={k: v for k, v in PROFILE.items() if k != 'sizing'})
    assert hit['economic_ready'] and hit['count'] == 10
    assert hit['sizing']['model'] == 'mobile_cycle_v1'
    unknown = candidate(profile={k: v for k, v in PROFILE.items() if k != 'sizing'})
    assert unknown['count'] is None and not unknown['economic_ready']
    assert 'Для этого решения не определена модель количества' not in unknown['count_note']
