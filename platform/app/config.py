from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://robots:robots@localhost:5432/platform"
    postgres_admin_url: str = "postgresql+psycopg://robots:robots@localhost:5432/postgres"
    platform_db_name: str = "platform"
    upload_dir: Path = Path("uploads")
    job_stale_s: int = 1800
    list_page_size: int = 24
    session_secret: str = "platform-demo-session-secret"
    # Внешний префикс за Traefik. Пустой — если uvicorn открыт напрямую, без /platform.
    root_path: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
