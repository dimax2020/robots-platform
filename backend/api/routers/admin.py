"""Административные операции над каталогом (§9.5).

Добавление ТТХ пишется в product.attrs напрямую: админ и есть модератор. Очередь
attr_proposal остаётся для импорта и парсера, где подтверждение человеком обязательно (§9.2).
"""

from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from api.db.models import AttributeDef, Product, Source
from api.deps import DbSession
from api.schemas.catalog import AttrPatch, ProductDetail
from api.services import catalog as svc

router = APIRouter(prefix="/admin", tags=["admin"])


def _resolve_source(db: DbSession, patch: AttrPatch) -> Source:
    """Источник у значения обязателен: достоверность выводится из него (§6.3, §6.4)."""
    if patch.source_kind in ("analogue", "assumption") and not patch.rationale:
        raise HTTPException(
            status_code=422,
            detail="Для источника вида «оценка по аналогу» и «допущение команды» обоснование обязательно",
        )

    stmt = select(Source).where(Source.kind == patch.source_kind)
    stmt = (
        stmt.where(Source.url == patch.source_url)
        if patch.source_url
        else stmt.where(Source.url.is_(None), Source.publisher == patch.source_publisher)
    )
    if existing := db.scalar(stmt.limit(1)):
        return existing

    source = Source(
        kind=patch.source_kind,
        url=patch.source_url,
        publisher=patch.source_publisher,
        title=patch.source_title,
        captured_at=date.today(),
        rationale=patch.rationale,
    )
    db.add(source)
    db.flush()
    return source


@router.post("/catalog/reload")
def reload_catalog(request: Request, db: DbSession) -> dict[str, int]:
    """Перечитать снимок каталога в app.state без рестарта процесса (§7.2)."""
    catalog = svc.reload_app_catalog(request.app, db)
    return {
        "catalog_version_id": catalog.version_id,
        "products": len(catalog.products),
    }


@router.patch("/products/{product_id}/attrs", response_model=ProductDetail)
def patch_attrs(product_id: UUID, patch: AttrPatch, request: Request, db: DbSession) -> ProductDetail:
    """Добавить или обновить характеристики продукта.

    В CSV организатора ТТХ нет ни одной, поэтому это основной путь их появления (§12.4).
    Ключи проверяются по attribute_def: параметра вне справочника не существует.
    """
    product = db.scalar(
        select(Product).where(Product.id == product_id, Product.valid_to.is_(None))
    )
    if product is None:
        raise HTTPException(status_code=404, detail="Решение не найдено")
    if not patch.values:
        raise HTTPException(status_code=422, detail="Не передано ни одной характеристики")

    known_keys = set(db.scalars(select(AttributeDef.key)).all())
    if unknown := sorted(set(patch.values) - known_keys):
        raise HTTPException(
            status_code=422,
            detail=f"Характеристик нет в справочнике: {', '.join(unknown)}. "
            "Сначала добавьте их в attribute_def.",
        )

    source = _resolve_source(db, patch)

    attrs = dict(product.attrs)
    for key, value in patch.values.items():
        stored = value.model_dump()
        if stored.get("source_id") is None:
            stored["source_id"] = source.id
        attrs[key] = stored
    product.attrs = attrs

    db.commit()
    svc.reload_app_catalog(request.app, db)
    detail = svc.product_detail(db, str(product_id))
    if detail is None:  # pragma: no cover — продукт только что был на месте
        raise HTTPException(status_code=404, detail="Решение не найдено")
    return detail
