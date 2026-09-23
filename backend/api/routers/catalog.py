from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from api.db.models import Source
from api.deps import DbSession
from api.schemas.catalog import (
    AttributeDefOut,
    CatalogAttrs,
    CatalogTree,
    CompareParamOut,
    ProductDetail,
    ProductList,
    SourceOut,
)
from api.services import catalog as svc

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/attrs", response_model=CatalogAttrs)
def attrs(db: DbSession) -> CatalogAttrs:
    """Массовая выдача характеристик всех продуктов текущей версии (E4 §2)."""
    return svc.catalog_attrs(db)


@router.get("/compare-spec", response_model=list[CompareParamOut])
def compare_spec() -> list[CompareParamOut]:
    """Параметры и направление сравнения из data/compare_spec.json (E4 §3)."""
    try:
        return svc.compare_spec()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/attributes", response_model=list[AttributeDefOut])
def attributes(db: DbSession) -> list[AttributeDefOut]:
    """Справочник характеристик. Из него строятся карточка, сравнение и форма ТТХ (§6.2)."""
    return svc.attribute_defs_out(db)


@router.get("/products", response_model=ProductList)
def products(db: DbSession) -> ProductList:
    cards = svc.product_cards(db)
    return ProductList(
        catalog_version_id=svc.current_version_id(db), total=len(cards), products=cards
    )


@router.get("/products/{key}", response_model=ProductDetail)
def product(key: str, db: DbSession) -> ProductDetail:
    """Карточка по slug или UUID: источник виден на каждом значении (ТЗ 3.3.4)."""
    detail = svc.product_detail(db, key)
    if detail is None:
        raise HTTPException(status_code=404, detail="Решение не найдено")
    return detail


@router.get("/tree", response_model=CatalogTree)
def tree(db: DbSession) -> CatalogTree:
    return CatalogTree(
        catalog_version_id=svc.current_version_id(db), nodes=svc.catalog_tree(db)
    )


@router.get("/sources", response_model=list[SourceOut])
def sources(db: DbSession) -> list[SourceOut]:
    rows = db.scalars(select(Source).order_by(Source.id)).all()
    usage = svc.source_usage(db)
    return [svc.source_out(s, usage.get(s.id, 0)) for s in rows]
