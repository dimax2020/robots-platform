import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.import_robots import MAPPING, additions, load_rows, map_row, names_match


def test_mapping_and_units():
    columns, attrs, skipped = map_row({"specs": {
        "Общие характеристики": {"Бренд": "Fanuc", "Страна производства": "Япония"},
        "Питание": {"Потребляемая мощность, кВт": "0,25"},
        "Основные характеристики": {"Минимальная ширина проезда, мм": "1400"},
    }})
    assert columns == {"manufacturer": "Fanuc", "country": "Япония"}
    assert attrs["power_watt"]["value"] == 250
    assert attrs["min_aisle_width_m"]["value"] == pytest.approx(1.4)
    assert not skipped


def test_preserve_existing_values_and_idempotence():
    product = SimpleNamespace(manufacturer="Existing", country=" ", attrs={
        "mass_kg": {"status": "unknown", "value": None},
        "axes": {}, "payload_kg": None,
    })
    incoming = {k: {"value": 10} for k in ["mass_kg", "axes", "payload_kg", "reach_mm"]}
    columns, attrs = additions(product, {"manufacturer": "New", "country": "Россия"}, incoming)
    assert columns == {"country": "Россия"}
    assert list(attrs) == ["reach_mm"]
    product.country = columns["country"]
    product.attrs = {**product.attrs, **attrs}
    assert additions(product, columns, incoming) == ({}, {})
    assert product.attrs["mass_kg"] == {"status": "unknown", "value": None}


@pytest.mark.parametrize("value", ["10-20", "до 10", "10 кг", "NaN", "Infinity"])
def test_ambiguous_numbers_are_reported(value):
    _, attrs, skipped = map_row({"specs": {"Основные характеристики": {"Вес, кг": value}}})
    assert not attrs
    assert skipped


def test_mapping_agrees_with_catalog_and_all_input_rows():
    root = Path(__file__).resolve().parents[3]
    schema = {a["key"]: a for a in json.loads((root / "data/attributes.json").read_text())["attributes"]}
    for key, datatype, unit, _ in MAPPING.values():
        assert (schema[key]["datatype"], schema[key].get("unit")) == (datatype, unit)
    path = root / "robots.json"
    if path.exists():
        for row in load_rows(path):
            map_row(row)


def test_invalid_input_fails_before_database(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('[{"name":"Robot","specs":{"section":[]}}]')
    with pytest.raises(ValueError):
        load_rows(path)


@pytest.mark.parametrize("existing", [None, "", "  ", "https://example.org/old.png"])
def test_png_url_only_fills_empty_column(existing):
    columns, attrs, skipped = map_row({"png_url": " https://example.org/new.png "})
    assert columns == {"png_url": "https://example.org/new.png"}
    assert not skipped
    product = SimpleNamespace(png_url=existing, attrs={})
    changed, _ = additions(product, columns, attrs)
    assert changed == ({} if existing == "https://example.org/old.png" else columns)


@pytest.mark.parametrize("value", [None, "", "   "])
def test_empty_png_url_is_ignored(value):
    assert map_row({"png_url": value}) == ({}, {}, [])


@pytest.mark.parametrize(("left", "right"), [
    ("Ronavi H1500", "Ronavi H1500 (грузоподъемность до 1 500 кг)"),
    ("AK-2000-2", "AUTOMACON AK-2000-2"),
    ("БРО 2.1", "168robotics BRO 2.1"),
    ("БРО 3.0", "168robotics BRO 3.0"),
    ("Ортез-1", "Ортез-1"),
])
def test_names_match_when_one_phrase_contains_the_other(left, right):
    assert names_match(left, right)
    assert names_match(right, left)


@pytest.mark.parametrize(("left", "right"), [
    ("Клинботикс 400 PRO", "Waybot Cleanbotics 400 PRO"),
    ("Unit", "Unitree A2"),
    ("AMR 100", "AUTOMACON AK-100"),
    ("Ronavi H1500", "Ronavi H2000"),
])
def test_names_do_not_match_lookalikes(left, right):
    assert not names_match(left, right)
