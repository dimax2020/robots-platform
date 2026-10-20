"""Аналитика подбора для кабинетов вендора и администратора.

Журнал пишет факт запуска. Готовность карточек считается по текущему каталогу,
теми же полями, что покрытие процесса в админке.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.domain.formula import identifiers
from app.domain.match_digest import count_reasons, digest_match, participation, public_params
from app.domain.specs import CANON_LABELS
from app.infrastructure.db.models import (
    MatchJournalRow,
    ObjectProcessRow,
    ObjectTypeRow,
    ProcessFilterRow,
    ProcessRow,
    ProductOfferRow,
    ProductProcessRow,
    ProductRow,
    SolutionTypeRow,
    VendorProfileRow,
    VendorRequestRow,
)
from app.infrastructure.db.object_repo import object_fields
from app.infrastructure.db.product_admin_repo import ECONOMY_KEYS, _filled, _labels
from app.infrastructure.db.vendor_repo import same_maker, vendor_stats

_KEEP = 400
_RANK = {"условие": 0, "количество": 1, "лучший": 2, "экономика": 3}


def remember_match(db: Session, *, source: str, object_code: str, object_name: str, site: dict | None, groups: list | None) -> None:
    """Один показ подбора. Имя заказчика и номер проекта сюда не кладём."""
    summary = digest_match(groups)
    _attach_makers(db, summary)
    params = _labeled_site(db, object_code, site) if summary["outcome"] == "empty" else []
    db.add(MatchJournalRow(
        id=uuid4(),
        object_code=(object_code or "")[:80],
        object_name=(object_name or "Объект")[:160],
        source=source if source in {"project", "preview"} else "project",
        outcome=summary["outcome"],
        site=params,
        summary=summary,
    ))
    db.flush()
    stale = list(db.scalars(select(MatchJournalRow.id).order_by(MatchJournalRow.created_at.desc()).offset(_KEEP)))
    if stale:
        db.execute(delete(MatchJournalRow).where(MatchJournalRow.id.in_(stale)))
    db.commit()


def remember_project_match(db: Session, project, site: dict | None, groups: list | None) -> None:
    obj = db.get(ObjectTypeRow, project.object_type_id)
    used = site if site is not None else (project.site or {})
    remember_match(
        db,
        source="project",
        object_code=obj.code if obj else "",
        object_name=obj.name if obj else "Объект",
        site=used,
        groups=groups,
    )


def remember_preview_match(db: Session, object_code: str, site: dict | None, groups: list | None) -> None:
    obj = db.scalar(select(ObjectTypeRow).where(ObjectTypeRow.code == object_code))
    remember_match(
        db,
        source="preview",
        object_code=object_code,
        object_name=obj.name if obj else object_code,
        site=site,
        groups=groups,
    )


def vendor_board(db: Session, profile: VendorProfileRow) -> dict:
    stats = vendor_stats(db, profile.manufacturer)
    robots = _robot_cards(db, profile.manufacturer, profile.city or "")
    _mark_revisions(db, profile.user_id, robots)
    journal = _journal(db)
    events = []
    success = 0
    empty = 0
    reason_chunks: list[list[str]] = []
    for row in journal:
        event = _vendor_event(row, profile.manufacturer)
        if event is None:
            continue
        if event["outcome"] == "success":
            success += 1
        else:
            empty += 1
            reason_chunks.append(event["reasons"])
        if len(events) < 30:
            events.append(event)
    pie = _pie(robots)
    return {
        **stats,
        "pie": pie,
        "matches": {"total": success + empty, "success": success, "empty": empty},
        "reasons": count_reasons(reason_chunks),
        "events": events,
        "robots": robots,
        "city": profile.city or "",
    }


def admin_board(db: Session) -> dict:
    journal = _journal(db)
    robots = _robot_cards(db, None, "")
    profiles = list(db.scalars(select(VendorProfileRow).order_by(VendorProfileRow.company_name)))
    by_maker: dict[str, list[dict]] = {}
    for robot in robots:
        by_maker.setdefault(robot["manufacturer"] or "Без производителя", []).append(robot)
    seen: set[str] = set()
    vendors = []
    for profile in profiles:
        bucket, key = _take_bucket(by_maker, profile.manufacturer)
        seen.add(key)
        vendors.append(_vendor_card(profile, bucket, journal))
    for maker, bucket in by_maker.items():
        if maker in seen:
            continue
        vendors.append(_vendor_card(None, bucket, journal, maker=maker))
    vendors.sort(key=lambda item: (item["ok"], item["rating"], item["company"]))
    vendor_ok = sum(1 for item in vendors if item["ok"])
    robot_pie = _pie(robots)
    success = sum(1 for row in journal if row.outcome == "success")
    empty_rows = [row for row in journal if row.outcome != "success"]
    problems = [robot for robot in robots if robot["state"] != "in"]
    problems.sort(key=lambda item: (item["state"] != "out", item["manufacturer"], item["name"]))
    return {
        "matches": {"total": len(journal), "success": success, "empty": len(empty_rows)},
        "reasons": count_reasons([list((row.summary or {}).get("reasons") or []) for row in empty_rows]),
        "vendor_pie": {"ok": vendor_ok, "fix": len(vendors) - vendor_ok},
        "robot_pie": {"in": robot_pie["in"], "out": robot_pie["out"], "note": robot_pie["note"]},
        "vendors": vendors,
        "problems": problems,
    }


def _comment_text(comment: str, *, required: bool) -> str:
    text = comment.strip()
    if required and not text:
        raise ValueError("Напишите, что исправить. Без комментария производитель не поймёт причину.")
    if len(text) > 2000:
        raise ValueError("Комментарий длиннее 2000 знаков. Сократите его.")
    return text


def _store_fix(db: Session, product: ProductRow, profile: VendorProfileRow, text: str, now: datetime) -> str:
    """Кладёт или обновляет заявку на доработку. Каталог не трогает, коммит снаружи."""
    existing = _open_fix(db, profile.user_id, product.slug)
    if existing is not None:
        existing.status = "revision"
        existing.admin_comment = text
        existing.owner_hidden = False
        existing.decided_at = now
        existing.title = f"Дополните карточку «{product.name}»"
        return str(existing.id)
    codes = [
        code for code, in db.execute(
            select(ProcessRow.code)
            .join(ProductProcessRow, ProductProcessRow.process_id == ProcessRow.id)
            .where(ProductProcessRow.product_id == product.id)
        )
    ]
    row = VendorRequestRow(
        id=uuid4(),
        user_id=profile.user_id,
        kind="product_update",
        title=f"Дополните карточку «{product.name}»",
        payload={
            "slug": product.slug,
            "robot": {
                "name": product.name,
                "summary": product.summary or "",
                "price_rub": None if product.price_rub is None else float(product.price_rub),
                "processes": codes,
                "attrs": [],
            },
        },
        status="revision",
        admin_comment=text,
        decided_at=now,
    )
    db.add(row)
    db.flush()
    return str(row.id)


def ask_fix(db: Session, slug: str, comment: str) -> dict:
    """Просьба вендору дополнить одну карточку. В каталог сама не пишет."""
    text = _comment_text(comment, required=True)
    product = db.scalar(select(ProductRow).where(ProductRow.slug == slug))
    if product is None:
        raise KeyError(slug)
    profile = _profile_for(db, product.manufacturer or "")
    if profile is None:
        raise ValueError("У этого производителя нет кабинета. Сначала заведите вендора, потом отправьте правку.")
    request_id = _store_fix(db, product, profile, text, datetime.now(timezone.utc))
    db.commit()
    return {"ok": True, "id": request_id, "updated": False, "sent": 1}


def ask_fixes(db: Session, items: list[dict]) -> dict:
    """Одна кнопка по вендору: заявка на каждую модель с пробелом. Каталог не меняется."""
    if len(items) > 200:
        raise ValueError("За один раз можно отправить не больше 200 карточек.")
    now = datetime.now(timezone.utc)
    profiles: dict[str, VendorProfileRow | None] = {}
    sent = 0
    for item in items:
        slug = str(item.get("slug") or "").strip()
        if not slug:
            continue
        text = str(item.get("comment") or "").strip() or "Дополните карточку: без этих данных робот не участвует в подборе."
        if len(text) > 2000:
            text = text[:2000]
        product = db.scalar(select(ProductRow).where(ProductRow.slug == slug))
        if product is None:
            continue
        maker = product.manufacturer or ""
        if maker not in profiles:
            profiles[maker] = _profile_for(db, maker)
        profile = profiles[maker]
        if profile is None:
            continue
        _store_fix(db, product, profile, text, now)
        sent += 1
    if not sent:
        raise ValueError("У этого вендора нет кабинета или не нашлось карточек, которые можно отправить на доработку.")
    db.commit()
    return {"ok": True, "sent": sent}


def _journal(db: Session) -> list[MatchJournalRow]:
    return list(db.scalars(select(MatchJournalRow).order_by(MatchJournalRow.created_at.desc()).limit(_KEEP)))


def _robot_cards(db: Session, manufacturer: str | None, city: str) -> list[dict]:
    keys_by_process = _keys_by_process(db)
    on_object = set(db.scalars(
        select(ObjectProcessRow.process_id)
        .join(ObjectTypeRow, ObjectTypeRow.id == ObjectProcessRow.object_type_id)
        .where(ObjectTypeRow.in_match.is_(True))
    ))
    types = {row.id: row.name for row in db.scalars(select(SolutionTypeRow))}
    labels = _labels(db)
    query = select(ProductRow).order_by(ProductRow.name)
    if manufacturer is not None:
        query = query.where(ProductRow.manufacturer == manufacturer)
    products = list(db.scalars(query))
    ids = [row.id for row in products]
    links: dict[UUID, list[tuple[int, str, str]]] = {item: [] for item in ids}
    if ids:
        joined = db.execute(
            select(ProductProcessRow.product_id, ProcessRow.id, ProcessRow.code, ProcessRow.name)
            .join(ProcessRow, ProcessRow.id == ProductProcessRow.process_id)
            .where(ProductProcessRow.product_id.in_(ids))
            .order_by(ProcessRow.name)
        )
        for product_id, process_id, code, name in joined:
            links.setdefault(product_id, []).append((process_id, code, name))
    offers = {
        row.product_id: int(row.offers)
        for row in db.scalars(select(ProductOfferRow).where(ProductOfferRow.product_id.in_(ids)))
    } if ids else {}
    cards = []
    for row in products:
        linked = links.get(row.id, [])
        gaps = _gaps(row, linked, keys_by_process)
        state, headline = participation(bool(linked), any(item[0] in on_object for item in linked), gaps)
        cards.append({
            "slug": row.slug,
            "name": row.name,
            "summary": row.summary,
            "price_rub": None if row.price_rub is None else float(row.price_rub),
            "image_url": row.image_url,
            "trl": row.trl,
            "availability": row.availability,
            "solution_type": types.get(row.solution_type_id),
            "manufacturer": row.manufacturer or "",
            "city": city,
            "state": state,
            "headline": headline,
            "gaps": gaps,
            "processes": [{"code": code, "name": name} for _pid, code, name in linked],
            "offers": int(offers.get(row.id, 0)),
            "highlights": _highlights(row, gaps, labels),
            "revision_comment": "",
            "has_cabinet": False,
        })
    cards.sort(key=lambda item: ({"out": 0, "note": 1, "in": 2}[item["state"]], item["name"]))
    return cards


def _gaps(product: ProductRow, linked: list[tuple[int, str, str]], keys_by_process: dict[int, list[dict]]) -> list[dict]:
    seen: dict[str, dict] = {}
    for process_id, _code, _name in linked:
        for item in keys_by_process.get(process_id, []):
            if _filled(product, item["key"]):
                continue
            prev = seen.get(item["key"])
            if prev is None or _RANK.get(item["used_in"], 9) < _RANK.get(prev["used_in"], 9):
                seen[item["key"]] = {"key": item["key"], "label": item["label"], "used_in": item["used_in"]}
    return list(seen.values())


def _keys_by_process(db: Session) -> dict[int, list[dict]]:
    """Те же поля, что required_keys, но одним проходом: админке не нужно ходить в базу по каждому процессу."""
    labels = _labels(db)
    names = dict(ECONOMY_KEYS)
    filters: dict[int, list] = {}
    for item in db.scalars(select(ProcessFilterRow)):
        filters.setdefault(item.process_id, []).append(item)
    result: dict[int, list[dict]] = {}
    for process in db.scalars(select(ProcessRow)):
        wanted: dict[str, str] = {}
        for item in filters.get(process.id, []):
            inputs = {row.get("key") for row in (item.inputs or []) if isinstance(row, dict)}
            for name in identifiers(item.formula or ""):
                bare = name.split(".", 1)[1] if name.startswith("robot.") else name
                if bare not in inputs and bare not in wanted:
                    wanted[bare] = "условие"
            for key in item.robot_keys or []:
                wanted.setdefault(key, "условие")
        count_inputs = {row.get("key") for row in (process.count_inputs or []) if isinstance(row, dict)}
        for name in identifiers(process.count_formula or ""):
            if name.startswith("robot."):
                wanted.setdefault(name.split(".", 1)[1], "количество")
            elif name not in count_inputs:
                wanted.setdefault(name, "количество")
        if process.rank_key:
            wanted.setdefault(process.rank_key, "лучший")
        # Цена нужна, чтобы робота можно было считать. Мощность и аренда живут в экономике и сами по себе робота из подбора не выкидывают.
        wanted.setdefault("price_rub", "экономика")
        result[process.id] = [
            {"key": key, "label": names.get(key) or labels.get(key) or CANON_LABELS.get(key, key), "used_in": used}
            for key, used in wanted.items()
        ]
    return result


def _highlights(product: ProductRow, gaps: list[dict], labels: dict[str, str]) -> list[dict]:
    items = [{"label": gap["label"], "value": "нужно заполнить", "missing": True} for gap in gaps[:4]]
    if len(items) >= 4:
        return items
    skip = {gap["key"] for gap in gaps}
    for key, raw in (product.attrs or {}).items():
        if not isinstance(raw, dict) or raw.get("value") in (None, "") or key in skip:
            continue
        value = str(raw.get("value"))
        items.append({"label": labels.get(key, key), "value": value[:40], "missing": False})
        if len(items) >= 4:
            break
    return items


def _pie(robots: list[dict]) -> dict:
    participating = sum(1 for item in robots if item["state"] != "out")
    return {
        "in": participating,
        "out": sum(1 for item in robots if item["state"] == "out"),
        "note": sum(1 for item in robots if item["state"] == "note"),
    }


def _mark_revisions(db: Session, user_id: UUID, robots: list[dict]) -> None:
    rows = db.scalars(select(VendorRequestRow).where(
        VendorRequestRow.user_id == user_id,
        VendorRequestRow.status == "revision",
        VendorRequestRow.owner_hidden.is_(False),
    ))
    by_slug = {}
    for row in rows:
        slug = str((row.payload or {}).get("slug") or "")
        if slug and row.admin_comment:
            by_slug[slug] = row.admin_comment
    for robot in robots:
        robot["revision_comment"] = by_slug.get(robot["slug"], "")


def _vendor_event(row: MatchJournalRow, manufacturer: str) -> dict | None:
    summary = row.summary or {}
    passed = [item for item in summary.get("passed") or [] if same_maker(manufacturer, item.get("manufacturer"))]
    noted = [item for item in summary.get("noted") or [] if same_maker(manufacturer, item.get("manufacturer"))]
    blocked = [item for item in summary.get("blocked") or [] if same_maker(manufacturer, item.get("manufacturer"))]
    if not passed and not noted and not blocked:
        return None
    outcome = "success" if passed else "empty"
    reasons: list[str] = []
    if outcome == "empty":
        codes = {item.get("process_code") for item in noted + blocked}
        for process in summary.get("processes") or []:
            if process.get("code") in codes:
                reasons.extend(process.get("reasons") or [])
        for item in noted:
            reasons.extend(item.get("missing") or [])
        for item in blocked:
            reasons.extend(item.get("reasons") or [])
    else:
        for item in noted:
            reasons.extend(item.get("missing") or [])
    unique = []
    for text in reasons:
        if text and text not in unique:
            unique.append(text)
    return {
        "at": row.created_at.isoformat() if row.created_at else None,
        "object_name": row.object_name,
        "outcome": outcome,
        "site": list(row.site or []) if outcome == "empty" else [],
        "reasons": unique[:8],
        "noted": [{"slug": item.get("slug") or "", "name": item.get("name") or "", "missing": item.get("missing") or []} for item in noted[:6]],
        "blocked": [{"slug": item.get("slug") or "", "name": item.get("name") or "", "reasons": item.get("reasons") or []} for item in blocked[:6]],
        "text": _event_text(row.object_name, outcome, noted, blocked),
    }


def _event_text(object_name: str, outcome: str, noted: list, blocked: list) -> str:
    place = object_name or "объекте"
    if outcome == "success" and noted:
        return f"По объекту «{place}» ваш робот подошёл. Часть моделей попала в подбор с пометкой: не хватает характеристик."
    if outcome == "success":
        return f"По объекту «{place}» ваш робот подошёл."
    if noted and not blocked:
        return f"По объекту «{place}» подходящим вашего робота признать не удалось. Он попал в подбор только с пометкой."
    if blocked:
        return f"По объекту «{place}» робот не прошёл подбор: в карточке не хватает характеристик, которые проверяет площадка."
    return f"По объекту «{place}» подходящий робот не нашёлся."


def _vendor_card(profile: VendorProfileRow | None, robots: list[dict], journal: list[MatchJournalRow], maker: str = "") -> dict:
    manufacturer = profile.manufacturer if profile else maker
    for robot in robots:
        robot["city"] = (profile.city if profile else "") or robot.get("city") or ""
        robot["has_cabinet"] = profile is not None
    stats = _match_stats(journal, manufacturer)
    total = len(robots)
    ready = sum(1 for item in robots if item["state"] == "in")
    rating = round(100 * ready / total) if total else 0
    ok = bool(total) and all(item["state"] == "in" for item in robots)
    return {
        "company": profile.company_name if profile else manufacturer or "Производитель",
        "manufacturer": manufacturer,
        "city": profile.city if profile else "",
        "logo_url": profile.logo_url if profile else None,
        "has_cabinet": profile is not None,
        "ok": ok,
        "rating": rating,
        "robots_total": total,
        "robots_in": sum(1 for item in robots if item["state"] != "out"),
        "robots_out": sum(1 for item in robots if item["state"] == "out"),
        "robots_note": sum(1 for item in robots if item["state"] == "note"),
        "matches": stats["matches"],
        "reasons": stats["reasons"],
        "robots": robots,
    }


def _match_stats(journal: list[MatchJournalRow], manufacturer: str) -> dict:
    success = 0
    empty = 0
    chunks: list[list[str]] = []
    for row in journal:
        event = _vendor_event(row, manufacturer)
        if event is None:
            continue
        if event["outcome"] == "success":
            success += 1
        else:
            empty += 1
            chunks.append(event["reasons"])
    return {
        "matches": {"total": success + empty, "success": success, "empty": empty},
        "reasons": count_reasons(chunks),
    }


def _take_bucket(by_maker: dict[str, list[dict]], manufacturer: str) -> tuple[list[dict], str]:
    if manufacturer in by_maker:
        return by_maker[manufacturer], manufacturer
    for key, bucket in by_maker.items():
        if same_maker(manufacturer, key):
            return bucket, key
    return [], manufacturer


def _profile_for(db: Session, manufacturer: str) -> VendorProfileRow | None:
    exact = db.scalar(select(VendorProfileRow).where(VendorProfileRow.manufacturer == manufacturer))
    if exact is not None:
        return exact
    for row in db.scalars(select(VendorProfileRow)):
        if same_maker(row.manufacturer, manufacturer):
            return row
    return None


def _open_fix(db: Session, user_id: UUID, slug: str) -> VendorRequestRow | None:
    rows = db.scalars(select(VendorRequestRow).where(
        VendorRequestRow.user_id == user_id,
        VendorRequestRow.kind == "product_update",
        VendorRequestRow.status.in_(("pending", "revision")),
    ))
    for row in rows:
        if str((row.payload or {}).get("slug") or "") == slug:
            return row
    return None


def _attach_makers(db: Session, summary: dict) -> None:
    slugs = {
        item.get("slug")
        for bucket in ("passed", "noted", "blocked")
        for item in summary.get(bucket) or []
        if item.get("slug")
    }
    if not slugs:
        return
    makers = {
        slug: manufacturer or ""
        for slug, manufacturer in db.execute(select(ProductRow.slug, ProductRow.manufacturer).where(ProductRow.slug.in_(slugs)))
    }
    for bucket in ("passed", "noted", "blocked"):
        for item in summary.get(bucket) or []:
            item["manufacturer"] = makers.get(item.get("slug"), "")


def _labeled_site(db: Session, object_code: str, site: dict | None) -> list[dict]:
    params = public_params(site)
    if not params or not object_code:
        return params
    obj = db.scalar(select(ObjectTypeRow).where(ObjectTypeRow.code == object_code))
    if obj is None:
        return params
    labels = {item["key"]: item["label"] for item in object_fields(db, obj.id)}
    for item in params:
        item["label"] = labels.get(item["key"], item["label"])
    return params
