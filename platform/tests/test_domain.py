import pytest

from app.application.assign_processes import classify
from app.domain.csv_parse import parse_catalog_csv, parse_manual_csv, parse_price
from app.domain.specs import expand_known_specs
from app.domain.match import FilterRule, Readiness, RobotView, match_robots
from app.parsers.robot_moscow import records_from_html, specs_from_html


def test_classify_cleaner_and_forklift():
    assert "floor_cleaning" in classify("Уборочные роботы Cleanbotics поломоечная", None)
    assert "pallet_transport" in classify("AMR Ronavi H1500 паллет", 1500)
    assert classify("Беспилотный трактор агро", None) == set()


def test_parser_spec_becomes_payload():
    attrs, labels = expand_known_specs(
        {"gruzopodemnost_maksimalnaya": "600 кг", "minimalnaya_shirina_proezda": "70 см"},
        {"gruzopodemnost_maksimalnaya": "Грузоподъемность (максимальная)", "minimalnaya_shirina_proezda": "Минимальная ширина проезда"},
    )
    assert attrs["payload_kg"] == "600"
    assert attrs["min_aisle_width_m"] == "0.7"
    assert labels["payload_kg"] == "Грузоподъёмность"


def test_water_tank_is_not_payload():
    attrs, _labels = expand_known_specs(
        {"gruzopodemnost": "Бак для воды 60 л"},
        {"gruzopodemnost": "Грузоподъёмность"},
    )
    assert "payload_kg" not in attrs


def test_price_with_spaces_and_comma():
    assert parse_price("2 700 000,00") == 2700000


def test_catalog_groups_rows_and_keeps_every_column():
    text = (
        "id;Название;тип;статус;компания;описание;Тип;Подтип;Сценарий;Кейсы;УГТ;Рын Потенциал;Регион;Отрасль;Цена изделия\n"
        "5760e938-9a43-45a7-b8e8-f4f2e6383930;Ronavi H1500;brs;operation;Ронави;Описание;Мобильные роботы;AMR;Логистика;Кейс;8;4;Москва;Торговля;2 700 000,00\n"
        "5760e938-9a43-45a7-b8e8-f4f2e6383930;Ronavi H1500;brs;operation;Ронави;Описание;Мобильные роботы;AMR;Сортировка;Второй;8;4;Москва;Торговля;2 700 000,00\n"
    )
    records = parse_catalog_csv(text)
    assert len(records) == 1
    assert records[0].name == "Ronavi H1500"
    assert records[0].price_rub == 2700000
    assert "Сортировка" in records[0].attributes["scenario"]
    assert records[0].raw["rows"][0]["Подтип"] == "AMR"
    assert records[0].source_publisher == "ФЦ БАС"


def test_manual_overlay_keeps_source_url():
    text = "product_slug,product_name,attr_key,value,status,source_kind,source_url,quote\nak,AK,payload_kg,2000,known,vendor,https://robot.automacon.ru/agv,груз\n"
    rows = parse_manual_csv(text)
    assert rows[0].source_url == "https://robot.automacon.ru/agv"
    assert rows[0].attr_key == "payload_kg"


def test_formula_filter_uses_object_binding():
    rules = (FilterRule("Проезд", (), (), "formula", "hard", (("aisle", "Ширина проезда"),), "min_aisle_width_m <= aisle"),)
    hits = match_robots(
        process_code="pallet_transport",
        process_name="Перевозка паллет",
        site={"aisle_width_m": 2.8},
        rules=rules,
        bindings={"aisle": "aisle_width_m"},
        robots=(
            RobotView("1", "Узкий", "narrow", {"min_aisle_width_m": 1.2}),
            RobotView("2", "Широкий", "wide", {"min_aisle_width_m": 3.4}),
        ),
    )
    by_name = {hit.name: hit.verdict for hit in hits}
    assert by_name["Узкий"] == "pass"
    assert by_name["Широкий"] == "fail"


def test_readiness_moves_immature_robots_to_review():
    rules = (FilterRule("Проезд", (), (), "formula", "hard", (("aisle", "Ширина проезда"),), "min_aisle_width_m <= aisle"),)
    hits = match_robots(
        process_code="pallet_transport",
        process_name="Перевозка паллет",
        site={"aisle_width_m": 2.8},
        rules=rules,
        bindings={"aisle": "aisle_width_m"},
        readiness=Readiness(min_trl=6, review_stages=("rnd",)),
        robots=(
            RobotView("1", "Серийный", "serial", {"min_aisle_width_m": 1.2}, trl=8, stage="operation"),
            RobotView("2", "Низкий УГТ", "low", {"min_aisle_width_m": 1.2}, trl=4, stage="piloting"),
            RobotView("3", "Разработка", "rnd", {"min_aisle_width_m": 1.2}, trl=7, stage="rnd"),
            RobotView("4", "Без УГТ", "bare", {"min_aisle_width_m": 1.2}),
            RobotView("5", "Широкий", "wide", {"min_aisle_width_m": 3.4}, trl=4, stage="rnd"),
        ),
    )
    by_name = {hit.name: hit for hit in hits}
    assert by_name["Серийный"].verdict == "pass"
    assert by_name["Низкий УГТ"].verdict == "unknown"
    assert by_name["Низкий УГТ"].notes[0] == "Готовность: УГТ 4 ниже порога 6"
    assert by_name["Разработка"].verdict == "unknown"
    assert by_name["Без УГТ"].verdict == "pass"
    assert by_name["Широкий"].verdict == "fail"
    assert by_name["Разработка"].stage == "rnd" and by_name["Серийный"].trl == 8

    off = match_robots(
        process_code="p", process_name="P", site={}, rules=(),
        readiness=Readiness(enabled=False),
        robots=(RobotView("1", "Разработка", "rnd", {}, trl=3, stage="rnd"),),
    )
    assert off[0].verdict == "pass"
    strict = Readiness.from_value({"min_trl": 12, "review_stages": ["rnd", "moon"], "review_missing_trl": True})
    assert strict.min_trl == 9 and strict.review_stages == ("rnd",)
    assert strict.notes(None, None) == ["Готовность: УГТ не указан"]


def test_number_inside_text_with_unit():
    from app.domain.formula import build_env, evaluate

    status, env, _detail = build_env(
        "robot.proizvoditelnost >= area",
        {"area"},
        {"area": "clean_area_m2"},
        {"clean_area_m2": 1000},
        {"proizvoditelnost": "1 200 м²/ч (макс)"},
    )
    assert status == "ok"
    assert evaluate("robot.proizvoditelnost >= area", env) is True


def test_mode_count_in_a_sentence_is_not_productivity():
    from app.domain.formula import build_env

    status, _env, detail = build_env(
        "area / robot.proizvoditelnost",
        {"area"},
        {"area": "clean_area_m2"},
        {"clean_area_m2": 10000},
        {"proizvoditelnost": "4 режима (всасывание, подметание, мойка, протирка)"},
    )
    assert status == "bad"
    assert detail == "proizvoditelnost"


_BARE = {
    "infra_pct": 0, "software_pct": 0, "integration_pct": 0, "commissioning_pct": 0, "training_pct": 0, "reserve_pct": 0,
    "service_pct": 0, "license_pct": 0, "energy_kwh": 0, "replacement_pct": 100, "raas_rate_pct": 2,
}


def _scenario(result, key):
    return next(item for item in result["scenarios"] if item["key"] == key)


def test_economy_skips_missing_price_and_uses_one_robot_without_count():
    from app.domain.economy import DISCLAIMER, NO_COUNT, NO_PRICE, calculate

    result = calculate(
        [
            {"process_code": "a", "process_name": "Паллеты", "product_id": "1", "name": "С ценой", "price_rub": 100_000, "count": 2},
            {"process_code": "b", "process_name": "Мойка", "product_id": "2", "name": "Без количества", "price_rub": 50_000, "count": None},
            {"process_code": "c", "process_name": "Фасад", "product_id": "3", "name": "Без цены", "price_rub": None, "count": 4},
        ],
        {"pickers_count": 2, "picker_salary_month_rub": 10_000, "payroll_burden": 1},
        standard=_BARE,
    )
    assert result["disclaimer"] == DISCLAIMER
    by_name = {row["name"]: row for row in result["fleet"]}
    assert by_name["Без цены"]["included"] is False
    assert by_name["Без цены"]["note"] == NO_PRICE
    assert by_name["Без цены"]["cost_rub"] is None
    assert by_name["Без количества"]["count_used"] == 1
    assert by_name["Без количества"]["note"] == NO_COUNT
    assert by_name["Без количества"]["cost_rub"] == 50_000

    buy = _scenario(result, "purchase")
    assert buy["capex"]["value"] == 250_000
    assert buy["opex"]["value"] == pytest.approx(7_000)
    assert result["payroll"]["value"] == 240_000
    assert buy["effect"]["value"] == pytest.approx(233_000)
    assert result["horizon_years"] == 5
    assert buy["payback"]["value"] == pytest.approx(250_000 / 233_000)
    assert buy["roi"]["value"] == pytest.approx(466)
    assert buy["tco"]["value"] == pytest.approx(250_000 + 7_000 * 5)

    base = _scenario(result, "asis")
    assert base["tco"]["value"] == 240_000 * 5
    assert base["years"][0]["cost_rub"] == 240_000

    rent = _scenario(result, "raas")
    assert rent["capex"]["value"] == 0
    assert rent["opex"]["value"] == pytest.approx(250_000 * 0.02 * 12 + 250_000 * 0.003)
    assert rent["payback"]["value"] is None


def test_economy_standard_capex_extras_opex_and_rent():
    from app.domain.economy import calculate

    result = calculate(
        [{"process_code": "a", "process_name": "A", "name": "A", "price_rub": 1_000_000, "count": 10}],
        {
            "pickers_count": 10, "picker_salary_month_rub": 100_000, "forklift_salary_month_rub": 100_000, "payroll_burden": 1,
            "shift_hours": 8, "shifts_per_day": 2, "days_year": 250,
        },
    )
    buy = _scenario(result, "purchase")
    subtotal = 10_000_000 * (1 + 0.115 + 0.091 + 0.137 + 0.064 + 0.017)
    capex = subtotal * 1.06
    energy = 10 * 0.9 * 4_000 * 7.2
    opex = 10_000_000 * (0.08 + 0.049 + 0.003 + 0.01 + 0.015) + energy + 1_200_000
    saving = 12_000_000 * 0.63
    assert buy["capex"]["value"] == pytest.approx(capex)
    assert buy["opex"]["value"] == pytest.approx(opex)
    assert buy["payroll_after"]["value"] == pytest.approx(12_000_000 * 0.37)
    assert buy["effect"]["value"] == pytest.approx(saving - opex)
    assert buy["payback"]["value"] == pytest.approx(capex / (saving - opex))

    rent = _scenario(result, "raas")
    rent_capex = 10_000_000 * (0.115 + 0.137 + 0.064 + 0.017) * 1.06
    rent_opex = 10_000_000 * 0.022 * 12 + energy + 10_000_000 * 0.003 + 1_200_000
    assert rent["capex"]["value"] == pytest.approx(rent_capex)
    assert rent["opex"]["value"] == pytest.approx(rent_opex)
    assert rent["payback"]["value"] == pytest.approx(rent_capex / (saving - rent_opex))
    assert all(item["tex"] for item in buy["capex_lines"] + buy["opex_lines"])
    assert result["sensitivity"]


def test_economy_project_value_beats_standard_and_site_beats_norm():
    from app.domain.economy import calculate

    result = calculate(
        [{"process_code": "a", "process_name": "A", "name": "A", "price_rub": 10, "count": 1}],
        {"payback_years": 7, "energy_tariff_rub_kwh": 9},
        standard={"service_pct": 5},
        overrides={"service_pct": 12},
    )
    params = {item["key"]: item for item in result["params"]}
    assert params["service_pct"]["value"] == 12
    assert params["service_pct"]["standard"] == 5
    assert params["service_pct"]["source"] == "project"
    assert params["energy_tariff"]["value"] == 9
    assert params["energy_tariff"]["source"] == "site"
    assert result["horizon_years"] == 7
    assert _scenario(result, "purchase")["payback"]["value"] is None


def test_economy_payroll_falls_back_to_task_staff():
    from app.domain.economy import calculate

    result = calculate(
        [{"process_code": "a", "process_name": "A", "name": "A", "price_rub": 10, "count": 1}],
        {"staff_salary_year_rub": 1_000_000},
        tasks=[{"staff_fte_now": 20}, {"staff_fte_now": None}],
    )
    assert result["payroll"]["value"] == 20_000_000


def test_economy_load_scales_only_daily_flows():
    from app.domain.economy import scale_load

    site = scale_load({"inbound_pallets_per_day": 1000, "pick_lines_per_day": 10, "area_m2": 500}, 150)
    assert site == {"inbound_pallets_per_day": 1500, "pick_lines_per_day": 15, "area_m2": 500}


def test_layout_items_defaults_and_cleanup():
    from app.domain.layout_items import DEFAULT_ITEMS, clean_items, default_items

    pallets = default_items("pallet_transport")
    assert [row["role"] for row in pallets] == ["pickup", "dropoff", "charge"]
    assert pallets[0]["label"] == "Приёмка"
    assert default_items("unknown_process") == []
    assert all(rows for rows in DEFAULT_ITEMS.values())

    cleaned = clean_items([
        {"key": "a", "label": "Точка", "role": "pickup", "min_count": "3"},
        {"key": "a", "label": "Дубль", "role": "pickup"},
        {"key": "b", "label": "Зона", "role": "work_zone"},
        {"key": "c", "label": "Плохая роль", "role": "teleport"},
        {"key": "", "label": "Без ключа", "role": "charge"},
    ])
    assert [row["key"] for row in cleaned] == ["a", "b"]
    assert cleaned[0]["min_count"] == 3
    assert cleaned[1]["shape"] == "area"


def test_pallet_fleet_uses_speed_and_daily_flow():
    from app.domain.match import robot_count

    formula = (
        "ceil(((inbound_pallets_per_day + outbound_pallets_per_day) / (shift_hours * shifts_per_day)) "
        "/ (3600 / (2 * picker_route_m / robot.speed_loaded_ms + 80) * 0.82)) + 1"
    )
    inputs = (
        ("inbound_pallets_per_day", "Приёмка"),
        ("outbound_pallets_per_day", "Отгрузка"),
        ("shift_hours", "Смена"),
        ("shifts_per_day", "Смен"),
        ("picker_route_m", "Маршрут"),
    )
    bindings = {key: key for key, _label in inputs}
    site = {
        "inbound_pallets_per_day": 1000,
        "outbound_pallets_per_day": 1000,
        "shift_hours": 11,
        "shifts_per_day": 2,
        "picker_route_m": 25,
    }
    amount, note = robot_count(formula, inputs, bindings, site, {"speed_loaded_ms": 2})
    assert note == ""
    assert amount == 5

    missing, missing_note = robot_count(formula, inputs, bindings, site, {})
    assert missing is None
    assert "Скорость с грузом" in missing_note


def test_floor_wash_count_uses_rate_and_shift():
    from app.domain.match import robot_count

    amount, note = robot_count(
        "ceil(clean_area_m2 / robot.proizvoditelnost / shift_hours)",
        (("clean_area_m2", "Площадь"), ("shift_hours", "Смена")),
        {"clean_area_m2": "clean_area_m2", "shift_hours": "shift_hours"},
        {"clean_area_m2": 10000, "shift_hours": 11},
        {"proizvoditelnost": "1 200 м²/ч (макс)"},
    )
    assert note == ""
    assert amount == 1

    empty, empty_note = robot_count(
        "ceil(clean_area_m2 / robot.proizvoditelnost / shift_hours)",
        (("clean_area_m2", "Площадь"), ("shift_hours", "Смена")),
        {"clean_area_m2": "clean_area_m2", "shift_hours": "shift_hours"},
        {"clean_area_m2": 10000, "shift_hours": 11},
        {"proizvoditelnost": "компактная мойка малых площадей"},
    )
    assert empty is None
    assert "не число" in empty_note


def test_formula_count_rounds_up_with_ceil():
    from app.domain.match import robot_count

    amount, note = robot_count(
        "ceil(flow / payload_kg)",
        (("flow", "Поток"),),
        {"flow": "inbound_pallets_per_day"},
        {"inbound_pallets_per_day": 1000},
        {"payload_kg": 300},
    )
    assert note == ""
    assert amount == 4


def test_match_fail_unknown_and_conditional():
    rules = (
        FilterRule("Груз", ("pallet_mass_kg",), ("payload_kg",), ">=", "hard"),
        FilterRule("Проезд", ("aisle_width_m",), ("min_aisle_width_m",), "<=", "hard"),
        FilterRule("Пол", ("floor_type",), ("floor_type",), "==", "conditional"),
    )
    site = {"pallet_mass_kg": 800, "aisle_width_m": 2.8, "floor_type": "бетон"}
    hits = match_robots(
        process_code="floor_washing",
        process_name="Мойка полов",
        site=site,
        rules=rules,
        robots=(
            RobotView("1", "Легкий", "light", {"payload_kg": 100, "min_aisle_width_m": 1, "floor_type": "бетон"}),
            RobotView("2", "Тяжелый", "heavy", {"payload_kg": 1500, "min_aisle_width_m": 1.2, "floor_type": "эпоксид"}),
            RobotView("3", "Без ширины", "gap", {"payload_kg": 900, "floor_type": "бетон"}),
        ),
    )
    by_name = {hit.name: hit.verdict for hit in hits}
    assert by_name["Легкий"] == "fail"
    assert by_name["Тяжелый"] == "conditional"
    assert by_name["Без ширины"] == "unknown"


def test_missing_site_value_does_not_reject():
    rules = (FilterRule("Проезд", ("aisle_width_m",), ("min_aisle_width_m",), "<=", "hard"),)
    hits = match_robots(
        process_code="x",
        process_name="X",
        site={},
        rules=rules,
        robots=(RobotView("1", "A", "a", {}),),
    )
    assert hits[0].verdict == "pass"


def test_moscow_spec_grid():
    html = '<div class="rd-specgrid"><div>Время работы 4 часа</div></div>'
    # stripped strings need separate text nodes
    html = '<div class="rd-specgrid"><div><span>Время работы</span><span>4 часа</span></div></div>'
    assert specs_from_html(html) == {"Время работы": "4 часа"}


def test_missing_site_limit_skips_even_if_robot_spec_is_first():
    from app.domain.formula import build_env

    status, _env, detail = build_env(
        "robot.min_aisle_width_m <= aisle",
        {"aisle"},
        {"aisle": "aisle_width_m"},
        {},
        {},
    )
    assert status == "skip"
    assert detail == "aisle"


def test_task_volume_replaces_hardcoded_airport_formula_only():
    from app.domain.match import count_site, formula_with_task

    formula = "ceil((420 / (shift_hours * shifts_per_day)) / (3600 / (584 / robot.speed_loaded_ms + 80) * 0.82)) + 1"
    changed = formula_with_task(formula, {"flow_per_day": 800, "route_len_m": 100})
    assert changed.startswith("ceil((800 /")
    assert "200 / robot.speed_loaded_ms" in changed

    warehouse = (
        "ceil(((inbound_pallets_per_day + outbound_pallets_per_day) / (shift_hours * shifts_per_day)) "
        "/ (3600 / (2 * picker_route_m / robot.speed_loaded_ms + 80) * 0.82)) + 1"
    )
    assert formula_with_task(warehouse, {"flow_per_day": 10, "route_len_m": 5}) == warehouse
    assert count_site({"area_m2": 45000})["clean_area_m2"] == 22500
    assert count_site({"area_m2": 85000, "clean_area_m2": 51000})["clean_area_m2"] == 51000


def test_unknown_best_is_used_only_as_fallback():
    from app.domain.match import MatchHit
    from app.infrastructure.db.taxonomy_repo import _best

    def hit(pid, verdict):
        return MatchHit(pid, pid, pid, "p", "P", verdict, ())

    attrs = {"priced": {"price_rub": 100}, "other": {"price_rub": 50}}
    counted = [(hit("priced", "unknown"), 3.0, ""), (hit("other", "unknown"), None, "параметр объекта не задан")]
    assert _best(counted, attrs, "payload_kg", "desc") is None
    assert _best(counted, attrs, "payload_kg", "desc", fallback_unknown=True) == "priced"
    passed = [(hit("priced", "pass"), 1.0, ""), (hit("other", "unknown"), 9.0, "")]
    assert _best(passed, attrs, "", "asc", fallback_unknown=True) == "priced"


def test_airport_staff_gives_a_payback():
    from app.domain.economy import calculate, scale_task_flows

    result = calculate(
        [{"process_code": "baggage_transport", "process_name": "Багаж", "name": "Тягач", "price_rub": 4_000_000, "count": 3}],
        {"staff_salary_year_rub": 1_365_538, "shift_hours": 24, "shifts_per_day": 1, "days_year": 365},
        tasks=[
            {"process_code": "baggage_transport", "staff_fte_now": 320},
            {"process_code": "passenger_service", "staff_fte_now": 180},
        ],
    )
    # 180 человек терминала не в парке: их ФОТ в эффект не входит.
    assert result["payroll"]["value"] == pytest.approx(320 * 1_365_538)
    purchase = _scenario(result, "purchase")
    assert purchase["effect"]["value"] > 0
    assert purchase["payback"]["value"] is not None
    scaled = scale_task_flows([{"flow_per_day": 420, "staff_fte_now": 320}], 150)
    assert scaled[0]["flow_per_day"] == 630
    assert scaled[0]["staff_fte_now"] == 320


def test_moscow_html_keeps_only_priced():
    html = r'''<script>self.__next_f.push([1,"{\"rows\":[{\"id\":\"a\",\"name\":\"Дешевый\",\"slug\":\"cheap\",\"maker\":\"M\",\"country\":\"Китай\",\"description\":\"Описание\",\"image\":\"/img.webp\",\"categoryName\":\"Уборка\",\"categorySlug\":\"u\",\"industries\":[\"Логистика\"],\"priceValue\":100,\"offersCount\":1,\"featured\":false,\"isNew\":false},{\"id\":\"b\",\"name\":\"Без цены\",\"slug\":\"free\",\"maker\":\"M\",\"country\":\"Китай\",\"description\":\"\",\"image\":\"\",\"categoryName\":\"Уборка\",\"categorySlug\":\"u\",\"industries\":[],\"priceValue\":null,\"offersCount\":1,\"featured\":false,\"isNew\":false}]}"])</script>'''
    records = records_from_html(html)
    assert len(records) == 1
    assert records[0].name == "Дешевый"
    assert records[0].price_rub == 100
    assert records[0].source_publisher == "robot.moscow"
    assert records[0].parser_code == "robot_moscow"
