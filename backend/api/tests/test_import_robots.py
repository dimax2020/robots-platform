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


def test_robort_flat_specs_and_price():
    columns, attrs, skipped = map_row({
        "url": "https://robort.ru/product/test/", "price": 2257600,
        "png_url": "https://robort.ru/image.png",
        "specs": {"Вес": "85 кг", "Время зарядки": "90 мин",
                  "Минимальная ширина проезда": "70 см", "Мощность, л.с.": "0,35 кВт"},
    })
    assert columns["png_url"] == "https://robort.ru/image.png"
    assert {k: v["value"] for k, v in attrs.items()} == {
        "mass_kg": 85, "charge_time_h": 1.5, "min_aisle_width_m": pytest.approx(.7),
        "power_watt": 350, "price_rub": 2257600,
    }
    assert all(v["extracted_by"] == "robort_robots.json / robort" for v in attrs.values())
    assert not skipped


@pytest.mark.parametrize("label,value", [
    ("Вес", "до 85 кг"), ("Время работы", "5~10 ч"),
    ("Мощность, л.с.", "192"), ("Мощность, л.с.", "2 л.с."),
    ("Минимальная ширина проезда", "70"),
    ("Максимальная скорость", "1.2 м/с"),
])
def test_robort_does_not_guess_units_or_meaning(label, value):
    _, attrs, skipped = map_row({"specs": {label: value}})
    assert not attrs
    assert skipped


def test_robort_fixture():
    path = Path(__file__).resolve().parents[3] / "robort_robots.json"
    if not path.exists():
        pytest.skip("Локальная выгрузка отсутствует")
    rows = load_rows(path)
    assert rows
    for row in rows:
        map_row(row)


def test_robort_solution_types_exist():
    from scripts.import_robots import robort_solution_code
    root = Path(__file__).resolve().parents[3]
    codes = {s['code'] for s in json.loads((root / 'data/catalog_normalized.json').read_text())['solution_types']}
    assert robort_solution_code({'name': 'Новый робот'}) in codes
    path = root / 'robort_robots.json'
    if path.exists():
        assert all(robort_solution_code(r) in codes for r in load_rows(path))


@pytest.mark.parametrize('price', [None, 0, -1, True, 'по запросу'])
def test_no_creation_without_positive_price(price):
    from unittest.mock import MagicMock
    from scripts.import_robots import import_rows
    db = MagicMock()
    db.scalars.return_value.all.return_value = []
    report = import_rows(db, [{'name': 'New', 'url': 'https://robort.ru/product/new/', 'price': price}])
    assert report[0]['status'] == 'not_found'
    db.add.assert_not_called()


@pytest.mark.parametrize('dry_run', [False, True])
def test_create_robot_with_price_and_source(dry_run):
    from unittest.mock import MagicMock
    from api.db.models import Product, Source, CatalogVersion
    from scripts.import_robots import import_rows
    db = MagicMock()
    db.scalars.side_effect = [
        [SimpleNamespace(key='price_rub', datatype='number', unit='₽')],
        SimpleNamespace(all=lambda: []),
    ]
    db.scalar.side_effect = [SimpleNamespace(id=7), None, None]
    added = []
    def add(obj):
        if isinstance(obj, (Source, CatalogVersion)):
            obj.id = 42
        added.append(obj)
    db.add.side_effect = add
    report = import_rows(db, [{'name': 'New', 'url': 'https://robort.ru/product/new/', 'price': 100}], dry_run=dry_run)
    assert report[0]['status'] == 'created'
    product = next(obj for obj in added if isinstance(obj, Product))
    assert product.attrs['price_rub']['value'] == 100
    assert product.attrs['price_rub']['source_id'] == 42
    assert product.valid_from == 42
    assert product.solution_type_id == 7
    assert product.manufacturer == 'Не указан'
    (db.rollback if dry_run else db.commit).assert_called_once()
    (db.commit if dry_run else db.rollback).assert_not_called()


def test_same_url_with_changed_name_updates_instead_of_creating():
    from unittest.mock import MagicMock
    from scripts.import_robots import import_rows
    db = MagicMock()
    db.scalars.side_effect = [
        [SimpleNamespace(key='price_rub', datatype='number', unit='₽')],
        SimpleNamespace(all=lambda: []),
    ]
    existing = SimpleNamespace(id='existing', name='Old', valid_to=None, attrs={'price_rub': {'value': 200}})
    db.scalar.side_effect = [SimpleNamespace(id=7), existing]
    report = import_rows(db, [{'name': 'New', 'url': 'https://robort.ru/product/new/', 'price': 100}])
    assert report[0]['status'] == 'unchanged'
    assert existing.attrs['price_rub']['value'] == 200
    db.add.assert_not_called()


def test_ambiguous_match_does_not_create():
    from unittest.mock import MagicMock
    from scripts.import_robots import import_rows
    db = MagicMock()
    db.scalars.return_value.all.return_value = [
        SimpleNamespace(name="New robot one"),
        SimpleNamespace(name="New robot two"),
    ]
    report = import_rows(db, [{'name': 'New robot', 'url': 'https://robort.ru/product/new/', 'price': 100}])
    assert report[0]['status'] == 'ambiguous'
    db.add.assert_not_called()
