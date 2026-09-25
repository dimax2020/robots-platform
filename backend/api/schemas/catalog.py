"""Модели ответов каталога.

Презентационных полей здесь нет: картинку и подборку highlights фронтенд выводит сам из кода
типа решения и из attrs. API отдаёт данные и их источники.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from engine.models import AttrValue, Availability, Reliability, SourceKind


class RefOut(BaseModel):
    code: str
    name: str


class AttributeDefOut(BaseModel):
    key: str
    group_code: str
    label: str
    unit: str | None = None
    datatype: str
    enum_values: list[str] | None = None
    required_for: list[str] | None = None
    sort: int | None = None


class SourceOut(BaseModel):
    id: int
    kind: SourceKind
    reliability: Reliability  # выводится из kind, а не хранится (§6.3)
    url: str | None = None
    publisher: str | None = None
    title: str | None = None
    captured_at: date
    rationale: str | None = None
    last_checked_at: datetime | None = None
    usage_count: int = 0  # сколько значений и кейсов на него ссылаются


class CaseOut(BaseModel):
    id: int
    summary: str | None = None
    customer: str | None = None
    process: RefOut | None = None
    source_id: int | None = None


class ProductCard(BaseModel):
    """Компактная карточка для списка и сравнения: без описания и кейсов."""

    id: UUID
    slug: str
    name: str
    manufacturer: str
    legal_entity: str | None = None
    country: str | None = None
    region: str | None = None
    availability: Availability
    trl: int | None = None
    market_potential: int | None = None
    auto_match: bool  # считается: УГТ ≥ 5 и статус не «разработка»
    solution_type: RefOut
    family: str
    processes: list[RefOut] = []
    object_types: list[RefOut] = []
    industries: list[RefOut] = []
    price_rub: float | None = None
    price_note: str | None = None
    completeness_filled: int
    completeness_total: int


class ProductDetail(ProductCard):
    summary: str | None = None
    attrs: dict[str, AttrValue] = {}
    cases: list[CaseOut] = []
    sources: list[SourceOut] = []


class ProductList(BaseModel):
    catalog_version_id: int
    total: int
    products: list[ProductCard]


class TreeNodeOut(BaseModel):
    key: str  # уникальный путь: industry/object/process/solution
    label: str
    level: str  # industry | object_type | process | solution_type
    children: list["TreeNodeOut"] = []
    product_ids: list[UUID] = []


class CatalogTree(BaseModel):
    catalog_version_id: int
    nodes: list[TreeNodeOut]


class AttrPatch(BaseModel):
    """Тело PATCH для добавления ТТХ: значения плюс описание источника."""

    values: dict[str, AttrValue]
    source_kind: SourceKind = "vendor"
    source_url: str | None = None
    source_publisher: str | None = None
    source_title: str | None = None
    rationale: str | None = None  # обязателен для analogue и assumption (§6.4)


class CatalogAttrs(BaseModel):
    """Массовая выдача attrs всех продуктов текущей версии (E4 §2)."""

    catalog_version_id: int
    attrs: dict[str, dict[str, AttrValue]]  # product UUID → key → AttrValue


class CompareParamOut(BaseModel):
    """Один параметр спеки сравнения из data/compare_spec.json (E4 §3)."""

    key: str
    label: str
    unit: str | None = None
    group: Literal["technical", "operational", "economic"]
    origin: Literal["attr", "engine", "derived"]
    better: Literal["max", "min", "none"]
    rationale: str
