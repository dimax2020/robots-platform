from unittest.mock import MagicMock

from api.db.models import AppUser
from api.deps import DEMO_USER_ID, DEMO_USER_LOGIN
from scripts.seed import seed_demo_user


def test_seed_demo_user_reuses_existing() -> None:
    existing = AppUser(
        id=DEMO_USER_ID,
        login=DEMO_USER_LOGIN,
        password_hash="already",
        role="admin",
    )
    db = MagicMock()
    db.scalar.return_value = existing
    assert seed_demo_user(db) is existing
    db.add.assert_not_called()


def test_seed_demo_user_creates_admin() -> None:
    db = MagicMock()
    db.scalar.return_value = None
    user = seed_demo_user(db)
    assert user.id == DEMO_USER_ID
    assert user.login == DEMO_USER_LOGIN
    assert user.role == "admin"
    assert user.password_hash
    db.add.assert_called_once()
    db.flush.assert_called_once()
