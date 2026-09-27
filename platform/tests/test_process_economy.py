import pytest

from app.domain.economy import NORMS, calculate, clamp_overrides

_QUIET = {norm.key: 0.0 for norm in NORMS}
_QUIET.update({
    "replacement_pct": 100,
    "price_factor": 100,
    "salary_factor": 100,
    "horizon_years": 5,
    "robots_per_operator": 50,
    "energy_kwh": 0,
    "energy_tariff": 7.2,
    "raas_rate_pct": 2,
})


def _buy(result):
    return next(item for item in result["scenarios"] if item["key"] == "purchase")


def _process(result, code):
    return next(item for item in result["processes"] if item["process_code"] == code)


def _purchase_of(process):
    return next(item for item in process["scenarios"] if item["key"] == "purchase")


_SITE = {"pickers_count": 10, "picker_salary_month_rub": 100_000, "payroll_burden": 1}


def test_single_process_matches_fleet():
    result = calculate(
        [{"process_code": "a", "process_name": "Паллеты", "name": "A", "price_rub": 1_000_000, "count": 2}],
        _SITE,
        standard=_QUIET,
    )
    fleet = _buy(result)
    process = _process(result, "a")
    assert process["share"] == 1
    assert process["profitable"] is True
    own = _purchase_of(process)
    assert own["effect"]["value"] == fleet["effect"]["value"]
    assert own["capex"]["value"] == fleet["capex"]["value"]
    assert own["payback"]["value"] == fleet["payback"]["value"]


def test_equal_share_marks_expensive_process_and_suggests_price():
    standard = dict(_QUIET)
    standard["horizon_years"] = 3
    result = calculate(
        [
            {"process_code": "cheap", "process_name": "Мойка", "name": "Дешёвый", "price_rub": 100_000, "count": 1},
            {"process_code": "dear", "process_name": "Паллеты", "name": "Дорогой", "price_rub": 20_000_000, "count": 1},
        ],
        _SITE,
        standard=standard,
    )
    # ФОТ 12 млн, доля 0,5 → экономия 6 млн. Дорогой CAPEX 20 млн окупается за 3,33 года при горизонте 3.
    cheap = _process(result, "cheap")
    dear = _process(result, "dear")
    assert cheap["share"] == 0.5
    assert cheap["profitable"] is True
    assert dear["profitable"] is False
    assert "горизонт" in dear["reason"]
    price = next(item for item in dear["suggestions"] if item["key"] == "price_factor")
    assert price["scope"] == "process"
    assert price["to"] <= 90
    assert price["payback"] <= 3


def test_staff_fte_weights_the_share():
    result = calculate(
        [
            {"process_code": "a", "process_name": "A", "name": "A", "price_rub": 100_000, "count": 1},
            {"process_code": "b", "process_name": "B", "name": "B", "price_rub": 100_000, "count": 1},
        ],
        _SITE,
        standard=_QUIET,
        tasks=[{"process_code": "a", "staff_fte_now": 9}, {"process_code": "b", "staff_fte_now": 1}],
    )
    assert _process(result, "a")["share"] == 0.9
    assert _process(result, "b")["share"] == 0.1


def test_process_price_and_service_do_not_leak():
    result = calculate(
        [
            {"process_code": "a", "process_name": "A", "name": "A", "price_rub": 1_000_000, "count": 1},
            {"process_code": "b", "process_name": "B", "name": "B", "price_rub": 1_000_000, "count": 1},
        ],
        _SITE,
        standard=_QUIET,
        overrides={"process:b:price_factor": 50, "process:b:service_pct": 10},
    )
    costs = {row["process_code"]: row["cost_rub"] for row in result["fleet"]}
    assert costs == {"a": 1_000_000, "b": 500_000}
    assert _buy(result)["capex"]["value"] == 1_500_000
    service = next(line for line in _buy(result)["opex_lines"] if line["key"] == "service")
    assert service["value"] == 50_000


def _subsidy_standard():
    standard = dict(_QUIET)
    standard.update({
        "mpt_rate_pct": 15, "mpt_limit_mln": 80, "leasing_discount_pct": 10, "moscow_rate_pct": 30, "moscow_limit_mln": 100,
        "frp_rate_pct": 3, "market_rate_pct": 18, "frp_share_pct": 50, "frp_term_years": 5,
        "accel_factor": 3, "service_life_years": 6, "profit_tax_pct": 25,
    })
    return standard


def test_mpt_subsidy_is_capped_and_cuts_capex():
    rows = [{"process_code": "a", "process_name": "A", "name": "A", "price_rub": 1_000_000_000, "count": 1}]
    base = calculate(rows, _SITE, standard=_subsidy_standard())
    with_mpt = calculate(rows, _SITE, standard=_subsidy_standard(), overrides={"subsidy:mpt": 1})
    item = next(row for row in with_mpt["subsidies"] if row["code"] == "mpt")
    assert item["enabled"] is True
    assert item["value"] == 80_000_000
    assert _buy(with_mpt)["capex"]["value"] == _buy(base)["capex"]["value"] - 80_000_000
    assert any(line["value"] == -80_000_000 for line in _buy(with_mpt)["capex_lines"])


def test_frp_and_amortization_are_yearly():
    rows = [{"process_code": "a", "process_name": "A", "name": "A", "price_rub": 6_000_000, "count": 1}]
    result = calculate(rows, _SITE, standard=_subsidy_standard(), overrides={"subsidy:frp": 1, "subsidy:amort": 1})
    items = {row["code"]: row for row in result["subsidies"]}
    assert items["frp"]["value"] == 0.15 * 0.5 * 6_000_000
    # 6 млн за 6 лет с коэффициентом 3: списание 3 млн в год два года, обычное 1 млн → экономия 2 млн × 25%.
    assert items["amort"]["value"] == 500_000
    assert items["amort"]["total"] == 1_000_000
    buy = _buy(result)
    assert buy["effect"]["value"] == 12_000_000 * 1 + 450_000 + 500_000


def test_payback_follows_the_support_schedule():
    rows = [{"process_code": "a", "process_name": "A", "name": "A", "price_rub": 30_000_000, "count": 1}]
    site = {"pickers_count": 1, "picker_salary_month_rub": 250_000, "payroll_burden": 1}
    plain = calculate(rows, site, standard=_subsidy_standard())
    assert _buy(plain)["payback"]["value"] == 10
    boosted = calculate(rows, site, standard=_subsidy_standard(), overrides={"subsidy:amort": 1})
    # Экономия налога 2,5 млн два года: 5,5 млн в первые два года, затем 3 млн.
    assert _buy(boosted)["payback"]["value"] == pytest.approx(2 + (30_000_000 - 11_000_000) / 3_000_000)


def test_subsidy_is_suggested_for_unprofitable_process():
    standard = _subsidy_standard()
    standard["horizon_years"] = 3
    rows = [
        {"process_code": "cheap", "process_name": "Мойка", "name": "Дешёвый", "price_rub": 100_000, "count": 1},
        {"process_code": "dear", "process_name": "Паллеты", "name": "Дорогой", "price_rub": 20_000_000, "count": 1},
    ]
    dear = _process(calculate(rows, _SITE, standard=standard), "dear")
    assert dear["profitable"] is False
    codes = {item["key"] for item in dear["suggestions"] if item["scope"] == "subsidy"}
    assert "mpt" in codes


def test_clamp_keeps_process_keys_inside_bounds():
    clean = clamp_overrides({"service_pct": 12, "process:pallet:price_factor": 10, "nope": 1, "process:bad": 5, "subsidy:mpt": 1, "subsidy:frp": 0, "subsidy:fake": 1})
    assert clean["service_pct"] == 12
    assert clean["subsidy:mpt"] == 1
    assert "subsidy:frp" not in clean
    assert "subsidy:fake" not in clean
    assert clean["process:pallet:price_factor"] == 50
    assert "nope" not in clean
    assert "process:bad" not in clean
