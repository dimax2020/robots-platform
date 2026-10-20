"""Кабинет интегратора и отправка проекта заказчиком. Заявки вендора здесь не решаются."""

import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.auth import SessionUser, optional_user, require_integrator, require_user
from app.config import get_settings
from app.infrastructure.db.integrator_repo import (
    accept_nda,
    add_message,
    decline_request,
    file_allowed,
    leave_feedback,
    list_for_integrator,
    list_for_owner,
    list_messages,
    own_profile,
    public_cards,
    save_profile,
    send_project,
)
from app.infrastructure.db.session import session_factory
from app.infrastructure.db.taxonomy_repo import project_access

router = APIRouter()
_IMAGE = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
_DOC = {**_IMAGE, "application/pdf": "pdf"}
_CHAT = {**_DOC, "text/plain": "txt", "text/csv": "csv"}
_NAME = re.compile(r"^[0-9a-f]{32}_[0-9a-f]{32}\.(png|jpg|jpeg|webp|pdf|txt|csv)$")


class DocIn(BaseModel):
    kind: str = "other"
    title: str = ""
    filename: str = ""


class ProfileIn(BaseModel):
    company_name: str = Field(min_length=1, max_length=200)
    brand: str = ""
    about: str = ""
    website: str = ""
    email: str = ""
    phone: str = ""
    city: str = ""
    address: str = ""
    inn: str = ""
    ogrn: str = ""
    regions: str = ""
    contact_name: str = ""
    experience_years: int | None = None
    specializations: list[str] = Field(default_factory=list)
    documents: list[DocIn] = Field(default_factory=list)
    logo: str | None = None


class SendIn(BaseModel):
    integrator_id: UUID
    note: str = ""


class CommentIn(BaseModel):
    comment: str = ""


def _fail(exc: Exception) -> None:
    if isinstance(exc, KeyError):
        raise HTTPException(404, "Не найдено") from None
    if isinstance(exc, PermissionError):
        raise HTTPException(403, str(exc)) from None
    if isinstance(exc, ValueError):
        raise HTTPException(422, str(exc)) from None
    raise exc


@router.get("/api/v1/integrators", tags=["Интегратор"], summary="Карточки интеграторов для заказчика")
def integrators(user: SessionUser = Depends(require_user)) -> list[dict]:
    del user
    with session_factory()() as db:
        return public_cards(db)


@router.get("/api/v1/integrator/me", tags=["Интегратор"], summary="Своя карточка и текст уведомления")
def integrator_me(user: SessionUser = Depends(require_integrator)) -> dict:
    with session_factory()() as db:
        return own_profile(db, user.id)


@router.put("/api/v1/integrator/profile", tags=["Интегратор"], summary="Сохранить карточку компании")
def integrator_profile(body: ProfileIn, user: SessionUser = Depends(require_integrator)) -> dict:
    with session_factory()() as db:
        try:
            return save_profile(db, user.id, body.model_dump())
        except Exception as exc:
            _fail(exc)


@router.post("/api/v1/integrator/nda", tags=["Интегратор"], summary="Принять уведомление о неразглашении")
def integrator_nda(user: SessionUser = Depends(require_integrator)) -> dict:
    with session_factory()() as db:
        try:
            return accept_nda(db, user.id)
        except Exception as exc:
            _fail(exc)


@router.post("/api/v1/integrator/files", tags=["Интегратор"], summary="Положить логотип или документ в карточку")
async def integrator_file(
    file: UploadFile = File(...),
    kind: str = Form("doc"),
    user: SessionUser = Depends(require_integrator),
) -> dict:
    allowed = _IMAGE if kind == "logo" else _DOC
    return await _store(file, allowed, user, 2 * 1024 * 1024 if kind == "logo" else 8 * 1024 * 1024)


@router.get("/api/v1/integrator/requests", tags=["Интегратор"], summary="Проекты, которые прислали на интеграцию")
def integrator_requests(user: SessionUser = Depends(require_integrator)) -> list[dict]:
    with session_factory()() as db:
        try:
            return list_for_integrator(db, user.id)
        except Exception as exc:
            _fail(exc)


@router.post("/api/v1/integrator/requests/{request_id}/feedback", tags=["Интегратор"], summary="Оставить отзыв по проекту")
def integrator_feedback(request_id: UUID, body: CommentIn, user: SessionUser = Depends(require_integrator)) -> dict:
    with session_factory()() as db:
        try:
            return leave_feedback(db, user.id, request_id, body.comment)
        except Exception as exc:
            _fail(exc)


@router.post("/api/v1/integrator/requests/{request_id}/decline", tags=["Интегратор"], summary="Отклонить проект с комментарием")
def integrator_decline(request_id: UUID, body: CommentIn, user: SessionUser = Depends(require_integrator)) -> dict:
    with session_factory()() as db:
        try:
            return decline_request(db, user.id, request_id, body.comment)
        except Exception as exc:
            _fail(exc)


@router.get("/api/v1/integration/mine", tags=["Интегратор"], summary="Запросы, которые отправил текущий пользователь")
def my_requests(user: SessionUser = Depends(require_user)) -> list[dict]:
    with session_factory()() as db:
        return list_for_owner(db, user.id)


@router.post("/api/v1/projects/{project_key}/integrate", tags=["Интегратор"], summary="Отправить свой проект интегратору")
def integrate_project(project_key: str, body: SendIn, user: SessionUser = Depends(require_user)) -> dict:
    with session_factory()() as db:
        try:
            project, _can_edit = project_access(db, project_key, user_id=user.id, role=user.role)
            return send_project(db, user.id, project, body.integrator_id, body.note)
        except Exception as exc:
            _fail(exc)


@router.get("/api/v1/integration/{request_id}/messages", tags=["Интегратор"], summary="История чата по запросу")
def integration_messages(request_id: UUID, user: SessionUser = Depends(require_user)) -> list[dict]:
    with session_factory()() as db:
        try:
            return list_messages(db, user.id, user.role, request_id)
        except Exception as exc:
            _fail(exc)


@router.post("/api/v1/integration/{request_id}/messages", tags=["Интегратор"], summary="Сообщение или файл в чат")
async def integration_message(
    request_id: UUID,
    text: str = Form(""),
    file: UploadFile | None = File(default=None),
    user: SessionUser = Depends(require_user),
) -> dict:
    files: list[dict] = []
    if file is not None and file.filename:
        saved = await _store(file, _CHAT, user, 8 * 1024 * 1024)
        files.append({"name": saved["filename"], "title": file.filename})
    with session_factory()() as db:
        try:
            return add_message(db, user.id, user.role, request_id, text, files)
        except Exception as exc:
            _fail(exc)


@router.get("/api/v1/integration/files/{name}", tags=["Интегратор"], summary="Файл карточки или чата, если он вам доступен")
def integration_file(name: str, user: SessionUser | None = Depends(optional_user)) -> FileResponse:
    if user is None or user.role == "guest":
        raise HTTPException(401, "Нужна авторизация")
    if not _NAME.match(name):
        raise HTTPException(404, "Файл не найден")
    with session_factory()() as db:
        if not file_allowed(db, user.id, user.role, name):
            raise HTTPException(403, "Этот файл вам не открыт")
    path = Path(get_settings().upload_dir) / "integrators" / name
    if not path.is_file():
        raise HTTPException(404, "Файл не найден")
    return FileResponse(path)


async def _store(file: UploadFile, allowed: dict[str, str], user: SessionUser, limit: int) -> dict:
    extension = allowed.get(file.content_type or "")
    if extension is None:
        # Браузер иногда не присылает тип. Тогда смотрим расширение имени.
        suffix = Path(file.filename or "").suffix.lower().lstrip(".")
        if suffix == "jpeg":
            suffix = "jpg"
        if suffix in set(allowed.values()):
            extension = suffix
    if extension is None:
        raise HTTPException(422, "Подойдут PNG, JPG, WebP, PDF, TXT или CSV.")
    payload = await file.read()
    if len(payload) > limit:
        raise HTTPException(413, "Файл слишком большой")
    folder = Path(get_settings().upload_dir) / "integrators"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{user.id.hex}_{uuid4().hex}.{extension}"
    (folder / name).write_bytes(payload)
    return {"filename": name, "url": f"/platform/api/v1/integration/files/{name}"}
