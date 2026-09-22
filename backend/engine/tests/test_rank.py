from datetime import date
from uuid import uuid4

import pytest

from engine.models import (
    AttributeDef,
    AttrValue,
    CalcNorm,
    CalcRequest,
    Candidate,
    Catalog,
    Product,
    SiteProfile,
    SizedOption,
    SolutionType,
    Source,
    Task,
)
from engine.rank import run


def _source(id: int = 1, kind: str = "vendor", url: str | None = "https://ronavi.ru/h1500") -> Source:
    return Source(id=id, kind=kind, url=url, publisher="Rona", captured_at=date(2026, 1, 1))


def _known(value, source_id: int | None = 1, unit: str | None = None) -> AttrValue:
    return AttrValue(status="known", value=value, unit=unit, source_id=source_id)


def _product(
    *,
    attrs: dict[str, AttrValue] | None = None,
    name: str = "H1500",
    solution_type_code: str = "amr",
    availability: str = "operation",
    trl: int | None = 9,
    case_process_codes: list[str] | None = None,
) -> Product:
    return Product(
        id=uuid4(),
        solution_type_code=solution_type_code,
        name=name,
        manufacturer="Rona",
        availability=availability,
        trl=trl,
        attrs=attrs or {},
        case_process_codes=case_process_codes or [],
    )


def _norm(key: str, value: float, unit: str | None = None, source_id: int = 99) -> CalcNorm:
    return CalcNorm(key=key, value=value, unit=unit, source_id=source_id)


def _attr_def(key: str, label: str | None = None, unit: str | None = None) -> AttributeDef:
    return AttributeDef(
        key=key,
        group_code="technical",
        label=label or key,
        unit=unit,
        datatype="number",
    )


def _st(
    code: str = "amr",
    family: str = "flow_cycle",
    soft: list[dict] | None = None,
    vars: dict[str, str] | None = None,
    formula: str = "1",
) -> SolutionType:
    return SolutionType(
        code=code,
        name=code,
        family=family,  # type: ignore[arg-type]
        rule_spec={
            "solution_type": code,
            "hard": [],
            "soft": soft or [],
            "sizing": {
                "family": family,
                "vars": vars or {},
                "formula": formula,
            },
        },
    )


def _catalog(
    products: list[Product],
    solution_types: list[SolutionType] | None = None,
    attribute_defs: list[AttributeDef] | None = None,
    sources: list[Source] | None = None,
) -> Catalog:
    return Catalog(
        version_id=1,
        products=products,
        sources=sources if sources is not None else [_source()],
        solution_types=solution_types if solution_types is not None else [_st()],
        attribute_defs=attribute_defs
        if attribute_defs is not None
        else [
            _attr_def("price_rub", "Цена", "₽"),
            _attr_def("speed_loaded_ms", "Скорость с грузом", "м/с"),
            _attr_def("work_time_h", "Время работы", "ч"),
            _attr_def("charge_time_h", "Время зарядки", "ч"),
            _attr_def("throughput", "Производительность", "м²/ч"),
        ],
    )


def _req(tasks: list[Task] | None = None) -> CalcRequest:
    return CalcRequest(
        site=SiteProfile(object_type_code="warehouse"),
        tasks=tasks or [Task(process_code="transport", name="Перевозка")],
    )


def _norms(*extra: CalcNorm) -> list[CalcNorm]:
    return [
        _norm("analogue_min_sample", 99),
        *extra,
    ]


def _cand(product: Product, process_code: str = "transport", verdict: str = "pass") -> Candidate:
    return Candidate(product_id=product.id, process_code=process_code, verdict=verdict)  # type: ignore[arg-type]


def _opt(product: Product, process_code: str = "transport", count: int = 2) -> SizedOption:
    return SizedOption(
        product_id=product.id,
        process_code=process_code,
        count=count,
        formula="1 = 1",
        family="flow_cycle",
    )


def _factor_steps(trace, product_id):
    return [s for s in trace if s.product_id == product_id and s.formula and "*" in s.formula]


def test_dir_max_and_min_normalization():
    # Три кандидата одного процесса, веса 0.6 (trl, dir max) и 0.4 (price_rub, dir min).
    # trl: min=5, max=9, размах=4
    #   Alpha 9: (9-5)/4 = 1.0  → 0.6 * 1.0 = 0.6
    #   Beta  7: (7-5)/4 = 0.5  → 0.6 * 0.5 = 0.3
    #   Gamma 5: (5-5)/4 = 0.0  → 0.6 * 0.0 = 0.0
    # price: min=100, max=300, размах=200
    #   Alpha 100: (300-100)/200 = 1.0  → 0.4 * 1.0 = 0.4
    #   Beta  200: (300-200)/200 = 0.5  → 0.4 * 0.5 = 0.2
    #   Gamma 300: (300-300)/200 = 0.0  → 0.4 * 0.0 = 0.0
    # score: Alpha=1.0, Beta=0.5, Gamma=0.0
    soft = [
        {"field": "trl", "weight": 0.6, "dir": "max"},
        {"field": "price_rub", "weight": 0.4, "dir": "min"},
    ]
    alpha = _product(name="Alpha", trl=9, attrs={"price_rub": _known(100)})
    beta = _product(name="Beta", trl=7, attrs={"price_rub": _known(200)})
    gamma = _product(name="Gamma", trl=5, attrs={"price_rub": _known(300)})
    catalog = _catalog([alpha, beta, gamma], [_st(soft=soft)])
    candidates = [_cand(alpha), _cand(beta), _cand(gamma)]
    scenarios, trace = run(_req(), candidates, [], catalog, _norms())

    assert alpha.id and candidates[0].score == pytest.approx(1.0)
    assert candidates[1].score == pytest.approx(0.5)
    assert candidates[2].score == pytest.approx(0.0)

    alpha_trl = next(s for s in _factor_steps(trace, alpha.id) if s.formula.startswith("0.60"))
    assert alpha_trl.formula == "0.60 * 1.00 = 0.600"
    assert alpha_trl.value == pytest.approx(0.6)
    assert "УГТ 9" in alpha_trl.message
    assert "лучший среди кандидатов процесса" in alpha_trl.message
    assert "вклад 0,600 из 0,6" in alpha_trl.message

    assert [s.code for s in scenarios] == ["baseline", "per_task", "optimal"]


def test_zero_spread_gives_one():
    soft = [{"field": "trl", "weight": 1.0, "dir": "max"}]
    # единственный кандидат: размах нулевой → фактор 1.0
    one = _product(name="One", trl=4)
    c_one = _cand(one)
    run(_req(), [c_one], [], _catalog([one], [_st(soft=soft)]), _norms())
    assert c_one.score == pytest.approx(1.0)

    a = _product(name="A", trl=9)
    b = _product(name="B", trl=9)
    ca, cb = _cand(a), _cand(b)
    run(_req(), [ca, cb], [], _catalog([a, b], [_st(soft=soft)]), _norms())
    assert ca.score == pytest.approx(1.0)
    assert cb.score == pytest.approx(1.0)


def test_map_unknown_key_gives_zero():
    # operation нет в шкале {piloting, rnd} → 0.0
    soft = [{"field": "availability", "weight": 1.0, "map": {"piloting": 1.0, "rnd": 0.5}}]
    product = _product(availability="operation")
    cand = _cand(product)
    _, trace = run(_req(), [cand], [], _catalog([product], [_st(soft=soft)]), _norms())
    assert cand.score == pytest.approx(0.0)
    factor = _factor_steps(trace, product.id)[0]
    assert factor.formula == "1.00 * 0.00 = 0.000"
    assert factor.value == pytest.approx(0.0)
    assert "нет в шкале" in factor.message


def test_normalization_isolated_by_process():
    # transport: цены 10 и 20; cleaning: цены 100 и 200. Только price_rub, dir min, вес 1.0.
    # По процессу: дешёвый = 1.0, дорогой = 0.0.
    # Если бы нормировали глобально (min=10, max=200):
    #   transport 20 → (200-20)/190 ≈ 0.947, cleaning 100 → (200-100)/190 ≈ 0.526
    soft = [{"field": "price_rub", "weight": 1.0, "dir": "min"}]
    t_cheap = _product(name="T10", attrs={"price_rub": _known(10)})
    t_dear = _product(name="T20", attrs={"price_rub": _known(20)})
    c_cheap = _product(name="C100", attrs={"price_rub": _known(100)})
    c_dear = _product(name="C200", attrs={"price_rub": _known(200)})
    catalog = _catalog([t_cheap, t_dear, c_cheap, c_dear], [_st(soft=soft)])
    cands = [
        _cand(t_cheap, "transport"),
        _cand(t_dear, "transport"),
        _cand(c_cheap, "cleaning"),
        _cand(c_dear, "cleaning"),
    ]
    req = _req(
        tasks=[
            Task(process_code="transport", name="Перевозка"),
            Task(process_code="cleaning", name="Уборка"),
        ]
    )
    run(req, cands, [], catalog, _norms())
    by_id = {c.product_id: c.score for c in cands}
    assert by_id[t_cheap.id] == pytest.approx(1.0)
    assert by_id[t_dear.id] == pytest.approx(0.0)
    assert by_id[c_cheap.id] == pytest.approx(1.0)
    assert by_id[c_dear.id] == pytest.approx(0.0)


def test_reliability_takes_worst_letter():
    # Ключи robot.* из sizing: speed_loaded_ms (vendor → A) и charge_time_h.
    # У Good оба из паспорта → A → map 1.0.
    # У Bad charge_time_h из default.* → D; худшая буква D → map 0.1.
    soft = [{"field": "reliability", "weight": 1.0, "map": {"A": 1.0, "B": 0.7, "C": 0.35, "D": 0.1}}]
    sizing_vars = {
        "t_cycle": "2 * task.route_len_m / robot.speed_loaded_ms",
        "uptime": "robot.work_time_h / (robot.work_time_h + robot.charge_time_h)",
    }
    good = _product(
        name="Good",
        attrs={
            "speed_loaded_ms": _known(2.0),
            "work_time_h": _known(10.0),
            "charge_time_h": _known(2.0),
        },
    )
    bad = _product(
        name="Bad",
        attrs={
            "speed_loaded_ms": _known(2.0),
            "work_time_h": _known(10.0),
        },
    )
    st = _st(soft=soft, vars=sizing_vars, formula="ceil(task.flow_per_hour / uptime) + 1")
    catalog = _catalog([good, bad], [st])
    cg, cb = _cand(good), _cand(bad)
    _, trace = run(
        _req(),
        [cg, cb],
        [],
        catalog,
        _norms(_norm("default.charge_time_h.flow_cycle", 2.0, "ч")),
    )
    assert cg.score == pytest.approx(1.0)
    assert cb.score == pytest.approx(0.1)
    bad_msg = " ".join(s.message for s in _factor_steps(trace, bad.id))
    assert "Достоверность данных D" in bad_msg


def test_has_case():
    soft = [{"field": "has_case", "weight": 1.0, "dir": "max"}]
    with_case = _product(name="With", case_process_codes=["transport"])
    without = _product(name="Without", case_process_codes=["cleaning"])
    cw, cn = _cand(with_case), _cand(without)
    _, trace = run(
        _req(),
        [cw, cn],
        [],
        _catalog([with_case, without], [_st(soft=soft)]),
        _norms(),
    )
    assert cw.score == pytest.approx(1.0)
    assert cn.score == pytest.approx(0.0)
    assert any("есть" in s.message and "Кейс на таком же процессе" in s.message for s in _factor_steps(trace, with_case.id))
    assert any("нет" in s.message and "Кейс на таком же процессе" in s.message for s in _factor_steps(trace, without.id))


def test_data_completeness():
    # Три характеристики. filled = known и not_applicable.
    # Full: 3/3 = 1.0 → (1-0)/(1-0) = 1.0
    # Mid:  2/3       → (2/3-0)/(1-0) = 2/3
    # Empty: 0/3 = 0  → 0.0
    soft = [{"field": "data_completeness", "weight": 1.0, "dir": "max"}]
    defs = [
        _attr_def("payload_kg", "Грузоподъёмность"),
        _attr_def("speed_loaded_ms", "Скорость"),
        _attr_def("price_rub", "Цена"),
    ]
    full = _product(
        name="Full",
        attrs={
            "payload_kg": _known(1500),
            "speed_loaded_ms": _known(2.0),
            "price_rub": AttrValue(status="not_applicable", value=None),
        },
    )
    mid = _product(
        name="Mid",
        attrs={
            "payload_kg": _known(800),
            "speed_loaded_ms": AttrValue(status="not_applicable", value=None),
        },
    )
    empty = _product(
        name="Empty",
        attrs={"payload_kg": AttrValue(status="unknown", value=None)},
    )
    cf, cm, ce = _cand(full), _cand(mid), _cand(empty)
    _, trace = run(
        _req(),
        [cf, cm, ce],
        [],
        _catalog([full, mid, empty], [_st(soft=soft)], attribute_defs=defs),
        _norms(),
    )
    assert cf.score == pytest.approx(1.0)
    assert cm.score == pytest.approx(2 / 3)
    assert ce.score == pytest.approx(0.0)
    assert any("Полнота данных" in s.message for s in _factor_steps(trace, mid.id))


def test_non_pass_candidates_are_not_scored():
    soft = [{"field": "trl", "weight": 1.0, "dir": "max"}]
    ok = _product(name="Ok", trl=9)
    failed = _product(name="Fail", trl=9)
    unknown = _product(name="Unknown", trl=9)
    c_ok, c_fail, c_unk = _cand(ok), _cand(failed, verdict="fail"), _cand(unknown, verdict="unknown")
    run(
        _req(),
        [c_ok, c_fail, c_unk],
        [],
        _catalog([ok, failed, unknown], [_st(soft=soft)]),
        _norms(),
    )
    assert c_ok.score == pytest.approx(1.0)
    assert c_fail.score is None
    assert c_unk.score is None


def test_per_task_picks_best_score_per_process():
    soft = [{"field": "trl", "weight": 1.0, "dir": "max"}]
    t_best = _product(name="TBest", trl=9, attrs={"raas_available": AttrValue(status="known", value=True)})
    t_worse = _product(name="TWorse", trl=5)
    c_best = _product(name="CBest", trl=8)
    c_worse = _product(name="CWorse", trl=3)
    catalog = _catalog([t_best, t_worse, c_best, c_worse], [_st(soft=soft)])
    cands = [
        _cand(t_best, "transport"),
        _cand(t_worse, "transport"),
        _cand(c_best, "cleaning"),
        _cand(c_worse, "cleaning"),
    ]
    options = [
        _opt(t_best, "transport", 4),
        _opt(t_worse, "transport", 3),
        _opt(c_best, "cleaning", 2),
        _opt(c_worse, "cleaning", 7),
    ]
    req = _req(
        tasks=[
            Task(process_code="transport", name="Перевозка"),
            Task(process_code="cleaning", name="Уборка"),
        ]
    )
    scenarios, trace = run(req, cands, options, catalog, _norms())
    assert [s.code for s in scenarios] == ["baseline", "per_task", "optimal"]
    baseline, per_task, optimal = scenarios
    assert baseline.options == []
    assert baseline.economics is None
    assert optimal.options == []
    assert optimal.economics is None
    assert per_task.economics is None
    assert [(o.product_id, o.process_code, o.count) for o in per_task.options] == [
        (t_best.id, "transport", 4),
        (c_best.id, "cleaning", 2),
    ]
    assert per_task.raas_available is True
    assert baseline.raas_available is False
    assert any("Без роботизации" in s.message and "заглушка" in s.message for s in trace)
    assert any("Оптимальный состав парка" in s.message and "заглушка" in s.message for s in trace)


def test_trace_contributions_sum_to_score():
    soft = [
        {"field": "trl", "weight": 0.25, "dir": "max"},
        {"field": "availability", "weight": 0.20, "map": {"operation": 1.0, "piloting": 0.5, "rnd": 0.0}},
        {"field": "reliability", "weight": 0.20, "map": {"A": 1.0, "B": 0.7, "C": 0.35, "D": 0.1}},
        {"field": "has_case", "weight": 0.15, "dir": "max"},
        {"field": "price_rub", "weight": 0.20, "dir": "min"},
    ]
    a = _product(
        name="A",
        trl=9,
        availability="operation",
        case_process_codes=["transport"],
        attrs={
            "price_rub": _known(100),
            "speed_loaded_ms": _known(2.0),
        },
    )
    b = _product(
        name="B",
        trl=5,
        availability="piloting",
        case_process_codes=[],
        attrs={
            "price_rub": _known(300),
            "speed_loaded_ms": _known(1.5),
        },
    )
    st = _st(soft=soft, vars={"x": "robot.speed_loaded_ms"}, formula="1")
    ca, cb = _cand(a), _cand(b)
    _, trace = run(_req(), [ca, cb], [], _catalog([a, b], [st]), _norms())

    # trl: (9-5)/4 → A=1, B=0
    # availability: A=1.0, B=0.5
    # reliability: оба vendor A → 1.0
    # has_case: A=1, B=0
    # price: A=1, B=0
    # A: 0.25*1 + 0.20*1 + 0.20*1 + 0.15*1 + 0.20*1 = 1.00
    # B: 0.25*0 + 0.20*0.5 + 0.20*1 + 0.15*0 + 0.20*0 = 0.30
    assert ca.score == pytest.approx(1.0)
    assert cb.score == pytest.approx(0.3)

    for cand, product in ((ca, a), (cb, b)):
        contribs = [s.value for s in _factor_steps(trace, product.id)]
        assert contribs
        assert sum(contribs) == pytest.approx(cand.score)
        totals = [
            s
            for s in trace
            if s.product_id == product.id and s.formula and "*" not in s.formula and s.value == cand.score
        ]
        assert len(totals) == 1
        assert totals[0].value == pytest.approx(cand.score)
