"""Создаёт базу platform. Пустую базу наполняет снимком каталога, иначе только догоняет схему."""

from pathlib import Path
import subprocess

import psycopg
from alembic import command
from alembic.config import Config

from app.application.reference_data import seed_reference
from app.application.seed_warehouse import seed
from app.config import get_settings
from app.infrastructure.db.session import session_factory

_LOCK = 481516234


def main() -> None:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    _ensure_database(settings.postgres_admin_url, settings.platform_db_name)
    url = _plain(settings.database_url)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (_LOCK,))
        try:
            if _product_count(conn) > 0:
                _migrate(settings)
                return
            dump = _dump_path()
            if dump.is_file():
                _restore(url, dump)
                _migrate(settings)
                return
            _migrate(settings)
            with session_factory()() as db:
                seed(db)
                seed_reference(db)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (_LOCK,))


def _plain(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://")


def _dump_path() -> Path:
    return Path(__file__).resolve().parents[1] / "seed" / "platform.sql"


def _product_count(conn: psycopg.Connection) -> int:
    exists = conn.execute("SELECT to_regclass('public.product')").fetchone()
    if exists is None or exists[0] is None:
        return 0
    count = conn.execute("SELECT count(*) FROM product").fetchone()
    return int(count[0]) if count else 0


def _migrate(settings) -> None:
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")
    # Метаданные справочника обновляются и для непустой БД.
    from app.application.reference_data import _seed_attribute_meta
    with session_factory()() as db:
        _seed_attribute_meta(db)
        db.commit()


def _restore(url: str, dump: Path) -> None:
    subprocess.run(["psql", url, "-v", "ON_ERROR_STOP=1", "-f", str(dump)], check=True)


def _ensure_database(admin_url: str, name: str) -> None:
    url = admin_url.replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
        if exists is None:
            conn.execute(f'CREATE DATABASE "{name}"')


if __name__ == "__main__":
    main()
