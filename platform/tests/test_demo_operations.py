"""Операционные условия DEV: реальный допуск, изоляция и сохранённая математика."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import get_settings
from app.domain.demo_synthetic import project_plan, project_inputs, operation_context, operation_links, catalog_process_quantity
from app.domain.match import FilterRule, robot_count
from app.infrastructure.db.session import session_factory
from app.infrastructure.db.taxonomy_repo import resolve_project, run_match, project_economy
from app.infrastructure.db.models import ProductRow, ProcessRow
from test_demo_synthetic import GREETING


@pytest.fixture(autouse=True)
def dev(monkeypatch):
    monkeypatch.setattr(get_settings(), 'demo_synthetic_enabled', True)


@pytest.fixture
def db():
    if '_test' not in get_settings().database_url:
        pytest.skip('Только временная копия PostgreSQL')
    with session_factory()() as session:
        session.execute(text('SET TRANSACTION READ ONLY'))
        yield session
        session.rollback()


def test_operation_scope_preserves_site_task_precedence_and_false_values():
    plan=project_plan(SimpleNamespace(slug='demo-airport',is_demo=True))
    site={'temp_min_c':-25,'shift_hours':24,'shifts_per_day':1}
    tasks=[{'process_code':'tote_delivery','temp_min_c':-30,'t_load_s':0,'availability':.4,'access_ready':False}]
    old=deepcopy((site,tasks))
    values,prepared,groups=project_inputs(plan,site,tasks)
    task=next(t for t in prepared if t['process_code']=='tote_delivery')
    process=plan['processes']['tote_delivery']
    scoped,_,_,_=operation_context(process,values,task,{},(),{})
    assert scoped['temp_min_c']==-30 and scoped['shift_hours']==24
    assert scoped['access_ready'] is False and scoped['t_load_s']==0 and scoped['availability']==.4
    assert (site,tasks)==old and values['temp_min_c']==-25
    fields=[e for g in groups if g['process_code']=='tote_delivery' for e in g['fields']]
    assert not any(e['key']=='temp_min_c' for e in fields)
    assert any(e['key']=='autonomy_required_h' and e['scope']=='tote_delivery' for e in fields)


def test_only_registered_dev_projects_receive_process_links_and_settings(monkeypatch):
    plan=project_plan(SimpleNamespace(slug='demo-hospital',is_demo=True))
    process=plan['processes']['biomaterial_delivery']
    assert operation_links(process)
    monkeypatch.setattr(get_settings(),'demo_synthetic_enabled',False)
    assert not operation_links(process)
    rule=FilterRule('Исходная проверка',('load',),('payload_kg',),'>=','hard')
    site={'temp_min_c':-25}
    assert operation_context(process,site,{}, {},(rule,),{}) == (site,{},(rule,),{})
    assert project_plan(SimpleNamespace(slug='demo-hospital',is_demo=True)) is None


def test_terminal_and_street_have_independent_climate_and_work_intervals(db):
    project=resolve_project(db,'demo-airport');original=deepcopy(project.site)
    groups={g['process_code']:g for g in run_match(db,project.id)['groups']}
    terminal=groups['passenger_service']
    hit=next(h for h in terminal['hits'] if h['product_id']==GREETING)
    assert hit['verdict']=='pass' and hit['applicability']=='conditional'
    assert not any(r.get('field')=='load' for r in hit['reasons'])
    assert terminal['operation']['effective_fields']['temp_min_c']==15
    assert terminal['operation']['effective_fields']['autonomy_required_h']==4
    assert groups['perimeter_security']['operation']['effective_fields']['temp_min_c']==-25
    assert original==project.site and original['shift_hours']==24 and original['temp_min_c']==-25
    # Известный предел X30 -20 не превращается в разрешение для -25.
    x30=next(h for h in groups['perimeter_security']['hits'] if h['product_id']=='eb40b62d-7f26-472c-aa3c-d507db62a81a')
    assert x30['verdict']=='fail' and not x30['demo_economic_ready']
    # Платформа без подтверждённой камеры не объявляется готовым видеопатрулём.
    piranha=next(h for h in groups['territory_inspection']['hits'] if h['product_id']=='73300188-d66e-4275-9934-dcdd7e1cecc1')
    assert piranha['verdict']!='pass'
    assert any(r['code']=='equipment_missing' for r in piranha['reasons'])


@pytest.mark.parametrize('code,task',[
    ('medicine_delivery',{'noise_limit_dba':30}),
    ('floor_cleaning',{'noise_limit_dba':30}),
    ('medicine_delivery',{'autonomy_required_h':20}),
])
def test_explicit_clinical_limits_cannot_be_relaxed_by_demo(db,code,task):
    project=resolve_project(db,'demo-hospital')
    matched=run_match(db,project.id,tasks=[{'process_code':code,**task}])
    group=next(g for g in matched['groups'] if g['process_code']==code)
    assert not any(h['verdict']=='pass' for h in group['hits'])
    assert not any(h['demo_economic_ready'] for h in group['hits'])


def test_original_lift_height_is_a_real_failure_not_a_missing_profile(db):
    project=resolve_project(db,'demo-warehouse')
    group=next(g for g in run_match(db,project.id)['groups'] if g['process_code']=='rack_placement')
    assert project.site['storage_height_m']==10
    assert group['hits'] and all(h['verdict']=='fail' for h in group['hits'])
    assert all(any(r['code']=='technical_constraint' and 'Высота размещения' in r['message'] for r in h['reasons']) for h in group['hits'])


@pytest.mark.parametrize('slug,technical,economic,default_scope',[('demo-warehouse',13,13,7),('demo-hospital',7,7,6),('demo-airport',8,8,6)])
def test_all_operations_have_settings_and_sources_without_automatic_statuses(db,slug,technical,economic,default_scope):
    project=resolve_project(db,slug);matched=run_match(db,project.id)
    assert sum(any(h['verdict']=='pass' for h in g['hits']) for g in matched['groups'])==technical
    assert sum(any(h['demo_economic_ready'] for h in g['hits']) for g in matched['groups'])==economic
    for group in matched['groups']:
        assert group['operation']['zone'] and group['operation']['explanation']
        assert not any(r['code'] in {'process_checks_missing','site_binding_missing','configuration_error'} for h in group['hits'] for r in h['reasons'])
        for hit in group['hits']:
            assert all(a['explanation'] for a in hit['assumptions'])
            if hit['verdict']=='pass':
                assert hit['applicability']=='conditional'
                assert any(a['key']=='operation_scope' and a['origin']=='demo_synthetic' for a in hit['assumptions'])
    report=project_economy(db,project.id,None,None)
    assert report['complete'] and report['coverage']['included_processes']==default_scope


@pytest.mark.parametrize('code',['perimeter_security','passenger_service'])
def test_retained_process_formula_is_called_verbatim(db,code):
    project=resolve_project(db,'demo-airport')
    matched=run_match(db,project.id)
    group=next(g for g in matched['groups'] if g['process_code']==code)
    hit=next(h for h in group['hits'] if h['product_id']==group['demo_best_product_id'])
    stored=db.query(ProcessRow).filter_by(code=code).one()
    assert hit['sizing']['formula']==stored.count_formula  # Исходные поток и маршрут не изменились.
    values=hit['sizing']['details'] if 'details' in hit['sizing'] else hit['sizing']
    inputs=values['inputs']
    expected,_=robot_count(stored.count_formula,tuple((r['key'],r['label']) for r in stored.count_inputs),
                           {r['key']:r['key'] for r in stored.count_inputs},inputs,{'speed_loaded_ms':inputs['speed_loaded_ms']})
    assert hit['count']==expected and expected>0
    assert hit['sizing']['formula_source']=='process.count_formula'


def test_new_quantity_bindings_reject_wrong_physical_class_and_invalid_hours():
    catalog=SimpleNamespace(facts={'execution_class':'aerial_inspection'})
    context={'process_code':'perimeter_security','formula':'unchanged','flow_unit':'missions/day'}
    assert catalog_process_quantity(catalog,{},context,{},{}).count is None
    catalog.facts['execution_class']='ground_patrol'
    for site in ({'shift_hours':25,'shifts_per_day':1},{'shift_hours':True,'shifts_per_day':1}):
        assert catalog_process_quantity(catalog,site,context,{},{}).count is None


def test_public_api_uses_scoped_conditions_and_rejects_real_conflict():
    if '_test' not in get_settings().database_url:pytest.skip('Нужна отдельная БД')
    from app.api.main import app
    with TestClient(app) as client:
        response=client.post('/api/v1/projects/demo-airport/match',json={})
        assert response.status_code==200
        groups={g['process_code']:g for g in response.json()['groups']}
        greeting=next(h for h in groups['passenger_service']['hits'] if h['product_id']==GREETING)
        assert greeting['demo_economic_ready']
        report=client.post('/api/v1/projects/demo-airport/economy',json={}).json()
        assert report['complete'] and report['fleet']
        cold=client.post('/api/v1/projects/demo-airport/match',json={'tasks':[{'process_code':'tote_delivery','temp_min_c':-25}]}).json()
        assert not any(h['verdict']=='pass' for g in cold['groups'] if g['process_code']=='tote_delivery' for h in g['hits'])
        apron=groups['apron_transport']['hits'][0]
        rejected=client.post('/api/v1/projects/demo-airport/economy',json={'picks':{'apron_transport':apron['product_id']}}).json()
        assert not rejected['complete'] and not rejected['fleet']
