"""Админка: продукты, покрытие данных по процессу, справочник характеристик."""

import re
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.infrastructure.db.product_admin_repo import (
    admin_products,
    attribute_dictionary,
    coverage,
    create_product,
    patch_product,
    product_detail,
    save_attribute,
    set_image,
    set_process_products,
)
from app.infrastructure.db.session import session_factory

router = APIRouter()

_IMAGE_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
_PRODUCT_FILE = re.compile(r"^[0-9a-f-]{36}\.(png|jpg|webp)$")


class SourceIn(BaseModel):
    kind: str = "vendor"
    publisher: str = ""
    url: str = ""
    title: str = ""
    rationale: str = ""


class AttrIn(BaseModel):
    status: str = "known"
    value: str | float | int | bool | None = None
    quote: str | None = None
    confirmed: bool = False
    label: str | None = None
    unit: str | None = None


class ProductPatch(BaseModel):
    columns: dict[str, str | float | int | None] = Field(default_factory=dict)
    attrs: dict[str, AttrIn | None] = Field(default_factory=dict)
    confirm: dict[str, bool] = Field(default_factory=dict)
    source: SourceIn = Field(default_factory=SourceIn)
    solution_type: str | None = None
    processes: list[str] | None = None
    set_type: bool = False


class NewProductIn(BaseModel):
    name: str
    manufacturer: str | None = None
    solution_type: str | None = None
    source: SourceIn = Field(default_factory=SourceIn)


class ProcessProductsIn(BaseModel):
    add: list[str] = Field(default_factory=list)
    remove: list[str] = Field(default_factory=list)


class AttributeIn(BaseModel):
    label: str | None = None
    unit: str | None = None
    group: str | None = None
    datatype: str | None = None
    sort: int | None = None


@router.get("/api/v1/admin/products")
def admin_product_list(q: str = "", process: str = "", type: str = "", limit: int = 0) -> list:
    with session_factory()() as db:
        return admin_products(db, q=q, process=process, solution_type=type, limit=limit)


@router.post("/api/v1/admin/products")
def admin_product_create(body: NewProductIn) -> dict:
    with session_factory()() as db:
        try:
            slug = create_product(db, name=body.name, manufacturer=body.manufacturer, solution_type=body.solution_type, source=body.source.model_dump())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return product_detail(db, slug)


@router.get("/api/v1/admin/products/{slug}")
def admin_product_read(slug: str) -> dict:
    with session_factory()() as db:
        try:
            return product_detail(db, slug)
        except KeyError:
            raise HTTPException(404, "Карточка не найдена") from None


@router.patch("/api/v1/admin/products/{slug}")
def admin_product_patch(slug: str, body: ProductPatch) -> dict:
    payload = body.model_dump()
    payload["attrs"] = {key: (None if item is None else item) for key, item in payload["attrs"].items()}
    if not body.set_type:
        payload.pop("solution_type")
    with session_factory()() as db:
        try:
            return patch_product(db, slug, payload)
        except KeyError:
            raise HTTPException(404, "Карточка не найдена") from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None


@router.post("/api/v1/admin/products/{slug}/image")
async def admin_product_image(slug: str, file: UploadFile = File(...)) -> dict:
    extension = _IMAGE_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(422, "Нужна картинка PNG, JPG или WebP")
    payload = await file.read()
    if len(payload) > 10 * 1024 * 1024:
        raise HTTPException(413, "Картинка больше 10 МБ")
    folder = Path(get_settings().upload_dir) / "products"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid4()}.{extension}"
    (folder / name).write_bytes(payload)
    url = f"/platform/api/v1/product-files/{name}"
    with session_factory()() as db:
        try:
            set_image(db, slug, url)
        except KeyError:
            (folder / name).unlink(missing_ok=True)
            raise HTTPException(404, "Карточка не найдена") from None
    return {"image_url": url}


@router.get("/api/v1/product-files/{name}")
def product_file(name: str) -> FileResponse:
    if not _PRODUCT_FILE.match(name):
        raise HTTPException(404, "Файл не найден")
    path = Path(get_settings().upload_dir) / "products" / name
    if not path.is_file():
        raise HTTPException(404, "Файл не найден")
    return FileResponse(path)


@router.get("/api/v1/admin/processes/{code}/coverage")
def admin_process_coverage(code: str) -> dict:
    with session_factory()() as db:
        try:
            return coverage(db, code)
        except KeyError:
            raise HTTPException(404, "Процесс не найден") from None


@router.put("/api/v1/admin/processes/{code}/products")
def admin_process_products(code: str, body: ProcessProductsIn) -> dict:
    with session_factory()() as db:
        try:
            changed = set_process_products(db, code, add=body.add, remove=body.remove)
        except KeyError:
            raise HTTPException(404, "Процесс не найден") from None
    return {"changed": changed}


@router.get("/api/v1/admin/attribute-dictionary")
def admin_attribute_dictionary() -> list:
    with session_factory()() as db:
        return attribute_dictionary(db)


@router.patch("/api/v1/admin/attribute-dictionary/{key}")
def admin_attribute_save(key: str, body: AttributeIn) -> dict:
    with session_factory()() as db:
        try:
            return save_attribute(db, key, body.model_dump())
        except KeyError:
            raise HTTPException(404, "Характеристика не найдена") from None
