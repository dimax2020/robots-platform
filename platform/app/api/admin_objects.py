"""Админка: объекты, их поля расчёта и справочник полей площадки."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.infrastructure.db.object_repo import (
    create_object,
    delete_site_field,
    form_fields,
    objects_overview,
    save_site_field,
    site_fields,
)
from app.infrastructure.db.session import session_factory
from app.infrastructure.db.taxonomy_repo import object_setup

router = APIRouter()


class NewObjectIn(BaseModel):
    name: str
    industries: list[str] = Field(default_factory=list)
    copy_fields_from: str | None = None
    in_match: bool = True


class SiteFieldIn(BaseModel):
    key: str | None = None
    label: str
    unit: str = ""
    kind: str = "number"
    min: float | None = None
    max: float | None = None
    hint: str = ""


@router.get("/api/v1/catalog/objects/{code}/fields", tags=["Каталог"], summary="Поля формы параметров объекта: подпись, единица, границы")
def catalog_object_fields(code: str) -> dict:
    with session_factory()() as db:
        try:
            return form_fields(db, code)
        except KeyError:
            raise HTTPException(404, "Объект не найден") from None


@router.get("/api/v1/catalog/industries", tags=["Каталог"], summary="Отрасли и их объекты для мастера нового проекта")
def catalog_industries() -> dict:
    """Отрасли и их объекты для мастера нового проекта: без входа, только имена и коды."""
    from sqlalchemy import select

    from app.infrastructure.db.catalog_repo import industries
    from app.infrastructure.db.models import ObjectTypeRow

    with session_factory()() as db:
        names = {row.code: row.name for row in db.scalars(select(ObjectTypeRow).where(ObjectTypeRow.in_match.is_(True)))}
        items = [
            {
                "code": row["code"],
                "name": row["name"],
                "objects": [{"code": code, "name": names[code]} for code in row["objects"] if code in names],
            }
            for row in industries(db)
        ]
        return {"items": items}


@router.get("/api/v1/admin/objects", tags=["Админка · объекты"], summary="Список объектов и краткая настройка")
def admin_objects() -> list:
    with session_factory()() as db:
        return objects_overview(db)


@router.post("/api/v1/admin/objects/new", tags=["Админка · объекты"], summary="Создать объект и при желании скопировать набор полей")
def admin_object_create(body: NewObjectIn) -> dict:
    with session_factory()() as db:
        try:
            code = create_object(db, name=body.name, industries=body.industries, copy_from=body.copy_fields_from, in_match=body.in_match)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return object_setup(db, code)


@router.get("/api/v1/admin/site-fields", tags=["Админка · объекты"], summary="Справочник полей площадки")
def admin_site_fields() -> list:
    with session_factory()() as db:
        return site_fields(db)


@router.post("/api/v1/admin/site-fields", tags=["Админка · объекты"], summary="Создать или обновить поле площадки")
def admin_site_field_save(body: SiteFieldIn) -> dict:
    with session_factory()() as db:
        try:
            return save_site_field(db, body.model_dump())
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None


@router.delete("/api/v1/admin/site-fields/{key}", tags=["Админка · объекты"], summary="Удалить поле площадки, если оно нигде не используется")
def admin_site_field_delete(key: str) -> dict:
    with session_factory()() as db:
        try:
            delete_site_field(db, key)
        except KeyError:
            raise HTTPException(404, "Поле не найдено") from None
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
    return {"deleted": key}
