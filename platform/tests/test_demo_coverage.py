"""Реалистичность, изоляция и сквозное покрытие всех демопроцессов."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from app.config import get_settings
from app.domain.catalog_assessment import resolve_catalog
from app.domain.demo_synthetic import manifest, supplements, technical_mode_values, catalog_inventory_quantity, project_plan
from app.domain.match import robot_count
from app.infrastructure.db.session import session_factory
from app.infrastructure.db.taxonomy_repo import resolve_project, run_match, project_economy

SR = '3f2aaa1b-2237-4d7b-b215-1ac5ec789ed5'
INVENTORY = '9dfb0b55-4d9e-47fc-8a28-ad4390147a26'


@pytest.fixture(autouse=True)
def dev(monkeypatch):
    monkeypatch.setattr(get_settings(), 'demo_synthetic_enabled', True)


def row(pid=SR, **attrs):
    return SimpleNamespace(id=pid, name='Робот', slug='test', summary=None, attrs=attrs,
                           column_sources={}, price_rub=1000, trl=8, availability='operation', image_url=None)


def runtime_catalog(value=16, quote='автономность до 16 ч', **extra):
    product = row(work_time_h={'status': 'known', 'value': value, 'unit': 'ч', 'quote': quote, **extra})
    old = deepcopy(product.attrs)
    catalog = resolve_catalog(product, process_code='parcel_sorting', allow_demo=True)
    assert product.attrs == old
    return catalog


def test_working_time_is_separate_from_published_upper_bound():
    catalog = runtime_catalog()
    assert 'work_time_h' not in catalog.values
    assert catalog.provenance['work_time_h']['value'] == 16
    assert technical_mode_values(catalog)['work_time_h'] == 12
    assert catalog.provenance['working_time_h']['origin'] == 'demo_synthetic'
    assert catalog.provenance['working_time_h']['references'][0]['url']
    assert technical_mode_values(runtime_catalog(8, ''))['work_time_h'] == 8  # Известное рабочее значение сильнее режима.
    assert 'work_time_h' not in technical_mode_values(runtime_catalog(8, 'до 8 ч'))  # Режим выше предела запрещён.
    assert 'work_time_h' not in technical_mode_values(runtime_catalog(conflict=True))
    assert 'work_time_h' not in technical_mode_values(runtime_catalog(conditions={'floor_type': 'smooth'}))


def inventory_catalog():
    return resolve_catalog(row(INVENTORY, throughput={'status': 'known', 'value': 30000, 'quote': 'до 30000 мест/ч'},
                               throughput_unit={'status': 'known', 'value': 'палето-мест/ч'}),
                           process_code='warehouse_inventory', allow_demo=True)


def quantity_context():
    # Та же сохранённая в БД формула: коэффициенты и резерв не заменены.
    return {'process_code':'warehouse_inventory', 'flow_unit':'locations/hour',
            'formula':'ceil(pallet_places / (robot.throughput * 0.82 * shift_hours * shifts_per_day)) + 1',
            'inputs':(('pallet_places','Места'),('shift_hours','Смена'),('shifts_per_day','Смены')),
            'bindings':{key:key for key in ('pallet_places','shift_hours','shifts_per_day')}}


def test_inventory_calls_existing_formula_and_retains_published_rate():
    catalog=inventory_catalog(); context=quantity_context()
    site={'pallet_places':20000,'shift_hours':11,'shifts_per_day':2}
    expected,_=robot_count(context['formula'], context['inputs'], context['bindings'], site, {'throughput':3000})
    result=catalog_inventory_quantity(catalog,site,context)
    assert result.count == expected == 2
    assert result.details['formula'] == context['formula']
    assert result.details['inputs']['throughput'] == 3000
    assert catalog.provenance['throughput']['value'] == 30000
    assert 'throughput' not in catalog.values
    assert catalog_inventory_quantity(catalog,{**site,'pallet_places':200000},context).count > result.count
    catalog.facts['execution_class']='automated_storage'
    assert catalog_inventory_quantity(catalog,site,context).count is None


def test_inventory_units_and_exact_published_rate_take_priority():
    site={'pallet_places':20000,'shift_hours':11,'shifts_per_day':2}
    catalog=resolve_catalog(row(INVENTORY, throughput={'status':'known','value':5000},
                               throughput_unit={'status':'known','value':'палето-мест/ч'}),
                           process_code='warehouse_inventory', allow_demo=True)
    result=catalog_inventory_quantity(catalog,site,quantity_context())
    assert result.details['inputs']['throughput']==5000
    assert result.details['throughput_parameter']=='throughput'
    catalog.values['throughput_unit']='кг/ч'
    assert catalog_inventory_quantity(catalog,site,quantity_context()).count is None


@pytest.mark.parametrize('change', [{'shift_hours':25},{'shifts_per_day':-1},{'pallet_places':-1},{'pallet_places':.5},{'pallet_places':True}])
def test_invalid_inventory_inputs_cannot_enter_quantity(change):
    site={'pallet_places':20000,'shift_hours':11,'shifts_per_day':2,**change}
    assert catalog_inventory_quantity(inventory_catalog(),site,quantity_context()).count is None


def test_production_and_non_demo_projects_do_not_receive_modes(monkeypatch):
    product=row(work_time_h={'status':'known','value':16,'unit':'ч','quote':'до 16 ч'})
    assert not resolve_catalog(product,process_code='parcel_sorting').demo_synthetic
    assert project_plan(SimpleNamespace(slug='demo-warehouse',is_demo=False)) is None
    monkeypatch.setattr(get_settings(),'demo_synthetic_enabled',False)
    catalog=resolve_catalog(product,process_code='parcel_sorting',allow_demo=True)
    assert not catalog.demo_synthetic and 'work_time_h' not in technical_mode_values(catalog)
    assert project_plan(SimpleNamespace(slug='demo-warehouse',is_demo=True)) is None


def test_manifest_has_no_outlier_batteries_silent_cleaners_or_ready_results():
    data=supplements()
    for pid,fields in data.items():
        assert not set(fields) & {'count','roi','payback','price_rub','verdict'}
        for key,entry in fields.items():
            assert entry['origin']=='demo_synthetic' and entry['explanation'] and entry['references']
            if key=='work_time_h':
                assert 0 < entry['value'] <= 16
                if entry['value'] > 12:
                    assert 'сетев' in entry['explanation']  # Сетевой рабочий режим, не чудо-АКБ.
            if key=='uroven_shuma': assert 45 <= entry['value'] <= 70
    climate = data['28a5afa8-0473-4f80-99a9-b2922b76810f']['temp_min_c']
    assert climate['value'] > 0 and 'apron_transport' not in climate['process_codes']
    for slug,total in [('demo-warehouse',14),('demo-hospital',7),('demo-airport',9)]:
        plan=manifest()['projects'][slug]
        assert len({**plan['processes'],**plan['technical_processes']})==total
        assert all(p['operation']['zone'] for p in {**plan['processes'],**plan['technical_processes']}.values())


@pytest.fixture
def db():
    if '_test' not in get_settings().database_url: pytest.skip('Только отдельная тестовая БД')
    with session_factory()() as session:
        session.execute(text('SET TRANSACTION READ ONLY'))
        yield session
        session.rollback()


def test_every_process_is_audited_and_every_eligible_alternative_reaches_economy(db):
    seen=0; selected=0
    for slug,total in [('demo-warehouse',14),('demo-hospital',7),('demo-airport',9)]:
        project=resolve_project(db,slug); old=deepcopy(project.site); matched=run_match(db,project.id)
        assert len(matched['groups']) == total
        defaults={g['process_code']:g['demo_best_product_id'] for g in matched['groups'] if g['demo_best_product_id']}
        for group in matched['groups']:
            seen += 1
            for hit in group['hits']:
                assert hit['verdict'] in {'pass','unknown','fail'}
                if hit['demo_economic_ready']:
                    report=project_economy(db,project.id,None,None,picks={**defaults,group['process_code']:hit['product_id']})
                    item=next(r for r in report['fleet'] if r['process_code']==group['process_code'])
                    assert item['product_id']==hit['product_id'] and item['count_used']==hit['count'] and item['included']
                    assert item['assumptions']==hit['assumptions'] and len(report['scenarios'])==3
                    assert report['complete']
                    if group['process_code']=='warehouse_inventory':
                        source=item['sizing']['input_provenance']['throughput']
                        assert source['origin']=='demo_synthetic' and source['parameter']=='working_inventory_rate_h'
                    selected += 1
                elif hit['verdict'] in {'unknown','fail'}:
                    assert not hit['economic_ready']
        assert project.site==old
        report=project_economy(db,project.id,None,None)
        assert report['complete'] and report['fleet']
        if slug=='demo-airport':
            apron=next(g for g in matched['groups'] if g['process_code']=='apron_transport')
            assert not any(h['verdict']=='pass' for h in apron['hits'])
    assert seen==30 and selected>=14
