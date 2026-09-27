from app.domain.economy import blend_by_type, resolve


def test_type_norm_equals_per_robot_sum() -> None:
    rows = [
        {"solution_type": "amr", "price_rub": 1_000_000, "count": 3},
        {"solution_type": "cobot", "price_rub": 2_000_000, "count": 1},
        {"solution_type": "", "price_rub": None, "count": 2},
    ]
    standard, notes = blend_by_type({"service_pct": 8.0}, rows, {"amr": {"service_pct": 6.0}}, {"amr": "AMR"})
    per_robot = 3_000_000 * 0.06 + 2_000_000 * 0.08
    assert abs(standard["service_pct"] / 100 * 5_000_000 - per_robot) < 1e-6
    assert "AMR 6%" in notes["service_pct"]["rationale"]


def test_project_value_beats_type_norm() -> None:
    standard, _ = blend_by_type({"service_pct": 8.0}, [{"solution_type": "amr", "price_rub": 1, "count": 1}], {"amr": {"service_pct": 6.0}})
    params = resolve(standard, {"service_pct": 10.0})
    assert params["service_pct"]["value"] == 10.0
    assert params["service_pct"]["source"] == "project"


def test_untouched_norms_stay_standard() -> None:
    standard, notes = blend_by_type({"license_pct": 4.9}, [{"solution_type": "amr", "price_rub": 1, "count": 1}], {"amr": {"service_pct": 6.0}})
    assert standard["license_pct"] == 4.9
    assert "license_pct" not in notes


def test_admin_source_replaces_code_text() -> None:
    params = resolve({}, {}, meta={"service_pct": {"rationale": "Договоры 2026", "origin": "Договоры вендоров"}})
    assert params["service_pct"]["rationale"] == "Договоры 2026"
    assert params["service_pct"]["origin"] == "Договоры вендоров"
