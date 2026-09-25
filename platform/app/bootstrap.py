"""Создаёт базу platform, применяет схему и сид склада. Повторный запуск ничего не ломает."""

from pathlib import Path

import psycopg
from alembic import command
from alembic.config import Config

from app.application.seed_warehouse import seed
from app.config import get_settings
from app.infrastructure.db.session import session_factory


def main() -> None:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    _ensure_database(settings.postgres_admin_url, settings.platform_db_name)
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")
    with session_factory()() as db:
        seed(db)


def _ensure_database(admin_url: str, name: str) -> None:
    url = admin_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
        if exists is None:
            conn.execute(f'CREATE DATABASE "{name}"')


if __name__ == "__main__":
    main()
