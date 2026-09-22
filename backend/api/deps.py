from collections.abc import Iterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.models import AppUser
from api.db.session import session_scope

# Фиксированный демо-пользователь: авторизации в E3 нет (§7.1).
DEMO_USER_ID = UUID("11111111-1111-4111-8111-111111111111")
DEMO_USER_LOGIN = "demo@local"


def get_db() -> Iterator[Session]:
    yield from session_scope()


DbSession = Annotated[Session, Depends(get_db)]


def get_current_user(db: DbSession) -> AppUser:
    """Заглушка до появления авторизации (§0, §7.1): все запросы идут от демо-пользователя."""
    user = db.scalar(
        select(AppUser).where(
            (AppUser.id == DEMO_USER_ID) | (AppUser.login == DEMO_USER_LOGIN)
        )
    )
    if user is None:
        raise HTTPException(
            status_code=503,
            detail="Демо-пользователь не засеян. Выполните: python -m scripts.seed",
        )
    return user


CurrentUser = Annotated[AppUser, Depends(get_current_user)]
