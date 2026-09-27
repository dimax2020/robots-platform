"""Сессия в подписанной httpOnly-cookie. Роль читается из базы на каждом запросе."""

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import select

from app.config import get_settings
from app.infrastructure.db.models import AppUserRow
from app.infrastructure.db.session import session_factory

COOKIE = "platform_session"
MAX_AGE = 7 * 24 * 3600
router = APIRouter()
_hasher = PasswordHasher()


@dataclass(frozen=True)
class SessionUser:
    id: UUID
    login: str
    role: str


class LoginIn(BaseModel):
    login: str
    password: str


def _sign(body: str) -> str:
    secret = get_settings().session_secret.encode()
    return hmac.new(secret, body.encode(), hashlib.sha256).hexdigest()


def _dump_token(user_id: UUID) -> str:
    raw = json.dumps({"uid": str(user_id), "iat": int(time.time())}, separators=(",", ":")).encode()
    body = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return f"{body}.{_sign(body)}"


def read_user_id(token: str | None) -> UUID | None:
    if not token or "." not in token:
        return None
    body, sig = token.rsplit(".", 1)
    if not hmac.compare_digest(_sign(body), sig):
        return None
    padded = body + "=" * (-len(body) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (ValueError, json.JSONDecodeError):
        return None
    issued = data.get("iat") if isinstance(data, dict) else None
    raw = data.get("uid") if isinstance(data, dict) else None
    if not isinstance(issued, int) or not isinstance(raw, str):
        return None
    if int(time.time()) - issued > MAX_AGE:
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


def load_user(token: str | None) -> SessionUser | None:
    user_id = read_user_id(token)
    if user_id is None:
        return None
    with session_factory()() as db:
        row = db.get(AppUserRow, user_id)
        if row is None:
            return None
        return SessionUser(id=row.id, login=row.login, role=row.role)


def optional_user(platform_session: str | None = Cookie(default=None)) -> SessionUser | None:
    return load_user(platform_session)


def require_user(user: SessionUser | None = Depends(optional_user)) -> SessionUser:
    if user is None or user.role == "guest":
        raise HTTPException(401, "Нужна авторизация")
    return user


def require_admin(user: SessionUser | None = Depends(optional_user)) -> SessionUser:
    if user is None:
        raise HTTPException(401, "Нужна авторизация")
    if user.role != "admin":
        raise HTTPException(403, "Нужны права администратора")
    return user


def set_session(response: Response, user_id: UUID) -> None:
    token = _dump_token(user_id)
    response.set_cookie(COOKIE, token, max_age=MAX_AGE, httponly=True, samesite="lax", path="/")


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/")


@router.post("/api/v1/auth/login", tags=["Авторизация"], summary="Войти и записать сессию в cookie")
def login(body: LoginIn, response: Response) -> dict:
    login_name = body.login.strip()
    with session_factory()() as db:
        row = db.scalar(select(AppUserRow).where(AppUserRow.login == login_name))
        if row is None:
            raise HTTPException(401, "Неверный логин или пароль")
        try:
            _hasher.verify(row.password_hash, body.password)
        except (VerifyMismatchError, VerificationError):
            raise HTTPException(401, "Неверный логин или пароль") from None
        user = SessionUser(id=row.id, login=row.login, role=row.role)
    set_session(response, user.id)
    return {"login": user.login, "role": user.role}


@router.post("/api/v1/auth/logout", tags=["Авторизация"], summary="Выйти и стереть cookie сессии")
def logout(response: Response) -> dict:
    clear_session(response)
    return {"ok": True}


@router.get("/api/v1/auth/me", tags=["Авторизация"], summary="Кто сейчас вошёл")
def me(user: SessionUser | None = Depends(optional_user)) -> dict:
    if user is None:
        raise HTTPException(401, "Нужна авторизация")
    return {"login": user.login, "role": user.role}
