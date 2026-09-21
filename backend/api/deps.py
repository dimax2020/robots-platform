from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from api.db.session import session_scope


def get_db() -> Iterator[Session]:
    yield from session_scope()


DbSession = Annotated[Session, Depends(get_db)]
