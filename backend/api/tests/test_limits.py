"""Проверка диапазонов полей (E4 §7)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from api.config import Settings
from api.schemas.project import ProjectPatch
from api.services import limits as limits_svc
from api.services.limits import (
    check_site,
    check_site_and_tasks,
    check_tasks,
    clear_limits_cache,
    load_field_limits,
)
from engine.models import SiteProfile, Task

REPO_DATA = Path(__file__).resolve().parents[3] / "data"
PROFILES = ("warehouse", "airport", "hospital")


@pytest.fixture(autouse=True)
def _limits_data_dir(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(limits_svc, "get_settings", lambda: Settings(data_dir=REPO_DATA))
    clear_limits_cache()
    yield
    clear_limits_cache()


def _load_profile(code: str) -> tuple[SiteProfile, list[Task]]:
    raw = json.loads((REPO_DATA / "site_profiles" / f"{code}.json").read_text(encoding="utf-8"))
    site = SiteProfile.model_validate(raw.get("site") or {"object_type_code": code})
    tasks = [Task.model_validate(item) for item in (raw.get("tasks") or [])]
    return site, tasks


def test_demo_profiles_pass_limits() -> None:
    for code in PROFILES:
        site, tasks = _load_profile(code)
        violations = check_site_and_tasks(site, tasks)
        assert violations == [], f"{code}: {[v.message for v in violations]}"


def test_site_below_min() -> None:
    site = SiteProfile(object_type_code="warehouse", shift_hours=0)
    violations = check_site(site)
    assert len(violations) == 1
    v = violations[0]
    assert v.loc == ("site", "shift_hours")
    assert v.value == 0
    assert "1-24" in v.message
    assert "Длительность смены" in v.message


def test_site_above_max() -> None:
    site = SiteProfile(object_type_code="warehouse", shift_hours=40)
    violations = check_site(site)
    assert len(violations) == 1
    assert violations[0].value == 40
    assert "выходит за границу 1-24 ч" in violations[0].message


def test_boundary_min_and_max_pass() -> None:
    limits = load_field_limits()["site"]["shift_hours"]
    lo = SiteProfile(object_type_code="warehouse", shift_hours=limits["min"])
    hi = SiteProfile(object_type_code="warehouse", shift_hours=limits["max"])
    assert check_site(lo) == []
    assert check_site(hi) == []


def test_none_passes() -> None:
    site = SiteProfile(object_type_code="warehouse", area_m2=None, budget_rub=None)
    assert check_site(site) == []


def test_t_load_s_zero_passes() -> None:
    task = Task(process_code="warehouse_logistics", t_load_s=0, t_unload_s=0)
    assert check_tasks([task]) == []


def test_task_violation_loc_includes_index() -> None:
    tasks = [
        Task(process_code="a", flow_per_day=100),
        Task(process_code="b", flow_per_day=-1),
    ]
    violations = check_tasks(tasks)
    assert len(violations) == 1
    assert violations[0].loc == ("tasks", 1, "flow_per_day")
    assert "Поток в сутки" in violations[0].message
    assert "выходит за границу" in violations[0].message


def test_project_patch_raises_with_loc_and_message() -> None:
    with pytest.raises(ValidationError) as exc:
        ProjectPatch(site=SiteProfile(object_type_code="warehouse", shift_hours=40))
    err = exc.value.errors()[0]
    assert err["loc"] == ("site", "shift_hours")
    assert "1-24 ч" in err["msg"]
    assert "Длительность смены" in err["msg"]


def test_project_patch_task_index_in_loc() -> None:
    with pytest.raises(ValidationError) as exc:
        ProjectPatch(
            tasks=[
                Task(process_code="ok", flow_per_day=10),
                Task(process_code="bad", flow_per_day=-5),
            ]
        )
    err = exc.value.errors()[0]
    assert err["loc"] == ("tasks", 1, "flow_per_day")


def test_missing_limits_file_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(limits_svc, "get_settings", lambda: Settings(data_dir=tmp_path))
    clear_limits_cache()
    with pytest.raises(FileNotFoundError, match="границ полей"):
        load_field_limits()
