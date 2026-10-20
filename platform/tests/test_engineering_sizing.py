"""Физические границы трёх новых инженерных моделей, без готовых входных количеств."""
from copy import deepcopy

import pytest

from app.domain.sizing import size_equipment


def sizing(model, unit, execution, inputs, robot):
    return size_equipment({'sizing': {'model': model, 'flow_unit': unit, 'quantity_unit': 'machines'}},
                          {'execution_class': execution}, inputs, robot)


def asrs(**changes):
    site = dict(flow_per_day=1000, pallet_places=2500, sizing_window_h=8, availability=.8, reserve_count=1)
    robot = dict(throughput=100, throughput_unit='паллет/ч на кран', module_storage_places=1000, work_units_per_cycle=1)
    return sizing('asrs_capacity_v1', 'pallets/day', 'automated_storage', {**site, **changes}, robot)


def stationary(**changes):
    site = dict(flow_per_day=1800, sizing_window_h=2, availability=.8, reserve_count=1)
    return sizing('stationary_cycle_v1', 'items/day', 'stationary_manipulation', {**site, **changes},
                  dict(handling_cycle_s=10, work_units_per_cycle=1))


def aerial(**changes):
    site = dict(flow_per_day=400, sizing_window_h=6, availability=.7, reserve_count=1)
    return sizing('aerial_surface_v1', 'm2/day', 'aerial_facade_cleaning', {**site, **changes},
                  dict(surface_rate_m2_h=300, work_time_h=.25, turnaround_h=.5))


def test_asrs_requires_both_storage_capacity_and_flow_capacity():
    assert asrs().count == 4  # Три модуля по ёмкости + резерв.
    assert asrs(flow_per_day=3000).count == 6  # Пять модулей по потоку + резерв.
    assert asrs(pallet_places=5000).count == 6
    assert asrs(pallet_places=0, flow_per_day=0).count == 0


def test_published_asrs_rate_has_priority_over_synthetic_cycle_and_wrong_units_block():
    site = dict(flow_per_day=2000, sizing_window_h=8, availability=.8, reserve_count=0)
    robot = dict(throughput=45, throughput_unit='паллет/ч на кран', handling_cycle_s=1, lines_per_presentation=10)
    old = deepcopy(robot)
    result = sizing('asrs_capacity_v1', 'lines/day', 'automated_storage', site, robot)
    assert result.count == 1 and result.details['cycles_per_hour'] == 45
    assert 'handling_cycle_s' not in result.details['inputs']
    assert result.details['daily_capacity_per_machine_items'] == 2880
    assert robot == old
    robot['throughput_unit'] = 'кг/ч'
    assert sizing('asrs_capacity_v1', 'lines/day', 'automated_storage', site, robot).count is None


def test_stationary_cycle_responds_to_load_and_work_window():
    assert stationary().count == 5
    assert stationary(flow_per_day=3600).count == 8
    assert stationary(sizing_window_h=4).count == 3
    assert stationary(flow_per_day=0).count == 0


def test_aerial_uses_whole_sorties_with_turnaround_and_responds_to_demand():
    result = aerial()
    assert result.details['coverage_per_sortie_m2'] == 75
    assert result.details['sorties_per_machine_day'] == 5
    assert result.details['required_sorties'] == 6
    assert result.count == 3
    assert aerial(flow_per_day=800).count > result.count
    assert aerial(flow_per_day=0).count == 0
    assert aerial(sizing_window_h=.5).count is None  # Нет окна для вылета и обслуживания.


def test_roof_survey_counts_area_per_inspection_and_uses_aerial_class():
    site = dict(flow_per_day=2, surface_area_m2=10000, sizing_window_h=6, availability=.7, reserve_count=1)
    robot = dict(surface_rate_m2_h=10000, work_time_h=.5, turnaround_h=1)
    result = sizing('aerial_surface_v1', 'surveys/day', 'aerial_inspection', site, robot)
    assert result.count == 3 and result.details['daily_work_m2'] == 20000
    assert sizing('aerial_surface_v1', 'surveys/day', 'aerial_inspection', {**site, 'flow_per_day': 4}, robot).count == 5
    assert sizing('aerial_surface_v1', 'surveys/day', 'ground_patrol', site, robot).count is None


@pytest.mark.parametrize('size', [asrs, stationary, aerial])
@pytest.mark.parametrize('change', [dict(flow_per_day=-1), dict(flow_per_day=True), dict(flow_per_day=float('inf')),
                                   dict(flow_per_day=float('nan')), dict(availability=0), dict(availability=1.1),
                                   dict(reserve_count=.5), dict(reserve_count=True), dict(sizing_window_h=25),
                                   dict(sizing_window_h=None)])
def test_invalid_inputs_do_not_get_quantity(size, change):
    assert size(**change).count is None


@pytest.mark.parametrize('change', [dict(pallet_places=.5), dict(pallet_places=True), dict(pallet_places=-1)])
def test_storage_requires_integer_nonnegative_places(change):
    assert asrs(**change).count is None


@pytest.mark.parametrize('field', ['handling_cycle_s', 'work_units_per_cycle'])
@pytest.mark.parametrize('value', [None, 0, -1, True, float('inf'), 'до 10'])
def test_robot_cycle_inputs_must_be_unambiguous_positive_numbers(field, value):
    inputs = dict(flow_per_day=100, sizing_window_h=8, availability=.8, reserve_count=0)
    robot = dict(handling_cycle_s=10, work_units_per_cycle=1)
    robot[field] = value
    assert sizing('stationary_cycle_v1', 'items/day', 'stationary_manipulation', inputs, robot).count is None


def test_wrong_class_or_units_and_numeric_overflow_fail_closed():
    inputs = dict(flow_per_day=100, sizing_window_h=8, availability=.8, reserve_count=0)
    robot = dict(handling_cycle_s=10, work_units_per_cycle=1)
    assert sizing('stationary_cycle_v1', 'kg/day', 'stationary_manipulation', inputs, robot).count is None
    assert sizing('stationary_cycle_v1', 'items/day', 'mobile_transport', inputs, robot).count is None
    tiny = dict(surface_rate_m2_h=100, work_time_h=5e-324, turnaround_h=0)
    assert sizing('aerial_surface_v1', 'm2/day', 'aerial_facade_cleaning', inputs, tiny).count is None
