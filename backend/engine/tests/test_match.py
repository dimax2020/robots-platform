from datetime import date
from uuid import uuid4

from engine.match import run
from engine.models import (
    AttributeDef,
    AttrValue,
    CalcNorm,
    CalcRequest,
    Catalog,
    Product,
    SiteProfile,
    SolutionType,
    Source,
    Task,
)


def _source(id: int = 1, kind: str = "vendor", url: str | None = "https://ronavi.ru/h1500") -> Source:
    return Source(id=id, kind=kind, url=url, publisher="Rona", captured_at=date(2026, 1, 1))


def _product(
    *,
    attrs: dict[str, AttrValue] | None = None,
    name: str = "H1500",
    availability: str = "operation",
    trl: int | None = 9,
    solution_type_code: str = "amr",
) -> Product:
    return Product(
        id=uuid4(),
        solution_type_code=solution_type_code,
        name=name,
        manufacturer="Rona",
        availability=availability,
        trl=trl,
        attrs=attrs or {},
    )


def _norm(key: str, value: float, unit: str | None = "УГТ") -> CalcNorm:
    return CalcNorm(key=key, value=value, unit=unit, source_id=99)


def _st(code: str = "amr", hard: list[dict] | None = None) -> SolutionType:
    return SolutionType(
        code=code,
        name=code,
        family="flow_cycle",
        rule_spec={
            "solution_type": code,
            "hard": hard or [],
            "soft": [],
            "sizing": {"family": "flow_cycle", "formula": "1"},
        },
    )


def _attr_def(key: str, label: str, unit: str | None) -> AttributeDef:
    return AttributeDef(
        key=key,
        group_code="technical",
        label=label,
        unit=unit,
        datatype="number",
    )


def _known(value, source_id: int | None = 1, unit: str | None = None) -> AttrValue:
    return AttrValue(status="known", value=value, unit=unit, source_id=source_id)


def _catalog(
    products: list[Product],
    hard: list[dict] | None = None,
    process_solutions: dict[str, list[str]] | None = None,
    sources: list[Source] | None = None,
) -> Catalog:
    return Catalog(
        version_id=1,
        products=products,
        sources=sources if sources is not None else [_source()],
        solution_types=[_st("amr", hard=hard)],
        attribute_defs=[
            _attr_def("payload_kg", "Грузоподъёмность", "кг"),
            _attr_def("min_aisle_width_m", "Мин. ширина прохода", "м"),
            _attr_def("temp_min_c", "Мин. температура", "°C"),
            _attr_def("lift_height_mm", "Высота подъёма", "мм"),
            _attr_def("speed_loaded_ms", "Скорость с грузом", "м/с"),
        ],
        process_solutions=process_solutions if process_solutions is not None else {"transport": ["amr"]},
    )


def _site(**kwargs) -> SiteProfile:
    defaults = dict(
        object_type_code="warehouse",
        aisle_width_m=3.0,
        temp_min_c=-10,
        temp_max_c=40,
        floor_load_kg_m2=2000,
        storage_height_m=8.0,
    )
    defaults.update(kwargs)
    return SiteProfile(**defaults)


def _req(site: SiteProfile | None = None, tasks: list[Task] | None = None, manual=None) -> CalcRequest:
    return CalcRequest(
        site=site or _site(),
        tasks=tasks or [Task(process_code="transport", name="Перевозка", max_load_kg=800)],
        manual_product_ids=list(manual or []),
    )


def _norms() -> list[CalcNorm]:
    return [_norm("trl_min_automatch", 6)]


_PAYLOAD = [{"field": "payload_kg", "op": ">=", "ref": "task.max_load_kg"}]
_TEMP = [{"field": "temp_min_c", "op": "<=", "ref": "site.temp_min_c"}]
_LIFT = [{"field": "lift_height_mm", "op": ">=", "ref": "site.storage_height_m * 1000"}]


def test_pass_hard_rule():
    product = _product(attrs={"payload_kg": _known(1500, unit="кг")})
    candidates, queries, trace = run(_req(), _catalog([product], hard=_PAYLOAD), _norms())
    assert len(candidates) == 1
    assert candidates[0].verdict == "pass"
    assert candidates[0].failed == []
    assert candidates[0].unknown == []
    assert candidates[0].score is None
    assert queries == []
    formulas = [s.formula for s in trace if s.formula]
    assert "1500 >= 800" in formulas
    messages = " ".join(s.message for s in trace)
    assert "Грузоподъёмность 1500 кг покрывает требуемые 800 кг" in messages
    assert any(s.verdict == "pass" and s.product_id == product.id and "подходит" in s.message for s in trace)
    assert any(s.source == "[A] ronavi.ru/h1500" for s in trace)


def test_fail_hard_rule():
    product = _product(attrs={"payload_kg": _known(500, unit="кг")})
    candidates, queries, trace = run(_req(), _catalog([product], hard=_PAYLOAD), _norms())
    assert len(candidates) == 1
    assert candidates[0].verdict == "fail"
    assert candidates[0].failed == ["payload_kg"]
    assert queries == []
    assert "500 >= 800" in [s.formula for s in trace if s.formula]
    assert any("не покрывает требуемые 800 кг" in s.message for s in trace)
    assert any(s.verdict == "fail" and "исключён" in s.message for s in trace)


def test_unknown_missing_and_status():
    missing = _product(name="Empty", attrs={"speed_loaded_ms": _known(1.2, unit="м/с")})
    flagged = _product(
        name="Blank",
        attrs={"payload_kg": AttrValue(status="unknown", value=999, unit="кг", source_id=1)},
    )
    candidates, queries, trace = run(_req(), _catalog([missing, flagged], hard=_PAYLOAD), _norms())
    assert {c.verdict for c in candidates} == {"unknown"}
    assert all(c.unknown == ["payload_kg"] for c in candidates)
    assert all(c.failed == [] for c in candidates)
    assert {q.field for q in queries} == {"payload_kg"}
    assert {q.product_id for q in queries} == {missing.id, flagged.id}
    assert all(q.source_url == "https://ronavi.ru/h1500" for q in queries)
    assert any("не опубликована" in s.message and s.verdict == "unknown" for s in trace)


def test_not_applicable_counts_as_pass():
    product = _product(
        attrs={
            "payload_kg": _known(1500, unit="кг"),
            "temp_min_c": AttrValue(status="not_applicable", value=None, unit="°C", source_id=1),
        }
    )
    hard = [*_PAYLOAD, *_TEMP]
    candidates, queries, _trace = run(_req(), _catalog([product], hard=hard), _norms())
    assert candidates[0].verdict == "pass"
    assert candidates[0].failed == []
    assert candidates[0].unknown == []
    assert queries == []


def test_skip_rule_when_site_field_none():
    product = _product(attrs={"payload_kg": _known(1500, unit="кг")})
    site = _site(temp_min_c=None)
    hard = [*_PAYLOAD, *_TEMP]
    candidates, queries, trace = run(_req(site=site), _catalog([product], hard=hard), _norms())
    assert candidates[0].verdict == "pass"
    assert candidates[0].unknown == []
    assert candidates[0].failed == []
    assert queries == []
    assert any("пропущено" in s.message and "temp_min_c" in (s.formula or "") for s in trace)
    assert all(s.verdict != "fail" for s in trace)


def test_skip_rule_when_site_expression_is_none():
    product = _product(attrs={"payload_kg": _known(1500, unit="кг")})
    site = _site(storage_height_m=None)
    hard = [*_PAYLOAD, *_LIFT]
    candidates, _, trace = run(_req(site=site), _catalog([product], hard=hard), _norms())
    assert candidates[0].verdict == "pass"
    assert "lift_height_mm" not in candidates[0].unknown
    assert any("storage_height_m" in (s.formula or "") and "пропущено" in s.message for s in trace)


def test_expression_ref_pass():
    product = _product(attrs={"lift_height_mm": _known(9000, unit="мм")})
    candidates, _, trace = run(_req(), _catalog([product], hard=_LIFT), _norms())
    assert candidates[0].verdict == "pass"
    assert "9000 >= 8000" in [s.formula for s in trace if s.formula]


def test_automatch_trl_and_rnd_excluded():
    low_trl = _product(name="Low", trl=4, attrs={"payload_kg": _known(1500)})
    rnd = _product(name="Lab", availability="rnd", trl=9, attrs={"payload_kg": _known(1500)})
    none_trl = _product(name="Draft", trl=None, attrs={"payload_kg": _known(1500)})
    ok = _product(name="Ready", trl=6, attrs={"payload_kg": _known(1500)})
    candidates, _, _trace = run(
        _req(),
        _catalog([low_trl, rnd, none_trl, ok], hard=_PAYLOAD),
        _norms(),
    )
    assert [c.product_id for c in candidates] == [ok.id]
    assert candidates[0].verdict == "pass"


def test_manual_product_ids_bypass_automatch():
    low = _product(name="Pilot", trl=3, attrs={"payload_kg": _known(1500)})
    candidates, _, trace = run(
        _req(manual=[low.id]),
        _catalog([low], hard=_PAYLOAD),
        _norms(),
    )
    assert len(candidates) == 1
    assert candidates[0].product_id == low.id
    assert candidates[0].verdict == "pass"
    assert any("добавлен вручную" in s.message and s.product_id == low.id for s in trace)
    assert any("УГТ 3" in s.message for s in trace)


def test_vendor_query_dedup_by_product_and_field():
    product = _product(attrs={"speed_loaded_ms": _known(1.5, unit="м/с")})
    req = _req(
        tasks=[
            Task(process_code="transport", name="A", max_load_kg=800),
            Task(process_code="transport", name="B", max_load_kg=900),
        ]
    )
    catalog = _catalog([product], hard=_PAYLOAD)
    candidates, queries, _trace = run(req, catalog, _norms())
    assert len(candidates) == 2
    assert all(c.verdict == "unknown" for c in candidates)
    assert len(queries) == 1
    q = queries[0]
    assert q.product_id == product.id
    assert q.product_name == "H1500"
    assert q.manufacturer == "Rona"
    assert q.field == "payload_kg"
    assert q.source_url == "https://ronavi.ru/h1500"


def test_unknown_process_code():
    product = _product(attrs={"payload_kg": _known(1500)})
    req = _req(tasks=[Task(process_code="no_such_process", name="Неизвестно", max_load_kg=800)])
    candidates, queries, trace = run(req, _catalog([product], hard=_PAYLOAD), _norms())
    assert candidates == []
    assert queries == []
    assert any("отсутствует в карте" in s.message and "Неизвестно" in s.message for s in trace)


def test_unparseable_value_is_unknown_not_fail():
    product = _product(attrs={"payload_kg": _known("много", unit="кг")})
    candidates, queries, trace = run(_req(), _catalog([product], hard=_PAYLOAD), _norms())
    assert candidates[0].verdict == "unknown"
    assert candidates[0].unknown == ["payload_kg"]
    assert candidates[0].failed == []
    assert len(queries) == 1
    assert any("не приводится к числу" in s.message for s in trace)


def test_fail_plus_unknown_is_fail_without_vendor_query():
    product = _product(
        attrs={"payload_kg": _known(100, unit="кг")},
    )
    hard = [*_PAYLOAD, *_TEMP]
    candidates, queries, _trace = run(_req(), _catalog([product], hard=hard), _norms())
    assert candidates[0].verdict == "fail"
    assert "payload_kg" in candidates[0].failed
    assert "temp_min_c" in candidates[0].unknown
    assert queries == []
