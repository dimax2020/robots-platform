from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.config import Settings
from api.db.models import AppUser, CalcRun, ObjectType, Project
from api.deps import DEMO_USER_ID, DEMO_USER_LOGIN, get_current_user, get_db
from api.routers import projects
from engine.models import Catalog, CalcResponse

REPO_DATA = Path(__file__).resolve().parents[3] / "data"


@pytest.fixture
def demo_user() -> AppUser:
    return AppUser(
        id=DEMO_USER_ID,
        login=DEMO_USER_LOGIN,
        password_hash="x",
        role="admin",
    )


@pytest.fixture
def object_type() -> ObjectType:
    return ObjectType(id=1, code="warehouse", name="Склад")


@pytest.fixture
def project(demo_user: AppUser, object_type: ObjectType) -> Project:
    now = datetime.now(timezone.utc)
    return Project(
        id=uuid4(),
        owner_id=demo_user.id,
        name="Склад",
        object_type_id=object_type.id,
        site={"object_type_code": "warehouse", "area_m2": 20000},
        tasks=[{"process_code": "warehouse_logistics", "flow_per_day": 2000}],
        overrides={},
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def db() -> MagicMock:
    session = MagicMock()
    result = MagicMock()
    result.first.return_value = None
    result.all.return_value = []
    session.execute.return_value = result
    session.scalar.return_value = None
    return session


@pytest.fixture
def client(db: MagicMock, demo_user: AppUser, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(projects, "get_settings", lambda: Settings(data_dir=REPO_DATA))

    app = FastAPI()
    app.include_router(projects.router, prefix="/api/v1")
    app.include_router(projects.refs_router, prefix="/api/v1")
    app.state.catalog = Catalog(version_id=1)
    cache = MagicMock()
    cache.get.return_value = None
    app.state.cache = cache

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: demo_user
    return TestClient(app)


def test_create_project_prefills_warehouse_profile(
    client: TestClient, db: MagicMock, object_type: ObjectType, demo_user: AppUser
) -> None:
    db.scalar.return_value = object_type

    res = client.post(
        "/api/v1/projects",
        json={"name": "Мой склад", "object_type_code": "warehouse"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["name"] == "Мой склад"
    assert body["object_type_code"] == "warehouse"
    assert body["owner_id"] == str(demo_user.id)
    assert body["site"]["area_m2"] == 20000
    assert body["site"]["pallet_places"] == 20000
    assert {t["process_code"] for t in body["tasks"]} >= {
        "warehouse_logistics",
        "order_picking",
        "indoor_cleaning",
    }
    db.add.assert_called_once()
    saved = db.add.call_args[0][0]
    assert saved.owner_id == demo_user.id
    assert saved.site["area_m2"] == 20000


def test_create_project_empty_if_no_profile(
    client: TestClient, db: MagicMock
) -> None:
    db.scalar.return_value = ObjectType(id=9, code="factory", name="Завод")

    res = client.post(
        "/api/v1/projects",
        json={"name": "Завод", "object_type_code": "factory"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["site"]["object_type_code"] == "factory"
    assert body["tasks"] == []


def test_create_project_unknown_object_type(client: TestClient, db: MagicMock) -> None:
    db.scalar.return_value = None
    res = client.post(
        "/api/v1/projects",
        json={"name": "Нет такого", "object_type_code": "spaceship"},
    )
    assert res.status_code == 422
    assert "не найден" in res.json()["detail"]


def test_get_project(
    client: TestClient, db: MagicMock, project: Project, object_type: ObjectType
) -> None:
    db.execute.return_value.first.return_value = (project, object_type)
    res = client.get(f"/api/v1/projects/{project.id}")
    assert res.status_code == 200
    assert res.json()["id"] == str(project.id)
    assert res.json()["name"] == "Склад"


def test_get_project_404(client: TestClient) -> None:
    res = client.get(f"/api/v1/projects/{uuid4()}")
    assert res.status_code == 404
    assert res.json()["detail"] == "Проект не найден"


def test_list_projects(
    client: TestClient, db: MagicMock, project: Project, object_type: ObjectType
) -> None:
    db.execute.return_value.all.return_value = [(project, object_type)]
    res = client.get("/api/v1/projects")
    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["id"] == str(project.id)


def test_patch_project(
    client: TestClient, db: MagicMock, project: Project, object_type: ObjectType
) -> None:
    db.execute.return_value.first.return_value = (project, object_type)
    res = client.patch(
        f"/api/v1/projects/{project.id}",
        json={"name": "Новое имя", "overrides": {"k_util": 0.9}},
    )
    assert res.status_code == 200
    assert res.json()["name"] == "Новое имя"
    assert res.json()["overrides"] == {"k_util": 0.9}
    assert project.name == "Новое имя"
    db.commit.assert_called()


def test_calculate_persists_run_and_returns_run_id(
    client: TestClient, db: MagicMock, project: Project, object_type: ObjectType
) -> None:
    db.execute.return_value.first.return_value = (project, object_type)

    res = client.post(f"/api/v1/projects/{project.id}/calculate")
    assert res.status_code == 200, res.text
    body = res.json()
    assert "run_id" in body
    assert body["engine_version"]
    assert body["catalog_version_id"] == 1
    assert "candidates" in body
    assert "scenarios" in body
    assert "vendor_queries" in body
    assert "trace" in body
    saved = db.add.call_args[0][0]
    assert isinstance(saved, CalcRun)
    assert saved.project_id == project.id
    assert saved.id is not None
    assert str(saved.id) == body["run_id"]


def test_calculate_missing_project(client: TestClient) -> None:
    res = client.post(f"/api/v1/projects/{uuid4()}/calculate")
    assert res.status_code == 404


def test_latest_run(
    client: TestClient, db: MagicMock, project: Project, object_type: ObjectType
) -> None:
    db.execute.return_value.first.return_value = (project, object_type)
    run_id = uuid4()
    payload = CalcResponse(engine_version="0.1.0", catalog_version_id=1)
    run = CalcRun(
        id=run_id,
        project_id=project.id,
        catalog_version_id=1,
        engine_version="0.1.0",
        request={},
        response=payload.model_dump(mode="json"),
    )
    db.scalar.return_value = run

    res = client.get(f"/api/v1/projects/{project.id}/runs/latest")
    assert res.status_code == 200
    assert res.json()["run_id"] == str(run_id)
    assert res.json()["engine_version"] == "0.1.0"


def test_latest_run_404(
    client: TestClient, db: MagicMock, project: Project, object_type: ObjectType
) -> None:
    db.execute.return_value.first.return_value = (project, object_type)
    db.scalar.return_value = None
    res = client.get(f"/api/v1/projects/{project.id}/runs/latest")
    assert res.status_code == 404
    assert res.json()["detail"] == "Прогон не найден"


def test_site_profile_ref(client: TestClient) -> None:
    res = client.get("/api/v1/refs/site-profiles/warehouse")
    assert res.status_code == 200
    body = res.json()
    assert body["object_type_code"] == "warehouse"
    assert body["site"]["area_m2"] == 20000
    assert body["tasks"]


def test_site_profile_ref_404(client: TestClient) -> None:
    res = client.get("/api/v1/refs/site-profiles/spaceship")
    assert res.status_code == 404
