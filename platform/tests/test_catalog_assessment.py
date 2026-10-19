"""Опубликованные данные, независимость этапов и реальные инвентаризаторы."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.domain.catalog_assessment import resolve_catalog
from app.domain.match import FilterRule, match_robots
from app.domain.assessment import select_hit
from app.infrastructure.db.taxonomy_repo import _robot_view, _candidate_payload

RULES = (FilterRule('Проезд', ('aisle_width_m',), ('min_aisle_width_m',), '<=', 'hard'),)


def packed(value, **kw):
    return {'status': 'known', 'value': value, 'source_id': 1, **kw}


def cleaner(**attrs):
    return SimpleNamespace(id='test', name='Тест', slug='test', price_rub=None, trl=8, availability='operation', image_url=None,
                           summary='Автономный мобильный робот для уборки полов', column_sources={'summary': 1},
                           attrs={'enclosure': packed('Indoor'), 'min_aisle_width_m': packed(1), **attrs})


def assess(row=None, *, site=None, metadata=None, rules=RULES, profile=None, code='floor_cleaning', name='Уборка полов'):
    row = row or cleaner()
    site = {'aisle_width_m': 2} if site is None else site
    catalog = resolve_catalog(row, metadata, process_code=code, process_name=name, site=site,
                              sources={1: {'id': 1, 'kind': 'vendor', 'url': 'https://vendor.example/spec'}})
    hit = match_robots(process_code=code, process_name=name, site=site, rules=rules,
                       robots=(_robot_view(row, catalog=catalog),), profile=profile)[0]
    return _candidate_payload(hit, row, metadata, profile or {}, site, None, catalog)


def test_published_card_passes_without_assessment_price_configuration_or_sizing():
    row = cleaner()
    before = deepcopy(row.__dict__)
    hit = assess(row)
    assert hit['verdict'] == 'pass' and hit['technical_ready']
    assert hit['count'] is None and not hit['sizing_ready'] and not hit['economic_ready']
    assert {'price_missing', 'price_scope_unconfirmed', 'configuration_missing', 'sizing_model_missing'} <= {r['code'] for r in hit['economic_reasons']}
    assert hit['provenance']['min_aisle_width_m']['source']['kind'] == 'vendor'
    assert hit['resolved_facts']['capabilities'] == ['floor_cleaning']
    assert row.__dict__ == before


@pytest.mark.parametrize('attrs,site,verdict', [
    ({'min_aisle_width_m': {'status': 'unknown', 'value': None}}, {'aisle_width_m': 2}, 'unknown'),
    ({'min_aisle_width_m': packed(3)}, {'aisle_width_m': 2}, 'fail'),
    ({}, {}, 'unknown'),
    ({'enclosure': packed('Outdoor')}, {'aisle_width_m': 2}, 'fail'),
    ({'min_aisle_width_m': packed(1, conflict=True)}, {'aisle_width_m': 2}, 'unknown'),
])
def test_missing_is_unknown_and_known_incompatibility_fails(attrs, site, verdict):
    assert assess(cleaner(**attrs), site=site)['verdict'] == verdict


def test_units_and_source_are_retained_without_changing_catalog():
    hit = assess(cleaner(min_aisle_width_m=packed(700, unit='мм', quote='700 мм')))
    assert hit['verdict'] == 'pass'
    evidence = hit['provenance']['min_aisle_width_m']
    assert evidence['normalized_value'] == .7 and evidence['normalized_unit'] == 'м'
    assert evidence['normalization_original']['value'] == 700
    assert evidence['quote'] == '700 мм' and evidence['source_id'] == 1


def test_alias_conflict_is_not_silently_resolved():
    hit = assess(cleaner(aisle=packed('3 м', label='Минимальная ширина прохода')))
    assert hit['verdict'] == 'unknown'
    assert any(r['code'] == 'catalog_attribute_ambiguous' for r in hit['reasons'])


def test_explicit_operating_conditions_are_not_ignored():
    row = cleaner(min_aisle_width_m=packed(1, conditions={'floor_type': 'smooth'}))
    assert assess(row)['verdict'] == 'unknown'
    assert assess(row, site={'aisle_width_m': 2, 'floor_type': 'smooth'})['verdict'] == 'pass'


def test_upper_runtime_bound_does_not_become_guaranteed_shift():
    rules = (*RULES, FilterRule('Смена', ('shift_hours',), ('work_time_h',), '>=', 'hard'))
    hit = assess(cleaner(work_time_h=packed('до 12 ч')), rules=rules, site={'aisle_width_m': 2, 'shift_hours': 8})
    assert hit['verdict'] == 'unknown'
    assert any(r['code'] == 'catalog_attribute_ambiguous' for r in hit['reasons'])


@pytest.mark.parametrize('temperature,expected', [(None, 'unknown'), (0, 'fail'), (-30, 'pass')])
def test_explicit_site_temperature_is_a_requirement(temperature, expected):
    attrs = {} if temperature is None else {'temp_min_c': packed(temperature)}
    assert assess(cleaner(**attrs), site={'aisle_width_m': 2, 'temp_min_c': -10})['verdict'] == expected


def test_source_assumption_cannot_supply_required_attribute():
    row = cleaner()
    catalog = resolve_catalog(row, process_code='floor_cleaning', sources={1: {'kind': 'assumption'}})
    assert 'min_aisle_width_m' not in catalog.values


def test_climate_check_does_not_replace_missing_process_specification():
    hit = assess(cleaner(temp_min_c=packed(-30)), rules=(), site={'temp_min_c': -10})
    assert hit['verdict'] == 'unknown'
    assert any(r['code'] == 'process_checks_missing' for r in hit['reasons'])


def test_family_is_unknown_and_optional_marking_is_not_mandatory():
    row = cleaner(infrastructure_req=packed('Опциональная QR-маркировка'))
    assert assess(row)['verdict'] == 'pass'
    row.summary = 'Серия автономных мобильных роботов для уборки полов'
    assert assess(row)['verdict'] == 'unknown'


def test_review_flags_do_not_change_admission_and_contradictions_are_visible():
    assert assess(metadata={'reviewed': False})['verdict'] == 'pass'
    assert assess(metadata={'control_mode': 'operator'})['verdict'] == 'unknown'
    assert assess(metadata={'price_complete': False, 'configuration_complete': False})['verdict'] == 'pass'
    sizing_conflict = assess(cleaner(execution_class=packed('floor_cleaning')), metadata={'execution_class': 'mobile_transport'})
    assert sizing_conflict['verdict'] == 'pass'
    assert any(r['code'] == 'catalog_fact_conflict' for r in sizing_conflict['sizing']['reasons'])
    assert assess(metadata={'capabilities': ['other_operation']})['verdict'] == 'pass'


def test_plain_process_link_or_robot_name_does_not_prove_capability():
    row = cleaner(); row.summary = 'Мобильная платформа общего назначения'; row.name = 'Робот для уборки полов'
    hit = assess(row)
    assert hit['verdict'] == 'unknown'
    assert any(r['code'] == 'capability_unconfirmed' for r in hit['reasons'])


def test_explicit_negative_capability_is_a_failure_and_conflicting_text_is_unknown():
    row = cleaner()
    row.summary = 'Автономный мобильный робот не предназначен для уборки полов'
    assert assess(row)['verdict'] == 'fail'
    row.attrs['purpose'] = packed('Автономный мобильный робот для уборки полов')
    hit = assess(row)
    assert hit['verdict'] == 'unknown'
    assert any(r['code'] == 'catalog_fact_conflict' for r in hit['reasons'])


def test_sizing_is_independent_of_technical_failure():
    from test_assessment import FACTS, PROFILE, ATTRS, SITE
    row = cleaner(**{k: packed(v) for k, v in ATTRS.items()})
    # Подтверждаем отрицательное условие, сохраняя все входы математической модели.
    hit = assess(row, metadata={**FACTS, 'capabilities': ['floor_cleaning']}, profile=PROFILE,
                 rules=(FilterRule('Груз', ('load',), ('payload_kg',), '>=', 'hard'), FilterRule('Проезд', ('aisle',), ('min_aisle_width_m',), '<=', 'hard')),
                 site={**SITE, 'load': 1000})
    assert hit['verdict'] == 'fail' and hit['count'] == 10 and hit['sizing_ready']
    assert not hit['economic_ready']
    assert select_hit({'hits': [hit], 'best_product_id': 'test'})[0] is None


def inventory_fixture():
    return json.loads((Path(__file__).parent / 'fixtures/inventory-catalog.json').read_text())


@pytest.mark.parametrize('index,control', [(0, 'operator'), (1, 'autonomous')])
def test_real_inventory_cards_use_catalog_and_report_actual_missing_inputs(index, control):
    fixture = inventory_fixture()
    row = SimpleNamespace(**fixture['products'][index], image_url=None)
    rules = tuple(FilterRule(r['name'], tuple(r['object_keys']), tuple(r['robot_keys']), r['op'], r['mode'],
                             tuple((i['key'], i['label']) for i in r['inputs']), r['formula']) for r in fixture['process_filters'])
    catalog = resolve_catalog(row, process_code='warehouse_inventory', process_name='Инвентаризация товаров', sources={s['id']: s for s in fixture['sources']})
    assert catalog.facts['control_mode'] == control
    assert catalog.facts['environments'] == ['indoor']
    assert 'warehouse_inventory' in catalog.facts['capabilities']
    assert catalog.values['lift_height_mm'] in (12000, 12500)
    h = match_robots(process_code='warehouse_inventory', process_name='Инвентаризация товаров', site=fixture['site'],
                     rules=rules, bindings=fixture['bindings'], robots=(_robot_view(row, catalog=catalog),))[0]
    assert h.verdict == 'unknown'
    codes = {r.code for r in h.reasons}
    assert 'robot_attribute_missing' in codes and 'site_condition_missing' in codes
    assert not codes & {'product_review_missing', 'process_profile_unreviewed', 'process_profile_incomplete'}
    payload = _candidate_payload(h, row, {}, {}, fixture['site'], None, catalog)
    assert payload['count'] is None and not payload['economic_ready']
    # Реальная высота ограничивает допуск даже при других неизвестных.
    high = match_robots(process_code='warehouse_inventory', process_name='Инвентаризация товаров', site={**fixture['site'], 'storage_height_m': 13},
                        rules=rules, bindings=fixture['bindings'], robots=(_robot_view(row, catalog=catalog),))[0]
    assert high.verdict == 'fail'
