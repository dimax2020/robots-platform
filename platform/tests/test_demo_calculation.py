"""Математика, изоляция DEV и сквозная экономика реальных демопроектов."""
from copy import deepcopy
from math import ceil
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.config import get_settings
from app.domain.demo_synthetic import manifest, project_inputs, project_plan
from app.domain.sizing import size_equipment
from app.domain.economy import calculate
from app.infrastructure.db.session import session_factory
from app.infrastructure.db.taxonomy_repo import resolve_project, run_match, project_economy

@pytest.fixture
def dev(monkeypatch):
    monkeypatch.setattr(get_settings(), 'demo_synthetic_enabled', True)

def cleaning(**changes):
    inputs = dict(clean_area_m2=12000, area_m2=45000, cleaning_passes_per_day=1, cleaning_window_h=8,
                  effective_cleaning_rate_m2_h=300, availability=.9, reserve_count=1)
    inputs.update(changes)
    return size_equipment({'sizing': {'model': 'cleaning_area_v1', 'flow_unit': 'm2/day', 'quantity_unit': 'machines'}},
                          {'execution_class': 'mobile_cleaning'}, inputs,
                          {'work_time_h': 14, 'charge_time_h': 2, 'proizvoditelnost': '300-700 м²/ч'})

def test_cleaning_formula_and_zero_demand():
    result = cleaning()
    assert result.count == ceil(12000 / (300 * 8 * .9 * 14/16)) + 1 == 8
    assert result.details['daily_capacity_per_machine_m2'] == 1890
    assert cleaning(clean_area_m2=0, reserve_count=0).count == 0
    assert cleaning(cleaning_passes_per_day=2).count == 14

@pytest.mark.parametrize('change', [dict(availability=0), dict(availability=1.1), dict(cleaning_window_h=25),
    dict(reserve_count=.5), dict(effective_cleaning_rate_m2_h=800), dict(clean_area_m2=50000),
    dict(clean_area_m2=None), dict(cleaning_window_h=float('inf')), dict(clean_area_m2=-1)])
def test_invalid_cleaning_does_not_get_quantity(change):
    assert cleaning(**change).count is None

def test_towing_formula_and_payload_constraint():
    process = manifest()['projects']['demo-warehouse']['processes']['cart_towing']
    site = {k: entry['value'] for k, entry in process['task'].items()}
    site.update(flow_per_day=2000, batch_size=4, route_len_m=200, t_load_s=120, t_unload_s=120,
                availability=.9, reserve_count=1, cart_tare_kg=100, working_speed_loaded_ms=1,
                working_speed_empty_ms=1.2, pallet_mass_kg=800, shift_hours=11, shifts_per_day=2)
    robot = dict(work_time_h=12, charge_time_h=2, payload_kg=5000, speed_loaded_limit_ms=2.2, speed_empty_limit_ms=2.2)
    def size(**changes):
        return size_equipment({'sizing': process['sizing']}, {'execution_class': 'mobile_transport'}, {**site, **changes}, robot)
    result = size()
    assert result.count == ceil(2000/4 * (200/1+200/1.2+240)/(22*3600*.9*12/14)) + 1 == 6
    assert result.details['train_mass_kg'] == 3600
    assert size(batch_size=6).count is None
    assert size(working_speed_loaded_ms=3).count is None
    assert size(flow_per_day=0, reserve_count=0).count == 0
    assert size(t_load_s=None).count is None

def test_input_precedence_and_production_isolation(dev, monkeypatch):
    project = SimpleNamespace(slug='demo-hospital', is_demo=True)
    plan = project_plan(project)
    site = {'area_m2':45000, 'clean_area_m2':20000}
    tasks = [{'process_code':'floor_cleaning', 'availability':.5}]
    old = deepcopy((site, tasks))
    _, prepared, groups = project_inputs(plan, site, tasks)
    assert 'clean_area_m2' not in prepared[0] and prepared[0]['availability'] == .5
    assert (site, tasks) == old
    assert not any(v['key'] in {'clean_area_m2','availability'} for v in groups[0]['fields'])
    assert project_plan(SimpleNamespace(slug='demo-hospital', is_demo=False)) is None
    assert project_plan(SimpleNamespace(slug='ordinary', is_demo=True)) is None
    monkeypatch.setattr(get_settings(), 'demo_synthetic_enabled', False)
    assert project_plan(project) is None

@pytest.fixture
def db():
    if '_test' not in get_settings().database_url: pytest.skip('Только изолированная тестовая БД')
    with session_factory()() as session:
        session.execute(text('SET TRANSACTION READ ONLY'))
        yield session
        session.rollback()

@pytest.mark.parametrize('slug,code,count', [('demo-warehouse','cart_towing',4),('demo-hospital','warehouse_inventory',2)])
def test_real_demo_pipeline_and_whatif(db, dev, slug, code, count):
    project = resolve_project(db, slug)
    original = deepcopy(project.site)
    match = run_match(db, project.id)
    group = next(g for g in match['groups'] if g['process_code'] == code)
    hit = next(h for h in group['hits'] if h['product_id'] == group['demo_best_product_id'])
    assert hit['verdict'] == 'pass' and hit['count'] == count
    assert hit['demo_economic_ready'] and not hit['economic_ready'] and group['best_product_id'] is None
    report = project_economy(db, project.id, None, None)
    assert report['status'] == 'demo_estimate' and report['scope'] == 'automation_program'
    assert report['complete'] and report['manual_processes']
    assert next(row for row in report['fleet'] if row['process_code'] == code)['count_used'] == count
    assert report['robots'] == sum(row['count_used'] for row in report['fleet'])
    assert report['payroll']['value'] > 0
    _, buy, raas = report['scenarios']
    assert buy['payroll_after']['value'] >= 0
    for scenario in (buy, raas):
        assert scenario['annual_cost'] == pytest.approx(scenario['payroll_after']['value'] + scenario['opex']['value'])
        assert scenario['tco']['value'] == pytest.approx(scenario['capex']['value'] + 5*scenario['annual_cost'])
        assert scenario['effect']['uses_demo_synthetic']
    for preview in [{'price_factor':150}, {'salary_factor':150}, {'replacement_pct':0}, {'service_pct':20}, {'energy_kwh':2}]:
        changed = project_economy(db, project.id, None, None, preview=preview)
        assert changed['scenarios'][1]['effect']['value'] != buy['effect']['value']
    loaded = project_economy(db, project.id, None, None, preview={'load_factor':200})
    assert loaded['robots'] > report['robots'] if slug == 'demo-warehouse' else loaded['robots'] == report['robots']
    empty = project_economy(db, project.id, None, None, picks={})
    assert empty['status'] == 'incomplete' and not empty['fleet']
    invalid = project_economy(db, project.id, None, None, picks={code:'invalid'})
    assert invalid['status'] == 'incomplete' and not invalid['fleet']
    assert project.site == original

def test_production_demos_remain_strict(db, monkeypatch):
    monkeypatch.setattr(get_settings(), 'demo_synthetic_enabled', False)
    project = resolve_project(db,'demo-hospital')
    report = project_economy(db,project.id,None,None)
    assert report['status'] == 'incomplete' and not report['uses_demo_synthetic']
    assert not any(h['demo_economic_ready'] or h['uses_demo_synthetic'] for g in run_match(db,project.id)['groups'] for h in g['hits'])

def test_airport_keeps_technical_blockers(db, dev):
    project = resolve_project(db,'demo-airport')
    result = run_match(db,project.id)
    greeting = next(h for g in result['groups'] for h in g['hits'] if h['slug']=='orionstar-greetingbot-mini-service-roboter')
    assert greeting['verdict']=='fail' and greeting['count'] is None
    assert any(r['severity']=='fail' and 'температура' in r['message'].lower() for r in greeting['reasons'])
    report=project_economy(db,project.id,None,None)
    assert report['status']=='incomplete' and not report['fleet']
    assert all(s['tco']['value'] is None for s in report['scenarios'])

def test_real_economy_http_api(dev):
    if '_test' not in get_settings().database_url: pytest.skip('Нужна отдельная БД')
    from app.api.main import app
    client=TestClient(app)
    base=client.post('/api/v1/projects/demo-hospital/economy',json={})
    assert base.status_code==200
    assert base.json()['status']=='demo_estimate'
    doubled=client.post('/api/v1/projects/demo-hospital/economy',json={'preview':{'price_factor':200}})
    assert doubled.status_code==200 and doubled.json()['robots']==base.json()['robots']
    assert doubled.json()['scenarios'][1]['capex']['value'] > base.json()['scenarios'][1]['capex']['value']
    bad=client.post('/api/v1/projects/demo-hospital/economy',json={'picks':{'floor_cleaning':'invalid'}})
    assert bad.status_code==200 and bad.json()['status']=='incomplete'

def test_zero_and_negative_effect_without_fabricated_payback():
    rows=[dict(process_code='clean',name='Тест',price_rub=1000,count=2,power_w=1)]
    site=dict(shift_hours=8,shifts_per_day=1,days_year=250,staff_salary_year_rub=100000)
    task=[dict(process_code='clean',staff_fte_now=2,staff_salary_year_rub=100000)]
    zero={key:0 for key in ['infra_pct','software_pct','integration_pct','commissioning_pct','training_pct','reserve_pct',
                            'service_pct','license_pct','comms_pct','consumables_pct','repair_pct','replacement_pct','energy_tariff']}
    no_operator={k:v for k,v in site.items() if k!='staff_salary_year_rub'}
    report=calculate(rows,no_operator,overrides=zero,tasks=task)
    assert report['scenarios'][1]['effect']['value']==0
    assert report['scenarios'][1]['payback']['value'] is None
    report=calculate(rows,site,overrides=zero,tasks=task)
    assert report['scenarios'][1]['effect']['value']<0 and report['scenarios'][1]['payback']['value'] is None


def test_duplicate_task_allocation_is_incomplete_not_double_counted(db, dev):
    project = resolve_project(db, 'demo-hospital')
    tasks = [{'process_code':'warehouse_inventory', 'staff_fte_now':.5},
             {'process_code':'warehouse_inventory', 'staff_fte_now':.5}]
    report = project_economy(db, project.id, None, None, tasks=tasks)
    assert report['status']=='incomplete' and not report['fleet']
    hit = next(h for g in run_match(db,project.id,tasks=tasks)['groups'] if g['process_code']=='warehouse_inventory'
               for h in g['hits'] if h['product_id']=='9dfb0b55-4d9e-47fc-8a28-ad4390147a26')
    assert hit['count'] is None and any(r['code']=='task_allocation_conflict' for r in hit['sizing']['reasons'])
    assert not any('__demo_input_conflict' in t for t in tasks)


def test_real_incompatibility_cannot_enter_demo_fleet(db, dev):
    project = resolve_project(db,'demo-warehouse')
    site = {**project.site, 'pallet_mass_kg':6000}
    report = project_economy(db,project.id,site,None)
    assert report['status']=='incomplete'
    assert not any(row['process_code'] in {'cart_towing','pallet_transport'} for row in report['fleet'])
    group = next(g for g in run_match(db,project.id,site)['groups'] if g['process_code']=='cart_towing')
    hit = next(h for h in group['hits'] if h['slug']=='robot-tyagach-robocv')
    assert hit['verdict']=='fail' and not hit['demo_economic_ready']


def test_sizing_provenance_tracks_scaled_value_and_original_origin(db, dev):
    project=resolve_project(db,'demo-warehouse')
    report=project_economy(db,project.id,None,None,preview={'load_factor':200})
    cleaner=next(row for row in report['fleet'] if row['process_code']=='floor_cleaning')
    source=cleaner['sizing']['input_provenance']['cleaning_passes_per_day']
    assert source['origin']=='demo_synthetic' and source['base_value']==1 and source['value']==2
    assert source['transformation']=='load_factor'
    price=cleaner['price_rub']
    assert price==1399900
