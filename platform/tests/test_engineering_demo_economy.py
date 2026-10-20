"""Новые процессы выбираются отдельно, исходная программа и карточки сохраняются."""
from copy import deepcopy

import pytest
from sqlalchemy import text

from app.config import get_settings
from app.domain.demo_synthetic import configuration_assumptions
from app.infrastructure.db.session import session_factory
from app.infrastructure.db.taxonomy_repo import resolve_project, run_match, project_economy


@pytest.fixture(autouse=True)
def dev(monkeypatch):
    monkeypatch.setattr(get_settings(), 'demo_synthetic_enabled', True)


@pytest.fixture
def db():
    if '_test' not in get_settings().database_url:
        pytest.skip('Только изолированная копия DEV')
    with session_factory()() as session:
        session.execute(text('SET TRANSACTION READ ONLY'))
        yield session
        session.rollback()


@pytest.mark.parametrize('slug,added', [('demo-warehouse', 10), ('demo-hospital', 2), ('demo-airport', 3)])
def test_new_alternatives_keep_base_facts_and_can_be_added_one_at_a_time(db, slug, added):
    project = resolve_project(db, slug)
    original = deepcopy(project.site)
    matched = run_match(db, project.id)
    baseline = project_economy(db, project.id, None, None)
    defaults = {r['process_code']: r['product_id'] for r in baseline['fleet']}
    new = [(g, h) for g in matched['groups'] for h in g['hits']
           if h['verdict'] == 'pass' and h['sizing']['model'] in {'asrs_capacity_v1', 'stationary_cycle_v1', 'aerial_surface_v1'}]
    assert len(new) == added
    for group, hit in new:
        code = group['process_code']
        assert hit['demo_economic_ready'] and not hit['economic_ready'] and hit['applicability'] == 'conditional'
        assert hit['sizing']['formula_source'] == 'engineering_registry'
        assert hit['sizing']['input_provenance']
        kit = next(a for a in hit['assumptions'] if a['key'] == 'configuration_complete' and a.get('category') == 'configuration')
        assert kit['origin'] == 'demo_synthetic' and kit['components'] and kit['requires_vendor_confirmation']
        # false относится к исходной поставке и не превращается в true.
        if hit['resolved_facts'].get('execution_class') in {'automated_storage', 'stationary_manipulation'}:
            assert hit['resolved_facts']['configuration_complete'] is False
        report = project_economy(db, project.id, None, None, picks={**defaults, code: hit['product_id']})
        assert report['complete'] and len(report['fleet']) == len(baseline['fleet']) + 1
        item = next(r for r in report['fleet'] if r['process_code'] == code)
        assert item['product_id'] == hit['product_id'] and item['included'] and item['count_source'] == 'formula'
        assert item['count_used'] == hit['count'] and item['assumptions'] == hit['assumptions']
        process = next(r for r in report['processes'] if r['process_code'] == code)
        buy = next(s for s in process['scenarios'] if s['key'] == 'purchase')
        infra = next(line for line in buy['capex_lines'] if line['key'] == 'infra')
        assert infra['value'] == pytest.approx(item['cost_rub'] * kit['infrastructure_pct'] / 100)
    assert project.site == original
    unchanged = project_economy(db, project.id, None, None)
    assert unchanged['fleet'] == baseline['fleet'] and unchanged['scenarios'] == baseline['scenarios']


def test_dev_configuration_cannot_be_used_when_synthetic_is_disabled(monkeypatch):
    monkeypatch.setattr(get_settings(), 'demo_synthetic_enabled', False)
    assert configuration_assumptions({'origin': 'demo_synthetic'}, 1000) == []


@pytest.mark.parametrize('configuration', [{'origin': 'demo_synthetic'}, {'origin': 'catalog', 'components': ['оснастка']}])
def test_incomplete_dev_configuration_is_not_a_commercial_override(configuration):
    with pytest.raises(ValueError):
        configuration_assumptions(configuration, 1000)


@pytest.mark.parametrize('unit,ready', [('с', True), ('мин', False)])
def test_refined_cycle_units_cannot_be_silently_misread(unit, ready):
    from types import SimpleNamespace
    from app.domain.catalog_assessment import CatalogAssessment
    from app.infrastructure.db.taxonomy_repo import _candidate_payload
    row = SimpleNamespace(price_rub=1000, attrs={})
    hit = SimpleNamespace(process_code='packing', process_name='Упаковка', verdict='pass',
                          product_id='test', name='Ячейка', slug='test', notes=[], reasons=[],
                          image_url=None, trl=8, stage='operation')
    catalog = CatalogAssessment({'execution_class': 'stationary_manipulation', 'solution_kind': 'robot'},
                                {'handling_cycle_s': 1, 'work_units_per_cycle': 1},
                                {'handling_cycle_s': {'value': 1, 'unit': unit, 'status': 'known'}})
    profile = {'sizing': {'model': 'stationary_cycle_v1', 'flow_unit': 'items/day', 'quantity_unit': 'machines'}}
    site = dict(flow_per_day=1000, sizing_window_h=8, availability=.8, reserve_count=0)
    result = _candidate_payload(hit, row, {}, profile, site, {}, catalog, demo=True)
    assert result['demo_economic_ready'] is ready
    if not ready:
        assert result['count'] is None
        assert any(r['code'] == 'sizing_unit_incompatible' for r in result['economic_reasons'])
