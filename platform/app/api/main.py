import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.api import admin_catalog, admin_objects, admin_products
from app.api.auth import SessionUser, load_user, optional_user, require_admin, require_user
from app.config import get_settings
from app.domain.layout_items import COUNT_RULES, ROLES, SHAPES
from app.infrastructure.db.job_repo import enqueue, get_job, parser_settings, set_schedule
from app.infrastructure.db.product_repo import get_product, list_products
from app.infrastructure.db.session import session_factory
from app.infrastructure.db.taxonomy_repo import (
    add_process,
    assign_processes,
    attributes,
    create_process,
    copy_project,
    create_demo_project,
    create_project,
    delete_project,
    demo_projects,
    delete_type_norm,
    save_type_norm,
    type_norm_list,
    economy_norm_log,
    preview_economy,
    preview_process,
    process_list,
    economy_norms,
    layout_files_in_use,
    list_projects,
    mark_unused,
    match_object,
    project_layout,
    save_project_layout,
    process_setup,
    project_access,
    project_economy,
    project_view,
    robot_attributes,
    run_match,
    object_setup,
    save_economy_norms,
    save_economy_overrides,
    save_object,
    save_object_setup,
    save_process_setup,
    set_demo_flags,
    tree,
    update_project,
)
from app.parsers import PARSERS

_prefix = get_settings().root_path.rstrip("/")

app = FastAPI(
    title="Платформа каталога",
    version="0.1.0",
    description=(
        "Каталог роботов, подбор под объект и расчёт экономики.\n\n"
        "Снаружи адрес начинается с `/platform`. "
        "Ручки `/admin` требуют cookie `platform_session` и роль admin: её выдаёт вход. "
        "Каталог открыт без сессии. Свой проект читает и меняет владелец; "
        "опубликованное демо открывается всем, а правит его только администратор."
    ),
    openapi_url="/api/v1/openapi.json",
    docs_url="/api/v1/docs",
    redoc_url="/api/v1/redoc",
    servers=[{"url": _prefix}] if _prefix else None,
    openapi_tags=[
        {"name": "Служебное", "description": "Живость сервиса."},
        {"name": "Авторизация", "description": "Вход по логину и паролю. Сессия — httpOnly-cookie platform_session."},
        {"name": "Каталог", "description": "Витрина: карточки, дерево, поля объекта и пробный расчёт без проекта."},
        {"name": "Проекты", "description": "Проекты пользователя и демо-объекты."},
        {"name": "Подбор", "description": "Какие роботы проходят фильтры процессов."},
        {"name": "Экономика", "description": "Бюджет, окупаемость и нормативы."},
        {"name": "Схема", "description": "План расстановки и подложка."},
        {"name": "Админка · каталог", "description": "Отрасли, типы решений, источники и очередь прогонов."},
        {"name": "Админка · объекты", "description": "Объекты, их поля и справочник величин площадки."},
        {"name": "Админка · процессы", "description": "Фильтры, формулы количества и привязка роботов."},
        {"name": "Админка · продукты", "description": "Ручные правки карточек. Следующий импорт их не затирает."},
        {"name": "Админка · демо", "description": "Учебные объекты: публикация и адрес."},
    ],
)
app.include_router(admin_catalog.router)
app.include_router(admin_objects.router)
app.include_router(admin_products.router)

from app.api.auth import router as auth_router

app.include_router(auth_router)


@app.middleware("http")
async def admin_session(request: Request, call_next):
    if request.url.path.startswith("/api/v1/admin"):
        user = load_user(request.cookies.get("platform_session"))
        if user is None:
            return JSONResponse({"detail": "Нужна авторизация"}, status_code=401)
        if user.role != "admin":
            return JSONResponse({"detail": "Нужны права администратора"}, status_code=403)
    return await call_next(request)


def _readable(db, key: str, user: SessionUser | None):
    """Проект по UUID или адресу демо. Опубликованное демо открывается без входа."""
    try:
        project, _ = project_access(db, key, user_id=user.id if user else None, role=user.role if user else None)
    except KeyError:
        raise HTTPException(404, "Проект не найден") from None
    return project


def _writable(db, key: str, user: SessionUser | None):
    """Правки: владелец обычного проекта или администратор; демо правит только администратор."""
    if user is None or user.role == "guest":
        raise HTTPException(401, "Нужна авторизация")
    try:
        project, can_edit = project_access(db, key, user_id=user.id, role=user.role)
    except KeyError:
        raise HTTPException(404, "Проект не найден") from None
    if not can_edit:
        raise HTTPException(403, "Демо-объект только для просмотра. Скопируйте его в свои проекты, чтобы менять.")
    return project


class ObjectIn(BaseModel):
    code: str
    name: str
    industries: list[str] = Field(default_factory=list)
    processes: list[str] = Field(default_factory=list)


class ProcessIn(BaseModel):
    code: str | None = None
    name: str
    objects: list[str] = Field(default_factory=list)


class InputIn(BaseModel):
    key: str
    label: str = ""


class FormulaFilterIn(BaseModel):
    name: str
    mode: str = "hard"
    inputs: list[InputIn] = Field(default_factory=list)
    formula: str = ""


class BindingIn(BaseModel):
    object_code: str
    input_key: str
    site_key: str


class ObjectBindingIn(BaseModel):
    process_code: str
    input_key: str
    site_key: str


class ObjectFieldIn(BaseModel):
    key: str
    label: str = ""
    group: str = ""
    required: bool = False
    default: float | int | bool | str | None = None
    source: str = ""


class ObjectSetupIn(BaseModel):
    name: str | None = None
    industries: list[str] | None = None
    in_match: bool | None = None
    fields: list[ObjectFieldIn] | None = None
    processes: list[str] = Field(default_factory=list)
    bindings: list[ObjectBindingIn] = Field(default_factory=list)


class LayoutItemIn(BaseModel):
    key: str
    label: str
    role: str
    shape: str = "point"
    min_count: int = 1
    count_rule: str = "fixed"
    hint: str = ""


class ProcessSetupIn(BaseModel):
    name: str | None = None
    filters: list[FormulaFilterIn] = Field(default_factory=list)
    count_inputs: list[InputIn] = Field(default_factory=list)
    count_formula: str = ""
    rank_key: str = ""
    rank_order: str = "asc"
    bindings: list[BindingIn] = Field(default_factory=list)
    layout_items: list[LayoutItemIn] | None = None


class PreviewIn(BaseModel):
    object_code: str
    site: dict = Field(default_factory=dict)
    filters: list[FormulaFilterIn] = Field(default_factory=list)
    count_inputs: list[InputIn] = Field(default_factory=list)
    count_formula: str = ""
    rank_key: str = ""
    rank_order: str = "asc"
    bindings: list[BindingIn] = Field(default_factory=list)


class MatchIn(BaseModel):
    site: dict = Field(default_factory=dict)
    tasks: list[dict] | None = None


class EconomyIn(BaseModel):
    site: dict | None = None
    choices: dict[str, str] = Field(default_factory=dict)
    picks: dict[str, str] | None = None
    tasks: list[dict] = Field(default_factory=list)
    preview: dict[str, float] | None = None


class LayoutIn(BaseModel):
    layout: dict


class OverridesIn(BaseModel):
    values: dict[str, float] = Field(default_factory=dict)


class TypeNormIn(BaseModel):
    type_code: str
    key: str
    value: float
    rationale: str = ""
    origin: str = ""


class NormSourceIn(BaseModel):
    rationale: str = ""
    origin: str = ""
    url: str = ""


class NormsIn(BaseModel):
    values: dict[str, float] = Field(default_factory=dict)
    sources: dict[str, NormSourceIn] = Field(default_factory=dict)
    note: str = ""


class AssignIn(BaseModel):
    processes: list[str]


class UsageIn(BaseModel):
    unused: bool


class ProjectIn(BaseModel):
    name: str
    object_code: str
    site: dict = Field(default_factory=dict)


class ProjectPatch(BaseModel):
    site: dict | None = None
    tasks: list | None = None
    enabled: dict[str, bool] | None = None
    reasons: dict[str, str] | None = None


class DemoFlagsIn(BaseModel):
    is_demo: bool | None = None
    published: bool | None = None
    slug: str | None = None
    name: str | None = None


class DemoProjectIn(BaseModel):
    name: str
    object_code: str
    slug: str | None = None


class PreviewMatchIn(BaseModel):
    object_code: str
    site: dict = Field(default_factory=dict)


class PreviewEconomyIn(BaseModel):
    object_code: str
    site: dict = Field(default_factory=dict)
    choices: dict[str, str] = Field(default_factory=dict)
    picks: dict[str, str] | None = None
    tasks: list[dict] = Field(default_factory=list)
    preview: dict[str, float] | None = None


class ScheduleIn(BaseModel):
    enabled: bool | None = None
    hour: int | None = None
    minute: int | None = None


@app.get("/api/v1/health", tags=["Служебное"], summary="Проверка, что сервис отвечает")
def health() -> dict:
    return {"ok": True}


@app.get("/api/v1/catalog/products", tags=["Каталог"], summary="Порция карточек каталога")
def catalog_products(
    cursor: str | None = None,
    limit: int | None = None,
    solution_type: str | None = None,
    process: str | None = None,
    object_code: str | None = None,
) -> dict:
    size = limit or get_settings().list_page_size
    size = max(1, min(size, 100))
    with session_factory()() as db:
        return list_products(db, cursor=cursor, limit=size, solution_type=solution_type, process=process, object_code=object_code)


@app.get("/api/v1/catalog/products/{slug}", tags=["Каталог"], summary="Карточка робота и источники её значений")
def catalog_product(slug: str) -> dict:
    with session_factory()() as db:
        item = get_product(db, slug)
    if item is None:
        raise HTTPException(404, "Карточка не найдена")
    return item


@app.get("/api/v1/catalog/tree", tags=["Каталог"], summary="Отрасли, объекты, процессы и счётчики")
def catalog_tree() -> dict:
    with session_factory()() as db:
        return tree(db)


@app.get("/api/v1/admin/robot-attributes", tags=["Админка · процессы"], summary="Характеристики роботов, которые читает фильтр процесса")
def admin_robot_attributes(process: str | None = None) -> list:
    with session_factory()() as db:
        return robot_attributes(db, process)


@app.get("/api/v1/admin/attributes", tags=["Админка · продукты"], summary="Характеристики каталога и пометки, используются ли они")
def admin_attributes() -> list:
    with session_factory()() as db:
        return attributes(db)


@app.post("/api/v1/admin/attributes/{key}/usage", tags=["Админка · продукты"], summary="Отложить характеристику или вернуть её в работу")
def admin_usage(key: str, body: UsageIn) -> dict:
    with session_factory()() as db:
        try:
            mark_unused(db, key, body.unused)
        except KeyError:
            raise HTTPException(404, "Характеристика не найдена") from None
    return {"key": key, "unused": body.unused}


@app.post("/api/v1/admin/imports", tags=["Админка · каталог"], summary="Поставить в очередь импорт CSV каталога или ручной таблицы")
async def admin_import(kind: str = Form(...), file: UploadFile = File(...)) -> dict:
    if kind not in {"catalog", "manual"}:
        raise HTTPException(422, "Вид файла: catalog или manual")
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    payload = await file.read()
    job_id = uuid4()
    path = Path(settings.upload_dir) / f"{job_id}.csv"
    path.write_bytes(payload)
    with session_factory()() as db:
        job = enqueue(db, kind=f"import_{kind}", parser_code="", file_path=str(path), job_id=job_id)
    if job is None:
        path.unlink(missing_ok=True)
        raise HTTPException(409, "Такой импорт уже выполняется")
    return {"job_id": str(job.id)}


@app.get("/api/v1/admin/jobs/{job_id}", tags=["Админка · каталог"], summary="Статус одного прогона импорта или парсера")
def admin_job(job_id: UUID) -> dict:
    with session_factory()() as db:
        item = get_job(db, job_id)
    if item is None:
        raise HTTPException(404, "Прогон не найден")
    return item


@app.get("/api/v1/admin/parsers", tags=["Админка · каталог"], summary="Парсеры: расписание и последнее состояние")
def admin_parsers() -> list:
    meta = {code: (title, summary) for code, (title, summary, _runner) in PARSERS.items()}
    with session_factory()() as db:
        rows = parser_settings(db)
    result = []
    for row in rows:
        title, summary = meta.get(row["code"], (row["code"], ""))
        result.append({**row, "title": title, "summary": summary})
    return result


@app.post("/api/v1/admin/parsers/{code}/runs", tags=["Админка · каталог"], summary="Запустить парсер вручную")
def admin_parser_run(code: str) -> dict:
    if code not in PARSERS:
        raise HTTPException(404, "Парсер не найден")
    with session_factory()() as db:
        job = enqueue(db, kind="parser", parser_code=code)
    if job is None:
        raise HTTPException(409, "Этот парсер уже выполняется")
    return {"job_id": str(job.id)}


@app.patch("/api/v1/admin/parsers/{code}", tags=["Админка · каталог"], summary="Включить парсер и задать час запуска по Москве")
def admin_parser_schedule(code: str, body: ScheduleIn) -> dict:
    if body.hour is not None and not 0 <= body.hour <= 23:
        raise HTTPException(422, "Час от 0 до 23")
    if body.minute is not None and not 0 <= body.minute <= 59:
        raise HTTPException(422, "Минуты от 0 до 59")
    with session_factory()() as db:
        try:
            return set_schedule(db, code, enabled=body.enabled, hour=body.hour, minute=body.minute)
        except KeyError:
            raise HTTPException(404, "Парсер не найден") from None


@app.get("/api/v1/admin/objects/{code}", tags=["Админка · объекты"], summary="Настройка объекта: поля, процессы и привязки")
def admin_object_read(code: str) -> dict:
    with session_factory()() as db:
        try:
            return object_setup(db, code)
        except KeyError:
            raise HTTPException(404, "Объект не найден") from None


@app.put("/api/v1/admin/objects/{code}/setup", tags=["Админка · объекты"], summary="Сохранить настройку объекта")
def admin_object_setup(code: str, body: ObjectSetupIn) -> dict:
    with session_factory()() as db:
        try:
            return save_object_setup(db, code, body.model_dump())
        except KeyError:
            raise HTTPException(404, "Объект не найден") from None


@app.post("/api/v1/admin/objects", tags=["Админка · объекты"], summary="Создать объект по коду и названию")
def admin_object(body: ObjectIn) -> dict:
    with session_factory()() as db:
        save_object(db, code=body.code, name=body.name, industries=body.industries, processes=body.processes)
        return tree(db)


@app.get("/api/v1/admin/processes", tags=["Админка · процессы"], summary="Список процессов и готовность настройки")
def admin_process_list() -> list:
    with session_factory()() as db:
        return process_list(db)


@app.post("/api/v1/admin/processes", tags=["Админка · процессы"], summary="Создать процесс по названию или добавить по коду")
def admin_process(body: ProcessIn) -> dict:
    with session_factory()() as db:
        if body.code:
            add_process(db, code=body.code, name=body.name)
            return process_setup(db, body.code)
        try:
            code = create_process(db, name=body.name, objects=body.objects)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return process_setup(db, code)


@app.post("/api/v1/admin/processes/{code}/preview", tags=["Админка · процессы"], summary="Прогнать подбор на данных площадки, не сохраняя настройку")
def admin_process_preview(code: str, body: PreviewIn) -> dict:
    with session_factory()() as db:
        try:
            return preview_process(db, code, body.model_dump())
        except KeyError:
            raise HTTPException(404, "Процесс или объект не найден") from None


@app.get("/api/v1/admin/processes/{code}", tags=["Админка · процессы"], summary="Фильтры, количество, ранжирование и схема процесса")
def admin_process_read(code: str) -> dict:
    with session_factory()() as db:
        try:
            return process_setup(db, code)
        except KeyError:
            raise HTTPException(404, "Процесс не найден") from None


@app.get("/api/v1/layout-items/dictionary", tags=["Схема"], summary="Роли, фигуры и правила количества для элементов схемы")
def layout_items_dictionary() -> dict:
    return {"roles": ROLES, "shapes": SHAPES, "count_rules": COUNT_RULES}


@app.put("/api/v1/admin/processes/{code}/setup", tags=["Админка · процессы"], summary="Сохранить настройку процесса")
def admin_process_setup(code: str, body: ProcessSetupIn) -> dict:
    with session_factory()() as db:
        try:
            return save_process_setup(db, code, body.model_dump())
        except KeyError:
            raise HTTPException(404, "Процесс не найден") from None


@app.put("/api/v1/admin/products/{slug}/processes", tags=["Админка · продукты"], summary="Назначить карточке список процессов")
def admin_assign(slug: str, body: AssignIn) -> dict:
    with session_factory()() as db:
        try:
            assign_processes(db, slug, body.processes)
        except KeyError:
            raise HTTPException(404, "Карточка не найдена") from None
    return {"slug": slug, "processes": body.processes}


@app.post("/api/v1/catalog/preview/match", tags=["Подбор"], summary="Подбор роботов по объекту и площадке без сохранённого проекта")
def catalog_preview_match(body: PreviewMatchIn) -> dict:
    with session_factory()() as db:
        try:
            return match_object(db, body.object_code, body.site)
        except KeyError:
            raise HTTPException(404, "Объект не найден") from None


@app.post("/api/v1/catalog/preview/economy", tags=["Экономика"], summary="Экономика по объекту и площадке без сохранённого проекта")
def catalog_preview_economy(body: PreviewEconomyIn) -> dict:
    with session_factory()() as db:
        try:
            return preview_economy(db, body.object_code, body.site, body.choices, body.tasks, body.preview, body.picks)
        except KeyError:
            raise HTTPException(404, "Объект не найден") from None


@app.get("/api/v1/projects", tags=["Проекты"], summary="Проекты текущего пользователя")
def projects(user: SessionUser = Depends(require_user)) -> dict:
    with session_factory()() as db:
        return {"items": list_projects(db, user_id=user.id, role=user.role)}


@app.get("/api/v1/projects/demo", tags=["Проекты"], summary="Опубликованные демо-объекты, доступны без входа")
def published_demos() -> dict:
    """Опубликованные демо-объекты: видны всем, включая гостей."""
    with session_factory()() as db:
        return {"items": demo_projects(db)}


@app.get("/api/v1/admin/projects/demo", tags=["Админка · демо"], summary="Все демо, включая ещё не опубликованные")
def admin_demos(_: SessionUser = Depends(require_admin)) -> dict:
    with session_factory()() as db:
        return {"items": demo_projects(db, include_unpublished=True)}


@app.post("/api/v1/admin/projects/demo", tags=["Админка · демо"], summary="Создать демо-проект")
def admin_demo_create(body: DemoProjectIn, user: SessionUser = Depends(require_admin)) -> dict:
    with session_factory()() as db:
        try:
            return create_demo_project(db, name=body.name, object_code=body.object_code, slug=body.slug, owner_id=user.id)
        except KeyError:
            raise HTTPException(404, "Объект не найден") from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None


@app.put("/api/v1/admin/projects/{project_id}/demo", tags=["Админка · демо"], summary="Публикация, адрес и название демо")
def admin_demo_flags(project_id: UUID, body: DemoFlagsIn, _: SessionUser = Depends(require_admin)) -> dict:
    with session_factory()() as db:
        try:
            return set_demo_flags(db, project_id, is_demo=body.is_demo, published=body.published, slug=body.slug, name=body.name)
        except KeyError:
            raise HTTPException(404, "Проект не найден") from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None


@app.post("/api/v1/projects", tags=["Проекты"], summary="Создать проект")
def create(body: ProjectIn, user: SessionUser = Depends(require_user)) -> dict:
    with session_factory()() as db:
        try:
            return create_project(db, name=body.name, object_code=body.object_code, site=body.site, owner_id=user.id)
        except KeyError:
            raise HTTPException(404, "Объект не найден") from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None


@app.get("/api/v1/projects/{project_key}", tags=["Проекты"], summary="Площадка проекта, процессы и можно ли его менять")
def read_project(project_key: str, user: SessionUser | None = Depends(optional_user)) -> dict:
    with session_factory()() as db:
        project = _readable(db, project_key, user)
        view = project_view(db, project.id)
        view["can_edit"] = bool(user) and (user.role == "admin" or (not project.is_demo and user.role != "guest"))
        return view


@app.patch("/api/v1/projects/{project_key}", tags=["Проекты"], summary="Сохранить площадку, задачи и включённые процессы")
def patch_project(project_key: str, body: ProjectPatch, user: SessionUser | None = Depends(optional_user)) -> dict:
    with session_factory()() as db:
        project = _writable(db, project_key, user)
        view = update_project(db, project.id, site=body.site, enabled=body.enabled, tasks=body.tasks, reasons=body.reasons)
        view["can_edit"] = True
        return view


@app.post("/api/v1/projects/{project_key}/copy", tags=["Проекты"], summary="Скопировать проект или демо себе")
def copy(project_key: str, user: SessionUser = Depends(require_user)) -> dict:
    """Копия доступна владельцу, администратору и любому вошедшему — для опубликованного демо."""
    with session_factory()() as db:
        project = _readable(db, project_key, user)
        return copy_project(db, project.id, owner_id=user.id)


@app.delete("/api/v1/projects/{project_key}", tags=["Проекты"], summary="Удалить проект и неиспользуемые подложки схемы")
def remove_project(project_key: str, user: SessionUser | None = Depends(optional_user)) -> dict:
    with session_factory()() as db:
        project = _writable(db, project_key, user)
        names = delete_project(db, project.id)
        used = layout_files_in_use(db)
    folder = Path(get_settings().upload_dir) / "layouts"
    for name in names - used:
        path = folder / name
        if path.is_file():
            path.unlink()
    return {"ok": True}


@app.post("/api/v1/projects/{project_key}/match", tags=["Подбор"], summary="Подобрать роботов под процессы проекта")
def match_project(project_key: str, body: MatchIn | None = None, user: SessionUser | None = Depends(optional_user)) -> dict:
    with session_factory()() as db:
        project = _readable(db, project_key, user)
        return run_match(
            db,
            project.id,
            site=None if body is None else body.site,
            tasks=None if body is None else body.tasks,
        )


@app.post("/api/v1/projects/{project_key}/economy", tags=["Экономика"], summary="Посчитать бюджет и окупаемость по выбранным роботам")
def economy_project(project_key: str, body: EconomyIn | None = None, user: SessionUser | None = Depends(optional_user)) -> dict:
    body = body or EconomyIn()
    with session_factory()() as db:
        project = _readable(db, project_key, user)
        return project_economy(db, project.id, body.site, body.choices, body.tasks, body.preview, body.picks)


@app.get("/api/v1/projects/{project_key}/layout", tags=["Схема"], summary="Схема расстановки проекта")
def layout_read(project_key: str, user: SessionUser | None = Depends(optional_user)) -> dict:
    with session_factory()() as db:
        project = _readable(db, project_key, user)
        return {"layout": project_layout(db, project.id)}


@app.put("/api/v1/projects/{project_key}/layout", tags=["Схема"], summary="Сохранить схему расстановки")
def layout_save(project_key: str, body: LayoutIn, user: SessionUser | None = Depends(optional_user)) -> dict:
    with session_factory()() as db:
        project = _writable(db, project_key, user)
        return {"layout": save_project_layout(db, project.id, body.layout)}


_IMAGE_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
_LAYOUT_FILE = re.compile(r"^[0-9a-f-]{36}\.(png|jpg|webp)$")


@app.post("/api/v1/projects/{project_key}/layout/background", tags=["Схема"], summary="Загрузить подложку схемы: PNG, JPG или WebP до 20 МБ")
async def layout_background(project_key: str, file: UploadFile = File(...), user: SessionUser | None = Depends(optional_user)) -> dict:
    extension = _IMAGE_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(422, "Нужна картинка PNG, JPG или WebP")
    payload = await file.read()
    if len(payload) > 20 * 1024 * 1024:
        raise HTTPException(413, "Картинка больше 20 МБ")
    with session_factory()() as db:
        _writable(db, project_key, user)
    folder = Path(get_settings().upload_dir) / "layouts"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid4()}.{extension}"
    (folder / name).write_bytes(payload)
    return {"name": name, "url": f"/api/v1/layout-files/{name}"}


@app.get("/api/v1/layout-files/{name}", tags=["Схема"], summary="Отдать файл подложки схемы")
def layout_file(name: str) -> FileResponse:
    if not _LAYOUT_FILE.match(name):
        raise HTTPException(404, "Файл не найден")
    path = Path(get_settings().upload_dir) / "layouts" / name
    if not path.is_file():
        raise HTTPException(404, "Файл не найден")
    return FileResponse(path)


@app.put("/api/v1/projects/{project_key}/economy/overrides", tags=["Экономика"], summary="Сохранить ручные значения экономики проекта")
def economy_overrides(project_key: str, body: OverridesIn, user: SessionUser | None = Depends(optional_user)) -> dict:
    with session_factory()() as db:
        project = _writable(db, project_key, user)
        return {"values": save_economy_overrides(db, project.id, body.values)}


@app.get("/api/v1/economy/norms", tags=["Экономика"], summary="Общие нормативы экономики")
def economy_norm_list() -> dict:
    with session_factory()() as db:
        return {"items": economy_norms(db)}


@app.put("/api/v1/admin/economy/norms", tags=["Экономика"], summary="Сохранить нормативы, источники и заметку к изменению")
def economy_norm_save(body: NormsIn) -> dict:
    with session_factory()() as db:
        sources = {key: item.model_dump() for key, item in body.sources.items()}
        return {"items": save_economy_norms(db, body.values, body.note, sources)}


@app.get("/api/v1/admin/economy/type-norms", tags=["Экономика"], summary="Нормативы по типам решений")
def economy_type_norm_list() -> dict:
    with session_factory()() as db:
        return type_norm_list(db)


@app.put("/api/v1/admin/economy/type-norms", tags=["Экономика"], summary="Записать норматив для типа решения")
def economy_type_norm_save(body: TypeNormIn) -> dict:
    with session_factory()() as db:
        try:
            save_type_norm(db, type_code=body.type_code, key=body.key, value=body.value, rationale=body.rationale, origin=body.origin)
        except KeyError:
            raise HTTPException(404, "Тип решения не найден") from None
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        return type_norm_list(db)


@app.delete("/api/v1/admin/economy/type-norms", tags=["Экономика"], summary="Удалить норматив типа решения")
def economy_type_norm_delete(type_code: str, key: str) -> dict:
    with session_factory()() as db:
        try:
            delete_type_norm(db, type_code=type_code, key=key)
        except KeyError:
            raise HTTPException(404, "Тип решения не найден") from None
        return type_norm_list(db)


@app.get("/api/v1/admin/economy/norms/log", tags=["Экономика"], summary="Журнал изменений нормативов")
def economy_norm_history() -> dict:
    with session_factory()() as db:
        return {"items": economy_norm_log(db)}
