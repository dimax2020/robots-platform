from uuid import UUID, uuid4

from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.main import app
from app.infrastructure.db.models import AppUserRow
from app.infrastructure.db.session import session_factory
from app.infrastructure.db.taxonomy_repo import delete_project

PASSWORD = "demo-2026"


def _login(login: str) -> TestClient:
    client = TestClient(app)
    response = client.post("/api/v1/auth/login", json={"login": login, "password": PASSWORD})
    assert response.status_code == 200, response.text
    assert response.json()["login"] == login
    return client


def test_wrong_password_and_logout():
    client = TestClient(app)
    denied = client.post("/api/v1/auth/login", json={"login": "user", "password": "wrong"})
    assert denied.status_code == 401
    assert denied.json()["detail"] == "Неверный логин или пароль"
    assert client.get("/api/v1/auth/me").status_code == 401

    signed = _login("admin")
    assert signed.get("/api/v1/auth/me").json()["role"] == "admin"
    assert signed.post("/api/v1/auth/logout").status_code == 200
    assert signed.get("/api/v1/auth/me").status_code == 401


def test_guest_and_user_cannot_open_admin():
    assert TestClient(app).get("/api/v1/catalog/tree").status_code == 200
    assert TestClient(app).get("/api/v1/admin/processes").status_code == 401
    guest = _login("guest")
    assert guest.post("/api/v1/projects", json={"name": "нет", "object_code": "warehouse", "site": {}}).status_code == 401
    assert guest.get("/api/v1/admin/processes").status_code == 403
    assert _login("user").get("/api/v1/admin/processes").status_code == 403
    assert _login("admin").get("/api/v1/admin/processes").status_code == 200


def test_owner_copy_and_delete():
    other_id = uuid4()
    with session_factory()() as db:
        db.add(AppUserRow(id=other_id, login="user-b", password_hash=PasswordHasher().hash(PASSWORD), role="user"))
        db.commit()
    created_ids: list[str] = []
    try:
        owner = _login("user")
        created = owner.post("/api/v1/projects", json={"name": "Изоляция", "object_code": "warehouse", "site": {"area_m2": 10}})
        assert created.status_code == 200, created.text
        project_id = created.json()["id"]
        created_ids.append(project_id)
        assert created.json()["site"]["area_m2"] == 10

        stranger = _login("user-b")
        assert stranger.get(f"/api/v1/projects/{project_id}").status_code == 404
        assert stranger.delete(f"/api/v1/projects/{project_id}").status_code == 404

        copied = owner.post(f"/api/v1/projects/{project_id}/copy")
        assert copied.status_code == 200, copied.text
        copy_id = copied.json()["id"]
        created_ids.append(copy_id)
        assert copied.json()["name"] == "Изоляция (копия)"
        assert stranger.get(f"/api/v1/projects/{copy_id}").status_code == 404
        assert owner.get(f"/api/v1/projects/{copy_id}").status_code == 200

        mine = {item["id"] for item in owner.get("/api/v1/projects").json()["items"]}
        assert project_id in mine and copy_id in mine
        assert project_id not in {item["id"] for item in stranger.get("/api/v1/projects").json()["items"]}

        admin = _login("admin")
        assert admin.get(f"/api/v1/projects/{project_id}").status_code == 200

        assert owner.delete(f"/api/v1/projects/{project_id}").status_code == 200
        assert owner.get(f"/api/v1/projects/{project_id}").status_code == 404
        created_ids.remove(project_id)
        assert owner.delete(f"/api/v1/projects/{copy_id}").status_code == 200
        created_ids.remove(copy_id)
    finally:
        with session_factory()() as db:
            for raw in created_ids:
                try:
                    delete_project(db, UUID(raw))
                except KeyError:
                    pass
            user = db.scalar(select(AppUserRow).where(AppUserRow.login == "user-b"))
            if user is not None:
                db.delete(user)
                db.commit()
