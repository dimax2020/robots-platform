import hashlib

from fastapi import APIRouter, Request

from api.config import get_settings
from engine.models import CalcRequest, CalcResponse
from engine.pipeline import run_pipeline

router = APIRouter(tags=["calc"])


def _payload_hash(req: CalcRequest) -> str:
    return hashlib.sha256(req.model_dump_json().encode()).hexdigest()[:32]


@router.post("/calculate", response_model=CalcResponse)
def calculate(req: CalcRequest, request: Request) -> CalcResponse:
    # именно def, не async def: тело CPU-bound (§11.1)
    cache = request.app.state.cache
    key = f"calc:{_payload_hash(req)}"
    try:
        if hit := cache.get(key):
            return CalcResponse.model_validate_json(hit)
    except Exception:  # noqa: BLE001 — кэш недоступен: считаем без него
        cache = None

    res = run_pipeline(req, request.app.state.catalog)

    if cache is not None:
        cache.setex(key, get_settings().calc_cache_ttl_s, res.model_dump_json())
    return res
