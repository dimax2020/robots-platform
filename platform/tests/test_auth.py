from uuid import UUID, uuid4

from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.main import app
from app.infrastructure.db.models import AppUserRow, ProjectRow
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


def test_demo_project_is_read_only_until_admin_edits():
    """Опубликованное демо читают все, правит только администратор; черновик виден только ему."""
    admin = _login("admin")
    created = admin.post("/api/v1/admin/projects/demo", json={"name": "Тестовое демо", "object_code": "warehouse", "slug": "demo-test-access"})
    assert created.status_code == 200, created.text
    demo_id = created.json()["id"]
    assert created.json()["is_demo"] is True and created.json()["published"] is False
    copies: list[str] = []
    try:
        anon = TestClient(app)
        guest = _login("guest")
        user = _login("user")
        # Черновик скрыт от всех, кроме администратора; в публичном списке его нет.
        assert anon.get("/api/v1/projects/demo-test-access").status_code == 404
        assert user.get(f"/api/v1/projects/{demo_id}").status_code == 404
        assert all(item["id"] != demo_id for item in anon.get("/api/v1/projects/demo").json()["items"])
        assert admin.get("/api/v1/projects/demo-test-access").json()["can_edit"] is True

        published = admin.put(f"/api/v1/admin/projects/{demo_id}/demo", json={"published": True})
        assert published.status_code == 200 and published.json()["published"] is True
        listed = anon.get("/api/v1/projects/demo").json()["items"]
        assert any(item["slug"] == "demo-test-access" for item in listed)

        # Чтение и расчёт по адресу без входа; правки запрещены гостю и пользователю.
        view = anon.get("/api/v1/projects/demo-test-access")
        assert view.status_code == 200 and view.json()["can_edit"] is False
        assert anon.post("/api/v1/projects/demo-test-access/match").status_code == 200
        assert anon.get("/api/v1/projects/demo-test-access/layout").status_code == 200
        assert anon.patch(f"/api/v1/projects/{demo_id}", json={"site": {"area_m2": 1}}).status_code == 401
        assert guest.patch(f"/api/v1/projects/{demo_id}", json={"site": {"area_m2": 1}}).status_code == 401
        assert user.patch(f"/api/v1/projects/{demo_id}", json={"site": {"area_m2": 1}}).status_code == 403
        assert user.put(f"/api/v1/projects/{demo_id}/layout", json={"layout": {}}).status_code == 403
        assert user.delete(f"/api/v1/projects/{demo_id}").status_code == 403
        # Демо не попадает в «мои проекты» пользователя, но копируется к нему обычным проектом.
        assert all(item["id"] != demo_id for item in user.get("/api/v1/projects").json()["items"])
        copied = user.post("/api/v1/projects/demo-test-access/copy")
        assert copied.status_code == 200, copied.text
        copies.append(copied.json()["id"])
        assert copied.json()["is_demo"] is False and copied.json()["slug"] is None
        # Администратор правит демо как обычный проект.
        assert admin.patch(f"/api/v1/projects/{demo_id}", json={"site": {"area_m2": 777}}).json()["site"]["area_m2"] == 777
        # Занятый адрес не отдаётся второму демо.
        clash = admin.post("/api/v1/admin/projects/demo", json={"name": "Дубль", "object_code": "warehouse", "slug": "demo-test-access"})
        assert clash.status_code == 422
    finally:
        with session_factory()() as db:
            for raw in [demo_id, *copies]:
                try:
                    delete_project(db, UUID(raw))
                except KeyError:
                    pass
            for row in db.scalars(select(ProjectRow).where(ProjectRow.name == "Дубль")):
                delete_project(db, row.id)


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
