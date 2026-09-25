"""Проекты и сохранённые прогоны (§7.1). Авторизации нет — owner всегда демо-пользователь."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from api.config import get_settings
from api.db.models import CalcRun, ObjectType, Project
from api.deps import CurrentUser, DbSession
from api.routers.calc import execute_calc
from api.schemas.project import (
    CalculateOut,
    ProjectCreate,
    ProjectOut,
    ProjectPatch,
    SiteProfileRefOut,
)
from engine.models import CalcRequest, CalcResponse, SiteProfile, Task

router = APIRouter(prefix="/projects", tags=["projects"])
refs_router = APIRouter(prefix="/refs", tags=["refs"])


def _profile_path(object_type_code: str):
    return get_settings().data_dir / "site_profiles" / f"{object_type_code}.json"


def _load_profile_file(object_type_code: str) -> dict | None:
    path = _profile_path(object_type_code)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _site_and_tasks(object_type_code: str, *, use_demo: bool) -> tuple[dict, list]:
    """Предзаполнить из data/site_profiles/; нет файла — пустые site и tasks, не падать."""
    empty_site = SiteProfile(object_type_code=object_type_code).model_dump()
    if not use_demo:
        return empty_site, []

    raw = _load_profile_file(object_type_code)
    if raw is None:
        return empty_site, []

    site = SiteProfile.model_validate(raw.get("site") or {"object_type_code": object_type_code})
    tasks = [Task.model_validate(item) for item in (raw.get("tasks") or [])]
    return site.model_dump(), [item.model_dump() for item in tasks]


def _object_type(db: DbSession, code: str) -> ObjectType:
    obj = db.scalar(select(ObjectType).where(ObjectType.code == code))
    if obj is None:
        raise HTTPException(status_code=422, detail=f"Тип объекта не найден: {code}")
    return obj


def _owned_project(db: DbSession, project_id: UUID, user) -> tuple[Project, ObjectType]:
    row = db.execute(
        select(Project, ObjectType)
        .join(ObjectType, ObjectType.id == Project.object_type_id)
        .where(Project.id == project_id, Project.owner_id == user.id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Проект не найден")
    return row[0], row[1]


def _project_out(project: Project, object_type: ObjectType) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        owner_id=project.owner_id,
        name=project.name,
        object_type_code=object_type.code,
        site=project.site,
        tasks=project.tasks,
        overrides=project.overrides or {},
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.post("", response_model=ProjectOut)
def create_project(body: ProjectCreate, db: DbSession, user: CurrentUser) -> ProjectOut:
    object_type = _object_type(db, body.object_type_code)
    site, tasks = _site_and_tasks(body.object_type_code, use_demo=body.use_demo)
    now = datetime.now(timezone.utc)
    project = Project(
        id=uuid4(),
        owner_id=user.id,
        name=body.name,
        object_type_id=object_type.id,
        site=site,
        tasks=tasks,
        overrides={},
        created_at=now,
        updated_at=now,
    )
    db.add(project)
    db.commit()
    return _project_out(project, object_type)


@router.get("", response_model=list[ProjectOut])
def list_projects(db: DbSession, user: CurrentUser) -> list[ProjectOut]:
    rows = db.execute(
        select(Project, ObjectType)
        .join(ObjectType, ObjectType.id == Project.object_type_id)
        .where(Project.owner_id == user.id)
        .order_by(Project.created_at.desc())
    ).all()
    return [_project_out(project, object_type) for project, object_type in rows]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: UUID, db: DbSession, user: CurrentUser) -> ProjectOut:
    project, object_type = _owned_project(db, project_id, user)
    return _project_out(project, object_type)


@router.patch("/{project_id}", response_model=ProjectOut)
def patch_project(
    project_id: UUID, body: ProjectPatch, db: DbSession, user: CurrentUser
) -> ProjectOut:
    project, object_type = _owned_project(db, project_id, user)
    if body.name is not None:
        project.name = body.name
    if body.site is not None:
        project.site = body.site.model_dump()
    if body.tasks is not None:
        project.tasks = [item.model_dump() for item in body.tasks]
    if body.overrides is not None:
        project.overrides = body.overrides
    project.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _project_out(project, object_type)


@router.post("/{project_id}/calculate", response_model=CalculateOut)
def calculate_project(
    project_id: UUID, request: Request, db: DbSession, user: CurrentUser
) -> CalculateOut:
    project, _object_type = _owned_project(db, project_id, user)
    site = SiteProfile.model_validate(project.site)
    horizon = 5
    if site.payback_years is not None:
        horizon = int(round(site.payback_years))
    req = CalcRequest(
        site=site,
        tasks=[Task.model_validate(item) for item in project.tasks],
        overrides=project.overrides or {},
        horizon_years=horizon,
    )
    res = execute_calc(req, request)

    run = CalcRun(
        id=uuid4(),
        project_id=project.id,
        catalog_version_id=res.catalog_version_id,
        engine_version=res.engine_version,
        request=req.model_dump(mode="json"),
        response=res.model_dump(mode="json"),
    )
    db.add(run)
    db.commit()
    return CalculateOut(run_id=run.id, **res.model_dump())


@router.get("/{project_id}/runs/latest", response_model=CalculateOut)
def latest_run(project_id: UUID, db: DbSession, user: CurrentUser) -> CalculateOut:
    project, _object_type = _owned_project(db, project_id, user)
    run = db.scalar(
        select(CalcRun)
        .where(CalcRun.project_id == project.id)
        .order_by(CalcRun.created_at.desc())
        .limit(1)
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Прогон не найден")
    payload = CalcResponse.model_validate(run.response)
    return CalculateOut(run_id=run.id, **payload.model_dump())


@refs_router.get("/site-profiles/{object_type_code}", response_model=SiteProfileRefOut)
def site_profile_ref(object_type_code: str) -> SiteProfileRefOut:
    raw = _load_profile_file(object_type_code)
    if raw is None:
        raise HTTPException(status_code=404, detail="Профиль объекта не найден")
    site = SiteProfile.model_validate(raw.get("site") or {"object_type_code": object_type_code})
    tasks = [Task.model_validate(item) for item in (raw.get("tasks") or [])]
    return SiteProfileRefOut(
        object_type_code=object_type_code,
        name=raw.get("name"),
        site=site,
        tasks=tasks,
    )
