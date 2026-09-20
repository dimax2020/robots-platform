from engine.models import CalcRequest, Catalog, SiteProfile, Task
from engine.pipeline import run_pipeline
from engine.rules import UnsafeExpression, evaluate

import pytest


def test_pipeline_stub_returns_events_and_trace():
    req = CalcRequest(
        site=SiteProfile(object_type_code="warehouse"),
        tasks=[Task(process_code="transport", flow_per_hour=120, route_len_m=80)],
    )
    res = run_pipeline(req, Catalog(version_id=0))
    assert res.sim is not None and len(res.sim.events) == 100
    assert len(res.trace) >= 2
    assert [s.code for s in res.scenarios] == ["baseline", "per_task", "optimal"]


def test_expression_evaluator_is_safe():
    ctx = {"task": {"flow_per_hour": 120}, "norm": {"k_util": 0.82}}
    assert evaluate("ceil(task.flow_per_hour / (3600 / 48 * norm.k_util))", ctx) == 2
    with pytest.raises(UnsafeExpression):
        evaluate("__import__('os').system('true')", ctx)
