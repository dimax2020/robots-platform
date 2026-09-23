import asyncio
from contextlib import asynccontextmanager, suppress
import logging


import redis
from fastapi import FastAPI

from api.config import get_settings
from api.db.session import get_sessionmaker
from api.routers import admin, calc, catalog, projects
from api.services.catalog import load_engine_catalog
from engine import ENGINE_VERSION
from engine.models import Catalog


async def watch_catalog(app: FastAPI, marker, seen):
    def refresh():
        with get_sessionmaker()() as db:
            return load_engine_catalog(db)

    while True:
        await asyncio.sleep(30)
        try:
            current = marker.read_text() if marker.exists() else None
            if current != seen:
                app.state.catalog = await asyncio.to_thread(refresh)
                seen = current
        except Exception:
            logging.getLogger(__name__).exception("Не удалось обновить каталог после импорта")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    marker = settings.data_dir / ".catalog-refresh"
    seen = marker.read_text() if marker.exists() else None

    # Каталог грузится один раз и живёт в app.state: ходить в БД на каждое движение
    # ползунка незачем, а падение валидации видно при старте, а не в середине расчёта (§11.1).
    try:
        with get_sessionmaker()() as db:
            app.state.catalog = load_engine_catalog(db)
    except Exception as exc:  # noqa: BLE001 — API должен подниматься и до сида
        print(f"Каталог не загружен ({exc.__class__.__name__}: {exc}). Работаем с пустым снимком.")
        app.state.catalog = Catalog(version_id=0)

    app.state.cache = redis.from_url(settings.redis_url, decode_responses=True)
    watcher = asyncio.create_task(watch_catalog(app, marker, seen))
    try:
        yield
    finally:
        watcher.cancel()
        with suppress(asyncio.CancelledError):
            await watcher
        app.state.cache.close()


app = FastAPI(
    title="Платформа подбора роботизированных решений",
    version=ENGINE_VERSION,
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    lifespan=lifespan,
)

app.include_router(catalog.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(calc.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(projects.refs_router, prefix="/api/v1")


@app.get("/api/v1/health")
def health() -> dict[str, str | int]:
    return {
        "status": "ok",
        "engine_version": ENGINE_VERSION,
        "catalog_version_id": app.state.catalog.version_id,
        "products": len(app.state.catalog.products),
    }
