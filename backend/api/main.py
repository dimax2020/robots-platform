from contextlib import asynccontextmanager

import redis
from fastapi import FastAPI

from api.config import get_settings
from api.routers import calc
from engine import ENGINE_VERSION
from engine.models import Catalog


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    # Каталог, правила и нормативы грузятся один раз и живут в app.state (§11.1).
    # Пока каталог пустой — загрузка из БД появится на этапе E1.
    app.state.catalog = Catalog(version_id=0)
    app.state.cache = redis.from_url(settings.redis_url, decode_responses=True)
    yield
    app.state.cache.close()


app = FastAPI(
    title="Платформа подбора роботизированных решений",
    version=ENGINE_VERSION,
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    lifespan=lifespan,
)

app.include_router(calc.router, prefix="/api/v1")


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "engine_version": ENGINE_VERSION}
