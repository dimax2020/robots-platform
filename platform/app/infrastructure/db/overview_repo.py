"""Сводка для обзора админки: что в каталоге и модели подбора требует внимания."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.domain.economy import NORMS
from app.infrastructure.db.catalog_repo import untyped_count
from app.infrastructure.db.job_repo import recent_jobs
from app.infrastructure.db.models import (
    EconomyNormLogRow,
    ObjectTypeRow,
    ProcessRow,
    ProductProcessRow,
    ProductRow,
    SourceRow,
)
from app.infrastructure.db.object_repo import unbound_inputs
from app.infrastructure.db.product_admin_repo import coverage
from app.infrastructure.db.taxonomy_repo import economy_meta, process_list


def overview(db: Session) -> dict:
    processes = process_list(db)
    readiness = []
    for item in processes:
        if not item["product_count"]:
            continue
        data = coverage(db, item["code"])
        average = sum(robot["ready"] for robot in data["robots"]) / len(data["robots"]) if data["robots"] else 0
        readiness.append({"code": item["code"], "name": item["name"], "ready": round(average, 3), "robots": data["total"], "complete": data["ready"]})
    readiness.sort(key=lambda item: item["ready"])
    objects = []
    for obj in db.scalars(select(ObjectTypeRow).order_by(ObjectTypeRow.name)):
        missing = unbound_inputs(db, obj.id)
        if missing:
            objects.append({"code": obj.code, "name": obj.name, "unbound": len(missing)})
    meta = economy_meta(db)
    last_norm = db.scalar(select(func.max(EconomyNormLogRow.at)))
    no_source = [
        norm.label for norm in NORMS
        if not ((meta.get(norm.key) or {}).get("origin") or norm.source).strip()
        or not ((meta.get(norm.key) or {}).get("rationale") or norm.rationale).strip()
    ]
    return {
        "products": {
            "total": db.scalar(select(func.count()).select_from(ProductRow)) or 0,
            "untyped": untyped_count(db),
            "without_process": db.scalar(select(func.count()).select_from(ProductRow).where(~ProductRow.id.in_(select(ProductProcessRow.product_id)))) or 0,
            "without_price": db.scalar(select(func.count()).select_from(ProductRow).where(ProductRow.price_rub.is_(None))) or 0,
        },
        "processes": {
            "total": len(processes),
            "without_robots": [{"code": item["code"], "name": item["name"]} for item in processes if not item["product_count"]],
            "without_filters": [{"code": item["code"], "name": item["name"]} for item in processes if item["product_count"] and not item["filter_count"]],
            "without_count": [{"code": item["code"], "name": item["name"]} for item in processes if item["product_count"] and not item["has_count"]],
            "without_objects": [{"code": item["code"], "name": item["name"]} for item in processes if not item["objects"]],
            "readiness": readiness,
            "average_ready": round(sum(item["ready"] for item in readiness) / len(readiness), 3) if readiness else 0,
        },
        "objects": objects,
        "norms": {
            "last_change": last_norm.isoformat() if last_norm else None,
            "without_source": no_source,
            "total": len(NORMS),
        },
        "sources": {
            "total": db.scalar(select(func.count()).select_from(SourceRow)) or 0,
            "without_url": db.scalar(select(func.count()).select_from(SourceRow).where((SourceRow.url.is_(None)) | (SourceRow.url == ""))) or 0,
        },
        "jobs": recent_jobs(db, limit=6),
        "process_count": db.scalar(select(func.count()).select_from(ProcessRow)) or 0,
    }
