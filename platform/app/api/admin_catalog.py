"""Админка: иерархия каталога, отрасли и типы решений."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.infrastructure.db.catalog_repo import (
    assign_type,
    delete_industry,
    delete_solution_type,
    delete_type_rule,
    hierarchy,
    industries,
    save_industry,
    save_solution_type,
    solution_types,
    source_registry,
    type_rules,
    untyped_groups,
)
from app.infrastructure.db.job_repo import recent_jobs
from app.infrastructure.db.product_repo import public_solution_types
from app.infrastructure.db.session import session_factory

router = APIRouter()


class IndustryIn(BaseModel):
    code: str | None = None
    name: str
    objects: list[str] = Field(default_factory=list)


class SolutionTypeIn(BaseModel):
    code: str | None = None
    name: str
    group: str = ""
    family: str = ""


class AssignTypeIn(BaseModel):
    solution_type: str | None = None
    slugs: list[str] = Field(default_factory=list)
    raw_key: str | None = None
    remember: bool = False


@router.get("/api/v1/catalog/solution-types", tags=["Каталог"], summary="Типы решений, у которых есть продукты")
def catalog_solution_types() -> list:
    with session_factory()() as db:
        return public_solution_types(db)


@router.get("/api/v1/admin/catalog/tree", tags=["Админка · каталог"], summary="Дерево: отрасль, объект, процесс, тип решения и счётчики")
def admin_catalog_tree() -> dict:
    with session_factory()() as db:
        return hierarchy(db)


@router.get("/api/v1/admin/industries", tags=["Админка · каталог"], summary="Список отраслей")
def admin_industries() -> list:
    with session_factory()() as db:
        return industries(db)


@router.post("/api/v1/admin/industries", tags=["Админка · каталог"], summary="Создать или обновить отрасль и её объекты")
def admin_industry_save(body: IndustryIn) -> dict:
    with session_factory()() as db:
        try:
            return save_industry(db, code=body.code, name=body.name, objects=body.objects)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None


@router.delete("/api/v1/admin/industries/{code}", tags=["Админка · каталог"], summary="Удалить отрасль")
def admin_industry_delete(code: str) -> dict:
    with session_factory()() as db:
        try:
            delete_industry(db, code)
        except KeyError:
            raise HTTPException(404, "Отрасль не найдена") from None
    return {"deleted": code}


@router.get("/api/v1/admin/solution-types", tags=["Админка · каталог"], summary="Все типы решений, включая пустые")
def admin_solution_types() -> list:
    with session_factory()() as db:
        return solution_types(db)


@router.post("/api/v1/admin/solution-types", tags=["Админка · каталог"], summary="Создать или обновить тип решения")
def admin_solution_type_save(body: SolutionTypeIn) -> dict:
    with session_factory()() as db:
        try:
            return save_solution_type(db, code=body.code, name=body.name, group=body.group, family=body.family)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None


@router.delete("/api/v1/admin/solution-types/{code}", tags=["Админка · каталог"], summary="Удалить тип решения")
def admin_solution_type_delete(code: str) -> dict:
    with session_factory()() as db:
        try:
            delete_solution_type(db, code)
        except KeyError:
            raise HTTPException(404, "Тип не найден") from None
    return {"deleted": code}


@router.get("/api/v1/admin/solution-types/untyped", tags=["Админка · каталог"], summary="Продукты и категории, которым ещё не назначен тип")
def admin_untyped() -> list:
    with session_factory()() as db:
        return untyped_groups(db)


@router.post("/api/v1/admin/solution-types/assign", tags=["Админка · каталог"], summary="Назначить тип продуктам или целой категории сайта")
def admin_assign_type(body: AssignTypeIn) -> dict:
    if not body.slugs and body.raw_key is None:
        raise HTTPException(422, "Выберите продукты или категорию")
    with session_factory()() as db:
        try:
            changed = assign_type(db, code=body.solution_type, slugs=body.slugs, raw=body.raw_key, remember=body.remember)
        except KeyError:
            raise HTTPException(404, "Тип не найден") from None
    return {"changed": changed}


@router.get("/api/v1/admin/overview", tags=["Админка · каталог"], summary="Сводка: объёмы каталога и очередь прогонов")
def admin_overview() -> dict:
    from app.infrastructure.db.overview_repo import overview

    with session_factory()() as db:
        return overview(db)


@router.get("/api/v1/admin/sources", tags=["Админка · каталог"], summary="Реестр источников значений характеристик")
def admin_sources() -> list:
    with session_factory()() as db:
        return source_registry(db)


@router.get("/api/v1/admin/jobs", tags=["Админка · каталог"], summary="Последние прогоны импорта и парсеров")
def admin_jobs(kind: str = "", limit: int = 20) -> list:
    with session_factory()() as db:
        return recent_jobs(db, prefix=kind, limit=max(1, min(limit, 100)))


@router.get("/api/v1/admin/solution-types/rules", tags=["Админка · каталог"], summary="Правила, которые сами ставят тип при следующем импорте")
def admin_type_rules() -> list:
    with session_factory()() as db:
        return type_rules(db)


@router.delete("/api/v1/admin/solution-types/rules", tags=["Админка · каталог"], summary="Забыть правило назначения типа")
def admin_type_rule_delete(raw_key: str) -> dict:
    with session_factory()() as db:
        delete_type_rule(db, raw_key)
    return {"deleted": raw_key}
