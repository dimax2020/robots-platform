from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://robots:robots@localhost:5432/robots"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-secret-change-in-prod"
    jwt_ttl_minutes: int = 60 * 12
    data_dir: Path = Path("data")
    calc_cache_ttl_s: int = 3600
    sources_check_cron_hour: int = 3  # плановая проверка источников, раз в сутки (§9.4)


@lru_cache
def get_settings() -> Settings:
    return Settings()
