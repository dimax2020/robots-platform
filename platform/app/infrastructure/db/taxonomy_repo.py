from uuid import UUID, uuid4

from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session

from app.domain.economy import NORM_BY_KEY, NORMS, calculate, scale_load
from app.domain.formula import _number, identifiers
from app.domain.specs import CANON_LABELS
from app.domain.match import FilterRule, RobotView, match_robots, robot_count, usage_for
from app.infrastructure.db.models import (
    AttributeDefRow,
    EconomyNormLogRow,
    EconomyNormRow,
    IndustryRow,
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
        objects.append({"code": obj.code, "name": obj.name, "industries": industry_codes, "processes": process_codes})
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
        objects.append({"code": obj.code, "name": obj.name, "bindings": bindings})
    return {
        "code": process.code,
        "name": process.name,
        "filters": filters,
        "count_inputs": process.count_inputs or [],
        "count_formula": process.count_formula or "",
        "rank_key": process.rank_key or "",
        "rank_order": process.rank_order or "asc",
        "objects": objects,
    }


def save_process_setup(db: Session, process_code: str, payload: dict) -> dict:
    process = db.scalar(select(ProcessRow).where(ProcessRow.code == process_code))
    if process is None:
        raise KeyError(process_code)
    process.count_formula = payload.get("count_formula") or ""
    process.count_inputs = payload.get("count_inputs") or []
    process.rank_key = payload.get("rank_key") or ""
    process.rank_order = payload.get("rank_order") or "asc"
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
        filters = list(db.scalars(select(ProcessFilterRow).where(ProcessFilterRow.process_id == process.id).order_by(ProcessFilterRow.id)))
        inputs: list[dict] = []
        seen: set[str] = set()
        for item in filters:
            for row in item.inputs or []:
                if not isinstance(row, dict):
                    continue
                key = str(row.get("key") or "")
                if not key or key in seen:
                    continue
                seen.add(key)
                inputs.append({"key": key, "label": item.name or row.get("label") or key, "kind": "filter"})
        for row in process.count_inputs or []:
            if not isinstance(row, dict):
                continue
            key = str(row.get("key") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            inputs.append({"key": key, "label": row.get("label") or key, "kind": "count"})
        processes.append({
            "code": process.code,
            "name": process.name,
            "product_count": int(counts.get(process.id, 0)),
            "enabled": process.id in enabled_ids,
            "inputs": inputs,
            "bindings": bindings_by_process.get(process.id, {}),
        })
    return {"code": obj.code, "name": obj.name, "processes": processes}


def save_object_setup(db: Session, object_code: str, payload: dict) -> dict:
    obj = db.scalar(select(ObjectTypeRow).where(ObjectTypeRow.code == object_code))
    if obj is None:
        raise KeyError(object_code)
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


def create_project(db: Session, *, name: str, object_code: str, site: dict) -> dict:
    obj = db.scalar(select(ObjectTypeRow).where(ObjectTypeRow.code == object_code))
    if obj is None:
        raise KeyError(object_code)
    project = ProjectRow(id=uuid4(), name=name, object_type_id=obj.id, site=site)
    db.add(project)
    db.flush()
    process_ids = list(db.scalars(select(ObjectProcessRow.process_id).where(ObjectProcessRow.object_type_id == obj.id)))
    for process_id in process_ids:
        db.add(ProjectProcessRow(project_id=project.id, process_id=process_id, enabled=True))
    db.commit()
    return project_view(db, project.id)


def update_project(db: Session, project_id: UUID, *, site: dict | None, enabled: dict[str, bool] | None) -> dict:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise KeyError(str(project_id))
    if site is not None:
        project.site = site
    if enabled is not None:
        for code, flag in enabled.items():
            process = db.scalar(select(ProcessRow).where(ProcessRow.code == code))
            if process is None:
                continue
            link = db.get(ProjectProcessRow, (project.id, process.id))
            if link is None:
                db.add(ProjectProcessRow(project_id=project.id, process_id=process.id, enabled=flag))
            else:
                link.enabled = flag
    db.commit()
    return project_view(db, project.id)


def project_view(db: Session, project_id: UUID) -> dict:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise KeyError(str(project_id))
    obj = db.get(ObjectTypeRow, project.object_type_id)
    processes = []
    stmt = (
        select(ProcessRow, ProjectProcessRow.enabled)
        .join(ProjectProcessRow, ProjectProcessRow.process_id == ProcessRow.id)
        .where(ProjectProcessRow.project_id == project.id)
        .order_by(ProcessRow.name)
    )
    for process, enabled in db.execute(stmt):
        filters = list(db.scalars(select(ProcessFilterRow).where(ProcessFilterRow.process_id == process.id)))
        processes.append({
            "code": process.code,
            "name": process.name,
            "enabled": enabled,
            "filters": [
                {"name": item.name, "object_keys": item.object_keys, "robot_keys": item.robot_keys, "op": item.op, "mode": item.mode, "inputs": item.inputs or [], "formula": item.formula or ""}
                for item in filters
            ],
        })
    return {
        "id": str(project.id),
        "name": project.name,
        "object_code": obj.code if obj else None,
        "site": project.site,
        "economy_overrides": project.economy_overrides or {},
        "processes": processes,
    }


def run_match(db: Session, project_id: UUID, site: dict | None = None) -> dict:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise KeyError(str(project_id))
    values = site if site is not None else (project.site or {})
    groups = []
    stmt = (
        select(ProcessRow)
        .join(ProjectProcessRow, ProjectProcessRow.process_id == ProcessRow.id)
        .where(ProjectProcessRow.project_id == project.id, ProjectProcessRow.enabled.is_(True))
        .order_by(ProcessRow.name)
    )
    for process in db.scalars(stmt):
        bindings = {
            row.input_key: row.site_key
            for row in db.scalars(select(ObjectInputBindingRow).where(
                ObjectInputBindingRow.object_type_id == project.object_type_id,
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
        robots = tuple(RobotView(str(row.id), row.name, row.slug, _values(row), row.image_url) for row in rows)
        hits = match_robots(
            process_code=process.code,
            process_name=process.name,
            site=values,
            rules=rules,
            robots=robots,
            bindings=bindings,
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
            "hits": [
                {
                    "product_id": hit.product_id,
                    "name": hit.name,
                    "slug": hit.slug,
                    "verdict": hit.verdict,
                    "notes": list(hit.notes),
                    "image_url": hit.image_url,
                    "count": amount,
                    "count_note": note,
                    "specs": _compare_specs(by_id.get(hit.product_id, {})),
                }
                for hit, amount, note in counted
            ],
        })
    return {"project_id": str(project.id), "groups": groups}


def economy_standards(db: Session) -> dict[str, float]:
    return {row.key: float(row.value) for row in db.scalars(select(EconomyNormRow))}


def economy_norms(db: Session) -> list[dict]:
    stored = economy_standards(db)
    updated = {row.key: row.updated_at for row in db.scalars(select(EconomyNormRow))}
    items = []
    for norm in NORMS:
        items.append({
            "key": norm.key,
            "group": norm.group,
            "label": norm.label,
            "symbol": norm.symbol,
            "unit": norm.unit,
            "value": stored.get(norm.key, norm.value),
            "default": norm.value,
            "rationale": norm.rationale,
            "origin": norm.source,
            "min": norm.min,
            "max": norm.max,
            "step": norm.step,
            "updated_at": updated[norm.key].isoformat() if norm.key in updated and updated[norm.key] else None,
        })
    return items


def save_economy_norms(db: Session, values: dict[str, float], note: str) -> list[dict]:
    current = economy_standards(db)
    for key, raw in values.items():
        norm = NORM_BY_KEY.get(key)
        if norm is None:
            continue
        value = float(raw)
        old = current.get(key, norm.value)
        if abs(old - value) < 1e-12:
            continue
        row = db.get(EconomyNormRow, key)
        if row is None:
            db.add(EconomyNormRow(key=key, value=value))
        else:
            row.value = value
        db.add(EconomyNormLogRow(key=key, old_value=old, new_value=value, note=note))
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
            "at": row.at.isoformat() if row.at else None,
        }
        for row in rows
    ]


def save_economy_overrides(db: Session, project_id: UUID, values: dict) -> dict:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise KeyError(str(project_id))
    clean = {key: float(value) for key, value in (values or {}).items() if key in NORM_BY_KEY and value is not None}
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
) -> dict:
    project = db.get(ProjectRow, project_id)
    if project is None:
        raise KeyError(str(project_id))
    site = site if site is not None else (project.site or {})
    overrides = dict(preview) if preview is not None else dict(project.economy_overrides or {})
    standard = economy_standards(db)
    load = overrides.get("load_factor", standard.get("load_factor", NORM_BY_KEY["load_factor"].value))
    matched = run_match(db, project_id, scale_load(site, float(load)))
    picked = []
    for group in matched["groups"]:
        hit = _economy_hit(group, (choices or {}).get(group["process_code"]))
        if hit is not None:
            picked.append((group, hit))
    ids = [UUID(hit["product_id"]) for _group, hit in picked]
    attrs = {str(row.id): _values(row) for row in db.scalars(select(ProductRow).where(ProductRow.id.in_(ids)))} if ids else {}
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
        })
    report = calculate(rows, site, standard=standard, overrides=overrides, tasks=tasks)
    report["project_id"] = matched["project_id"]
    report["saved_overrides"] = project.economy_overrides or {}
    return report


def _economy_hit(group: dict, chosen_id: str | None) -> dict | None:
    hits = group.get("hits") or []
    if chosen_id:
        found = next((hit for hit in hits if hit["product_id"] == chosen_id), None)
        if found is not None:
            return found
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
