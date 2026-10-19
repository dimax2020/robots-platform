"""Выборочный слой DEV: исходные данные сильнее допущений, результат считают правила."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

@pytest.fixture(autouse=True)
def enable_dev_synthetic(monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "demo_synthetic_enabled", True)


from app.domain.catalog_assessment import CatalogAssessment, resolve_catalog
from app.domain.demo_synthetic import apply_supplements, supplements
from app.domain.match import FilterRule, match_robots
from app.infrastructure.db.taxonomy_repo import _robot_view

ROBOCV = 'b4a9ef38-b68a-4c0f-8512-9bc9a718c4e1'
PHANTAS = '4e06a969-ae1a-4977-9edc-d59bbb37f633'
GREETING = '3317fb22-58ef-4cdb-b974-ebf7a51f38df'


def row(attrs=None, product_id=ROBOCV):
    return SimpleNamespace(id=product_id, attrs=attrs or {}, price_rub=None, trl=8, availability='operation',
                           name='Тест', slug='test', summary=None, column_sources={}, image_url=None)


def test_supplement_scope_and_origin_do_not_encode_results_or_enterprise_inputs():
    data = supplements()
    assert set(data) == {ROBOCV, PHANTAS, GREETING}
    assert sum(len(fields) for fields in data.values()) < 30
    for fields in data.values():
        assert not set(fields) & {'count', 'roi', 'payback', 'price_rub', 'batch_size', 'availability', 'reserve_count', 'site', 'verdict'}
        for item in fields.values():
            assert item['origin'] == 'demo_synthetic' and item['explanation']
            assert isinstance(item['unit'], str)


@pytest.mark.parametrize('raw', [
    {'status': 'known', 'value': 6, 'source_id': 42},
    {'status': 'known', 'value': 'нет однозначного числа', 'source_id': 42},
    {'status': 'not_applicable', 'value': None},
    {'status': 'conflict', 'value': None},
])
def test_existing_values_or_explicit_inapplicability_are_not_replaced(raw):
    product = row({'work_time_h': raw})
    old = deepcopy(product.__dict__)
    catalog = resolve_catalog(product, allow_demo=True)
    assert not any(item['key'] == 'work_time_h' for item in catalog.demo_synthetic)
    assert catalog.provenance.get('work_time_h', {}).get('origin') != 'demo_synthetic'
    assert product.__dict__ == old


def test_derived_catalog_fact_has_priority_and_missing_fields_remain_requestable():
    product = row({'control_mode': {'status': 'known', 'value': 'operator', 'source_id': 42}})
    catalog = resolve_catalog(product, allow_demo=True)
    assert catalog.facts['control_mode'] == 'operator'
    assert not any(item['key'] == 'control_mode' for item in catalog.demo_synthetic)
    assert 'work_time_h' not in product.attrs
    item = next(item for item in catalog.demo_synthetic if item['key'] == 'work_time_h')
    assert item['vendor_confirmed'] is False and item['requires_vendor_confirmation'] is True
    assert catalog.provenance['work_time_h']['origin'] == 'demo_synthetic'


def test_alias_data_and_conflicting_normalization_are_not_overwritten():
    product = row({'aisle': {'status': 'known', 'value': '3 м', 'label': 'Минимальная ширина прохода', 'source_id': 42}}, PHANTAS)
    catalog = resolve_catalog(product, allow_demo=True)
    assert catalog.values['min_aisle_width_m'] == 3
    assert not any(item['key'] == 'min_aisle_width_m' for item in catalog.demo_synthetic)
    product.attrs['min_aisle_width_m'] = {'status': 'known', 'value': 2, 'source_id': 43}
    catalog = resolve_catalog(product, allow_demo=True)
    assert 'min_aisle_width_m' in catalog.issues
    assert not any(item['key'] == 'min_aisle_width_m' for item in catalog.demo_synthetic)


def test_normal_rules_can_reject_a_synthetic_candidate():
    product = row({'purpose': {'status': 'known', 'value': 'Буксировка тележек'},
                   'payload_kg': {'status': 'known', 'value': 5000, 'source_id': 42}})
    catalog = resolve_catalog(product, process_code='cart_towing', allow_demo=True)
    rules = (FilterRule('Тяга', ('load',), ('payload_kg',), '>=', 'hard'),)
    for load, expected in [(800, 'pass'), (6000, 'fail')]:
        hit = match_robots(process_code='cart_towing', process_name='Буксировка', site={'load': load}, rules=rules,
                           robots=(_robot_view(product, catalog=catalog),))[0]
        assert hit.verdict == expected


def test_synthetic_units_are_normalized_and_known_facts_not_mutated():
    product = row()
    catalog = CatalogAssessment({}, {}, {})
    entry = {'value': 480, 'unit': 'мин', 'origin': 'demo_synthetic', 'explanation': 'Условное время'}
    result = apply_supplements(product, catalog, entries={'work_time_h': entry})
    assert catalog.values['work_time_h'] == 8 and result[0]['unit'] == 'ч'
    assert product.attrs == {} and entry['value'] == 480


def test_nonselected_card_has_no_synthetic_values():
    catalog = resolve_catalog(row(product_id='unselected'))
    assert catalog.demo_synthetic == [] and catalog.facts == {} and not catalog.values.get('work_time_h')
