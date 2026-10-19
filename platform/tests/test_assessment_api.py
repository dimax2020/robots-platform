"""Регрессии публичных API и повторной загрузки существующих проектов."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.api.main import app
from app.config import get_settings
from app.infrastructure.db.models import ProductAssessmentRow, ProductRow, ProcessAssessmentRow
from app.infrastructure.db.session import session_factory
from app.infrastructure.db.taxonomy_repo import run_match, project_economy, resolve_project


@pytest.fixture(autouse=True)
def isolated_database_only():
    if '_test' not in get_settings().database_url:
        pytest.skip('Эти интеграционные проверки требуют отдельную тестовую БД')


def test_seeded_environment_and_operator_evidence_are_applied():
    with session_factory()() as db:
        project = resolve_project(db, 'demo-hospital')
        result = run_match(db, project.id)
        for code in ['medicine_delivery', 'biomaterial_delivery']:
            group = next(g for g in result['groups'] if g['process_code'] == code)
            hit = next(h for h in group['hits'] if h['product_id'] == '00ddbb71-8fca-4cb1-9998-78250c62ea03')
            assert hit['verdict'] == 'fail'
            assert any(r['code'] == 'environment_incompatible' for r in hit['reasons'])
            assert not hit['economic_ready'] and hit['count'] is None
        group = next(g for g in result['groups'] if g['process_code'] == 'floor_cleaning')
        for pid in ['1f44e524-acf6-4d6f-976e-d1039922fd32', '715f65cd-fa1d-4821-94b8-30f9ea5de8d0']:
            hit = next(h for h in group['hits'] if h['product_id'] == pid)
            assert hit['verdict'] == 'fail' and not hit['economic_ready']


def test_fail_and_stale_id_cannot_be_smuggled_into_economy_api():
    client = TestClient(app)
    for pid in ['00ddbb71-8fca-4cb1-9998-78250c62ea03', 'deleted-or-invalid-id']:
        response = client.post('/api/v1/projects/demo-hospital/economy', json={
            'picks': {'medicine_delivery': pid}, 'economic_ready': True, 'count': 1})
        assert response.status_code == 200, response.text
        report = response.json()
        assert report['fleet'] == [] and not report['complete']
        assert any(b['code'] == 'selection_invalid' for b in report['blockers'])
        assert all(s['capex']['value'] is None and s['payback']['value'] is None for s in report['scenarios'])


def test_automatic_and_explicit_empty_are_distinguishable():
    client = TestClient(app)
    automatic = client.post('/api/v1/projects/demo-warehouse/economy', json={}).json()
    empty = client.post('/api/v1/projects/demo-warehouse/economy', json={'picks': {}}).json()
    assert automatic['selection_mode'] == 'automatic'
    assert empty['selection_mode'] == 'explicit' and empty['fleet'] == []
    assert all(b['code'] != 'process_not_selected' for b in automatic['blockers'])
    assert any(b['code'] == 'process_not_selected' for b in empty['blockers'])


def test_existing_demo_projects_are_incomplete_and_asrs_is_not_150():
    with session_factory()() as db:
        for slug in ['demo-warehouse', 'demo-airport', 'demo-hospital']:
            project = resolve_project(db, slug)
            match = run_match(db, project.id)
            automatic = project_economy(db, project.id, None, None)
            frontend_picks = {g['process_code']: g['best_product_id'] for g in match['groups'] if g['best_product_id']}
            explicit = project_economy(db, project.id, None, {}, picks=frontend_picks)
            assert automatic['fleet'] == explicit['fleet']
            assert automatic['status'] == 'incomplete'
            assert all(s['payback']['value'] is None for s in automatic['scenarios'])
            if slug == 'demo-warehouse':
                group = next(g for g in match['groups'] if g['process_code'] == 'order_picking')
                asrs = next(h for h in group['hits'] if h['product_id'] == 'cebbdfa8-500a-425f-bcbc-ad2dcc106539')
                assert asrs['count'] is None and not asrs['economic_ready']


def test_reviewed_metadata_endpoints_require_admin_and_validate():
    client = TestClient(app)
    assert client.put('/api/v1/admin/processes/pallet_transport/assessment', json={'reviewed': True}).status_code == 401
    assert client.post('/api/v1/auth/login', json={'login': 'admin', 'password': 'demo-2026'}).status_code == 200
    bad = client.put('/api/v1/admin/processes/pallet_transport/assessment', json={'reviewed': True})
    assert bad.status_code == 422
    assert client.get('/api/v1/admin/processes/pallet_transport/assessment').json()['reviewed'] is False


def test_metadata_does_not_change_original_catalog_or_origins():
    # Compare immutable source identifiers with the snapshot fixtures, independent of test-generated products.
    seed = json.loads((Path(__file__).parents[1] / 'alembic/versions/0024_assessment_seed.json').read_text())
    with session_factory()() as db:
        for item in seed['products']:
            assert db.get(ProductRow, item['id']) is not None
            assert db.get(ProductAssessmentRow, item['id']).data == item['data']


def test_positive_api_selection_from_published_catalog_without_product_assessment(monkeypatch):
    """Опубликованные структурированные факты проходят API без отдельного подтверждения."""
    from uuid import uuid4
    from sqlalchemy.orm import Session
    from app.infrastructure.db.session import get_engine
    from app.infrastructure.db.models import ObjectTypeRow, ProcessRow, ObjectProcessRow, ProductProcessRow, ProcessFilterRow
    from app.api import main
    from test_assessment import FACTS, PROFILE, ATTRS, SITE
    connection = get_engine().connect()
    transaction = connection.begin()
    db = Session(bind=connection, join_transaction_mode='create_savepoint', expire_on_commit=False)
    code = 'stage1-' + uuid4().hex
    try:
        obj = ObjectTypeRow(code=code, name='Проверка')
        process = ProcessRow(code=code, name='Перевозка')
        published = {**ATTRS, **{k: v for k, v in FACTS.items() if k not in {'version', 'reviewed', 'evidence'}}, 'capabilities': [code]}
        product = ProductRow(id=uuid4(), slug=code, name='Опубликованный тестовый робот', price_rub=1000,
                             attrs={k: {'status': 'known', 'value': v, 'source_id': 2} for k, v in published.items()})
        db.add_all([obj, process, product]); db.flush()
        db.add_all([ObjectProcessRow(object_type_id=obj.id, process_id=process.id),
                    ProductProcessRow(product_id=product.id, process_id=process.id),
                    ProcessAssessmentRow(process_id=process.id, data={**PROFILE, 'reviewed': False, 'evidence': []})])
        db.add_all([ProcessFilterRow(process_id=process.id, name='Груз', object_keys=['load'], robot_keys=['payload_kg'], op='>=', mode='hard'),
                    ProcessFilterRow(process_id=process.id, name='Проезд', object_keys=['aisle'], robot_keys=['min_aisle_width_m'], op='<=', mode='hard')])
        db.flush()
        product_id = str(product.id)
        db.commit()  # Освобождаем savepoint, внешняя транзакция по-прежнему откатит fixture.
        monkeypatch.setattr(main, 'session_factory', lambda: lambda: db)
        client = TestClient(app)
        site = {**SITE, 'staff_salary_year_rub': 1000000}
        body = {'object_code': code, 'site': site, 'tasks': [{'process_code': code, 'staff_fte_now': 1}]}
        matched = client.post('/api/v1/catalog/preview/match', json=body)
        assert matched.status_code == 200, matched.text
        group = matched.json()['groups'][0]
        assert group['hits'][0]['verdict'] == 'pass'
        assert group['hits'][0]['economic_ready'] is True and group['hits'][0]['count'] == 10
        assert group['hits'][0]['data_basis'] == 'published_catalog_v1'
        assert group['technical_best_product_id'] == product_id
        assert group['best_product_id'] == product_id
        automatic = client.post('/api/v1/catalog/preview/economy', json=body).json()
        chosen = client.post('/api/v1/catalog/preview/economy', json={**body, 'picks': {code: product_id}}).json()
        empty = client.post('/api/v1/catalog/preview/economy', json={**body, 'picks': {}}).json()
        assert automatic['complete'] is True and automatic['robots'] == 10
        assert automatic['fleet'] == chosen['fleet']
        assert empty['fleet'] == [] and empty['status'] == 'incomplete'
        assert empty['scenarios'][1]['payback']['value'] is None
        product.price_rub = None
        db.get(ProcessAssessmentRow, process.id).data = {**PROFILE, 'reviewed': False, 'sizing': {}}
        db.commit()
        preliminary = client.post('/api/v1/catalog/preview/match', json=body).json()['groups'][0]
        assert preliminary['hits'][0]['technical_ready'] is True
        assert preliminary['hits'][0]['count'] is None and not preliminary['hits'][0]['economic_ready']
        assert preliminary['technical_best_product_id'] == product_id and preliminary['best_product_id'] is None
    finally:
        db.close()
        transaction.rollback()
        connection.close()


def test_real_inventory_api_has_concrete_reasons_instead_of_review_gates():
    with session_factory()() as db:
        result = run_match(db, resolve_project(db, 'demo-warehouse').id)
        group = next(g for g in result['groups'] if g['process_code'] == 'warehouse_inventory')
        assert len(group['hits']) == 2
        assert group['best_product_id'] is None and group['technical_best_product_id'] is None
        for hit in group['hits']:
            assert hit['verdict'] == 'unknown' and not hit['economic_ready']
            assert hit['resolved_facts']['capabilities'] == ['warehouse_inventory']
            assert hit['provenance']['lift_height_mm']['source']['url']
            assert not any(r['code'] in {'product_review_missing', 'process_profile_unreviewed', 'process_profile_incomplete'} for r in hit['reasons'])
            assert any(r['field'] == 'min_aisle_width_m' for r in hit['reasons'])
