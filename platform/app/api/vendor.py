"""Кабинет вендора и решения администратора по его заявкам."""

import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.auth import SessionUser, require_admin, require_vendor
from app.config import get_settings
from app.infrastructure.db.session import session_factory
from app.infrastructure.db.vendor_repo import (
    ask_withdraw,
    decide,
    hide_request,
    list_requests,
    load_profile,
    own_products,
    publish_request,
    vendor_stats,
    parser_choices,
    partners,
    process_choices,
    profile_view,
    read_remote_robots,
    robots_from_text,
    submit_request,
)

router = APIRouter()
_IMAGE = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
_DOC = {**_IMAGE, "application/pdf": "pdf"}
_NAME = re.compile(r"^[0-9a-f]{32}_[0-9a-f]{32}\.(png|jpg|jpeg|webp|pdf)$")


class RequestIn(BaseModel):
    kind: str
    payload: dict = Field(default_factory=dict)


class DecisionIn(BaseModel):
    status: str
    comment: str = ""


class RobotEdit(BaseModel):
    name: str = ""
    summary: str = ""
    price_rub: float | None = None
    processes: list[str] = Field(default_factory=list)


class PublishIn(BaseModel):
    """Правки администратора перед записью в каталог. Пустые поля не затирают заявку."""

    company_name: str | None = None
    about: str | None = None
    website: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    robots: list[RobotEdit] | None = None


class RemoteIn(BaseModel):
    url: str


def _fail(exc: Exception) -> None:
    if isinstance(exc, KeyError):
        raise HTTPException(404, "Не найдено") from None
    if isinstance(exc, ValueError):
        raise HTTPException(422, str(exc)) from None
    raise exc


@router.get("/api/v1/catalog/partners", tags=["Каталог"], summary="Производители, чьи роботы уже стоят в каталоге")
def catalog_partners() -> dict:
    with session_factory()() as db:
        items = partners(db)
    return {"total": len(items), "items": items}


@router.get("/api/v1/vendor/me", tags=["Вендор"], summary="Профиль вендора и число его заявок")
def vendor_me(user: SessionUser = Depends(require_vendor)) -> dict:
    with session_factory()() as db:
        try:
            row = load_profile(db, user.id)
        except KeyError:
            raise HTTPException(404, "Профиль вендора не заведён") from None
        pending = sum(1 for item in list_requests(db, user.id, audience="vendor") if item["status"] == "pending")
        return {"login": user.login, "profile": profile_view(row), "pending": pending}


@router.get("/api/v1/vendor/stats", tags=["Вендор"], summary="Сколько карточек, процессов и показов в подборе, без данных заказчиков")
def vendor_statistics(user: SessionUser = Depends(require_vendor)) -> dict:
    with session_factory()() as db:
        try:
            row = load_profile(db, user.id)
        except KeyError:
            raise HTTPException(404, "Профиль производителя не найден") from None
        return vendor_stats(db, row.manufacturer)


@router.get("/api/v1/vendor/products", tags=["Вендор"], summary="Роботы этого производителя в каталоге")
def vendor_products(user: SessionUser = Depends(require_vendor)) -> list[dict]:
    with session_factory()() as db:
        try:
            row = load_profile(db, user.id)
        except KeyError:
            raise HTTPException(404, "Профиль вендора не заведён") from None
        return own_products(db, row.manufacturer)


@router.get("/api/v1/vendor/processes", tags=["Вендор"], summary="Процессы, к которым можно привязать робота")
def vendor_processes(user: SessionUser = Depends(require_vendor)) -> list[dict]:
    del user
    with session_factory()() as db:
        return process_choices(db)


@router.get("/api/v1/vendor/parsers", tags=["Вендор"], summary="Открытые источники, которые умеет обходить платформа")
def vendor_parsers(user: SessionUser = Depends(require_vendor)) -> list[dict]:
    del user
    return parser_choices()


@router.get("/api/v1/vendor/requests", tags=["Вендор"], summary="Заявки текущего вендора")
def vendor_requests(user: SessionUser = Depends(require_vendor)) -> list[dict]:
    with session_factory()() as db:
        return list_requests(db, user.id, audience="vendor")


@router.post("/api/v1/vendor/requests/{request_id}/withdraw", tags=["Вендор"], summary="Попросить отозвать заявку. В каталог это попадёт только после подтверждения")
def vendor_withdraw(request_id: UUID, user: SessionUser = Depends(require_vendor)) -> dict:
    with session_factory()() as db:
        try:
            return ask_withdraw(db, user.id, request_id)
        except Exception as exc:
            _fail(exc)


@router.post("/api/v1/vendor/requests/{request_id}/hide", tags=["Вендор"], summary="Убрать закрытую заявку из списка вендора")
def vendor_hide(request_id: UUID, user: SessionUser = Depends(require_vendor)) -> dict:
    with session_factory()() as db:
        try:
            hide_request(db, request_id, audience="vendor", user_id=user.id)
        except Exception as exc:
            _fail(exc)
    return {"ok": True}


@router.post("/api/v1/vendor/requests", tags=["Вендор"], summary="Отправить изменение на проверку администратору")
def vendor_submit(body: RequestIn, user: SessionUser = Depends(require_vendor)) -> dict:
    with session_factory()() as db:
        try:
            return submit_request(db, user.id, body.kind, body.payload)
        except Exception as exc:
            _fail(exc)


@router.post("/api/v1/vendor/preview-url", tags=["Вендор"], summary="Прочитать JSON с сайта вендора, не публикуя его")
def vendor_preview_url(body: RemoteIn, user: SessionUser = Depends(require_vendor)) -> dict:
    with session_factory()() as db:
        try:
            robots = read_remote_robots(db, user.id, body.url)
        except Exception as exc:
            _fail(exc)
    return {"robots": robots}


@router.post("/api/v1/vendor/preview-file", tags=["Вендор"], summary="Разобрать JSON или таблицу, не публикуя её")
async def vendor_preview_file(
    file: UploadFile = File(...),
    user: SessionUser = Depends(require_vendor),
) -> dict:
    name = (file.filename or "").lower()
    fmt = "json" if name.endswith(".json") else "csv" if name.endswith(".csv") else ""
    if not fmt:
        raise HTTPException(422, "Нужен файл .json или .csv")
    raw = await file.read()
    if len(raw) > 2_000_000:
        raise HTTPException(413, "Файл больше 2 МБ")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(422, "Файл должен быть в кодировке UTF-8") from exc
    with session_factory()() as db:
        try:
            robots = robots_from_text(db, user.id, text, fmt)
        except Exception as exc:
            _fail(exc)
    return {"robots": robots}


@router.post("/api/v1/vendor/files", tags=["Вендор"], summary="Положить логотип или документ. В профиль он попадёт после подтверждения заявки.")
async def vendor_file(
    file: UploadFile = File(...),
    kind: str = Form("doc"),
    user: SessionUser = Depends(require_vendor),
) -> dict:
    allowed = _IMAGE if kind == "logo" else _DOC
    extension = allowed.get(file.content_type or "")
    if extension is None:
        raise HTTPException(422, "Логотип: PNG, JPG или WebP. Документ: ещё и PDF.")
    payload = await file.read()
    limit = 2 * 1024 * 1024 if kind == "logo" else 8 * 1024 * 1024
    if len(payload) > limit:
        raise HTTPException(413, "Файл слишком большой")
    folder = Path(get_settings().upload_dir) / "vendors"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{user.id.hex}_{uuid4().hex}.{extension}"
    (folder / name).write_bytes(payload)
    return {"filename": name, "url": f"/platform/api/v1/vendor-files/{name}"}


@router.get("/api/v1/vendor-files/{name}", tags=["Вендор"], summary="Отдать файл вендора владельцу или администратору")
def vendor_file_get(name: str, user: SessionUser = Depends(require_vendor)) -> FileResponse:
    return _send_file(name, user)


@router.get("/api/v1/admin/vendor-files/{name}", tags=["Админка · вендоры"], summary="Отдать файл вендора из заявки")
def admin_vendor_file(name: str, user: SessionUser = Depends(require_admin)) -> FileResponse:
    return _send_file(name, user)


def _send_file(name: str, user: SessionUser) -> FileResponse:
    if not _NAME.match(name):
        raise HTTPException(404, "Файл не найден")
    if user.role != "admin" and not name.startswith(f"{user.id.hex}_"):
        raise HTTPException(403, "Это файл другого вендора")
    path = Path(get_settings().upload_dir) / "vendors" / name
    if not path.is_file():
        raise HTTPException(404, "Файл не найден")
    return FileResponse(path)


@router.get("/api/v1/admin/vendor-requests", tags=["Админка · вендоры"], summary="Очередь заявок вендоров")
def admin_vendor_requests(user: SessionUser = Depends(require_admin)) -> list[dict]:
    del user
    with session_factory()() as db:
        return list_requests(db)


@router.post("/api/v1/admin/vendor-requests/{request_id}/hide", tags=["Админка · вендоры"], summary="Убрать закрытую заявку из списка администратора")
def admin_vendor_hide(request_id: UUID, user: SessionUser = Depends(require_admin)) -> dict:
    del user
    with session_factory()() as db:
        try:
            hide_request(db, request_id, audience="admin")
        except Exception as exc:
            _fail(exc)
    return {"ok": True}


@router.post("/api/v1/admin/vendor-requests/{request_id}/apply", tags=["Админка · вендоры"], summary="Записать принятую заявку в каталог. До кнопки каталог не меняется")
def admin_vendor_apply(request_id: UUID, body: PublishIn, user: SessionUser = Depends(require_admin)) -> dict:
    del user
    with session_factory()() as db:
        try:
            return publish_request(db, request_id, body.model_dump())
        except Exception as exc:
            _fail(exc)


@router.post("/api/v1/admin/vendor-requests/{request_id}", tags=["Админка · вендоры"], summary="Подтвердить, отклонить или вернуть заявку на доработку")
def admin_vendor_decide(request_id: UUID, body: DecisionIn, user: SessionUser = Depends(require_admin)) -> dict:
    del user
    with session_factory()() as db:
        try:
            return decide(db, request_id, body.status, body.comment)
        except Exception as exc:
            _fail(exc)
