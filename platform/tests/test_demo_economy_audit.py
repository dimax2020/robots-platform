"""Аудит должен обнаруживать расхождение между флагом допуска и реальным выбором."""
from copy import deepcopy

import pytest

from tools.check_demo_coverage import audit_match, blocker_category, summary


@pytest.mark.parametrize('reason,fields,expected', [
    ({'code': 'sizing_model_missing'}, (), 'model'),
    ({'code': 'sizing_incompatible'}, (), 'model'),
    ({'code': 'configuration_missing'}, (), 'configuration'),
    ({'code': 'price_scope_unconfirmed'}, (), 'price'),
    ({'code': 'price_missing'}, (), 'price'),
    ({'code': 'sizing_attribute_missing', 'field': 'speed_empty_ms'}, (), 'robot_characteristics'),
    ({'code': 'sizing_input_missing', 'field': 'charge_time_h'}, (), 'robot_characteristics'),
    ({'code': 'sizing_input_missing', 'field': 'flow_per_day'}, (), 'quantity_inputs'),
    ({'code': 'sizing_input_missing', 'field': 'autonomy_required_h'}, ('autonomy_required_h',), 'operation_parameters'),
])
def test_blockers_distinguish_model_data_and_commercial_scope(reason, fields, expected):
    assert blocker_category(reason, fields) == expected


def test_every_alternative_is_selected_and_false_readiness_is_detected():
    def hit(pid, *, ready=True):
        return {'product_id': pid, 'name': pid, 'verdict': 'pass', 'applicability': 'conditional',
                'count': 2 if ready else None, 'demo_economic_ready': ready, 'economic_ready': False,
                'sizing': {'model': 'existing' if ready else None}, 'assumptions': [],
                'economic_reasons': [] if ready else [{'code': 'sizing_model_missing', 'message': 'Нет модели'}],
                'resolved_facts': {}}
    matched = {'groups': [{'process_code': 'move', 'process_name': 'Перевозка', 'calculation_mode': 'demo',
                           'demo_best_product_id': 'default', 'hits': [hit('default'), hit('alternative'), hit('blocked', ready=False)]}]}
    old = deepcopy(matched)
    calls = []

    def calculate(picks):
        calls.append(picks)
        pid = picks['move']
        return {'complete': pid == 'default', 'blockers': [] if pid == 'default' else [{'code': 'missing_finance'}],
                'scenarios': [{}, {}, {}],
                'fleet': [{'process_code': 'move', 'product_id': pid, 'count_used': 2, 'included': True,
                           'sizing': {'model': 'existing'}, 'assumptions': []}]}

    rows = audit_match('demo', matched, calculate)
    assert calls == [{'move': 'default'}, {'move': 'alternative'}]
    candidates = rows[0]['technical_candidates']
    assert candidates[0]['selection_check']['verified']
    assert not candidates[1]['selection_check']['verified']
    assert candidates[2]['blocker_categories'] == ['model']
    assert not rows[0]['economy_verified']
    assert summary(rows)['selection_failures'] == 1
    assert summary(rows)['blocked_candidates'] == 1
    assert matched == old
