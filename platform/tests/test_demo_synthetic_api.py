"""Реальные демо и публичные контракты на изолированной БД, без записи в каталог."""
from copy import deepcopy

import pytest

@pytest.fixture(autouse=True)
def enable_dev_synthetic(monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "demo_synthetic_enabled", True)

from sqlalchemy import select, text

from app.config import get_settings
from app.domain import demo_synthetic
from app.infrastructure.db.models import ProductRow
from app.infrastructure.db.product_repo import get_product
from app.infrastructure.db.session import session_factory
from app.infrastructure.db.taxonomy_repo import resolve_project, run_match, project_economy
from test_demo_synthetic import ROBOCV, PHANTAS, GREETING


@pytest.fixture
def db():
    if '_test' not in get_settings().database_url:
        pytest.skip('Нужна отдельная тестовая БД')
    with session_factory()() as session:
        session.execute(text('SET TRANSACTION READ ONLY'))
        yield session
        session.rollback()


@pytest.mark.parametrize('slug,process,product_id,expected', [
    ('demo-warehouse', 'cart_towing', ROBOCV, 'pass'),
    ('demo-hospital', 'floor_cleaning', PHANTAS, 'pass'),
    ('demo-airport', 'passenger_service', GREETING, 'unknown'),
])
def test_existing_demo_rules_compute_status_and_preserve_original_inputs(db, monkeypatch, slug, process, product_id, expected):
    project = resolve_project(db, slug)
    before_site = deepcopy(project.site)
    product = db.get(ProductRow, product_id)
    before_attrs = deepcopy(product.attrs)
    with monkeypatch.context() as context:
        context.setattr(demo_synthetic, 'supplements', lambda: {})
        original = run_match(db, project.id)
    before_hit = next(h for g in original['groups'] if g['process_code'] == process for h in g['hits'] if h['product_id'] == product_id)
    assert before_hit['verdict'] == 'unknown'
    match = run_match(db, project.id)
    group = next(g for g in match['groups'] if g['process_code'] == process)
    hit = next(h for h in group['hits'] if h['product_id'] == product_id)
    assert hit['verdict'] == expected and hit['uses_demo_synthetic']
    assert hit['data_basis'] == 'catalog_with_demo_synthetic_v1'
    assert hit['vendor_confirmation_fields'] == [item['key'] for item in hit['demo_synthetic']]
    assert all(item['origin'] == 'demo_synthetic' and not item['vendor_confirmed'] for item in hit['demo_synthetic'])
    assert not hit['economic_ready'] and group['best_product_id'] is None
    if expected == 'pass':
        assert hit['count'] > 0 and hit['demo_economic_ready']
        assert group['demo_best_product_id'] == product_id
    if expected == 'pass':
        assert group['technical_best_product_id'] == product_id
    else:
        assert any(r['code'] == 'site_input_missing' for r in hit['reasons'])
        assert any(r.get('field') == 'temp_min_c' for r in hit['reasons'])
    assert product.attrs == before_attrs and project.site == before_site
    assert any(h['verdict'] == 'unknown' and not h['uses_demo_synthetic'] for h in group['hits'])


@pytest.mark.parametrize('slug', ['demo-warehouse', 'demo-airport', 'demo-hospital'])
def test_incomplete_economy_keeps_origin_even_without_selected_fleet(db, slug):
    report = project_economy(db, resolve_project(db, slug).id, None, None)
    assert report['status'] == ('incomplete' if slug == 'demo-airport' else 'demo_estimate') and report['uses_demo_synthetic']
    assert report['demo_synthetic']
    assert 'синтетические' in report['disclaimer'] and 'не подтверждены вендором' in report['disclaimer']
    if slug == 'demo-airport':
        assert all(s['capex']['value'] is None and s['payback']['value'] is None for s in report['scenarios'])
    else:
        assert all(s['capex']['value'] is not None for s in report['scenarios'])


def test_card_api_keeps_original_attrs_separate_for_future_vendor_confirmation(db):
    product = db.get(ProductRow, PHANTAS)
    result = get_product(db, product.slug)
    original_keys = {item['key'] for item in result['attrs']}
    assert not {'min_aisle_width_m', 'uroven_shuma'} & original_keys
    assert result['uses_demo_synthetic']
    assert {'min_aisle_width_m', 'uroven_shuma'} <= set(result['vendor_confirmation_fields'])
    assert all(item['requires_vendor_confirmation'] for item in result['demo_synthetic'])


def test_two_real_inventory_cards_stay_incomplete_without_synthetic_data(db):
    result = run_match(db, resolve_project(db, 'demo-warehouse').id)
    group = next(g for g in result['groups'] if g['process_code'] == 'warehouse_inventory')
    assert len(group['hits']) == 2
    assert all(h['verdict'] == 'unknown' and not h['uses_demo_synthetic'] for h in group['hits'])
    assert all(any(r['code'] in {'robot_attribute_missing', 'site_condition_missing'} for r in h['reasons']) for h in group['hits'])
