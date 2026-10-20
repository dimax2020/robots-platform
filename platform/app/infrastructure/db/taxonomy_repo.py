import json
import re
from copy import deepcopy
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.domain.economy import NORM_BY_KEY, NORMS, TYPE_NORMS, WORK_SPECS, blend_by_type, calculate, clamp_overrides, scale_load, scale_task_flows
from app.domain.layout_items import clean_items, default_items
from app.domain.formula import _number, identifiers
from app.domain.specs import CANON_LABELS, display_label
from app.domain.assessment import economy_eligible, select_hit, reason, valid_count, checked
from app.domain.sizing import size_equipment, input_label
from app.domain.catalog_assessment import resolve_catalog
from app.infrastructure.db.assessment_repo import metadata_maps
from app.domain.match import STAGES, FilterRule, Readiness, RobotView, match_robots, usage_for
from app.infrastructure.db.models import (
    AttributeDefRow,
    EconomyNormLogRow,
    EconomyNormOverrideRow,
    EconomyNormRow,
    IndustryRow,
    MatchSettingRow,
    ObjectFieldRow,
    ObjectIndustryRow,
    ObjectInputBindingRow,
    ObjectProcessRow,
    ObjectTypeRow,
    ProcessFilterRow,
    ProcessRow,
    ProductProcessRow,
    ProductRow,
    ProjectProcessRow,
    ProjectRow,
    SolutionTypeRow,
    SourceRow,
)
from app.infrastructure.db.catalog_repo import make_code
from app.infrastructure.db.object_repo import (
    object_fields,
    object_industries,
    process_inputs,
    replace_object_fields,
    set_object_identity,
)
from app.infrastructure.db.product_repo import products_for_process


def tree(db: Session) -> dict:
    industries = [{"code": row.code, "name": row.name} for row in db.scalars(select(IndustryRow).order_by(IndustryRow.name))]
    objects = []
    for obj in db.scalars(select(ObjectTypeRow).order_by(ObjectTypeRow.name)):
        industry_codes = list(db.scalars(
            select(IndustryRow.code)
            .join(ObjectIndustryRow, ObjectIndustryRow.industry_id == IndustryRow.id)
            .where(ObjectIndustryRow.object_type_id == obj.id)
        ))
        process_codes = list(db.scalars(
            select(ProcessRow.code)
            .join(ObjectProcessRow, ObjectProcessRow.process_id == ProcessRow.id)
            .where(ObjectProcessRow.object_type_id == obj.id)
        ))
        objects.append({
            "code": obj.code,
            "name": obj.name,
            "industries": industry_codes,
            "processes": process_codes,
            "in_match": obj.in_match,
        })
    processes = []
    for proc in db.scalars(select(ProcessRow).order_by(ProcessRow.name)):
        count = db.scalar(select(func.count()).select_from(ProductProcessRow).where(ProductProcessRow.process_id == proc.id)) or 0
        filters = [
            {
                "id": item.id,
                "name": item.name,
                "object_keys": item.object_keys,
                "robot_keys": item.robot_keys,
                "op": item.op,
                "mode": item.mode,
                "inputs": item.inputs or [],
                "formula": item.formula or "",
            }
            for item in db.scalars(select(ProcessFilterRow).where(ProcessFilterRow.process_id == proc.id).order_by(ProcessFilterRow.id))
        ]
        processes.append({"code": proc.code, "name": proc.name, "product_count": count, "filters": filters})
    return {"industries": industries, "objects": objects, "processes": processes}


def save_object(db: Session, *, code: str, name: str, industries: list[str], processes: list[str]) -> None:
    obj = db.scalar(select(ObjectTypeRow).where(ObjectTypeRow.code == code))
    if obj is None:
        obj = ObjectTypeRow(code=code, name=name)
        db.add(obj)
        db.flush()
    else:
        obj.name = name
    industry_ids = []
    for industry_code in industries:
        industry = db.scalar(select(IndustryRow).where(IndustryRow.code == industry_code))
        if industry is None:
            industry = IndustryRow(code=industry_code, name=industry_code)
            db.add(industry)
            db.flush()
        industry_ids.append(industry.id)
    process_ids = []
    for process_code in processes:
        process = db.scalar(select(ProcessRow).where(ProcessRow.code == process_code))
        if process is None:
            continue
        process_ids.append(process.id)
    db.execute(delete(ObjectIndustryRow).where(ObjectIndustryRow.object_type_id == obj.id))
    db.execute(delete(ObjectProcessRow).where(ObjectProcessRow.object_type_id == obj.id))
    for industry_id in industry_ids:
        db.add(ObjectIndustryRow(object_type_id=obj.id, industry_id=industry_id))
    for process_id in process_ids:
        db.add(ObjectProcessRow(object_type_id=obj.id, process_id=process_id))
    db.commit()


def add_process(db: Session, *, code: str, name: str) -> None:
    row = db.scalar(select(ProcessRow).where(ProcessRow.code == code))
    if row is None:
        db.add(ProcessRow(code=code, name=name))
    else:
        row.name = name
    db.commit()


def replace_filters(db: Session, process_code: str, filters: list[dict]) -> None:
    process = db.scalar(select(ProcessRow).where(ProcessRow.code == process_code))
    if process is None:
        raise KeyError(process_code)
    db.execute(delete(ProcessFilterRow).where(ProcessFilterRow.process_id == process.id))
    for item in filters:
        db.add(ProcessFilterRow(
            process_id=process.id,
            name=item["name"],
            object_keys=item.get("object_keys") or [],
            robot_keys=item.get("robot_keys") or [],
            op=item.get("op") or "formula",
            mode=item.get("mode") or "hard",
            inputs=item.get("inputs") or [],
            formula=item.get("formula") or "",
        ))
    db.flush()
    recompute_usage(db)
    db.commit()


def process_setup(db: Session, process_code: str) -> dict:
    process = db.scalar(select(ProcessRow).where(ProcessRow.code == process_code))
    if process is None:
        raise KeyError(process_code)
    filters = [
        {
            "name": item.name,
            "mode": item.mode,
            "inputs": item.inputs or [],
            "formula": item.formula or "",
        }
        for item in db.scalars(select(ProcessFilterRow).where(ProcessFilterRow.process_id == process.id).order_by(ProcessFilterRow.id))
    ]
    objects = []
    linked = select(ObjectTypeRow).join(ObjectProcessRow, ObjectProcessRow.object_type_id == ObjectTypeRow.id).where(ObjectProcessRow.process_id == process.id).order_by(ObjectTypeRow.name)
    for obj in db.scalars(linked):
        bindings = {
            row.input_key: row.site_key
            for row in db.scalars(select(ObjectInputBindingRow).where(
                ObjectInputBindingRow.object_type_id == obj.id,
                ObjectInputBindingRow.process_id == process.id,
            ))
        }
        fields = [
            {"key": item["key"], "label": item["label"], "unit": item["unit"], "default": item["default"]}
            for item in object_fields(db, obj.id)
        ]
        objects.append({"code": obj.code, "name": obj.name, "bindings": bindings, "fields": fields})
    product_count = db.scalar(select(func.count()).select_from(ProductProcessRow).where(ProductProcessRow.process_id == process.id)) or 0
    return {
        "code": process.code,
        "name": process.name,
        "description": process.description or "",
        "product_count": product_count,
        "filters": filters,
        "count_inputs": process.count_inputs or [],
        "count_formula": process.count_formula or "",
        "rank_key": process.rank_key or "",
        "rank_order": process.rank_order or "asc",
        "layout_items": process.layout_items or default_items(process.code),
        "layout_items_default": not process.layout_items,
        "objects": objects,
    }


def save_process_setup(db: Session, process_code: str, payload: dict) -> dict:
    process = db.scalar(select(ProcessRow).where(ProcessRow.code == process_code))
    if process is None:
        raise KeyError(process_code)
    if (payload.get("name") or "").strip():
        process.name = payload["name"].strip()
    if payload.get("description") is not None:
        process.description = payload["description"].strip()
    process.count_formula = payload.get("count_formula") or ""
    process.count_inputs = payload.get("count_inputs") or []
    process.rank_key = payload.get("rank_key") or ""
    process.rank_order = payload.get("rank_order") or "asc"
    if "layout_items" in payload and payload["layout_items"] is not None:
        process.layout_items = clean_items(payload["layout_items"])
    if payload.get("bindings"):
        _save_process_bindings(db, process, payload["bindings"])
    db.execute(delete(ProcessFilterRow).where(ProcessFilterRow.process_id == process.id))
    for item in payload.get("filters") or []:
        db.add(ProcessFilterRow(
            process_id=process.id,
            name=item["name"],
            object_keys=[],
            robot_keys=[],
            op="formula",
            mode=item.get("mode") or "hard",
            inputs=item.get("inputs") or [],
            formula=item.get("formula") or "",
        ))
    db.flush()
    recompute_usage(db)
    db.commit()
    return process_setup(db, process_code)


def _save_process_bindings(db: Session, process: ProcessRow, rows: list[dict]) -> None:
    """Привязки из редактора процесса. Пустое поле снимает привязку; чужие величины объекта не трогаются."""
    objects = {row.code: row.id for row in db.scalars(select(ObjectTypeRow))}
    for item in rows:
        object_id = objects.get(item.get("object_code") or "")
        input_key = item.get("input_key") or ""
        if object_id is None or not input_key:
            continue
        link = db.get(ObjectInputBindingRow, (object_id, process.id, input_key))
        site_key = item.get("site_key") or ""
        if not site_key:
            if link is not None:
                db.delete(link)
            continue
        if link is None:
            db.add(ObjectInputBindingRow(object_type_id=object_id, process_id=process.id, input_key=input_key, site_key=site_key))
        else:
            link.site_key = site_key


def create_process(db: Session, *, name: str, objects: list[str]) -> str:
    name = name.strip()
    if not name:
        raise ValueError("Нужно название процесса")
    code = make_code(name, set(db.scalars(select(ProcessRow.code))))
    process = ProcessRow(code=code, name=name)
    db.add(process)
    db.flush()
    for object_code in dict.fromkeys(objects):
        obj = db.scalar(select(ObjectTypeRow).where(ObjectTypeRow.code == object_code))
        if obj is not None:
            db.add(ObjectProcessRow(object_type_id=obj.id, process_id=process.id))
    db.commit()
    return code


def process_list(db: Session) -> list[dict]:
    """Процессы со статусом настройки: без роботов, без условий, без схемы."""
    counts = dict(db.execute(select(ProductProcessRow.process_id, func.count()).group_by(ProductProcessRow.process_id)).all())
    filters = dict(db.execute(select(ProcessFilterRow.process_id, func.count()).group_by(ProcessFilterRow.process_id)).all())
    names = {row.id: (row.code, row.name) for row in db.scalars(select(ObjectTypeRow))}
    by_process: dict[int, list[str]] = {}
    for link in db.scalars(select(ObjectProcessRow)):
        if link.object_type_id in names:
            by_process.setdefault(link.process_id, []).append(link.object_type_id)
    result = []
    for process in db.scalars(select(ProcessRow).order_by(ProcessRow.name)):
        object_ids = by_process.get(process.id, [])
        result.append({
            "code": process.code,
            "name": process.name,
            "product_count": int(counts.get(process.id, 0)),
            "filter_count": int(filters.get(process.id, 0)),
            "has_count": bool((process.count_formula or "").strip()),
            "has_layout": bool(process.layout_items) or bool(default_items(process.code)),
            "objects": [{"code": names[oid][0], "name": names[oid][1]} for oid in object_ids],
        })
    return result


def preview_process(db: Session, process_code: str, payload: dict) -> dict:
    """Подбор одного процесса на значениях площадки до сохранения: те же фильтры и формула, что в run_match."""
    process = db.scalar(select(ProcessRow).where(ProcessRow.code == process_code))
    if process is None:
        raise KeyError(process_code)
    obj = db.scalar(select(ObjectTypeRow).where(ObjectTypeRow.code == payload.get("object_code")))
    if obj is None:
        raise KeyError(payload.get("object_code") or "")
    site = {item["key"]: item["default"] for item in object_fields(db, obj.id) if item["default"] not in (None, "")}
    site.update({key: value for key, value in (payload.get("site") or {}).items() if value not in (None, "")})
    bindings = {
        row.input_key: row.site_key
        for row in db.scalars(select(ObjectInputBindingRow).where(
            ObjectInputBindingRow.object_type_id == obj.id,
            ObjectInputBindingRow.process_id == process.id,
        ))
    }
    for item in payload.get("bindings") or []:
        if item.get("object_code") == obj.code and item.get("input_key"):
            if item.get("site_key"):
                bindings[item["input_key"]] = item["site_key"]
            else:
                bindings.pop(item["input_key"], None)
    rules = tuple(
        FilterRule(
            item.get("name") or "",
            (),
            (),
            "formula",
            item.get("mode") or "hard",
            tuple((row.get("key", ""), row.get("label", "")) for row in (item.get("inputs") or []) if isinstance(row, dict)),
            item.get("formula") or "",
        )
        for item in payload.get("filters") or []
        if (item.get("formula") or "").strip()
    )
    rows = products_for_process(db, process.id)
    facts_map, profiles = metadata_maps(db)
    profile = profiles.get(process.id, {})
    sources = _assessment_sources(db)
    catalogs = {str(row.id): resolve_catalog(row, facts_map.get(str(row.id)), process_code=process.code, process_name=process.name, sources=sources, site=site) for row in rows}
    robots = tuple(_robot_view(row, catalog=catalogs[str(row.id)]) for row in rows)
    hits = match_robots(process_code=process.code, process_name=process.name, site=site, rules=rules, robots=robots, bindings=bindings, readiness=readiness_filter(db), profile=profile)
    by_id = {key: catalog.values for key, catalog in catalogs.items()}
    rows_by_id = {str(row.id): row for row in rows}
    assessed = {hit.product_id: _candidate_payload(hit, rows_by_id[hit.product_id], facts_map.get(hit.product_id, {}), profile, site, None, catalogs[hit.product_id]) for hit in hits}
    counted = [(hit, assessed[hit.product_id]['count'], assessed[hit.product_id]['count_note']) for hit in hits]
    ready = [item for item in counted if economy_eligible(assessed[item[0].product_id])]
    best = _best(ready, by_id, payload.get("rank_key") or "", payload.get("rank_order") or "asc")
    tally = {"pass": 0, "conditional": 0, "unknown": 0, "fail": 0}
    reasons: dict[str, int] = {}
    for hit, _amount, _note in counted:
        tally[hit.verdict] = tally.get(hit.verdict, 0) + 1
        for note in hit.notes:
            reason = note.split(":", 1)[0]
            reasons[f"{hit.verdict}:{reason}"] = reasons.get(f"{hit.verdict}:{reason}", 0) + 1
    order = {"pass": 0, "conditional": 1, "unknown": 2, "fail": 3}
    counted.sort(key=lambda item: (item[0].product_id != best, order.get(item[0].verdict, 4), item[0].name))
    used_keys = sorted({value for value in bindings.values() if value})
    return {
        "object": {"code": obj.code, "name": obj.name},
        "site": {key: site.get(key) for key in used_keys},
        "tally": tally,
        "reasons": [
            {"verdict": key.split(":", 1)[0], "reason": key.split(":", 1)[1], "count": count}
            for key, count in sorted(reasons.items(), key=lambda pair: -pair[1])
        ],
        "best_product_id": best,
        "robots": [assessed[hit.product_id] for hit, _amount, _note in counted],
    }


def object_setup(db: Session, object_code: str) -> dict:
    obj = db.scalar(select(ObjectTypeRow).where(ObjectTypeRow.code == object_code))
    if obj is None:
        raise KeyError(object_code)
    enabled_ids = set(db.scalars(select(ObjectProcessRow.process_id).where(ObjectProcessRow.object_type_id == obj.id)))
    counts = dict(db.execute(
        select(ProductProcessRow.process_id, func.count()).group_by(ProductProcessRow.process_id)
    ).all())
    bindings_by_process: dict[int, dict[str, str]] = {}
    for row in db.scalars(select(ObjectInputBindingRow).where(ObjectInputBindingRow.object_type_id == obj.id)):
        bindings_by_process.setdefault(row.process_id, {})[row.input_key] = row.site_key
    processes = []
    for process in db.scalars(select(ProcessRow).order_by(ProcessRow.name)):
        processes.append({
            "code": process.code,
            "name": process.name,
            "product_count": int(counts.get(process.id, 0)),
            "enabled": process.id in enabled_ids,
            "inputs": process_inputs(db, process),
            "bindings": bindings_by_process.get(process.id, {}),
        })
    return {
        "code": obj.code,
        "name": obj.name,
        "industries": object_industries(db, obj.id),
        "fields": object_fields(db, obj.id),
        "projects": db.scalar(select(func.count()).select_from(ProjectRow).where(ProjectRow.object_type_id == obj.id)) or 0,
        "in_match": obj.in_match,
        "processes": processes,
    }


def save_object_setup(db: Session, object_code: str, payload: dict) -> dict:
    obj = db.scalar(select(ObjectTypeRow).where(ObjectTypeRow.code == object_code))
    if obj is None:
        raise KeyError(object_code)
    set_object_identity(db, obj, name=payload.get("name"), industries=payload.get("industries"))
    if payload.get("in_match") is not None:
        obj.in_match = bool(payload["in_match"])
    if payload.get("fields") is not None:
        replace_object_fields(db, obj, payload["fields"])
    db.execute(delete(ObjectProcessRow).where(ObjectProcessRow.object_type_id == obj.id))
    for code in payload.get("processes") or []:
        process = db.scalar(select(ProcessRow).where(ProcessRow.code == code))
        if process is not None:
            db.add(ObjectProcessRow(object_type_id=obj.id, process_id=process.id))
    db.execute(delete(ObjectInputBindingRow).where(ObjectInputBindingRow.object_type_id == obj.id))
    for item in payload.get("bindings") or []:
        process = db.scalar(select(ProcessRow).where(ProcessRow.code == item.get("process_code")))
        if process is None or not item.get("input_key") or not item.get("site_key"):
            continue
        db.add(ObjectInputBindingRow(
            object_type_id=obj.id,
            process_id=process.id,
            input_key=item["input_key"],
            site_key=item["site_key"],
        ))
    db.commit()
    return object_setup(db, object_code)


def assign_processes(db: Session, slug: str, process_codes: list[str]) -> None:
    product = db.scalar(select(ProductRow).where(ProductRow.slug == slug))
    if product is None:
        raise KeyError(slug)
    db.execute(delete(ProductProcessRow).where(ProductProcessRow.product_id == product.id))
    for code in process_codes:
        process = db.scalar(select(ProcessRow).where(ProcessRow.code == code))
        if process is not None:
            db.add(ProductProcessRow(product_id=product.id, process_id=process.id))
    db.commit()


def mark_unused(db: Session, key: str, unused: bool) -> None:
    row = db.get(AttributeDefRow, key)
    if row is None:
        raise KeyError(key)
    row.usage = "unused" if unused else "pending"
    recompute_usage(db)
    db.commit()


def recompute_usage(db: Session) -> None:
    referenced: set[str] = set()
    for item in db.scalars(select(ProcessFilterRow)):
        referenced.update(item.robot_keys or [])
        input_keys = {row.get("key") for row in (item.inputs or []) if isinstance(row, dict)}
        for name in identifiers(item.formula or ""):
            bare = name.split(".", 1)[1] if name.startswith("robot.") else name
            if bare not in input_keys:
                referenced.add(bare)
    for row in db.scalars(select(AttributeDefRow)):
        row.usage = usage_for(row.key, unused=row.usage == "unused", referenced=referenced)


def attributes(db: Session) -> list[dict]:
    return [
        {"key": row.key, "label": row.label, "unit": row.unit, "usage": row.usage}
        for row in db.scalars(select(AttributeDefRow).order_by(AttributeDefRow.key))
    ]


def robot_attributes(db: Session, process_code: str | None = None) -> list[dict]:
    rows = db.execute(text(
        "select key, count(*)::int as products from product, lateral jsonb_object_keys(attrs) as key group by key"
    )).all()
    labels = {row.key: row.label for row in db.scalars(select(AttributeDefRow))}

    def label_for(key: str) -> str:
        stored = labels.get(key) or ""
        if stored and stored != key:
            return stored
        return CANON_LABELS.get(key, key)
    on_process: dict[str, int] = {}
    if process_code:
        counted = db.execute(text(
            """
            select k.key, count(*)::int as products
            from product pr
            join product_process pp on pp.product_id = pr.id
            join process p on p.id = pp.process_id and p.code = :code
            cross join lateral jsonb_object_keys(pr.attrs) as k(key)
            group by k.key
            """
        ), {"code": process_code}).all()
        on_process = {key: products for key, products in counted}
    items = [
        {"key": key, "label": label_for(key), "products": products, "on_process": on_process.get(key, 0)}
        for key, products in rows
    ]
    items.sort(key=lambda item: (-item["on_process"], -item["products"], item["label"]))
    return items


def _public_site(site: dict | None) -> dict:
    return {key: value for key, value in (site or {}).items() if not str(key).startswith("__")}


def _split_site(site: dict | None) -> tuple[dict, list]:
    raw = dict(site or {})
    tasks = raw.pop("__tasks", [])
    public = _public_site(raw)
    return public, tasks if isinstance(tasks, list) else []


def _store_site(site: dict | None, tasks: list | None, previous: dict | None) -> dict:
    stored = _public_site(site if site is not None else previous)
    if tasks is None:
        old = (previous or {}).get("__tasks")
        if old is not None:
            stored["__tasks"] = old
    else:
        stored["__tasks"] = tasks
    return stored


def owned_project(db: Session, project_id: UUID, *, user_id: UUID, role: str) -> ProjectRow:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise KeyError(str(project_id))
    if role == "admin":
        return project
    if project.owner_id is None or project.owner_id != user_id:
        raise KeyError(str(project_id))
    return project


def resolve_project(db: Session, key: str) -> ProjectRow:
    """Проект по UUID или по постоянному адресу демо-объекта (например, demo-warehouse)."""
    try:
        project = db.get(ProjectRow, UUID(str(key)))
    except ValueError:
        project = db.scalar(select(ProjectRow).where(ProjectRow.slug == str(key)))
    if project is None:
        raise KeyError(str(key))
    return project


def project_access(db: Session, key: str, *, user_id: UUID | None, role: str | None) -> tuple[ProjectRow, bool]:
    """Кто может открыть проект и может ли править.

    Опубликованный демо-объект читают все, включая гостей; правит только администратор.
    Обычный проект видит владелец и администратор.
    """
    project = resolve_project(db, key)
    if role == "admin":
        return project, True
    if project.is_demo:
        if project.published:
            return project, False
        raise KeyError(str(key))
    if user_id is None or role in (None, "guest"):
        raise KeyError(str(key))
    if project.owner_id is None or project.owner_id != user_id:
        raise KeyError(str(key))
    return project, True


def _demo_item(db: Session, project: ProjectRow, obj: ObjectTypeRow) -> dict:
    industry = db.scalar(
        select(IndustryRow.name)
        .join(ObjectIndustryRow, ObjectIndustryRow.industry_id == IndustryRow.id)
        .where(ObjectIndustryRow.object_type_id == obj.id)
        .limit(1)
    )
    site, tasks = _split_site(project.site)
    enabled = db.scalar(
        select(func.count()).select_from(ProjectProcessRow)
        .where(ProjectProcessRow.project_id == project.id, ProjectProcessRow.enabled.is_(True))
    ) or 0
    layout = project.layout or {}
    return {
        "id": str(project.id),
        "slug": project.slug,
        "name": project.name,
        "object_code": obj.code,
        "object_name": obj.name,
        "industry": industry or "",
        "is_demo": project.is_demo,
        "published": project.published,
        "area_m2": site.get("area_m2"),
        "shifts_per_day": site.get("shifts_per_day"),
        "processes": enabled,
        "tasks": len(tasks),
        "has_layout": bool(layout.get("floors")),
        "overrides": len(project.economy_overrides or {}),
    }


def demo_projects(db: Session, *, include_unpublished: bool = False) -> list[dict]:
    stmt = (
        select(ProjectRow, ObjectTypeRow)
        .join(ObjectTypeRow, ObjectTypeRow.id == ProjectRow.object_type_id)
        .where(ProjectRow.is_demo.is_(True))
        .order_by(ProjectRow.name)
    )
    if not include_unpublished:
        stmt = stmt.where(ProjectRow.published.is_(True))
    return [_demo_item(db, project, obj) for project, obj in db.execute(stmt)]


def _clean_slug(raw: str | None) -> str | None:
    text = re.sub(r"[^a-z0-9-]+", "-", (raw or "").strip().lower()).strip("-")
    return text or None


def set_demo_flags(db: Session, project_id: UUID, *, is_demo: bool | None, published: bool | None, slug: str | None, name: str | None = None) -> dict:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise KeyError(str(project_id))
    if is_demo is not None:
        project.is_demo = is_demo
        if not is_demo:
            project.published = False
            project.slug = None
    if published is not None and project.is_demo:
        project.published = published
    if slug is not None and project.is_demo:
        clean = _clean_slug(slug)
        taken = db.scalar(select(ProjectRow.id).where(ProjectRow.slug == clean, ProjectRow.id != project.id)) if clean else None
        if taken is not None:
            raise ValueError(f"Адрес «{clean}» уже занят другим демо-объектом")
        project.slug = clean
    if name is not None and name.strip():
        project.name = name.strip()
    db.commit()
    return project_view(db, project.id)


def object_defaults(db: Session, object_code: str) -> dict:
    """Значения по умолчанию из полей объекта: с них начинается любой демо-объект."""
    obj = db.scalar(select(ObjectTypeRow).where(ObjectTypeRow.code == object_code))
    if obj is None:
        raise KeyError(object_code)
    site: dict = {}
    for row in db.scalars(select(ObjectFieldRow).where(ObjectFieldRow.object_type_id == obj.id)):
        if row.default_value not in (None, ""):
            site[row.field_key] = row.default_value
    return site


def create_demo_project(db: Session, *, name: str, object_code: str, slug: str | None, owner_id: UUID | None, site: dict | None = None) -> dict:
    created = create_project(db, name=name, object_code=object_code, site=site if site is not None else object_defaults(db, object_code), owner_id=owner_id)
    return set_demo_flags(db, UUID(created["id"]), is_demo=True, published=False, slug=slug or name)


def create_project(db: Session, *, name: str, object_code: str, site: dict, owner_id: UUID | None = None) -> dict:
    obj = db.scalar(select(ObjectTypeRow).where(ObjectTypeRow.code == object_code))
    if obj is None:
        raise KeyError(object_code)
    if not obj.in_match:
        raise ValueError("Объект выключен из подбора: его нельзя выбрать для нового проекта")
    project = ProjectRow(id=uuid4(), name=name, object_type_id=obj.id, site=_store_site(site, None, None), owner_id=owner_id)
    db.add(project)
    db.flush()
    process_ids = list(db.scalars(select(ObjectProcessRow.process_id).where(ObjectProcessRow.object_type_id == obj.id)))
    for process_id in process_ids:
        db.add(ProjectProcessRow(project_id=project.id, process_id=process_id, enabled=True))
    db.commit()
    return project_view(db, project.id)


def update_project(
    db: Session,
    project_id: UUID,
    *,
    site: dict | None,
    enabled: dict[str, bool] | None,
    tasks: list | None = None,
    reasons: dict[str, str] | None = None,
) -> dict:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise KeyError(str(project_id))
    if site is not None or tasks is not None:
        project.site = _store_site(site, tasks, project.site)
    if enabled is not None:
        reasons = reasons or {}
        for code, flag in enabled.items():
            process = db.scalar(select(ProcessRow).where(ProcessRow.code == code))
            if process is None:
                continue
            link = db.get(ProjectProcessRow, (project.id, process.id))
            if link is None:
                link = ProjectProcessRow(project_id=project.id, process_id=process.id, enabled=flag)
                db.add(link)
            else:
                link.enabled = flag
            if flag:
                link.disabled_reason = None
            elif code in reasons:
                link.disabled_reason = (reasons[code] or "").strip() or None
    db.commit()
    return project_view(db, project.id)


def project_view(db: Session, project_id: UUID) -> dict:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise KeyError(str(project_id))
    obj = db.get(ObjectTypeRow, project.object_type_id)
    processes = []
    stmt = (
        select(ProcessRow, ProjectProcessRow.enabled, ProjectProcessRow.disabled_reason)
        .join(ProjectProcessRow, ProjectProcessRow.process_id == ProcessRow.id)
        .where(ProjectProcessRow.project_id == project.id)
        .order_by(ProcessRow.name)
    )
    robots = dict(db.execute(select(ProductProcessRow.process_id, func.count()).group_by(ProductProcessRow.process_id)).all())
    for process, enabled, reason in db.execute(stmt):
        filters = list(db.scalars(select(ProcessFilterRow).where(ProcessFilterRow.process_id == process.id)))
        processes.append({
            "code": process.code,
            "name": process.name,
            "description": process.description or "",
            "product_count": int(robots.get(process.id, 0)),
            "enabled": enabled,
            "disabled_reason": None if enabled else reason,
            "filters": [
                {"name": item.name, "object_keys": item.object_keys, "robot_keys": item.robot_keys, "op": item.op, "mode": item.mode, "inputs": item.inputs or [], "formula": item.formula or ""}
                for item in filters
            ],
        })
    site, tasks = _split_site(project.site)
    industry = None
    if obj is not None:
        industry = db.scalar(
            select(IndustryRow.name)
            .join(ObjectIndustryRow, ObjectIndustryRow.industry_id == IndustryRow.id)
            .where(ObjectIndustryRow.object_type_id == obj.id)
            .limit(1)
        )
    return {
        "id": str(project.id),
        "slug": project.slug,
        "name": project.name,
        "object_code": obj.code if obj else None,
        "object_name": obj.name if obj else None,
        "industry": industry or "",
        "site": site,
        "tasks": tasks,
        "economy_overrides": project.economy_overrides or {},
        "processes": processes,
        "is_demo": project.is_demo,
        "published": project.published,
        "owner_id": str(project.owner_id) if project.owner_id else None,
    }


def list_projects(db: Session, *, user_id: UUID, role: str) -> list[dict]:
    stmt = (
        select(ProjectRow, ObjectTypeRow)
        .join(ObjectTypeRow, ObjectTypeRow.id == ProjectRow.object_type_id)
        .order_by(ProjectRow.name)
    )
    if role != "admin":
        stmt = stmt.where(ProjectRow.owner_id == user_id, ProjectRow.is_demo.is_(False))
    items = []
    for project, obj in db.execute(stmt):
        industry = db.scalar(
            select(IndustryRow.name)
            .join(ObjectIndustryRow, ObjectIndustryRow.industry_id == IndustryRow.id)
            .where(ObjectIndustryRow.object_type_id == obj.id)
            .limit(1)
        )
        items.append({
            "id": str(project.id),
            "slug": project.slug,
            "name": project.name,
            "object_code": obj.code,
            "object_name": obj.name,
            "industry": industry or "",
            "is_demo": project.is_demo,
            "published": project.published,
        })
    return items


def copy_project(db: Session, project_id: UUID, *, owner_id: UUID) -> dict:
    src = db.get(ProjectRow, project_id)
    if src is None:
        raise KeyError(str(project_id))
    # Копия демо-объекта становится обычным проектом пользователя.
    project = ProjectRow(
        id=uuid4(),
        name=f"{src.name} (копия)",
        object_type_id=src.object_type_id,
        owner_id=owner_id,
        site=dict(src.site or {}),
        economy_overrides=dict(src.economy_overrides or {}),
        layout=dict(src.layout or {}),
        is_demo=False,
        published=False,
        slug=None,
    )
    db.add(project)
    db.flush()
    for link in db.scalars(select(ProjectProcessRow).where(ProjectProcessRow.project_id == src.id)):
        db.add(ProjectProcessRow(project_id=project.id, process_id=link.process_id, enabled=link.enabled, disabled_reason=link.disabled_reason))
    db.commit()
    return project_view(db, project.id)


_LAYOUT_FILE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(?:png|jpg|webp)")


def layout_file_names(layout: dict | None) -> set[str]:
    return set(_LAYOUT_FILE.findall(json.dumps(layout or {}, ensure_ascii=False)))


def delete_project(db: Session, project_id: UUID) -> set[str]:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise KeyError(str(project_id))
    names = layout_file_names(project.layout)
    db.execute(delete(ProjectProcessRow).where(ProjectProcessRow.project_id == project.id))
    db.delete(project)
    db.commit()
    return names


def layout_files_in_use(db: Session) -> set[str]:
    used: set[str] = set()
    for layout in db.scalars(select(ProjectRow.layout)):
        used |= layout_file_names(layout)
    return used


def run_match(db: Session, project_id: UUID, site: dict | None = None, tasks: list | None = None, *, _prepared=False, _input_groups=None) -> dict:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise KeyError(str(project_id))
    stored_site, stored_tasks = _split_site(project.site or {})
    values = _public_site(site if site is not None else stored_site)
    if tasks is None:
        tasks = stored_tasks
    processes = list(db.scalars(
        select(ProcessRow)
        .join(ProjectProcessRow, ProjectProcessRow.process_id == ProcessRow.id)
        .where(ProjectProcessRow.project_id == project.id, ProjectProcessRow.enabled.is_(True))
        .order_by(ProcessRow.name)
    ))
    from app.domain.demo_synthetic import project_plan, project_inputs
    plan = project_plan(project)
    inputs = _input_groups or []
    if plan and not _prepared:
        values, tasks, inputs = project_inputs(plan, values, tasks)
    return {"project_id": str(project.id), "groups": _match_groups(db, project.object_type_id, processes, values, tasks, plan=plan, input_groups=inputs),
            'demo_plan': plan, 'demo_input_groups': inputs}


def match_object(db: Session, object_code: str, site: dict | None, tasks: list | None = None) -> dict:
    obj = db.scalar(select(ObjectTypeRow).where(ObjectTypeRow.code == object_code))
    if obj is None:
        raise KeyError(object_code)
    processes = list(db.scalars(
        select(ProcessRow)
        .join(ObjectProcessRow, ObjectProcessRow.process_id == ProcessRow.id)
        .where(ObjectProcessRow.object_type_id == obj.id)
        .order_by(ProcessRow.name)
    ))
    return {"project_id": None, "groups": _match_groups(db, obj.id, processes, _public_site(site), tasks or [])}


def _tasks_by_code(tasks: list | None) -> dict[str, dict]:
    found: dict[str, dict] = {}
    for task in tasks or []:
        if isinstance(task, dict) and task.get("process_code"):
            found[str(task["process_code"])] = task
    return found


def _candidate_payload(hit, row, facts, profile, values, task, catalog=None, *, demo=False, input_fields=(), quantity_context=None, sizing_limitation=None, demo_configuration=None):
    from app.domain.selection_assumptions import catalog_assumptions, commercial_assumptions, sizing_profile
    catalog = catalog or resolve_catalog(row, facts, process_code=hit.process_code, process_name=hit.process_name, site=values)
    facts = catalog.facts
    profile, _ = checked(profile, product=False)
    profile = sizing_profile(profile, hit.process_code, facts)
    assumptions = [*catalog_assumptions(catalog), *catalog.demo_synthetic]
    assumptions.extend(deepcopy(entry) for entry in input_fields if entry.get('category') == 'operation')
    commercial = [a for a in commercial_assumptions(facts, _number(row.price_rub))
                  if not any(r.field == a['key'] for r in catalog.reasons)]
    if demo and demo_configuration:
        from app.domain.demo_synthetic import configuration_assumptions
        configured = configuration_assumptions(demo_configuration, _number(row.price_rub))
        commercial = [a for a in commercial if a['key'] not in {v['key'] for v in configured}] + configured
    assumptions.extend(commercial)
    assumed_commercial = {a['key'] for a in commercial}
    from app.domain.demo_synthetic import technical_mode_values, MODE_UNITS
    sizing_values = technical_mode_values(catalog) if demo else dict(catalog.values)
    for kind in ('loaded', 'empty'):
        raw = (row.attrs or {}).get(f'speed_{kind}_ms') or {}
        if raw.get('status') == 'known' and not raw.get('conflict') and raw.get('unit') == 'м/с':
            sizing_values[f'speed_{kind}_limit_ms'] = raw.get('value')
    sizing_task = dict(task or {})
    mode_sources = {}
    if 'work_time_h' not in catalog.values and 'work_time_h' in sizing_values:
        mode_sources['work_time_h'] = {**catalog.provenance.get('working_time_h', {}), 'parameter': 'working_time_h'}
    mode_errors = []
    policy = profile.get('sizing') or {}
    if policy.get('model') in {'asrs_capacity_v1', 'stationary_cycle_v1', 'aerial_surface_v1'}:
        for key in ('handling_cycle_s', 'work_units_per_cycle', 'module_storage_places',
                    'lines_per_presentation', 'surface_rate_m2_h', 'turnaround_h'):
            unit = catalog.provenance.get(key, {}).get('unit')
            if key in sizing_values and unit not in (None, '', MODE_UNITS[key]):
                mode_errors.append(reason('sizing_unit_incompatible',
                    f'Для «{input_label(key)}» требуется единица {MODE_UNITS[key]}', field=key, stage='sizing'))
    unit = catalog.provenance.get('throughput_unit', {})
    if (demo and policy.get('model') == 'asrs_capacity_v1' and 'throughput_unit' not in sizing_values
            and unit.get('status') == 'known' and not unit.get('conflict') and not unit.get('conditions')
            and catalog.issues.get('throughput_unit') == 'Для допущения или аналога нужны обоснование и однозначные единицы'):
        # Текст единицы исходного аналога — размерность, а не численная
        # характеристика. Явная привязка только новой модели AS/RS.
        binding = {'key': 'throughput_unit', 'value': unit['value'], 'unit': '',
                   'label': 'Размерность производительности AS/RS', 'origin': 'demo_synthetic',
                   'explanation': 'DEV: единица исходного аналога привязана к циклам выдачи одной паллеты. Число производительности сохранено.',
                   'requires_vendor_confirmation': True, 'vendor_confirmed': False,
                   'source': unit.get('source')}
        sizing_values['throughput_unit'] = unit['value']
        mode_sources['throughput_unit'] = binding
        assumptions.append(binding)
    if policy.get('speed_basis') == 'working_mode':
        for kind in ('loaded', 'empty'):
            key, mode_key = f'speed_{kind}_ms', f'working_speed_{kind}_ms'
            working = _number(catalog.values.get(mode_key))
            if working is not None:
                limits = [_number(sizing_values.get(f'speed_{kind}_limit_ms')), _number(catalog.values.get('max_speed_ms'))]
                if any(limit is not None and working > limit for limit in limits):
                    mode_errors.append(reason('working_speed_exceeds_limit', 'Рабочая скорость превышает опубликованный предел', field=mode_key, stage='sizing'))
                sizing_values[key] = working
                mode_sources[key] = {**catalog.provenance.get(mode_key, {}), 'parameter': mode_key}
    if policy.get('rate_basis') == 'robot_mode' and catalog.values.get('effective_cleaning_rate_m2_h') is not None:
        sizing_task['effective_cleaning_rate_m2_h'] = catalog.values['effective_cleaning_rate_m2_h']
    sizing = size_equipment(profile, facts, values, sizing_values, sizing_task)
    if demo and sizing_limitation and any(r.code == 'sizing_model_missing' for r in sizing.reasons):
        # Диагностика отсутствующей модели не меняет количество или допуск.
        from dataclasses import replace
        sizing = replace(sizing, reasons=tuple(
            replace(r, message=sizing_limitation) if r.code == 'sizing_model_missing' else r
            for r in sizing.reasons))
    if demo and policy.get('reuse_catalog_formula') is True:
        from app.domain.demo_synthetic import catalog_process_quantity
        sizing = catalog_process_quantity(catalog, values, quantity_context, sizing_values, sizing_task)
        if sizing.details.get('throughput_parameter') == 'working_inventory_rate_h':
            mode_sources['throughput'] = {**catalog.provenance['working_inventory_rate_h'], 'parameter': 'working_inventory_rate_h'}
    if mode_errors:
        from app.domain.sizing import SizingResult
        sizing = SizingResult(None, tuple(mode_errors), sizing.model)
    if demo and (task or {}).get('__demo_input_conflict'):
        from app.domain.sizing import SizingResult
        sizing = SizingResult(None, (reason('task_allocation_conflict', 'Для нескольких задач одного процесса необходимо распределить нагрузку и исходный штат', stage='sizing'),), sizing.model)
    input_provenance = {}
    synthetic_inputs = {entry['key']: entry for entry in input_fields}
    for key, value in sizing.details.get('inputs', {}).items():
        source = mode_sources.get(key) or catalog.provenance.get(key) or synthetic_inputs.get(key) or {'origin': 'project_input', 'scope': hit.process_code}
        input_provenance[key] = {**source, 'value': value}
        if source.get('value') is not None and source['value'] != value:
            input_provenance[key]['base_value'] = source['value']
            input_provenance[key]['transformation'] = 'load_factor'

    count = sizing.count
    sizing_reasons = [*sizing.reasons, *(r for r in catalog.reasons if r.stage == 'sizing')]
    economic_reasons = [r.as_dict() for r in sizing_reasons]
    economic_reasons.extend(r.as_dict() for r in catalog.reasons if r.stage == 'economy')
    if count == 0:
        economic_reasons.append(reason('no_equipment_required', 'При нулевой потребности парк роботизации не формируется', stage='economy').as_dict())
    if hit.verdict != 'pass':
        economic_reasons.append(reason('technical_not_confirmed', 'Перед расчётом экономики уточните обязательные условия технической применимости', stage='economy').as_dict())
    if _number(row.price_rub) is None or _number(row.price_rub) <= 0:
        economic_reasons.append(reason('price_missing', 'Отсутствует необходимая положительная цена решения', stage='economy').as_dict())
    if facts.get('price_complete') is not True and 'price_complete' not in assumed_commercial:
        economic_reasons.append(reason('price_scope_unconfirmed', 'Не подтверждено, что цена покрывает необходимую комплектацию решения', stage='economy').as_dict())
    if facts.get('configuration_complete') is not True and 'configuration_complete' not in assumed_commercial:
        economic_reasons.append(reason('configuration_missing', 'Не определена комплектность решения для экономического расчёта', stage='economy').as_dict())
    clarifications = [r.as_dict() for r in hit.reasons if r.severity != 'fail']
    clarifications.extend(economic_reasons)
    clarifications.extend({'code': 'optional_attribute_missing', 'field': key, 'severity': 'info',
                           'message': 'Уточнить у вендора: ' + str(raw.get('label') or display_label(key))}
                          for key, raw in (row.attrs or {}).items()
                          if isinstance(raw, dict) and raw.get('status') == 'unknown'
                          and not any(r.get('field') == key for r in clarifications))
    clarifications = list({(r.get('code'), r.get('field'), r['message']): r for r in clarifications}.values())
    return {
        'product_id': hit.product_id, 'name': hit.name, 'slug': hit.slug,
        'verdict': hit.verdict, 'notes': list(hit.notes),
        'reasons': [r.as_dict() for r in hit.reasons],
        'applicability': 'conditional' if hit.verdict == 'pass' and assumptions else hit.verdict,
        'assumptions': assumptions,
        'significant_reasons': [r.as_dict() for r in hit.reasons if r.severity in {'fail', 'unknown'}],
        'clarifications': clarifications,
        'technical_ready': hit.verdict == 'pass',
        'sizing_ready': count is not None,
        'economic_ready': not demo and not catalog.demo_synthetic and hit.verdict == 'pass' and count is not None and not economic_reasons,
        'demo_economic_ready': demo and hit.verdict == 'pass' and count is not None and not economic_reasons,
        'calculation_mode': 'demo' if demo else 'ordinary',
        'economic_reasons': economic_reasons,
        'image_url': hit.image_url, 'trl': hit.trl, 'stage': hit.stage,
        'manufacturer': (getattr(row, 'manufacturer', None) or '').strip() or None,
        'count': count, 'count_note': '; '.join(r.message for r in sizing_reasons),
        'sizing': {'model': sizing.model, 'reasons': [r.as_dict() for r in sizing_reasons], **sizing.details, 'origin': 'calculated', 'uses_demo_synthetic': demo, 'input_provenance': input_provenance},
        'specs': _compare_specs(catalog.values),
        'data_basis': 'catalog_with_demo_synthetic_v1' if demo else 'catalog_with_assumptions_v1' if assumptions else 'published_catalog_v1', 'provenance': catalog.provenance,
        'resolved_facts': facts,
        'uses_demo_synthetic': bool(catalog.demo_synthetic) or any(a.get('category') == 'operation' for a in assumptions),
        'demo_synthetic': catalog.demo_synthetic,
        'vendor_confirmation_fields': list(dict.fromkeys(item['key'] for item in assumptions if item.get('requires_vendor_confirmation'))),
    }


def _match_groups(db: Session, object_type_id: int, processes: list, values: dict, tasks: list | None = None, *, plan=None, input_groups=()) -> list:
    readiness = readiness_filter(db)
    facts_map, profiles = metadata_maps(db)
    sources = _assessment_sources(db)
    by_task = _tasks_by_code(tasks)
    groups = []
    for process in processes:
        profile = profiles.get(process.id, {})
        demo_process = ((plan or {}).get('processes', {}).get(process.code)
                        or (plan or {}).get('technical_processes', {}).get(process.code))
        if demo_process and not profile.get('sizing'):
            profile = {**profile, 'sizing': demo_process['sizing']}
        bindings = {row.input_key: row.site_key for row in db.scalars(select(ObjectInputBindingRow).where(
            ObjectInputBindingRow.object_type_id == object_type_id, ObjectInputBindingRow.process_id == process.id))}
        rules = tuple(FilterRule(item.name, tuple(item.object_keys or []), tuple(item.robot_keys or []), item.op, item.mode,
                                 tuple((r.get('key', ''), r.get('label', '')) for r in (item.inputs or []) if isinstance(r, dict)), item.formula or '')
                      for item in db.scalars(select(ProcessFilterRow).where(ProcessFilterRow.process_id == process.id).order_by(ProcessFilterRow.id)))
        from app.domain.demo_synthetic import operation_context, operation_links
        task = by_task.get(process.code)
        process_values, profile, rules, bindings = operation_context(demo_process, values, task, profile, rules, bindings)
        rows = products_for_process(db, process.id)
        links = operation_links(demo_process)
        existing = {str(row.id) for row in rows}
        for link in links:
            if link['product_id'] not in existing:
                row = db.get(ProductRow, UUID(link['product_id']))
                if row is None:
                    raise ValueError('DEV-связь с отсутствующей карточкой: ' + link['product_id'])
                rows.append(row)
                existing.add(str(row.id))
        catalogs = {str(row.id): resolve_catalog(row, facts_map.get(str(row.id)), process_code=process.code, process_name=process.name, sources=sources, site=process_values, allow_demo=bool(plan)) for row in rows}
        robots = tuple(_robot_view(row, catalog=catalogs[str(row.id)]) for row in rows)
        hits = match_robots(process_code=process.code, process_name=process.name, site=process_values, rules=rules,
                            robots=robots, bindings=bindings, readiness=readiness, profile=profile)
        by_id = {str(row.id): row for row in rows}
        quantity_context = {'process_code': process.code, 'formula': process.count_formula,
                            'inputs': tuple((r['key'], r['label']) for r in (process.count_inputs or [])),
                            'bindings': bindings, 'flow_unit': (profile.get('sizing') or {}).get('flow_unit')}
        input_fields = [entry for group in input_groups if group['process_code'] in ('', process.code) for entry in group['fields']]
        if demo_process and demo_process.get('operation'):
            operation = demo_process['operation']
            input_fields.append({'key': 'operation_scope', 'label': 'Рабочая зона и режим',
                                 'value': operation['zone'], 'unit': '', 'origin': 'demo_synthetic',
                                 'explanation': operation['explanation'], 'category': 'operation',
                                 'scope': process.code, 'requires_vendor_confirmation': False})
        payloads = []
        for hit in hits:
            configuration = (demo_process or {}).get('configurations', {}).get(hit.product_id)
            if configuration:
                infra = demo_process.get('finance', {}).get('infra_pct', {}).get('value')
                if (not isinstance(infra, (int, float)) or isinstance(infra, bool)
                        or not 0 < infra <= NORM_BY_KEY['infra_pct'].max
                        or configuration.get('infrastructure_pct') != infra):
                    raise ValueError('DEV-комплектация должна покрываться допустимым коэффициентом инфраструктуры')
            linked_fields = [
                {'key': 'process_link', 'label': 'Назначение решения', 'unit': '', 'value': process.name,
                 'category': 'operation', 'requires_vendor_confirmation': True, **link}
                for link in links if link['product_id'] == hit.product_id]
            payloads.append(_candidate_payload(
                hit, by_id[hit.product_id], facts_map.get(hit.product_id, {}), profile,
                process_values, task, catalogs[hit.product_id], demo=bool(demo_process),
                input_fields=[*input_fields, *linked_fields], quantity_context=quantity_context,
                sizing_limitation=(demo_process or {}).get('sizing_limitation'),
                demo_configuration=configuration))
        eligible = {h['product_id'] for h in payloads if economy_eligible(h)}
        counted = [(hit, next(h['count'] for h in payloads if h['product_id'] == hit.product_id), '') for hit in hits if hit.product_id in eligible]
        attributes = {key: catalog.values for key, catalog in catalogs.items()}
        best = _best(counted, attributes, process.rank_key or '', process.rank_order or 'asc')
        technical_best = _best([(h, None, '') for h in hits], attributes, process.rank_key or '', process.rank_order or 'asc', technical=True)
        demo_counted = [(hit, next(h['count'] for h in payloads if h['product_id'] == hit.product_id), '') for hit in hits
                        if next(h['demo_economic_ready'] for h in payloads if h['product_id'] == hit.product_id)]
        demo_best = _best(demo_counted, attributes, process.rank_key or '', process.rank_order or 'asc')
        groups.append({'process_code': process.code, 'process_name': process.name, 'best_product_id': best,
                       'demo_best_product_id': demo_best, 'calculation_mode': 'demo' if demo_process else 'ordinary',
                       'technical_best_product_id': technical_best,
                       # Правило выбора лучшего: по характеристике процесса, а если её нет — самый дешёвый.
                       'rank_key': process.rank_key or '', 'rank_order': process.rank_order or 'asc',
                       'selection_policy': 'confirmed_economic_ready_v1',
                       'operation': ({**deepcopy(demo_process['operation']),
                                      'effective_fields': {key: process_values.get(key) for key in demo_process['operation'].get('fields', {})}}
                                     if demo_process and demo_process.get('operation') else None),
                       'layout_items': process.layout_items or default_items(process.code), 'hits': payloads})
    return groups


def economy_standards(db: Session) -> dict[str, float]:
    return {row.key: float(row.value) for row in db.scalars(select(EconomyNormRow))}


def economy_type_norms(db: Session) -> tuple[dict[str, dict[str, float]], dict[str, str]]:
    types = {row.id: (row.code, row.name) for row in db.scalars(select(SolutionTypeRow))}
    by_type: dict[str, dict[str, float]] = {}
    for row in db.scalars(select(EconomyNormOverrideRow)):
        if row.solution_type_id in types:
            by_type.setdefault(types[row.solution_type_id][0], {})[row.norm_key] = float(row.value)
    return by_type, {code: name for code, name in types.values()}


def type_norm_list(db: Session) -> dict:
    """Нормативы по типам: какие ключи можно переопределить и что уже переопределено."""
    types = {row.id: row for row in db.scalars(select(SolutionTypeRow))}
    counts = dict(db.execute(select(ProductRow.solution_type_id, func.count()).where(ProductRow.solution_type_id.is_not(None)).group_by(ProductRow.solution_type_id)).all())
    standard = economy_standards(db)
    overrides = []
    for row in db.scalars(select(EconomyNormOverrideRow).order_by(EconomyNormOverrideRow.solution_type_id, EconomyNormOverrideRow.norm_key)):
        kind = types.get(row.solution_type_id)
        if kind is None or row.norm_key not in NORM_BY_KEY:
            continue
        norm = NORM_BY_KEY[row.norm_key]
        overrides.append({
            "type_code": kind.code,
            "type_name": kind.name,
            "type_group": kind.group_name,
            "products": int(counts.get(kind.id, 0)),
            "key": row.norm_key,
            "label": norm.label,
            "unit": norm.unit,
            "value": float(row.value),
            "standard": standard.get(row.norm_key, norm.value),
            "rationale": row.rationale,
            "origin": row.origin,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        })
    norms = [
        {"key": key, "label": NORM_BY_KEY[key].label, "unit": NORM_BY_KEY[key].unit, "group": NORM_BY_KEY[key].group,
         "standard": standard.get(key, NORM_BY_KEY[key].value), "min": NORM_BY_KEY[key].min, "max": NORM_BY_KEY[key].max, "step": NORM_BY_KEY[key].step}
        for key in TYPE_NORMS
    ]
    return {"norms": norms, "overrides": overrides}


def save_type_norm(db: Session, *, type_code: str, key: str, value: float, rationale: str, origin: str) -> None:
    if key not in TYPE_NORMS:
        raise ValueError("Этот норматив по типам не переопределяется: он не доля от стоимости оборудования")
    if not rationale.strip():
        raise ValueError("Нужно обоснование: почему у этого типа своё значение")
    norm = NORM_BY_KEY[key]
    if not norm.min <= value <= norm.max:
        raise ValueError(f"Значение вне границ {norm.min}–{norm.max}")
    type_id = db.scalar(select(SolutionTypeRow.id).where(SolutionTypeRow.code == type_code))
    if type_id is None:
        raise KeyError(type_code)
    row = db.get(EconomyNormOverrideRow, (key, type_id))
    if row is None:
        row = EconomyNormOverrideRow(norm_key=key, solution_type_id=type_id, value=value)
        db.add(row)
    row.value = value
    row.rationale = rationale.strip()
    row.origin = origin.strip()
    db.commit()


def delete_type_norm(db: Session, *, type_code: str, key: str) -> None:
    type_id = db.scalar(select(SolutionTypeRow.id).where(SolutionTypeRow.code == type_code))
    if type_id is None:
        raise KeyError(type_code)
    db.execute(delete(EconomyNormOverrideRow).where(EconomyNormOverrideRow.norm_key == key, EconomyNormOverrideRow.solution_type_id == type_id))
    db.commit()


def economy_meta(db: Session) -> dict[str, dict]:
    """Обоснование и источник из базы. Пустое поле значит «как в коде»."""
    return {
        row.key: {"rationale": row.rationale or "", "origin": row.origin or "", "url": row.url or ""}
        for row in db.scalars(select(EconomyNormRow))
    }


def economy_norms(db: Session) -> list[dict]:
    stored = economy_standards(db)
    meta = economy_meta(db)
    updated = {row.key: row.updated_at for row in db.scalars(select(EconomyNormRow))}
    projects = list(db.scalars(select(ProjectRow.economy_overrides)))
    items = []
    for norm in NORMS:
        own = meta.get(norm.key) or {}
        items.append({
            "key": norm.key,
            "group": norm.group,
            "label": norm.label,
            "symbol": norm.symbol,
            "unit": norm.unit,
            "value": stored.get(norm.key, norm.value),
            "default": norm.value,
            "rationale": own.get("rationale") or norm.rationale,
            "origin": own.get("origin") or norm.source,
            "url": own.get("url") or "",
            "default_rationale": norm.rationale,
            "default_origin": norm.source,
            "min": norm.min,
            "max": norm.max,
            "step": norm.step,
            "site_key": {"energy_tariff": "energy_tariff_rub_kwh", "horizon_years": "payback_years"}.get(norm.key, ""),
            "projects_custom": sum(1 for item in projects if norm.key in (item or {})),
            "projects_total": len(projects),
            "updated_at": updated[norm.key].isoformat() if norm.key in updated and updated[norm.key] else None,
        })
    return items


def save_economy_norms(db: Session, values: dict[str, float], note: str, sources: dict[str, dict] | None = None) -> list[dict]:
    current = economy_standards(db)
    sources = sources or {}
    for key in set(values) | set(sources):
        norm = NORM_BY_KEY.get(key)
        if norm is None:
            continue
        old = current.get(key, norm.value)
        value = float(values[key]) if key in values else old
        row = db.get(EconomyNormRow, key)
        if row is None:
            row = EconomyNormRow(key=key, value=old)
            db.add(row)
        before = (row.rationale or "", row.origin or "", row.url or "")
        if key in sources:
            item = sources[key]
            rationale = (item.get("rationale") or "").strip()
            origin = (item.get("origin") or "").strip()
            row.rationale = rationale if rationale and rationale != norm.rationale else None
            row.origin = origin if origin and origin != norm.source else None
            row.url = (item.get("url") or "").strip() or None
        after = (row.rationale or "", row.origin or "", row.url or "")
        value_changed = abs(old - value) >= 1e-12
        if value_changed:
            row.value = value
        if value_changed or before != after:
            log_note = note
            if before != after and not value_changed:
                log_note = f"Изменён источник. {note}".strip()
            db.add(EconomyNormLogRow(key=key, old_value=old, new_value=value, note=log_note, origin=row.origin or norm.source))
    db.commit()
    return economy_norms(db)


def economy_norm_log(db: Session, limit: int = 50) -> list[dict]:
    rows = db.scalars(select(EconomyNormLogRow).order_by(EconomyNormLogRow.at.desc(), EconomyNormLogRow.id.desc()).limit(limit))
    return [
        {
            "key": row.key,
            "label": NORM_BY_KEY[row.key].label if row.key in NORM_BY_KEY else row.key,
            "unit": NORM_BY_KEY[row.key].unit if row.key in NORM_BY_KEY else "",
            "old_value": float(row.old_value) if row.old_value is not None else None,
            "new_value": float(row.new_value),
            "note": row.note,
            "origin": row.origin,
            "at": row.at.isoformat() if row.at else None,
        }
        for row in rows
    ]


def project_layout(db: Session, project_id: UUID) -> dict:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise KeyError(str(project_id))
    return project.layout or {}


def save_project_layout(db: Session, project_id: UUID, layout: dict) -> dict:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise KeyError(str(project_id))
    project.layout = layout
    db.commit()
    return project.layout


def save_economy_overrides(db: Session, project_id: UUID, values: dict) -> dict:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise KeyError(str(project_id))
    clean = clamp_overrides(values)
    project.economy_overrides = clean
    db.commit()
    return clean


def project_economy(
    db: Session,
    project_id: UUID,
    site: dict | None,
    choices: dict[str, str] | None,
    tasks: list[dict] | None = None,
    preview: dict | None = None,
    picks: dict[str, str] | None = None,
) -> dict:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise KeyError(str(project_id))
    stored_site, stored_tasks = _split_site(project.site or {})
    site = _public_site(site if site is not None else stored_site)
    use_tasks = tasks if tasks is not None else stored_tasks
    overrides = dict(preview) if preview is not None else dict(project.economy_overrides or {})
    active_overrides = dict(overrides)
    standard = economy_standards(db)
    load = overrides.get("load_factor", standard.get("load_factor", NORM_BY_KEY["load_factor"].value))
    from app.domain.demo_synthetic import project_plan, project_inputs
    plan = project_plan(project)
    input_groups = []
    if plan:
        site, use_tasks, input_groups = project_inputs(plan, site, use_tasks)
        processes = {**{c: p for c, p in plan['technical_processes'].items() if p.get('optional')}, **plan['processes']}
        defaults = {k: v['value'] for k, v in plan['finance'].items()}
        if site.get('energy_tariff_rub_kwh') is not None:
            defaults.pop('energy_tariff', None)
        defaults.update({f'process:{code}:{k}': v['value'] for code, process in processes.items() for k, v in process['finance'].items()})
        # Явный глобальный What-if должен менять и процесс, если нет его явного override.
        for code, process in processes.items():
            for key in process['finance']:
                if key in overrides:
                    defaults[f'process:{code}:{key}'] = overrides[key]
        overrides = {**defaults, **overrides}
    matched = run_match(db, project_id, scale_load(site, float(load)), scale_task_flows(use_tasks, float(load)), _prepared=True, _input_groups=input_groups)
    matched['demo_input_groups'] = input_groups
    report = _economy_report(db, matched, site, choices, use_tasks, overrides, dict(project.economy_overrides or {}), picks)
    report['active_overrides'] = active_overrides
    return report


def preview_economy(
    db: Session,
    object_code: str,
    site: dict | None,
    choices: dict[str, str] | None,
    tasks: list[dict] | None = None,
    preview: dict | None = None,
    picks: dict[str, str] | None = None,
) -> dict:
    values = _public_site(site)
    overrides = dict(preview or {})
    standard = economy_standards(db)
    load = overrides.get("load_factor", standard.get("load_factor", NORM_BY_KEY["load_factor"].value))
    use_tasks = tasks or []
    matched = match_object(db, object_code, scale_load(values, float(load)), scale_task_flows(use_tasks, float(load)))
    return _economy_report(db, matched, values, choices, use_tasks, overrides, {}, picks)


def _economy_report(
    db: Session,
    matched: dict,
    site: dict,
    choices,
    tasks,
    overrides: dict,
    saved: dict,
    picks: dict[str, str] | None = None,
) -> dict:
    picked = []
    blockers = []
    plan = matched.get('demo_plan')
    processes = {**{c: p for c, p in plan['technical_processes'].items() if p.get('optional')}, **plan['processes']} if plan else {}
    # Новые инженерные процессы доступны по явному выбору; прежний состав
    # программы и его финансовые результаты по умолчанию сохраняются.
    requested = set(picks if picks is not None else (choices or {}))
    automated = {code for code, process in processes.items()
                 if not process.get('optional') or code in requested} if plan else None
    manual = []
    if plan and not automated:
        blockers.append({'code': 'demo_scope_undefined', 'message': 'Нет процесса с достаточными техническими данными и моделью количества. Требуются обследование рабочих зон и эксплуатационное исполнение.'})
        for group in matched['groups']:
            relevant = [h for h in group['hits'] if h.get('uses_demo_synthetic')]
            for hit in relevant:
                blockers.extend({'process_code': group['process_code'], 'code': r['code'], 'message': hit['name'] + ': ' + r['message']} for r in hit['reasons'])
    known_codes = {g['process_code'] for g in matched['groups']}
    for code in set(picks if picks is not None else (choices or {})) - known_codes:
        blockers.append({'process_code': code, 'code': 'selection_invalid', 'message': 'Выбранный процесс отсутствует в текущем подборе'})
    for group in matched['groups']:
        code = group['process_code']
        if automated is not None and code not in automated:
            manual.append({'process_code': code, 'process_name': group['process_name'], 'mode': 'manual', 'cost_rub': None})
            if code in (picks or {}) or code in (choices or {}):
                blockers.append({'process_code': code, 'code': 'selection_invalid', 'message': 'Процесс находится вне области демонстрационной программы'})
            continue
        if plan:
            group = {**group, 'best_product_id': group.get('demo_best_product_id'),
                     'hits': [{**h, 'economic_ready': h.get('demo_economic_ready', False)} for h in group['hits']]}
        if picks is not None and code not in picks:
            blockers.append({'process_code': code, 'code': 'process_not_selected', 'message': 'Процесс не включён в расчёт проекта'})
            continue
        chosen = picks.get(code) if picks is not None else (choices or {}).get(code)
        hit, problems = select_hit(group, chosen, explicit=picks is not None)
        blockers.extend({'process_code': code, **p} for p in problems)
        if hit is not None:
            picked.append((group, hit))
    ids = [UUID(hit["product_id"]) for _group, hit in picked]
    products = list(db.scalars(select(ProductRow).where(ProductRow.id.in_(ids)))) if ids else []
    attrs = {str(row.id): _values(row) for row in products}
    type_codes = {row.id: row.code for row in db.scalars(select(SolutionTypeRow))}
    product_types = {str(row.id): type_codes.get(row.solution_type_id, "") for row in products}
    rows = []
    for group, hit in picked:
        values = attrs.get(hit["product_id"], {})
        raas = str(values.get("raas_available", "")).strip().lower() in {"true", "да", "yes", "1"}
        rows.append({
            "process_code": group["process_code"],
            "process_name": group["process_name"],
            "product_id": hit["product_id"],
            "name": hit["name"],
            "slug": hit["slug"],
            "image_url": hit.get("image_url"),
            "price_rub": values.get("price_rub"),
            "count": hit.get("count"),
            "power_w": _number(values.get("power_watt")) if values.get("power_watt") is not None else None,
            "raas_available": raas,
            "solution_type": product_types.get(hit["product_id"], ""),
            "specs": {key: values.get(key) for key in WORK_SPECS if values.get(key) not in (None, "")},
            "sizing": hit.get('sizing'),
            "assumptions": hit.get('assumptions', []),
            "applicability": hit.get('applicability', hit['verdict']),
            "uses_demo_synthetic": bool(plan),
            "operating_hours_per_day": (hit.get('sizing') or {}).get('operating_hours_per_day'),
        })
    blockers = list({(b.get('process_code'), b['code'], b['message']): b for b in blockers}.values())
    meta = economy_meta(db)
    by_type, type_names = economy_type_norms(db)
    standard = economy_standards(db)
    standard, type_meta = blend_by_type(standard, rows, by_type, type_names, meta)
    meta.update(type_meta)
    if plan:
        for key, entry in plan['finance'].items():
            if key in overrides:
                meta[key] = {**meta.get(key, {}), 'origin': 'demo_synthetic', 'rationale': entry['explanation']}
    report = calculate(rows, site, standard=standard, overrides=overrides, tasks=tasks, meta=meta, blockers=blockers)
    report['manual_processes'] = manual
    if plan and report['complete']:
        report['status'] = 'demo_estimate'
    if plan:
        report['disclaimer'] += ' Демонстрационная программа роботизации внутри объекта. Полные затраты предприятия неизвестны: ручные процессы вне программы сохраняются и не включаются в её экономию.'
        for figure in _financial_figures(report):
            figure['origin'] = 'calculated'
            figure['uses_demo_synthetic'] = True
    for item, row in zip(report['fleet'], rows):
        item['sizing'] = row.get('sizing')
        item['uses_demo_synthetic'] = bool(plan)
        item['assumptions'] = row.get('assumptions', [])
        item['applicability'] = row.get('applicability')
    report['assumptions'] = [
        {'process_code': group['process_code'], 'product_id': hit['product_id'], 'name': hit['name'],
         'fields': hit.get('assumptions', [])} for group, hit in picked if hit.get('assumptions')]
    if report['assumptions']:
        report['disclaimer'] += ' Расчёт предварительный: используются явно указанные допущения. Уточните характеристики и состав поставки у вендора.'
    report["coverage"] = {"requested_processes": len(matched["groups"]), "included_processes": len(picked)}
    report["selection_policy"] = "demo_economic_ready_v1" if plan else "confirmed_economic_ready_v1"
    report["selection_mode"] = "automatic" if picks is None else "explicit"
    report["scope"] = "automation_program" if plan else "project"
    report["project_id"] = matched["project_id"]
    report["saved_overrides"] = saved
    report['effective_overrides'] = overrides
    selected = {(group['process_code'], hit['product_id']) for group, hit in picked}
    synthetic = [
        {'process_code': group['process_code'], 'process_name': group['process_name'],
         'product_id': hit['product_id'], 'name': hit['name'], 'fields': hit['demo_synthetic'],
         'included_in_economy': (group['process_code'], hit['product_id']) in selected}
        for group in matched['groups'] for hit in group['hits'] if hit.get('demo_synthetic')
    ]
    if plan:
        synthetic.extend({**group, 'included_in_economy': bool(picked) if not group['process_code'] else group['process_code'] in {g['process_code'] for g, h in picked}} for group in matched.get('demo_input_groups', []))
        for code, process in {'': {'name': 'Финансовые допущения программы', 'finance': plan['finance']}, **processes}.items():
            if process.get('optional') and code not in automated:
                continue
            synthetic.append({'process_code': code, 'process_name': process['name'], 'product_id': '', 'name': 'Финансовые коэффициенты',
                              'included_in_economy': bool(picked), 'fields': [{'key': k, 'label': NORM_BY_KEY[k].label, **v,
                              'value': overrides.get(f'process:{code}:{k}' if code else k, v['value']),
                              'category': 'finance', 'vendor_confirmed': False, 'requires_vendor_confirmation': False} for k, v in process['finance'].items() if k in NORM_BY_KEY and (code or k in overrides)]})
    report['demo_synthetic'] = synthetic
    report['uses_demo_synthetic'] = bool(synthetic)
    if synthetic:
        from app.domain.demo_synthetic import NOTICE
        report['disclaimer'] += ' ' + NOTICE
    return report


def _economy_hit(group: dict, chosen_id: str | None, *, strict: bool = False) -> dict | None:
    return select_hit(group, chosen_id, explicit=strict)[0]


_COMPARE_SPECS = (
    ("payload_kg", "Грузоподъёмность", "кг", "high"),
    ("speed_loaded_ms", "Скорость", "м/с", "high"),
    ("work_time_h", "Время работы", "ч", "high"),
    ("charge_time_h", "Время зарядки", "ч", "low"),
    ("proizvoditelnost", "Производительность", "", "high"),
    ("throughput", "Пропускная способность", "", "high"),
    ("min_aisle_width_m", "Проезд", "м", "low"),
    ("lift_height_mm", "Высота подъёма", "мм", "high"),
    ("price_rub", "Цена", "₽", "low"),
)


def _compare_specs(attrs: dict) -> list[dict]:
    rows = []
    for key, label, unit, direction in _COMPARE_SPECS:
        number = _number(attrs.get(key))
        if number is None:
            continue
        rows.append({"key": key, "label": label, "unit": unit, "direction": direction, "value": number})
    return rows


def _priced(attrs: dict[str, dict], product_id: str) -> bool:
    price = _number((attrs.get(product_id) or {}).get("price_rub"))
    return price is not None and price > 0


def _best(counted: list, attrs: dict[str, dict], rank_key: str, rank_order: str, fallback_unknown: bool = False, *, technical=False) -> str | None:
    # Параметр fallback_unknown сохранён для совместимости вызовов, но допуск не меняет.
    pool = [item for item in counted if item[0].verdict == 'pass' and (technical or (valid_count(item[1]) and _priced(attrs, item[0].product_id)))]
    if not pool:
        return None

    def sort_key(item):
        hit, _amount, _note = item
        robot = attrs.get(hit.product_id, {})
        if rank_key:
            number = _number(robot.get(rank_key))
            missing = number is None
            directed = 0 if missing else (number if rank_order == "asc" else -number)
            return (missing, directed, hit.name)
        price = robot.get("price_rub")
        priced = price not in (None, "")
        try:
            number = float(price) if priced else 0
        except (TypeError, ValueError):
            priced, number = False, 0
        return (not priced, number, hit.name)

    pool.sort(key=sort_key)
    return pool[0][0].product_id


def _robot_view(row: ProductRow, assessment: dict | None = None, *, catalog=None) -> RobotView:
    catalog = catalog or resolve_catalog(row, assessment)
    from app.domain.demo_synthetic import technical_mode_values
    return RobotView(str(row.id), row.name, row.slug, technical_mode_values(catalog), row.image_url, row.trl, row.availability or None,
                     catalog.facts, catalog.issues, tuple(r for r in catalog.reasons if r.stage in {'functional', 'technical'}), catalog.site_conditions)


def _assessment_sources(db):
    return {row.id: {'id': row.id, 'kind': row.kind, 'publisher': row.publisher, 'url': row.url, 'title': row.title}
            for row in db.scalars(select(SourceRow))}


READINESS = "readiness"


def readiness_filter(db: Session) -> Readiness:
    row = db.get(MatchSettingRow, READINESS)
    return Readiness.from_value(row.value if row else None)


def match_filters(db: Session) -> dict:
    """Общие фильтры подбора и раскладка роботов по УГТ и стадии: админка по ней считает, сколько уйдёт в «Уточнить»."""
    assigned = select(ProductProcessRow.product_id).distinct()
    rows = db.execute(
        select(ProductRow.trl, ProductRow.availability, func.count())
        .where(ProductRow.id.in_(assigned))
        .group_by(ProductRow.trl, ProductRow.availability)
    ).all()
    return {
        "readiness": readiness_filter(db).as_value(),
        "stages": [{"code": code, "label": label} for code, label in STAGES.items()],
        "products": [{"trl": trl, "stage": stage or None, "count": int(count)} for trl, stage, count in rows],
    }


def save_match_filters(db: Session, readiness: dict) -> dict:
    value = Readiness.from_value(readiness).as_value()
    row = db.get(MatchSettingRow, READINESS)
    if row is None:
        db.add(MatchSettingRow(code=READINESS, value=value))
    else:
        row.value = value
    db.commit()
    return match_filters(db)


def _values(row: ProductRow) -> dict:
    values = {}
    for key, raw in (row.attrs or {}).items():
        if raw.get("status") == "known":
            values[key] = raw.get("value")
    if row.price_rub is not None:
        values["price_rub"] = float(row.price_rub)
    if row.trl is not None:
        values["trl"] = row.trl
    return values


def _financial_figures(value):
    if isinstance(value, dict):
        if 'value' in value and 'tex' in value:
            yield value
        for item in value.values():
            yield from _financial_figures(item)
    elif isinstance(value, list):
        for item in value:
            yield from _financial_figures(item)
