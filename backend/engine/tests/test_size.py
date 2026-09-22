from datetime import date
from uuid import uuid4

from engine.models import (
    AttributeDef,
    AttrValue,
    CalcNorm,
    CalcRequest,
    Candidate,
    Catalog,
    Product,
    SiteProfile,
    SolutionType,
    Source,
    Task,
)
from engine.size import run


def _source(id: int = 1, kind: str = "vendor", url: str | None = "https://ronavi.ru/h1500") -> Source:
    return Source(id=id, kind=kind, url=url, publisher="Rona", captured_at=date(2026, 1, 1))


def _known(value, source_id: int | None = 1, unit: str | None = None) -> AttrValue:
    return AttrValue(status="known", value=value, unit=unit, source_id=source_id)


def _product(
    *,
    attrs: dict[str, AttrValue] | None = None,
    name: str = "H1500",
    solution_type_code: str = "amr",
) -> Product:
    return Product(
        id=uuid4(),
        solution_type_code=solution_type_code,
        name=name,
        manufacturer="Rona",
        availability="operation",
        trl=9,
        attrs=attrs or {},
    )


def _norm(
    key: str,
    value: float,
    unit: str | None = None,
    solution_type_code: str | None = None,
    source_id: int = 99,
) -> CalcNorm:
    return CalcNorm(key=key, value=value, unit=unit, solution_type_code=solution_type_code, source_id=source_id)


def _attr_def(key: str, unit: str | None = None) -> AttributeDef:
    return AttributeDef(
        key=key,
        group_code="technical",
        label=key,
        unit=unit,
        datatype="number",
    )


_FAMILY_SIZING: dict[str, dict] = {
    "flow_cycle": {
        "vars": {
            "t_cycle": "2 * task.route_len_m / robot.speed_loaded_ms + task.t_load_s + task.t_unload_s + norm.t_wait_s",
            "uptime": "robot.work_time_h / (robot.work_time_h + robot.charge_time_h)",
            "q": "3600 / t_cycle * uptime * norm.k_util",
        },
        "formula": "ceil(task.flow_per_hour / q) + norm.n_reserve",
    },
    "area_window": {
        "vars": {
            "t_window": "site.shift_hours * site.shifts_per_day",
            "q": "robot.throughput * norm.k_util",
        },
        "formula": "ceil(site.clean_area_m2 * norm.f_passes / (q * t_window)) + norm.n_reserve",
    },
    "count_window": {
        "vars": {
            "t_window": "site.shift_hours * site.shifts_per_day",
            "q": "robot.throughput * norm.k_util",
        },
        "formula": "ceil(site.pallet_places * norm.f_frequency / (q * t_window)) + norm.n_reserve",
    },
    "station_robots": {
        "vars": {
            "stations": "ceil(task.flow_per_hour / (robot.throughput * norm.k_util))",
        },
        "formula": "ceil(stations * robot.robots_per_station) + norm.n_reserve",
    },
    "perimeter_rounds": {
        "vars": {
            "t_round": "task.route_len_m / robot.speed_empty_ms + norm.n_stops * norm.t_stop_s",
            "t_window": "site.shift_hours * site.shifts_per_day * 3600",
        },
        "formula": "ceil(norm.rounds_required * t_round / (t_window * norm.k_util)) + norm.n_reserve",
    },
}


def _st(code: str, family: str, vars: dict[str, str] | None = None, formula: str | None = None) -> SolutionType:
    sizing = _FAMILY_SIZING.get(family, {"vars": {}, "formula": "1"})
    return SolutionType(
        code=code,
        name=code,
        family=family,  # type: ignore[arg-type]
        rule_spec={
            "solution_type": code,
            "hard": [],
            "soft": [],
            "sizing": {
                "family": family,
                "vars": vars if vars is not None else sizing["vars"],
                "formula": formula if formula is not None else sizing["formula"],
            },
        },
    )


def _catalog(
    products: list[Product],
    solution_types: list[SolutionType],
    sources: list[Source] | None = None,
) -> Catalog:
    return Catalog(
        version_id=1,
        products=products,
        sources=sources if sources is not None else [_source()],
        solution_types=solution_types,
        attribute_defs=[
            _attr_def("speed_loaded_ms", "м/с"),
            _attr_def("speed_empty_ms", "м/с"),
            _attr_def("work_time_h", "ч"),
            _attr_def("charge_time_h", "ч"),
            _attr_def("throughput", "м²/ч"),
            _attr_def("robots_per_station", "шт"),
        ],
    )


def _site(**kwargs) -> SiteProfile:
    defaults = dict(
        object_type_code="warehouse",
        shift_hours=11,
        shifts_per_day=2,
        days_year=365,
        clean_area_m2=10_000,
        pallet_places=20_000,
    )
    defaults.update(kwargs)
    return SiteProfile(**defaults)


def _task(process_code: str = "transport", **kwargs) -> Task:
    defaults = dict(
        process_code=process_code,
        name="Перевозка",
        flow_per_hour=50,
        route_len_m=80,
        max_load_kg=800,
        t_load_s=30,
        t_unload_s=30,
    )
    defaults.update(kwargs)
    return Task(**defaults)


def _req(site: SiteProfile | None = None, tasks: list[Task] | None = None) -> CalcRequest:
    return CalcRequest(site=site or _site(), tasks=tasks or [_task()])


def _norms(*extra: CalcNorm) -> list[CalcNorm]:
    return [
        _norm("k_util", 0.82, "доля"),
        _norm("n_reserve", 1, "шт"),
        _norm("t_wait_s", 20, "с"),
        _norm("f_passes", 1, "раз"),
        _norm("f_frequency", 1, "раз"),
        _norm("rounds_required", 24, "шт"),
        _norm("n_stops", 4, "шт"),
        _norm("t_stop_s", 60, "с"),
        _norm("analogue_min_sample", 3, "шт"),
        *extra,
    ]


def _cand(product: Product, process_code: str = "transport", verdict: str = "pass") -> Candidate:
    return Candidate(product_id=product.id, process_code=process_code, verdict=verdict)  # type: ignore[arg-type]


def test_family_flow_cycle():
    # t_cycle = 2*80/2 + 30+30+20 = 160
    # uptime = 10/(10+2) = 10/12
    # q = 3600/160 * 10/12 * 0.82 = 15.375
    # ceil(50 / 15.375) + 1 = ceil(3.252...) + 1 = 4 + 1 = 5
    product = _product(
        attrs={
            "speed_loaded_ms": _known(2.0, unit="м/с"),
            "work_time_h": _known(10.0, unit="ч"),
            "charge_time_h": _known(2.0, unit="ч"),
        }
    )
    options, trace = run(
        _req(),
        [_cand(product)],
        _catalog([product], [_st("amr", "flow_cycle")]),
        _norms(),
    )
    assert len(options) == 1
    assert options[0].count == 5
    assert options[0].family == "flow_cycle"
    assert options[0].process_code == "transport"
    assert options[0].formula == "ceil(50 / 15.38) + 1 = 5"
    final = [s for s in trace if s.value == 5 and s.unit == "шт"]
    assert len(final) == 1
    assert final[0].step == "size"
    assert "50" in final[0].message and "5 единиц" in final[0].message
    assert "цикл 160 с" in final[0].message
    assert "загрузка 0,82" in final[0].message
    assert "резерв 1" in final[0].message


def test_family_area_window():
    # t_window = 11 * 2 = 22
    # q = 400 * 0.82 = 328
    # ceil(10000 * 1 / (328 * 22)) + 1 = ceil(1.3858...) + 1 = 2 + 1 = 3
    product = _product(
        name="Cleaner",
        solution_type_code="cleaning_robot",
        attrs={"throughput": _known(400, unit="м²/ч")},
    )
    options, _trace = run(
        _req(tasks=[_task("cleaning")]),
        [_cand(product, "cleaning")],
        _catalog([product], [_st("cleaning_robot", "area_window")]),
        _norms(),
    )
    assert len(options) == 1
    assert options[0].count == 3
    assert options[0].family == "area_window"
    assert "ceil(" in options[0].formula and "= 3" in options[0].formula


def test_family_count_window():
    # t_window = 11 * 2 = 22
    # q = 200 * 0.82 = 164
    # ceil(20000 * 1 / (164 * 22)) + 1 = ceil(5.543...) + 1 = 6 + 1 = 7
    product = _product(
        name="Scanner",
        solution_type_code="inventory_robot",
        attrs={"throughput": _known(200, unit="мест/ч")},
    )
    options, _trace = run(
        _req(tasks=[_task("inventory")]),
        [_cand(product, "inventory")],
        _catalog([product], [_st("inventory_robot", "count_window")]),
        _norms(),
    )
    assert len(options) == 1
    assert options[0].count == 7
    assert options[0].family == "count_window"


def test_family_station_robots():
    # stations = ceil(50 / (12 * 0.82)) = ceil(5.081...) = 6
    # ceil(6 * 1) + 1 = 7
    product = _product(
        name="Crane",
        solution_type_code="stacker_crane",
        attrs={
            "throughput": _known(12, unit="оп/ч"),
            "robots_per_station": _known(1, unit="шт"),
        },
    )
    options, _trace = run(
        _req(tasks=[_task("storage")]),
        [_cand(product, "storage")],
        _catalog([product], [_st("stacker_crane", "station_robots")]),
        _norms(),
    )
    assert len(options) == 1
    assert options[0].count == 7
    assert options[0].family == "station_robots"
    assert "ceil(" in options[0].formula and "= 7" in options[0].formula


def test_family_perimeter_rounds():
    # t_round = 8000/2 + 4*60 = 4240
    # t_window = 11*2*3600 = 79200
    # ceil(24 * 4240 / (79200 * 0.82)) + 1 = ceil(1.5669...) + 1 = 2 + 1 = 3
    product = _product(
        name="Guard",
        solution_type_code="security_robot",
        attrs={"speed_empty_ms": _known(2.0, unit="м/с")},
    )
    options, _trace = run(
        _req(tasks=[_task("security", route_len_m=8000)]),
        [_cand(product, "security")],
        _catalog([product], [_st("security_robot", "perimeter_rounds")]),
        _norms(),
    )
    assert len(options) == 1
    assert options[0].count == 3
    assert options[0].family == "perimeter_rounds"


def test_vars_evaluated_in_declaration_order():
    # a = 10; b = a*2 = 20; c = b + a = 30. Если не копить vars — KeyError на b.
    product = _product()
    st = _st(
        "amr",
        "flow_cycle",
        vars={"a": "task.flow_per_hour", "b": "a * 2", "c": "b + a"},
        formula="c",
    )
    options, _trace = run(
        _req(tasks=[_task(flow_per_hour=10)]),
        [_cand(product)],
        _catalog([product], [st]),
        _norms(),
    )
    assert len(options) == 1
    assert options[0].count == 30


def test_skip_candidate_without_pass():
    ok = _product(
        name="Ok",
        attrs={
            "speed_loaded_ms": _known(2.0, unit="м/с"),
            "work_time_h": _known(10.0, unit="ч"),
            "charge_time_h": _known(2.0, unit="ч"),
        },
    )
    failed = _product(name="Fail", attrs=ok.attrs)
    unknown = _product(name="Unknown", attrs=ok.attrs)
    catalog = _catalog([ok, failed, unknown], [_st("amr", "flow_cycle")])
    options, _trace = run(
        _req(),
        [
            _cand(ok, verdict="pass"),
            _cand(failed, verdict="fail"),
            _cand(unknown, verdict="unknown"),
        ],
        catalog,
        _norms(),
    )
    assert [o.product_id for o in options] == [ok.id]


def test_zero_division_skips_product():
    product = _product(
        attrs={
            "speed_loaded_ms": _known(0.0, unit="м/с"),
            "work_time_h": _known(10.0, unit="ч"),
            "charge_time_h": _known(2.0, unit="ч"),
        }
    )
    options, trace = run(
        _req(),
        [_cand(product)],
        _catalog([product], [_st("amr", "flow_cycle")]),
        _norms(),
    )
    assert options == []
    assert any("деление на ноль" in s.message and s.verdict == "unknown" for s in trace)
    assert all(s.product_id == product.id for s in trace)


def test_placeholder_formula_zero_is_visible():
    product = _product(name="Draft")
    st = _st("amr", "flow_cycle", vars={}, formula="0")
    options, trace = run(_req(), [_cand(product)], _catalog([product], [st]), _norms())
    assert options == []
    assert any(
        s.verdict == "unknown" and "дала 0" in s.message and "не считаем" in s.message for s in trace
    )


def test_formula_substitutes_numbers_not_names():
    # q + q2: наивная замена подстроки «q» дала бы «10 + 102». AST сохраняет имена.
    product = _product()
    st = _st("amr", "flow_cycle", vars={"q": "10", "q2": "21"}, formula="q + q2")
    options, _trace = run(_req(), [_cand(product)], _catalog([product], [st]), _norms())
    assert len(options) == 1
    assert options[0].count == 31
    assert options[0].formula == "10 + 21 = 31"
    assert "q2" not in options[0].formula
    assert "task." not in options[0].formula


def test_trace_for_assumption_norm_stage_d():
    product = _product(
        attrs={
            "speed_loaded_ms": _known(2.0, unit="м/с"),
            "work_time_h": _known(10.0, unit="ч"),
        }
    )
    options, trace = run(
        _req(),
        [_cand(product)],
        _catalog([product], [_st("amr", "flow_cycle")]),
        _norms(_norm("default.charge_time_h.flow_cycle", 2.0, "ч")),
    )
    assert len(options) == 1
    assert options[0].count == 5
    d_steps = [s for s in trace if s.source and s.source.startswith("[D]")]
    assert len(d_steps) == 1
    assert d_steps[0].source == "[D] допущение: default.charge_time_h.flow_cycle = 2"
    assert "default.charge_time_h.flow_cycle" in d_steps[0].message
    assert d_steps[0].value == 2.0
    vendor_dupes = [s for s in trace if s.source and s.source.startswith("[A]")]
    assert vendor_dupes == []
    finals = [s for s in trace if s.unit == "шт" and s.formula]
    assert len(finals) == 1
    assert finals[0].value == 5


def test_solution_type_norm_overrides_general():
    # Общий k_util=0.82 дал бы count=5. Тип amr перекрывает k_util=0.5:
    # q = 3600/160 * 10/12 * 0.5 = 9.375
    # ceil(50 / 9.375) + 1 = ceil(5.333...) + 1 = 6 + 1 = 7
    product = _product(
        attrs={
            "speed_loaded_ms": _known(2.0, unit="м/с"),
            "work_time_h": _known(10.0, unit="ч"),
            "charge_time_h": _known(2.0, unit="ч"),
        }
    )
    options, _trace = run(
        _req(),
        [_cand(product)],
        _catalog([product], [_st("amr", "flow_cycle")]),
        _norms(_norm("k_util", 0.5, "доля", solution_type_code="amr")),
    )
    assert len(options) == 1
    assert options[0].count == 7
