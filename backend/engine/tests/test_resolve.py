from datetime import date
from uuid import uuid4

import pytest

from engine.models import (
    AttributeDef,
    AttrValue,
    CalcNorm,
    Catalog,
    Product,
    SolutionType,
    Source,
)
from engine.resolve import Resolver


def _source(id: int, kind: str, url: str | None = None, publisher: str | None = None) -> Source:
    return Source(id=id, kind=kind, url=url, publisher=publisher, captured_at=date(2026, 1, 1))


def _product(solution_type_code: str, attrs: dict[str, AttrValue] | None = None, name: str = "P") -> Product:
    return Product(
        id=uuid4(),
        solution_type_code=solution_type_code,
        name=name,
        manufacturer="M",
        availability="operation",
        attrs=attrs or {},
    )


def _norm(key: str, value: float, unit: str | None = "ч", source_id: int = 99) -> CalcNorm:
    return CalcNorm(key=key, value=value, unit=unit, source_id=source_id)


def _st(code: str, family: str) -> SolutionType:
    return SolutionType(
        code=code,
        name=code,
        family=family,
        rule_spec={
            "solution_type": code,
            "hard": [],
            "soft": [],
            "sizing": {"family": family, "formula": "1"},
        },
    )


def _attr_def(key: str, unit: str | None = "ч") -> AttributeDef:
    return AttributeDef(
        key=key,
        group_code="technical",
        label=key,
        unit=unit,
        datatype="number",
    )


def _catalog(
    products: list[Product],
    sources: list[Source] | None = None,
    solution_types: list[SolutionType] | None = None,
    attribute_defs: list[AttributeDef] | None = None,
) -> Catalog:
    return Catalog(
        version_id=1,
        products=products,
        sources=sources or [],
        solution_types=solution_types or [_st("amr", "flow_cycle"), _st("mobile_picker", "flow_cycle")],
        attribute_defs=attribute_defs or [_attr_def("charge_time_h"), _attr_def("speed_loaded_ms", "м/с")],
    )


def _known(value, source_id: int | None = 1, unit: str | None = "ч") -> AttrValue:
    return AttrValue(status="known", value=value, unit=unit, source_id=source_id)


def test_robot_vendor_step():
    product = _product("amr", {"charge_time_h": _known(1.5)})
    peers = [_product("amr", {"charge_time_h": _known(9.0, source_id=1)}) for _ in range(3)]
    catalog = _catalog(
        [product, *peers],
        sources=[_source(1, "vendor", url="https://ronavi-robotics.ru/catalogue/h1500")],
    )
    norms = [
        _norm("analogue_min_sample", 3, unit="шт"),
        _norm("default.charge_time_h.flow_cycle", 2.0),
    ]
    resolved = Resolver(catalog, norms).robot(product, "charge_time_h")
    assert resolved is not None
    assert resolved.origin == "vendor"
    assert resolved.reliability == "A"
    assert resolved.value == 1.5
    assert resolved.unit == "ч"
    assert resolved.source_id == 1
    assert resolved.source_label == "[A] ronavi-robotics.ru/catalogue/h1500"
    assert "паспорта" in resolved.message


def test_robot_analogue_median_step():
    target = _product("amr", name="target")
    peers = [
        _product("amr", {"charge_time_h": _known(1.0)}),
        _product("amr", {"charge_time_h": _known(2.0)}),
        _product("amr", {"charge_time_h": _known(4.0)}),
        _product("amr", {"charge_time_h": _known(6.0)}),
    ]
    catalog = _catalog(
        [target, *peers],
        sources=[_source(1, "vendor", url="https://example.com/p")],
    )
    norms = [
        _norm("analogue_min_sample", 3, unit="шт"),
        _norm("default.charge_time_h.flow_cycle", 99.0),
    ]
    resolved = Resolver(catalog, norms).robot(target, "charge_time_h")
    assert resolved is not None
    assert resolved.origin == "analogue_median"
    assert resolved.reliability == "C"
    assert resolved.value == 3.0
    assert resolved.source_id is None
    assert resolved.source_label == "[C] медиана по классу amr, 4 позиций"
    assert "4" in resolved.message and "amr" in resolved.message


def test_robot_assumption_norm_step():
    target = _product("amr")
    lone = _product("amr", {"charge_time_h": _known(9.0)})
    catalog = _catalog(
        [target, lone],
        sources=[_source(1, "vendor")],
    )
    norms = [
        _norm("analogue_min_sample", 3, unit="шт"),
        _norm("default.charge_time_h.flow_cycle", 2.0),
        _norm("default.charge_time_h", 99.0),
    ]
    resolved = Resolver(catalog, norms).robot(target, "charge_time_h")
    assert resolved is not None
    assert resolved.origin == "assumption_norm"
    assert resolved.reliability == "D"
    assert resolved.value == 2.0
    assert resolved.source_id == 99
    assert resolved.source_label == "[D] допущение: default.charge_time_h.flow_cycle = 2"
    assert "default.charge_time_h.flow_cycle" in resolved.message


def test_robot_expands_sample_from_type_to_family():
    target = _product("amr", name="target")
    same_type = _product("amr", {"charge_time_h": _known(1.0)})
    family_peers = [
        _product("mobile_picker", {"charge_time_h": _known(2.0)}),
        _product("mobile_picker", {"charge_time_h": _known(3.0)}),
    ]
    catalog = _catalog(
        [target, same_type, *family_peers],
        sources=[_source(1, "vendor")],
    )
    norms = [
        _norm("analogue_min_sample", 3, unit="шт"),
        _norm("default.charge_time_h.flow_cycle", 99.0),
    ]
    resolved = Resolver(catalog, norms).robot(target, "charge_time_h")
    assert resolved is not None
    assert resolved.origin == "analogue_median"
    assert resolved.reliability == "C"
    assert resolved.value == 2.0
    assert resolved.source_label == "[C] медиана по классу flow_cycle, 3 позиций"
    assert "flow_cycle" in resolved.message and "3" in resolved.message


def test_robot_returns_none_when_nothing_found():
    target = _product("amr")
    catalog = _catalog([target])
    resolved = Resolver(catalog, [_norm("analogue_min_sample", 3, unit="шт")]).robot(target, "charge_time_h")
    assert resolved is None
    assert Resolver(catalog, []).reliability_of(target, "charge_time_h") is None


@pytest.mark.parametrize(
    ("kind", "letter"),
    [
        ("vendor", "A"),
        ("dealer", "B"),
        ("media", "B"),
        ("catalog", "B"),
        ("analogue", "C"),
        ("assumption", "D"),
    ],
)
def test_reliability_map_by_kind(kind: str, letter: str):
    product = _product("amr", {"charge_time_h": _known(2.0, source_id=1)})
    catalog = _catalog([product], sources=[_source(1, kind, publisher="Издатель")])
    resolved = Resolver(catalog, []).robot(product, "charge_time_h")
    assert resolved is not None
    assert resolved.reliability == letter
    assert resolved.source_label.startswith(f"[{letter}] ")
    assert Resolver(catalog, []).reliability_of(product, "charge_time_h") == letter


def test_reliability_d_when_source_missing():
    no_id = _product("amr", {"charge_time_h": _known(2.0, source_id=None)})
    unknown_id = _product("amr", {"speed_loaded_ms": _known(1.0, source_id=404, unit="м/с")})
    catalog = _catalog([no_id, unknown_id], sources=[_source(1, "vendor")])
    resolver = Resolver(catalog, [])
    assert resolver.robot(no_id, "charge_time_h").reliability == "D"
    assert resolver.robot(unknown_id, "speed_loaded_ms").reliability == "D"


def test_unknown_status_skips_vendor_step():
    target = _product("amr", {"charge_time_h": AttrValue(status="unknown", value=9.0, unit="ч", source_id=1)})
    catalog = _catalog([target], sources=[_source(1, "vendor")])
    norms = [_norm("analogue_min_sample", 3, unit="шт"), _norm("default.charge_time_h", 2.0)]
    resolved = Resolver(catalog, norms).robot(target, "charge_time_h")
    assert resolved is not None
    assert resolved.origin == "assumption_norm"
    assert resolved.value == 2.0


def test_not_applicable_status_skips_vendor_step():
    target = _product(
        "amr",
        {"charge_time_h": AttrValue(status="not_applicable", value=9.0, unit="ч", source_id=1)},
    )
    catalog = _catalog([target], sources=[_source(1, "vendor")])
    norms = [_norm("analogue_min_sample", 3, unit="шт"), _norm("default.charge_time_h", 2.0)]
    resolved = Resolver(catalog, norms).robot(target, "charge_time_h")
    assert resolved is not None
    assert resolved.origin == "assumption_norm"
    assert resolved.value == 2.0


def test_range_list_takes_midpoint():
    product = _product("amr", {"speed_loaded_ms": _known([1.0, 3.0], unit="м/с")})
    catalog = _catalog([product], sources=[_source(1, "vendor", url="https://example.com/amr")])
    resolved = Resolver(catalog, []).robot(product, "speed_loaded_ms")
    assert resolved is not None
    assert resolved.origin == "vendor"
    assert resolved.value == 2.0
    assert "середин" in resolved.message
    assert "1" in resolved.message and "3" in resolved.message


def test_bool_is_not_a_number():
    product = _product("amr", {"has_lidar": AttrValue(status="known", value=True, source_id=1)})
    catalog = _catalog([product], sources=[_source(1, "vendor")])
    assert Resolver(catalog, []).robot(product, "has_lidar") is None


def test_site_uses_provided_value():
    catalog = _catalog([])
    norms = [_norm("default.site.shift_hours.airport", 24, unit="ч")]
    resolved = Resolver(catalog, norms).site("shift_hours", 11, "warehouse")
    assert resolved is not None
    assert resolved.origin == "vendor"
    assert resolved.reliability == "B"
    assert resolved.value == 11
    assert resolved.source_id is None
    assert resolved.source_label == "[B] датасет площадки"
    assert "датасет" in resolved.message


def test_site_default_by_object_type():
    catalog = _catalog([])
    norms = [
        _norm("default.site.shift_hours.airport", 24, unit="ч"),
        _norm("default.site.shift_hours", 11, unit="ч"),
    ]
    resolved = Resolver(catalog, norms).site("shift_hours", None, "airport")
    assert resolved is not None
    assert resolved.origin == "assumption_norm"
    assert resolved.reliability == "D"
    assert resolved.value == 24
    assert resolved.source_label == "[D] допущение: default.site.shift_hours.airport = 24"


def test_site_default_without_object_type():
    catalog = _catalog([])
    norms = [
        _norm("default.site.shift_hours.airport", 24, unit="ч"),
        _norm("default.site.shift_hours", 11, unit="ч"),
    ]
    resolved = Resolver(catalog, norms).site("shift_hours", None, "warehouse")
    assert resolved is not None
    assert resolved.origin == "assumption_norm"
    assert resolved.reliability == "D"
    assert resolved.value == 11
    assert resolved.source_label == "[D] допущение: default.site.shift_hours = 11"


def test_norm_lookup_and_string_number():
    product = _product("amr", {"charge_time_h": _known("1 500,5")})
    catalog = _catalog([product], sources=[_source(1, "catalog", publisher="Каталог")])
    norms = [_norm("k_util", 0.82, unit="доля"), _norm("analogue_min_sample", 3, unit="шт")]
    resolver = Resolver(catalog, norms)
    assert resolver.norm("k_util") == 0.82
    assert resolver.norm("missing") is None
    resolved = resolver.robot(product, "charge_time_h")
    assert resolved is not None
    assert resolved.value == 1500.5
    assert resolved.reliability == "B"
