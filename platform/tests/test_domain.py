from app.application.assign_processes import classify
from app.domain.csv_parse import parse_catalog_csv, parse_manual_csv, parse_price
from app.domain.specs import expand_known_specs
from app.domain.match import FilterRule, RobotView, match_robots
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
        {"proizvoditelnost": "1 200 м²/ч (макс), 700 м²/ч (при высоком трафике)"},
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


def test_moscow_html_keeps_only_priced():
    html = r'''<script>self.__next_f.push([1,"{\"rows\":[{\"id\":\"a\",\"name\":\"Дешевый\",\"slug\":\"cheap\",\"maker\":\"M\",\"country\":\"Китай\",\"description\":\"Описание\",\"image\":\"/img.webp\",\"categoryName\":\"Уборка\",\"categorySlug\":\"u\",\"industries\":[\"Логистика\"],\"priceValue\":100,\"offersCount\":1,\"featured\":false,\"isNew\":false},{\"id\":\"b\",\"name\":\"Без цены\",\"slug\":\"free\",\"maker\":\"M\",\"country\":\"Китай\",\"description\":\"\",\"image\":\"\",\"categoryName\":\"Уборка\",\"categorySlug\":\"u\",\"industries\":[],\"priceValue\":null,\"offersCount\":1,\"featured\":false,\"isNew\":false}]}"])</script>'''
    records = records_from_html(html)
    assert len(records) == 1
    assert records[0].name == "Дешевый"
    assert records[0].price_rub == 100
    assert records[0].source_publisher == "robot.moscow"
    assert records[0].parser_code == "robot_moscow"
