import pytest

from app.domain.economy import NORMS, calculate, clamp_overrides

# Нормативы без шума: без налогов, НДС, дисконтирования и уведомления, чтобы проверять одну механику за раз.
_QUIET = {norm.key: 0.0 for norm in NORMS}
_QUIET.update({
    "price_factor": 100,
    "salary_factor": 100,
    "horizon_years": 5,
    "robots_per_operator": 50,
    "energy_kwh": 0,
    "energy_tariff": 7.2,
    "raas_rate_pct": 2,
    "fte_hours": 2000,
    "service_life_years": 5,
})

# Склад: 10 операторов погрузчиков по 100 000 ₽, одна смена.
_SITE = {"forklift_operators": 10, "forklift_salary_month_rub": 100_000, "payroll_burden": 1, "shifts_per_day": 1}
_RATE = 1_200_000
# Один робот занимает 1/50 поста диспетчера; часов работы на площадке нет, значит пост — один человек.
_DISPATCH = _RATE / 50


def _buy(result):
    return next(item for item in result["scenarios"] if item["key"] == "purchase")


def _rent(result):
    return next(item for item in result["scenarios"] if item["key"] == "raas")


def _process(result, code):
    return next(item for item in result["processes"] if item["process_code"] == code)


def _purchase_of(process):
    return next(item for item in process["scenarios"] if item["key"] == "purchase")


def _row(code, price, count=1, name="Робот"):
    return {"process_code": code, "process_name": code, "name": name, "price_rub": price, "count": count}


def test_single_process_matches_fleet():
    result = calculate([_row("pallet_transport", 1_000_000, 2)], _SITE, standard=_QUIET)
    fleet = _buy(result)
    process = _process(result, "pallet_transport")
    assert result["release"]["fte"] == 10
    assert process["share"] == 1
    assert process["profitable"] is True
    own = _purchase_of(process)
    assert own["effect"]["value"] == fleet["effect"]["value"]
    assert own["capex"]["value"] == fleet["capex"]["value"]
    assert own["npv"]["value"] == pytest.approx(fleet["npv"]["value"])


def test_role_is_split_between_fleet_processes_and_rounded_by_shift():
    site = {**_SITE, "shifts_per_day": 2, "oversized_share_pct": 5}
    result = calculate([_row("pallet_transport", 1_000_000), _row("rack_placement", 1_000_000)], site, standard=_QUIET)
    # 10 операторов × 0,95 = 9,5 → целыми ставками на 2 смены = 8, поровну между двумя процессами.
    assert result["release"]["fte"] == 8
    items = {item["process_code"]: item for item in result["release"]["items"]}
    assert items["pallet_transport"]["staff"] == 5
    assert items["pallet_transport"]["auto"] == pytest.approx(0.95)
    assert items["pallet_transport"]["fte"] == 4
    assert _process(result, "rack_placement")["share"] == 0.5
    assert _buy(result)["effect_lines"][0]["value"] == 8 * _RATE


def test_process_without_staff_saves_nothing_and_asks_the_customer():
    result = calculate([_row("pallet_transport", 1_000_000), _row("facade_washing", 100_000)], _SITE, standard=_QUIET)
    facade = _process(result, "facade_washing")
    assert facade["share"] == 0
    assert facade["profitable"] is False
    assert facade["suggestions"] == []
    assert "численности" in facade["reason"]
    # Люди фасада из часов роботов не появляются: вся экономия — операторы погрузчиков.
    assert _buy(result)["effect_lines"][0]["value"] == 10 * _RATE
    asks = [item for item in result["requests"] if item["process_code"] == "facade_washing"]
    assert asks and asks[0]["to"] == "customer"


def test_assisted_picking_needs_vendor_productivity():
    site = {"pickers_count": 50, "picker_salary_month_rub": 100_000, "payroll_burden": 1}
    result = calculate([_row("order_picking", 1_000_000)], site, standard=_QUIET)
    assert result["release"]["fte"] == 0
    assert result["requests"][0]["to"] == "vendor"


def test_task_staff_is_capped_by_robot_hours():
    site = {"staff_salary_year_rub": 1_000_000, "shift_hours": 8, "shifts_per_day": 1, "days_year": 250}
    tasks = [{"process_code": "baggage", "name": "Багаж", "staff_fte_now": 320}]
    result = calculate([_row("baggage", 4_000_000, 3)], site, standard=_QUIET, tasks=tasks)
    # 3 робота × 2 000 ч не заменят больше 3 человек с годовым фондом 2 000 ч.
    item = result["release"]["items"][0]
    assert item["capped"] is True
    assert result["release"]["fte"] == 3
    assert result["payroll"]["value"] == 320 * 1_000_000


def test_robot_without_count_counts_as_one_until_user_sets_it():
    rows = [_row("pallet_transport", 1_000_000, None), _row("rack_placement", 1_000_000, 150)]
    plain = calculate(rows, _SITE, standard=_QUIET)
    fleet = {row["process_code"]: row for row in plain["fleet"]}
    assert fleet["pallet_transport"]["included"] is True
    assert fleet["pallet_transport"]["count_used"] == 1
    assert fleet["pallet_transport"]["count_source"] == "default"
    assert fleet["rack_placement"]["count_source"] == "formula"
    own = calculate(rows, _SITE, standard=_QUIET, overrides={"count:pallet_transport": 4, "count:rack_placement": 10})
    fleet = {row["process_code"]: row for row in own["fleet"]}
    assert fleet["pallet_transport"]["count_used"] == 4
    assert fleet["pallet_transport"]["count_source"] == "project"
    assert fleet["rack_placement"]["count_used"] == 10
    assert _buy(own)["capex"]["value"] == 14_000_000


def test_dispatch_post_covers_all_working_hours():
    standard = {**_QUIET, "robots_per_operator": 10, "fte_hours": 1810}
    site = {**_SITE, "shift_hours": 11, "shifts_per_day": 2, "days_year": 365}
    result = calculate([_row("pallet_transport", 1_000_000, 17)], site, standard=standard)
    operators = next(line for line in _buy(result)["opex_lines"] if line["key"] == "operators")
    # 17 / 10 = 1,7 поста × 8 030 ч / 1 810 ч ≈ 7,5 человека, а не 2: пост занят всё время работы парка.
    assert operators["value"] == pytest.approx(1.7 * 8030 / 1810 * _RATE)
    assert operators["count"] == pytest.approx(7.54, abs=0.01)


def test_vat_is_taken_out_of_equipment():
    standard = {**_QUIET, "vat_pct": 22}
    result = calculate([_row("pallet_transport", 1_220_000)], _SITE, standard=standard)
    assert result["fleet"][0]["cost_rub"] == pytest.approx(1_000_000)
    assert _buy(result)["capex"]["value"] == pytest.approx(1_000_000)


def test_cash_flow_follows_notice_severance_tax_and_residual():
    standard = {**_QUIET, "notice_months": 2, "severance_months": 2, "profit_tax_pct": 25}
    result = calculate([_row("pallet_transport", 5_000_000)], _SITE, standard=standard)
    rows = _buy(result)["cashflow"]
    saving = 10 * _RATE
    first = saving * 10 / 12
    paid = 10 * 100_000 * 2
    dep = 1_000_000
    assert rows[0]["saving_rub"] == pytest.approx(first)
    assert rows[0]["payouts_rub"] == pytest.approx(-paid)
    assert rows[0]["tax_rub"] == pytest.approx(-0.25 * (first - _DISPATCH - paid - dep))
    assert rows[1]["payouts_rub"] == 0
    assert rows[1]["cf_rub"] == pytest.approx(saving - _DISPATCH - 0.25 * (saving - _DISPATCH - dep))
    # Срок службы 5 лет = горизонт: к концу всё списано, остаточной стоимости нет.
    assert rows[-1]["residual_rub"] == pytest.approx(0)


def test_npv_irr_and_net_roi_without_discounting():
    standard = {**_QUIET, "horizon_years": 2, "service_life_years": 4}
    result = calculate([_row("pallet_transport", 20_000_000)], _SITE, standard=standard)
    buy = _buy(result)
    # Поток 12 млн минус доля поста диспетчера в год два года и остаточная стоимость 10 млн при ставке 0.
    flow = 12_000_000 - _DISPATCH
    assert buy["npv"]["value"] == pytest.approx(-20_000_000 + flow * 2 + 10_000_000)
    assert buy["roi"]["value"] == pytest.approx((flow * 2 + 10_000_000 - 20_000_000) / 20_000_000 * 100)
    # Окупаемость без остаточной стоимости: 1 год и остаток из потока второго года.
    assert buy["payback"]["value"] == pytest.approx(1 + (20_000_000 - flow) / flow)
    assert buy["irr"]["value"] > 0


def test_real_discount_rate_comes_from_market_rate_and_inflation_target():
    standard = {**_QUIET, "market_rate_pct": 18, "inflation_target_pct": 4}
    result = calculate([_row("pallet_transport", 1_000_000)], _SITE, standard=standard)
    assert result["discount"]["value"] == pytest.approx((1.18 / 1.04 - 1) * 100)


def test_rent_shows_npv_but_no_payback_or_roi():
    result = calculate([_row("pallet_transport", 1_000_000)], _SITE, standard=_QUIET)
    rent = _rent(result)
    assert rent["payback"]["value"] is None
    assert rent["roi"]["value"] is None
    assert rent["npv"]["value"] is not None


def test_share_above_the_demo_benchmark_is_flagged():
    result = calculate([_row("pallet_transport", 1_000_000, 10)], _SITE, standard=_QUIET)
    assert result["release"]["share"] == 1
    assert "ориентира" in result["release"]["check"]


def test_expensive_process_gets_a_price_suggestion():
    standard = {**_QUIET, "horizon_years": 3}
    result = calculate([_row("pallet_transport", 60_000_000)], _SITE, standard=standard)
    process = _process(result, "pallet_transport")
    # 12 млн в год за 3 года и остаточная стоимость 24 млн не возвращают 60 млн.
    assert process["profitable"] is False
    price = next(item for item in process["suggestions"] if item["key"] == "price_factor")
    assert price["scope"] == "process"
    assert price["to"] < 100


def test_process_price_and_service_do_not_leak():
    rows = [_row("pallet_transport", 1_000_000), _row("rack_placement", 1_000_000)]
    result = calculate(rows, _SITE, standard=_QUIET, overrides={"process:rack_placement:price_factor": 50, "process:rack_placement:service_pct": 10})
    costs = {row["process_code"]: row["cost_rub"] for row in result["fleet"]}
    assert costs == {"pallet_transport": 1_000_000, "rack_placement": 500_000}
    assert _buy(result)["capex"]["value"] == 1_500_000
    service = next(line for line in _buy(result)["opex_lines"] if line["key"] == "service")
    assert service["value"] == 50_000


def _subsidy_standard():
    return {
        **_QUIET,
        "mpt_rate_pct": 15, "mpt_limit_mln": 80, "leasing_discount_pct": 10, "moscow_rate_pct": 30, "moscow_limit_mln": 100,
        "frp_rate_pct": 3, "market_rate_pct": 18, "frp_share_pct": 50, "frp_term_years": 5,
        "accel_factor": 3, "service_life_years": 6, "profit_tax_pct": 25,
    }


def test_mpt_subsidy_is_capped_and_cuts_capex():
    rows = [_row("pallet_transport", 1_000_000_000)]
    base = calculate(rows, _SITE, standard=_subsidy_standard())
    with_mpt = calculate(rows, _SITE, standard=_subsidy_standard(), overrides={"subsidy:mpt": 1})
    item = next(row for row in with_mpt["subsidies"] if row["code"] == "mpt")
    assert item["enabled"] is True
    assert item["value"] == 80_000_000
    assert _buy(with_mpt)["capex"]["value"] == _buy(base)["capex"]["value"] - 80_000_000
    assert any(line["value"] == -80_000_000 for line in _buy(with_mpt)["capex_lines"])


def test_leasing_measures_do_not_touch_purchase():
    rows = [_row("pallet_transport", 10_000_000)]
    base = calculate(rows, _SITE, standard=_subsidy_standard())
    leased = calculate(rows, _SITE, standard=_subsidy_standard(), overrides={"subsidy:leasing": 1, "subsidy:moscow": 1})
    assert {row["code"] for row in leased["subsidies"]} == {"mpt", "frp", "amort"}
    assert _buy(leased)["capex"]["value"] == _buy(base)["capex"]["value"]


def test_frp_benefit_follows_the_remaining_debt():
    rows = [_row("pallet_transport", 6_000_000)]
    result = calculate(rows, _SITE, standard=_subsidy_standard(), overrides={"subsidy:frp": 1})
    frp = next(row for row in result["subsidies"] if row["code"] == "frp")
    loan = 0.5 * 6_000_000
    assert frp["value"] == pytest.approx(0.15 * loan * 4.5 / 5)
    assert frp["total"] == pytest.approx(sum(0.15 * loan * (5 - year + 0.5) / 5 for year in range(1, 6)))
    assert _buy(result)["cashflow"][1]["support_rub"] == pytest.approx(0.15 * loan * 3.5 / 5)


def test_accelerated_depreciation_moves_tax_to_later_years():
    rows = [_row("pallet_transport", 6_000_000)]
    plain = calculate(rows, _SITE, standard=_subsidy_standard())
    fast = calculate(rows, _SITE, standard=_subsidy_standard(), overrides={"subsidy:amort": 1})
    # 6 млн за 6 лет с коэффициентом 3: списание 3 млн в первый год вместо 1 млн.
    assert _buy(fast)["cashflow"][0]["depreciation_rub"] == 3_000_000
    assert _buy(plain)["cashflow"][0]["depreciation_rub"] == 1_000_000
    item = next(row for row in fast["subsidies"] if row["code"] == "amort")
    assert item["value"] == 500_000
    assert _buy(fast)["npv"]["value"] > _buy(plain)["npv"]["value"]


def test_subsidy_is_suggested_for_unprofitable_process():
    standard = {**_subsidy_standard(), "horizon_years": 3, "profit_tax_pct": 0}
    result = calculate([_row("pallet_transport", 40_000_000)], _SITE, standard=standard)
    process = _process(result, "pallet_transport")
    assert process["profitable"] is False
    codes = {item["key"] for item in process["suggestions"] if item["scope"] == "subsidy"}
    assert "mpt" in codes


def test_clamp_keeps_process_keys_inside_bounds():
    clean = clamp_overrides({"service_pct": 12, "process:pallet:price_factor": 10, "nope": 1, "process:bad": 5, "subsidy:mpt": 1, "subsidy:frp": 0, "subsidy:fake": 1, "count:pallet": 2.6, "count:huge": 1e9})
    assert clean["count:pallet"] == 3
    assert clean["count:huge"] == 10_000
    assert clean["service_pct"] == 12
    assert clean["subsidy:mpt"] == 1
    assert "subsidy:frp" not in clean
    assert "subsidy:fake" not in clean
    assert clean["process:pallet:price_factor"] == 50
    assert "nope" not in clean
    assert "process:bad" not in clean


def test_breakeven_price_and_people_bracket_zero_npv():
    result = calculate([_row("pallet_transport", 20_000_000)], _SITE, standard=_QUIET)
    points = {item["key"]: item for item in result["breakeven"]}
    price = points["price_factor"]
    assert price["direction"] == "max"
    assert price["value"] > 100
    changed = calculate([_row("pallet_transport", 20_000_000)], _SITE, standard=_QUIET, overrides={"price_factor": price["value"]})
    assert abs(_buy(changed)["npv"]["value"]) < 50_000
    people = points["release"]
    assert people["direction"] == "min"
    assert people["value"] < 10


def test_interval_wraps_the_center_and_tornado_uses_source_ranges():
    standard = {**_QUIET, "comms_pct": 0.3, "service_pct": 8}
    result = calculate([_row("pallet_transport", 20_000_000)], _SITE, standard=standard)
    interval = result["interval"]
    assert interval["npv_low"] < interval["npv"] < interval["npv_high"]
    comms = next(item for item in result["sensitivity"] if item["key"] == "comms_pct")
    assert (comms["low_value"], comms["high_value"]) == (0.2, 0.5)
    service = next(item for item in result["sensitivity"] if item["key"] == "service_pct")
    assert service["low_value"] == pytest.approx(6.4)
    assert sum(item["share"] for item in result["sensitivity"]) == pytest.approx(1)


def test_excluded_process_leaves_the_total_but_keeps_its_verdict():
    rows = [_row("pallet_transport", 1_000_000), _row("facade_washing", 5_000_000)]
    full = calculate(rows, _SITE, standard=_QUIET)
    cut = calculate(rows, _SITE, standard=_QUIET, overrides={"off:facade_washing": 1})
    assert _buy(cut)["capex"]["value"] == 1_000_000
    assert _buy(cut)["npv"]["value"] > _buy(full)["npv"]["value"]
    facade = _process(cut, "facade_washing")
    assert facade["off"] is True
    assert facade["profitable"] is False
    assert _purchase_of(facade)["capex"]["value"] == 5_000_000
    assert clamp_overrides({"off:facade_washing": 1, "off:x": 0}) == {"off:facade_washing": 1}


def test_process_alone_takes_its_whole_role_and_own_dispatch_post():
    site = {**_SITE, "shifts_per_day": 2}
    result = calculate([_row("pallet_transport", 1_000_000), _row("rack_placement", 1_000_000)], site, standard=_QUIET)
    # В парке роль делится поровну, а «только этот процесс» забирает её целиком.
    assert {item["fte"] for item in result["release"]["items"]} == {5}
    transport = _process(result, "pallet_transport")
    assert transport["release"]["fte"] == 10
    assert _purchase_of(transport)["effect_lines"][0]["value"] == 10 * _RATE


def test_monthly_task_salary_and_process_story():
    site = {"payroll_burden": 1.302, "shifts_per_day": 1}
    tasks = [{"process_code": "floor_cleaning", "name": "Уборка", "staff_fte_now": 6, "staff_salary_month_rub": 60_000}]
    result = calculate([_row("floor_cleaning", 1_500_000, 2)], site, standard=_QUIET, tasks=tasks)
    story = _process(result, "floor_cleaning")["story"]
    rate = 60_000 * 12 * 1.302
    assert story["staff"] == 6
    assert story["wage_month"] == 60_000
    assert story["payroll_now"] == pytest.approx(6 * rate)
    assert story["released"] == 6
    assert story["saving_year"] == pytest.approx(story["cost_before"] - story["cost_after"])
    assert story["needs_staff"] is False
    assert result["story"]["payroll_now"] == pytest.approx(6 * rate)


def test_story_counts_a_shared_role_once():
    result = calculate([_row("pallet_transport", 1_000_000), _row("rack_placement", 1_000_000)], _SITE, standard=_QUIET)
    assert result["story"]["staff_now"] == 10
    assert result["story"]["payroll_now"] == 10 * _RATE
    assert _process(result, "pallet_transport")["story"]["shared_with"] == ["rack_placement"]


def test_process_that_pays_off_with_a_discount_is_conditional():
    standard = {**_QUIET, "horizon_years": 3}
    result = calculate([_row("pallet_transport", 60_000_000)], _SITE, standard=standard)
    process = _process(result, "pallet_transport")
    assert process["status"] == "conditional"
    # Сначала условие, которое меняет только этот процесс: скидка вендора, а не зарплаты всей площадки.
    assert process["condition"]["key"] in {item["key"] for item in process["suggestions"]}
    assert process["condition"]["scope"] != "site"
    assert process["condition"]["hard"] is False
    cheap = calculate([_row("pallet_transport", 1_000_000)], _SITE, standard=standard)
    assert _process(cheap, "pallet_transport")["status"] == "ok"
    empty = calculate([_row("facade_washing", 1_000_000)], _SITE, standard=standard)
    assert _process(empty, "facade_washing")["status"] == "no_staff"


def test_hard_condition_is_still_a_condition_but_flagged():
    standard = {**_QUIET, "horizon_years": 3}
    result = calculate([_row("pallet_transport", 90_000_000)], _SITE, standard=standard)
    process = _process(result, "pallet_transport")
    assert process["status"] == "conditional"
    assert process["condition"]["hard"] is True
    hopeless = calculate([_row("pallet_transport", 2_000_000_000)], _SITE, standard=standard)
    assert _process(hopeless, "pallet_transport")["status"] == "bad"


def test_discount_with_support_is_offered_when_nothing_alone_helps():
    standard = {**_subsidy_standard(), "horizon_years": 3, "profit_tax_pct": 0}
    rows = [_row("pallet_transport", 52_000_000)]
    process = _process(calculate(rows, _SITE, standard=standard), "pallet_transport")
    combos = [item for item in process["suggestions"] if item["scope"] == "combo"]
    if combos:
        combo = combos[0]
        assert combo["to"] < 100
        assert set(combo["with"]) <= {"mpt", "frp", "amort"}
        assert process["status"] == "conditional"


def test_profitability_index_and_equivalent_annual_cost():
    result = calculate([_row("pallet_transport", 1_000_000, 2)], _SITE, standard=_QUIET)
    buy, asis = _buy(result), result["scenarios"][0]
    npv, capex = buy["npv"]["value"], buy["capex"]["value"]
    assert buy["pi"]["value"] == pytest.approx((npv + capex) / capex)
    # Без ставки и налога аннуитет — 1/T: разница годовой стоимости равна NPV, разложенному на горизонт.
    assert asis["eac"]["value"] == 10 * _RATE
    assert asis["eac"]["value"] - buy["eac"]["value"] == pytest.approx(npv / 5)
    assert _rent(result)["pi"]["value"] is None


def test_switch_point_between_rent_and_buy():
    result = calculate([_row("pallet_transport", 1_000_000, 2)], _SITE, standard=_QUIET)
    buy, rent = _buy(result), _rent(result)
    gap = buy["cashflow"][1]["cf_rub"] - rent["cashflow"][1]["cf_rub"]
    months = (buy["capex"]["value"] - rent["capex"]["value"]) / gap * 12
    assert result["switch"]["value"] == pytest.approx(months)


def test_stress_cases_are_worse_and_all_at_once_is_worst():
    standard = {**_QUIET, "market_rate_pct": 18, "inflation_target_pct": 4, "notice_months": 2}
    result = calculate([_row("pallet_transport", 1_000_000, 2)], _SITE, standard=standard)
    base = _buy(result)["npv"]["value"]
    stress = {item["key"]: item for item in result["stress"]}
    assert set(stress) == {"volume", "rate", "slow", "price", "all"}
    for key in ("volume", "rate", "slow", "price"):
        assert stress[key]["npv"] < base
        assert stress["all"]["npv"] <= stress[key]["npv"]
    assert 0 <= result["chance"]["npv_positive"] <= 1


def test_best_set_skips_a_process_that_shares_the_same_people():
    # Перевозка и размещение делят 10 операторов: второй процесс людей не добавляет, а вложения добавляет.
    rows = [_row("pallet_transport", 1_000_000), _row("rack_placement", 3_000_000)]
    result = calculate(rows, _SITE, standard=_QUIET)
    best = result["best_set"]
    assert best["codes"] == ["pallet_transport"]
    assert best["dropped"] == ["rack_placement"]
    assert best["npv"] > best["current_npv"]


def test_best_set_respects_site_budget():
    rows = [_row("pallet_transport", 1_000_000), _row("packing", 2_000_000)]
    site = {**_SITE, "pack_operators": 10, "pack_salary_month_rub": 100_000, "budget_rub": 1_500_000}
    best = calculate(rows, site, standard=_QUIET)["best_set"]
    assert best["codes"] == ["pallet_transport"]
    assert best["capex"] <= 1_500_000


def test_unit_cost_per_pallet_before_and_after():
    site = {**_SITE, "inbound_pallets_per_day": 100, "outbound_pallets_per_day": 100, "days_year": 300}
    unit = _process(calculate([_row("pallet_transport", 1_000_000)], site, standard=_QUIET), "pallet_transport")["story"]["unit"]
    assert unit["label"] == "паллета"
    assert unit["volume_year"] == 60_000
    assert unit["before"] == pytest.approx(10 * _RATE / 60_000)
    assert unit["after"] < unit["before"]


def test_fleet_is_bought_again_when_horizon_outlives_it():
    # Срок службы 5 лет, горизонт 7: на 6-й год парк покупается заново, остаток считается от новой закупки.
    result = calculate([_row("pallet_transport", 1_000_000, 2)], _SITE, standard={**_QUIET, "horizon_years": 7})
    buy = _buy(result)
    capex = buy["capex"]["value"]
    flows = {row["year"]: row for row in buy["cashflow"]}
    assert [year for year, row in flows.items() if row["reinvest_rub"]] == [6]
    assert flows[6]["reinvest_rub"] == pytest.approx(-capex)
    assert flows[7]["residual_rub"] == pytest.approx(capex * 3 / 5)
