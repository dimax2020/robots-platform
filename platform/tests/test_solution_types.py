import json
from pathlib import Path

from app.domain.solution_types import canon, classify, raw_key, read_mapping

MAPPING = read_mapping(json.loads((Path(__file__).resolve().parents[1] / "seed" / "solution_types.json").read_text(encoding="utf-8")))


def test_canon_glues_spelling_variants() -> None:
    assert canon(" Робот-Штабелёр ") == canon("робот штабелер")


def test_pair_from_catalog_columns() -> None:
    code = classify(MAPPING, {}, robot_class="Мобильные роботы", subtype="AMR", system_class="brs")
    assert code == "amr"


def test_empty_pair_falls_back_by_system_class() -> None:
    assert classify(MAPPING, {}, robot_class="", subtype="", system_class="bas") == "bas_unspecified"


def test_unknown_parser_category_stays_untyped_until_rule() -> None:
    kwargs = {"robot_class": "Уборочные роботы", "subtype": "", "system_class": ""}
    assert classify(MAPPING, {}, **kwargs) is None
    rules = {raw_key("Уборочные роботы", "", ""): "cleaning_robot"}
    assert classify(MAPPING, rules, **kwargs) == "cleaning_robot"


def test_bas_pairs_without_type_get_bas_group() -> None:
    groups = {spec.code: spec.group for spec in MAPPING.types}
    assert groups["uav_vtol"] == "БАС"
    assert groups["bas_unspecified"] == "Тип не уточнён"
