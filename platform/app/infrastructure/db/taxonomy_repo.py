import json
import re
from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.domain.economy import NORM_BY_KEY, NORMS, TYPE_NORMS, blend_by_type, calculate, clamp_overrides, scale_load
from app.domain.layout_items import clean_items, default_items
from app.domain.formula import _number, identifiers
from app.domain.specs import CANON_LABELS
from app.domain.match import STAGES, FilterRule, Readiness, RobotView, match_robots, robot_count, usage_for
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
    robots = tuple(_robot_view(row) for row in rows)
    hits = match_robots(process_code=process.code, process_name=process.name, site=site, rules=rules, robots=robots, bindings=bindings, readiness=readiness_filter(db))
    by_id = {str(row.id): _values(row) for row in rows}
    count_inputs = tuple((row.get("key", ""), row.get("label", "")) for row in (payload.get("count_inputs") or []) if isinstance(row, dict))
    counted = []
    for hit in hits:
        amount, note = robot_count(payload.get("count_formula") or "", count_inputs, bindings, site, by_id.get(hit.product_id, {}))
        counted.append((hit, amount, note))
    best = _best(counted, by_id, payload.get("rank_key") or "", payload.get("rank_order") or "asc")
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
        "robots": [
            {
                "product_id": hit.product_id,
                "name": hit.name,
                "slug": hit.slug,
                "verdict": hit.verdict,
                "notes": list(hit.notes),
                "trl": hit.trl,
                "stage": hit.stage,
                "count": amount,
                "count_note": note,
            }
            for hit, amount, note in counted[:40]
        ],
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
    for process, enabled, reason in db.execute(stmt):
        filters = list(db.scalars(select(ProcessFilterRow).where(ProcessFilterRow.process_id == process.id)))
        processes.append({
            "code": process.code,
            "name": process.name,
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


def run_match(db: Session, project_id: UUID, site: dict | None = None) -> dict:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise KeyError(str(project_id))
    values = _public_site(site if site is not None else (project.site or {}))
    processes = list(db.scalars(
        select(ProcessRow)
        .join(ProjectProcessRow, ProjectProcessRow.process_id == ProcessRow.id)
        .where(ProjectProcessRow.project_id == project.id, ProjectProcessRow.enabled.is_(True))
        .order_by(ProcessRow.name)
    ))
    return {"project_id": str(project.id), "groups": _match_groups(db, project.object_type_id, processes, values)}


def match_object(db: Session, object_code: str, site: dict | None) -> dict:
    obj = db.scalar(select(ObjectTypeRow).where(ObjectTypeRow.code == object_code))
    if obj is None:
        raise KeyError(object_code)
    processes = list(db.scalars(
        select(ProcessRow)
        .join(ObjectProcessRow, ObjectProcessRow.process_id == ProcessRow.id)
        .where(ObjectProcessRow.object_type_id == obj.id)
        .order_by(ProcessRow.name)
    ))
    return {"project_id": None, "groups": _match_groups(db, obj.id, processes, _public_site(site))}


def _match_groups(db: Session, object_type_id: int, processes: list, values: dict) -> list:
    readiness = readiness_filter(db)
    groups = []
    for process in processes:
        bindings = {
            row.input_key: row.site_key
            for row in db.scalars(select(ObjectInputBindingRow).where(
                ObjectInputBindingRow.object_type_id == object_type_id,
                ObjectInputBindingRow.process_id == process.id,
            ))
        }
        rules = tuple(
            FilterRule(
                item.name,
                tuple(item.object_keys or []),
                tuple(item.robot_keys or []),
                item.op,
                item.mode,
                tuple((row.get("key", ""), row.get("label", "")) for row in (item.inputs or []) if isinstance(row, dict)),
                item.formula or "",
            )
            for item in db.scalars(select(ProcessFilterRow).where(ProcessFilterRow.process_id == process.id).order_by(ProcessFilterRow.id))
        )
        rows = products_for_process(db, process.id)
        robots = tuple(_robot_view(row) for row in rows)
        hits = match_robots(
            process_code=process.code,
            process_name=process.name,
            site=values,
            rules=rules,
            robots=robots,
            bindings=bindings,
            readiness=readiness,
        )
        by_id = {str(row.id): _values(row) for row in rows}
        counted = []
        for hit in hits:
            amount, note = robot_count(
                process.count_formula or "",
                tuple((row.get("key", ""), row.get("label", "")) for row in (process.count_inputs or []) if isinstance(row, dict)),
                bindings,
                values,
                by_id.get(hit.product_id, {}),
            )
            counted.append((hit, amount, note))
        best = _best(counted, by_id, process.rank_key or "", process.rank_order or "asc")
        groups.append({
            "process_code": process.code,
            "process_name": process.name,
            "best_product_id": best,
            "layout_items": process.layout_items or default_items(process.code),
            "hits": [
                {
                    "product_id": hit.product_id,
                    "name": hit.name,
                    "slug": hit.slug,
                    "verdict": hit.verdict,
                    "notes": list(hit.notes),
                    "image_url": hit.image_url,
                    "trl": hit.trl,
                    "stage": hit.stage,
                    "count": amount,
                    "count_note": note,
                    "specs": _compare_specs(by_id.get(hit.product_id, {})),
                }
                for hit, amount, note in counted
            ],
        })
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
    site = _public_site(site if site is not None else (project.site or {}))
    overrides = dict(preview) if preview is not None else dict(project.economy_overrides or {})
    standard = economy_standards(db)
    load = overrides.get("load_factor", standard.get("load_factor", NORM_BY_KEY["load_factor"].value))
    matched = run_match(db, project_id, scale_load(site, float(load)))
    return _economy_report(db, matched, site, choices, tasks, overrides, dict(project.economy_overrides or {}), picks)


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
    matched = match_object(db, object_code, scale_load(values, float(load)))
    return _economy_report(db, matched, values, choices, tasks, overrides, {}, picks)


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
    for group in matched["groups"]:
        if picks is not None and group["process_code"] not in picks:
            continue
        chosen = picks.get(group["process_code"]) if picks is not None else (choices or {}).get(group["process_code"])
        hit = _economy_hit(group, chosen, strict=picks is not None)
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
        })
    meta = economy_meta(db)
    by_type, type_names = economy_type_norms(db)
    standard = economy_standards(db)
    standard, type_meta = blend_by_type(standard, rows, by_type, type_names, meta)
    meta.update(type_meta)
    report = calculate(rows, site, standard=standard, overrides=overrides, tasks=tasks, meta=meta)
    report["project_id"] = matched["project_id"]
    report["saved_overrides"] = saved
    return report


def _economy_hit(group: dict, chosen_id: str | None, *, strict: bool = False) -> dict | None:
    hits = group.get("hits") or []
    if chosen_id:
        found = next((hit for hit in hits if hit["product_id"] == chosen_id), None)
        if found is not None:
            return found
        if strict:
            return None
    if strict:
        return None
    best = group.get("best_product_id")
    if best:
        return next((hit for hit in hits if hit["product_id"] == best), None)
    return None


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


def _best(counted: list, attrs: dict[str, dict], rank_key: str, rank_order: str) -> str | None:
    pool = [item for item in counted if item[0].verdict == "pass"] or [item for item in counted if item[0].verdict == "conditional"]
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


def _robot_view(row: ProductRow) -> RobotView:
    return RobotView(str(row.id), row.name, row.slug, _values(row), row.image_url, row.trl, row.availability or None)


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
