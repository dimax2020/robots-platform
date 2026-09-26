import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.domain.layout_items import COUNT_RULES, ROLES, SHAPES
from app.infrastructure.db.job_repo import enqueue, get_job, parser_settings, set_schedule
from app.infrastructure.db.product_repo import get_product, list_products
from app.infrastructure.db.session import session_factory
from app.infrastructure.db.taxonomy_repo import (
    add_process,
    assign_processes,
    attributes,
    create_project,
    economy_norm_log,
    economy_norms,
    mark_unused,
    project_layout,
    save_project_layout,
    process_setup,
    project_economy,
    project_view,
    replace_filters,
    robot_attributes,
    run_match,
    object_setup,
    save_economy_norms,
    save_economy_overrides,
    save_object,
    save_object_setup,
    save_process_setup,
    tree,
    update_project,
)
from app.parsers import PARSERS

app = FastAPI(title="Платформа каталога", version="0.1.0")


class ObjectIn(BaseModel):
    code: str
    name: str
    industries: list[str] = Field(default_factory=list)
    processes: list[str] = Field(default_factory=list)


class ProcessIn(BaseModel):
    code: str
    name: str


class FilterIn(BaseModel):
    name: str
    object_keys: list[str]
    robot_keys: list[str]
    op: str
    mode: str


class FiltersIn(BaseModel):
    filters: list[FilterIn]


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


class ObjectSetupIn(BaseModel):
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
    filters: list[FormulaFilterIn] = Field(default_factory=list)
    count_inputs: list[InputIn] = Field(default_factory=list)
    count_formula: str = ""
    rank_key: str = ""
    rank_order: str = "asc"
    bindings: list[BindingIn] = Field(default_factory=list)
    layout_items: list[LayoutItemIn] | None = None


class MatchIn(BaseModel):
    site: dict = Field(default_factory=dict)


class EconomyIn(BaseModel):
    site: dict | None = None
    choices: dict[str, str] = Field(default_factory=dict)
    tasks: list[dict] = Field(default_factory=list)
    preview: dict[str, float] | None = None


class LayoutIn(BaseModel):
    layout: dict


class OverridesIn(BaseModel):
    values: dict[str, float] = Field(default_factory=dict)


class NormsIn(BaseModel):
    values: dict[str, float]
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
    enabled: dict[str, bool] | None = None


class ScheduleIn(BaseModel):
    enabled: bool | None = None
    hour: int | None = None
    minute: int | None = None


@app.get("/api/v1/health")
def health() -> dict:
    return {"ok": True}


@app.get("/api/v1/catalog/products")
def catalog_products(cursor: str | None = None, limit: int | None = None) -> dict:
    size = limit or get_settings().list_page_size
    size = max(1, min(size, 100))
    with session_factory()() as db:
        return list_products(db, cursor=cursor, limit=size)


@app.get("/api/v1/catalog/products/{slug}")
def catalog_product(slug: str) -> dict:
    with session_factory()() as db:
        item = get_product(db, slug)
    if item is None:
        raise HTTPException(404, "Карточка не найдена")
    return item


@app.get("/api/v1/catalog/tree")
def catalog_tree() -> dict:
    with session_factory()() as db:
        return tree(db)


@app.get("/api/v1/admin/robot-attributes")
def admin_robot_attributes(process: str | None = None) -> list:
    with session_factory()() as db:
        return robot_attributes(db, process)


@app.get("/api/v1/admin/attributes")
def admin_attributes() -> list:
    with session_factory()() as db:
        return attributes(db)


@app.post("/api/v1/admin/attributes/{key}/usage")
def admin_usage(key: str, body: UsageIn) -> dict:
    with session_factory()() as db:
        try:
            mark_unused(db, key, body.unused)
        except KeyError:
            raise HTTPException(404, "Характеристика не найдена") from None
    return {"key": key, "unused": body.unused}


@app.post("/api/v1/admin/imports")
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


@app.get("/api/v1/admin/jobs/{job_id}")
def admin_job(job_id: UUID) -> dict:
    with session_factory()() as db:
        item = get_job(db, job_id)
    if item is None:
        raise HTTPException(404, "Прогон не найден")
    return item


@app.get("/api/v1/admin/parsers")
def admin_parsers() -> list:
    meta = {code: (title, summary) for code, (title, summary, _runner) in PARSERS.items()}
    with session_factory()() as db:
        rows = parser_settings(db)
    result = []
    for row in rows:
        title, summary = meta.get(row["code"], (row["code"], ""))
        result.append({**row, "title": title, "summary": summary})
    return result


@app.post("/api/v1/admin/parsers/{code}/runs")
def admin_parser_run(code: str) -> dict:
    if code not in PARSERS:
        raise HTTPException(404, "Парсер не найден")
    with session_factory()() as db:
        job = enqueue(db, kind="parser", parser_code=code)
    if job is None:
        raise HTTPException(409, "Этот парсер уже выполняется")
    return {"job_id": str(job.id)}


@app.patch("/api/v1/admin/parsers/{code}")
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


@app.get("/api/v1/admin/objects/{code}")
def admin_object_read(code: str) -> dict:
    with session_factory()() as db:
        try:
            return object_setup(db, code)
        except KeyError:
            raise HTTPException(404, "Объект не найден") from None


@app.put("/api/v1/admin/objects/{code}/setup")
def admin_object_setup(code: str, body: ObjectSetupIn) -> dict:
    with session_factory()() as db:
        try:
            return save_object_setup(db, code, body.model_dump())
        except KeyError:
            raise HTTPException(404, "Объект не найден") from None


@app.post("/api/v1/admin/objects")
def admin_object(body: ObjectIn) -> dict:
    with session_factory()() as db:
        save_object(db, code=body.code, name=body.name, industries=body.industries, processes=body.processes)
        return tree(db)


@app.post("/api/v1/admin/processes")
def admin_process(body: ProcessIn) -> dict:
    with session_factory()() as db:
        add_process(db, code=body.code, name=body.name)
        return tree(db)


@app.get("/api/v1/admin/processes/{code}")
def admin_process_read(code: str) -> dict:
    with session_factory()() as db:
        try:
            return process_setup(db, code)
        except KeyError:
            raise HTTPException(404, "Процесс не найден") from None


@app.get("/api/v1/layout-items/dictionary")
def layout_items_dictionary() -> dict:
    return {"roles": ROLES, "shapes": SHAPES, "count_rules": COUNT_RULES}


@app.put("/api/v1/admin/processes/{code}/setup")
def admin_process_setup(code: str, body: ProcessSetupIn) -> dict:
    with session_factory()() as db:
        try:
            return save_process_setup(db, code, body.model_dump())
        except KeyError:
            raise HTTPException(404, "Процесс не найден") from None


@app.put("/api/v1/admin/processes/{code}/filters")
def admin_filters(code: str, body: FiltersIn) -> dict:
    with session_factory()() as db:
        try:
            replace_filters(db, code, [item.model_dump() for item in body.filters])
        except KeyError:
            raise HTTPException(404, "Процесс не найден") from None
        return tree(db)


@app.put("/api/v1/admin/products/{slug}/processes")
def admin_assign(slug: str, body: AssignIn) -> dict:
    with session_factory()() as db:
        try:
            assign_processes(db, slug, body.processes)
        except KeyError:
            raise HTTPException(404, "Карточка не найдена") from None
    return {"slug": slug, "processes": body.processes}


@app.post("/api/v1/projects")
def create(body: ProjectIn) -> dict:
    with session_factory()() as db:
        try:
            return create_project(db, name=body.name, object_code=body.object_code, site=body.site)
        except KeyError:
            raise HTTPException(404, "Объект не найден") from None


@app.get("/api/v1/projects/{project_id}")
def read_project(project_id: UUID) -> dict:
    with session_factory()() as db:
        try:
            return project_view(db, project_id)
        except KeyError:
            raise HTTPException(404, "Проект не найден") from None


@app.patch("/api/v1/projects/{project_id}")
def patch_project(project_id: UUID, body: ProjectPatch) -> dict:
    with session_factory()() as db:
        try:
            return update_project(db, project_id, site=body.site, enabled=body.enabled)
        except KeyError:
            raise HTTPException(404, "Проект не найден") from None


@app.post("/api/v1/projects/{project_id}/match")
def match_project(project_id: UUID, body: MatchIn | None = None) -> dict:
    with session_factory()() as db:
        try:
            return run_match(db, project_id, site=None if body is None else body.site)
        except KeyError:
            raise HTTPException(404, "Проект не найден") from None


@app.post("/api/v1/projects/{project_id}/economy")
def economy_project(project_id: UUID, body: EconomyIn | None = None) -> dict:
    body = body or EconomyIn()
    with session_factory()() as db:
        try:
            return project_economy(db, project_id, body.site, body.choices, body.tasks, body.preview)
        except KeyError:
            raise HTTPException(404, "Проект не найден") from None


@app.get("/api/v1/projects/{project_id}/layout")
def layout_read(project_id: UUID) -> dict:
    with session_factory()() as db:
        try:
            return {"layout": project_layout(db, project_id)}
        except KeyError:
            raise HTTPException(404, "Проект не найден") from None


@app.put("/api/v1/projects/{project_id}/layout")
def layout_save(project_id: UUID, body: LayoutIn) -> dict:
    with session_factory()() as db:
        try:
            return {"layout": save_project_layout(db, project_id, body.layout)}
        except KeyError:
            raise HTTPException(404, "Проект не найден") from None


_IMAGE_TYPES = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
_LAYOUT_FILE = re.compile(r"^[0-9a-f-]{36}\.(png|jpg|webp)$")


@app.post("/api/v1/projects/{project_id}/layout/background")
async def layout_background(project_id: UUID, file: UploadFile = File(...)) -> dict:
    extension = _IMAGE_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(422, "Нужна картинка PNG, JPG или WebP")
    payload = await file.read()
    if len(payload) > 20 * 1024 * 1024:
        raise HTTPException(413, "Картинка больше 20 МБ")
    with session_factory()() as db:
        try:
            project_layout(db, project_id)
        except KeyError:
            raise HTTPException(404, "Проект не найден") from None
    folder = Path(get_settings().upload_dir) / "layouts"
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{uuid4()}.{extension}"
    (folder / name).write_bytes(payload)
    return {"name": name, "url": f"/api/v1/layout-files/{name}"}


@app.get("/api/v1/layout-files/{name}")
def layout_file(name: str) -> FileResponse:
    if not _LAYOUT_FILE.match(name):
        raise HTTPException(404, "Файл не найден")
    path = Path(get_settings().upload_dir) / "layouts" / name
    if not path.is_file():
        raise HTTPException(404, "Файл не найден")
    return FileResponse(path)


@app.put("/api/v1/projects/{project_id}/economy/overrides")
def economy_overrides(project_id: UUID, body: OverridesIn) -> dict:
    with session_factory()() as db:
        try:
            return {"values": save_economy_overrides(db, project_id, body.values)}
        except KeyError:
            raise HTTPException(404, "Проект не найден") from None


@app.get("/api/v1/economy/norms")
def economy_norm_list() -> dict:
    with session_factory()() as db:
        return {"items": economy_norms(db)}


@app.put("/api/v1/admin/economy/norms")
def economy_norm_save(body: NormsIn) -> dict:
    with session_factory()() as db:
        return {"items": save_economy_norms(db, body.values, body.note)}


@app.get("/api/v1/admin/economy/norms/log")
def economy_norm_history() -> dict:
    with session_factory()() as db:
        return {"items": economy_norm_log(db)}
