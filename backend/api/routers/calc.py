import hashlib

from fastapi import APIRouter, Request

from api.config import get_settings
from engine import ENGINE_VERSION
from engine.models import CalcRequest, CalcResponse
from engine.pipeline import run_pipeline

router = APIRouter(tags=["calc"])


def _payload_hash(req: CalcRequest) -> str:
    return hashlib.sha256(req.model_dump_json().encode()).hexdigest()[:32]


def _schema_hash() -> str:
    """Новое поле в ответе обязано обесценить старые записи кэша:
    иначе pydantic молча подставит default и отдаст ответ прошлой формы."""
    raw = str(CalcResponse.model_json_schema()).encode()
    return hashlib.sha256(raw).hexdigest()[:8]


def execute_calc(req: CalcRequest, request: Request) -> CalcResponse:
    # именно def, не async def: тело CPU-bound (§11.1)
    cache = request.app.state.cache
    catalog = request.app.state.catalog
    # версия движка и версия каталога — часть ключа: правка ТТХ в админке
    # перезагружает снимок, и старый результат обязан перестать отдаваться
    key = f"calc:{ENGINE_VERSION}:{_schema_hash()}:{catalog.version_id}:{_payload_hash(req)}"
    try:
        if hit := cache.get(key):
            return CalcResponse.model_validate_json(hit)
    except Exception:  # noqa: BLE001 — кэш недоступен: считаем без него
        cache = None

    res = run_pipeline(req, catalog)

    if cache is not None:
        cache.setex(key, get_settings().calc_cache_ttl_s, res.model_dump_json())
    return res


@router.post("/calculate", response_model=CalcResponse)
def calculate(req: CalcRequest, request: Request) -> CalcResponse:
    return execute_calc(req, request)
