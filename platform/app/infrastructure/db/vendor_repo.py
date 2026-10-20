"""Заявки вендора. Живой каталог меняется только когда администратор нажимает «подтвердить»."""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime, timezone
from uuid import UUID, uuid4
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.domain.csv_parse import attr_key
from app.infrastructure.db.models import (
    ObjectProcessRow,
    ObjectTypeRow,
    ProcessRow,
    ProductOfferRow,
    ProductProcessRow,
    ProductRow,
    VendorProfileRow,
    VendorRequestRow,
)
from app.infrastructure.db.product_admin_repo import create_product, patch_product, product_detail
from app.parsers import PARSERS

KINDS = {"profile", "product_create", "product_update", "import_batch", "parse"}
STATUSES = {"pending", "approved", "rejected", "revision"}
DOC_KINDS = {"card", "permit", "certificate", "other"}
DOC_LABEL = {
    "card": "Карточка предприятия",
    "permit": "Разрешительный документ",
    "certificate": "Сертификат",
    "other": "Другой документ",
}
_FILE = re.compile(r"^[0-9a-f]{32}_[0-9a-f]{32}\.(png|jpg|jpeg|webp|pdf)$")


def same_maker(vendor: str, record: str | None) -> bool:
    """Одно и то же имя, если совпадает текст без кавычек и лишних пробелов, либо одно имя входит в другое."""
    left, right = _fold(vendor), _fold(record)
    if not left or not right:
        return False
    return left == right or left in right or right in left


def _fold(value: str | None) -> str:
    text = (value or "").casefold().replace('"', " ").replace("«", " ").replace("»", " ")
    return " ".join(text.split())


def partners(db: Session) -> list[dict]:
    rows = db.execute(
        select(ProductRow.manufacturer, func.count())
        .where(ProductRow.manufacturer.is_not(None), func.btrim(ProductRow.manufacturer) != "")
        .group_by(ProductRow.manufacturer)
        .order_by(func.count().desc(), ProductRow.manufacturer)
    ).all()
    return [{"name": name, "products": int(count)} for name, count in rows]


def profile_view(row: VendorProfileRow) -> dict:
    return {
        "manufacturer": row.manufacturer,
        "company_name": row.company_name,
        "about": row.about,
        "website": row.website,
        "email": row.email,
        "phone": row.phone,
        "city": row.city,
        "logo_url": row.logo_url,
        "documents": list(row.documents or []),
    }


def load_profile(db: Session, user_id: UUID) -> VendorProfileRow:
    row = db.get(VendorProfileRow, user_id)
    if row is None:
        raise KeyError(user_id)
    return row


def own_products(db: Session, manufacturer: str) -> list[dict]:
    rows = db.scalars(
        select(ProductRow).where(ProductRow.manufacturer == manufacturer).order_by(ProductRow.name)
    )
    return [product_detail(db, row.slug) for row in rows]


# В список заказчика попадают эти три вкладки. «Не подходит» человек не выбирает.
_SHOWN = {"pass", "conditional", "unknown"}


def remember_offers(db: Session, groups: list) -> None:
    """Один открытый подбор прибавляет единицу каждой показанной модели. Чей это был проект, не сохраняем."""
    wanted: set[UUID] = set()
    for group in groups or []:
        for hit in group.get("hits") or []:
            if hit.get("verdict") not in _SHOWN:
                continue
            try:
                wanted.add(UUID(str(hit.get("product_id"))))
            except (TypeError, ValueError):
                continue
    if not wanted:
        return
    owned = list(db.scalars(
        select(ProductRow.id)
        .join(VendorProfileRow, VendorProfileRow.manufacturer == ProductRow.manufacturer)
        .where(ProductRow.id.in_(wanted))
    ))
    if not owned:
        return
    stmt = pg_insert(ProductOfferRow).values([{"product_id": item, "offers": 1} for item in owned])
    stmt = stmt.on_conflict_do_update(
        index_elements=[ProductOfferRow.product_id],
        set_={"offers": ProductOfferRow.offers + 1},
    )
    db.execute(stmt)
    db.commit()


def vendor_stats(db: Session, manufacturer: str) -> dict:
    """Сводка для кабинета: свои карточки, их процессы, объекты подбора и число показов."""
    products = list(db.scalars(
        select(ProductRow).where(ProductRow.manufacturer == manufacturer).order_by(ProductRow.name)
    ))
    ids = [row.id for row in products]
    process_by_product: dict[UUID, list[tuple[int, str]]] = {item: [] for item in ids}
    process_ids: set[int] = set()
    if ids:
        links = db.execute(
            select(ProductProcessRow.product_id, ProcessRow.id, ProcessRow.name)
            .join(ProcessRow, ProcessRow.id == ProductProcessRow.process_id)
            .where(ProductProcessRow.product_id.in_(ids))
            .order_by(ProcessRow.name)
        )
        for product_id, process_id, name in links:
            process_by_product.setdefault(product_id, []).append((process_id, name))
            process_ids.add(process_id)
    objects_by_process: dict[int, list[str]] = {}
    if process_ids:
        places = db.execute(
            select(ObjectProcessRow.process_id, ObjectTypeRow.name)
            .join(ObjectTypeRow, ObjectTypeRow.id == ObjectProcessRow.object_type_id)
            .where(ObjectProcessRow.process_id.in_(process_ids), ObjectTypeRow.in_match.is_(True))
            .order_by(ObjectTypeRow.name)
        )
        for process_id, name in places:
            bucket = objects_by_process.setdefault(process_id, [])
            if name not in bucket:
                bucket.append(name)
    offer_rows = {
        row.product_id: row.offers
        for row in db.scalars(select(ProductOfferRow).where(ProductOfferRow.product_id.in_(ids)))
    } if ids else {}
    models = []
    object_names: set[str] = set()
    process_names: set[str] = set()
    for row in products:
        linked = process_by_product.get(row.id, [])
        names = [name for _process_id, name in linked]
        process_names.update(names)
        places: list[str] = []
        for process_id, _name in linked:
            for place in objects_by_process.get(process_id, []):
                if place not in places:
                    places.append(place)
        object_names.update(places)
        models.append({
            "name": row.name,
            "offers": int(offer_rows.get(row.id, 0)),
            "processes": names,
            "objects": places,
        })
    models.sort(key=lambda item: (-item["offers"], item["name"]))
    return {
        "cards": len(products),
        "processes": len(process_names),
        "objects": len(object_names),
        "offers": sum(item["offers"] for item in models),
        "process_names": sorted(process_names),
        "object_names": sorted(object_names),
        "models": models,
    }


def process_choices(db: Session) -> list[dict]:
    return [{"code": row.code, "name": row.name} for row in db.scalars(select(ProcessRow).order_by(ProcessRow.name))]


def parser_choices() -> list[dict]:
    return [{"code": code, "title": title, "summary": summary} for code, (title, summary, _runner) in PARSERS.items()]


def list_requests(db: Session, user_id: UUID | None = None, *, audience: str = "admin") -> list[dict]:
    query = select(VendorRequestRow).order_by(VendorRequestRow.created_at.desc())
    if user_id is not None:
        query = query.where(VendorRequestRow.user_id == user_id)
    # Каждый видит свой список. Чужое скрытие на вторую сторону не действует.
    if audience == "vendor":
        query = query.where(VendorRequestRow.owner_hidden.is_(False))
    else:
        query = query.where(VendorRequestRow.admin_hidden.is_(False))
    rows = list(db.scalars(query.limit(200)))
    names = _company_names(db, {row.user_id for row in rows})
    process_names = _process_titles(db)
    pictures = _request_pictures(db, rows)
    return [
        _request_view(row, names.get(row.user_id, ""), process_names, pictures.get(row.id, {}))
        for row in rows
    ]


def submit_request(db: Session, user_id: UUID, kind: str, payload: dict) -> dict:
    if kind not in KINDS:
        raise ValueError("Неизвестный тип заявки")
    profile = load_profile(db, user_id)
    clean = _clean_payload(db, profile, kind, payload)
    row = VendorRequestRow(
        id=uuid4(),
        user_id=user_id,
        kind=kind,
        title=_title(kind, clean),
        payload=clean,
        status="pending",
    )
    db.add(row)
    db.commit()
    return _request_view(row, profile.company_name, _process_titles(db))


def decide(db: Session, request_id: UUID, status: str, comment: str) -> dict:
    if status not in {"approved", "rejected", "revision"}:
        raise ValueError("Нужно решение: подтвердить, отклонить или вернуть на доработку")
    comment = comment.strip()
    if status in {"rejected", "revision"} and not comment:
        raise ValueError("Напишите комментарий: вендору должно быть понятно, что исправить")
    row = db.get(VendorRequestRow, request_id)
    if row is None:
        raise KeyError(request_id)
    if row.status == "withdraw_pending":
        if status == "revision":
            raise ValueError("Отзыв можно подтвердить или оставить заявку как была")
        if status == "approved":
            row.status = "withdrawn"
        else:
            before = str((row.payload or {}).get("_before") or "pending")
            row.status = before if before in {"pending", "revision"} else "pending"
        row.admin_comment = comment
        row.decided_at = datetime.now(timezone.utc)
        db.commit()
        names = _company_names(db, {row.user_id})
        return _request_view(row, names.get(row.user_id, ""), _process_titles(db))
    if row.status != "pending":
        raise ValueError("По этой заявке решение уже есть")
    row.status = status
    row.admin_comment = comment
    row.decided_at = datetime.now(timezone.utc)
    db.commit()
    names = _company_names(db, {row.user_id})
    return _request_view(row, names.get(row.user_id, ""), _process_titles(db))


def publish_request(db: Session, request_id: UUID, edits: dict | None) -> dict:
    """В каталог пишет только эта кнопка. Подтверждение заявки само ничего не публикует."""
    row = db.get(VendorRequestRow, request_id)
    if row is None:
        raise KeyError(request_id)
    if row.status != "approved":
        raise ValueError("Сначала примите заявку. В каталог она попадает отдельной кнопкой")
    if row.catalog_applied:
        raise ValueError("Эта заявка уже внесена в каталог")
    profile = load_profile(db, row.user_id)
    payload = _with_admin_edits(db, row, edits or {})
    if row.kind == "profile":
        payload = _clean_profile(profile, payload)
    row.payload = payload
    row.title = _title(row.kind, payload)
    row.catalog_applied = True
    _apply(db, row)
    db.commit()
    names = _company_names(db, {row.user_id})
    return _request_view(row, names.get(row.user_id, ""), _process_titles(db))


def _with_admin_edits(db: Session, row: VendorRequestRow, edits: dict) -> dict:
    payload = dict(row.payload or {})
    if row.kind == "profile":
        for key in ("company_name", "about", "website", "email", "phone", "city"):
            if key in edits and edits[key] is not None:
                payload[key] = edits[key]
        return payload
    if row.kind == "parse" or not edits.get("robots"):
        return payload
    robots = [dict(item) for item in (payload.get("robots") or ([payload["robot"]] if payload.get("robot") else []))]
    known = {item.code: item.name for item in db.scalars(select(ProcessRow))}
    for index, patch in enumerate(edits["robots"]):
        if index >= len(robots) or not isinstance(patch, dict):
            continue
        robot = dict(robots[index])
        if patch.get("name") is not None:
            robot["name"] = str(patch["name"]).strip()
        if "summary" in patch:
            robot["summary"] = str(patch.get("summary") or "").strip()
        if "price_rub" in patch:
            raw = patch.get("price_rub")
            if raw in (None, ""):
                robot["price_rub"] = None
            else:
                try:
                    robot["price_rub"] = float(str(raw).replace(" ", "").replace(",", "."))
                except ValueError as exc:
                    raise ValueError("Цена должна быть числом") from exc
        if isinstance(patch.get("processes"), list):
            found, missing = _process_codes([str(code) for code in patch["processes"]], known)
            if missing:
                raise ValueError(f"Нет таких процессов: {', '.join(missing)}. Напишите название как в кабинете.")
            robot["processes"] = found
        if not str(robot.get("name") or "").strip():
            raise ValueError("У модели нужно название")
        robots[index] = robot
    if payload.get("robot") and not payload.get("robots"):
        return {"slug": payload.get("slug"), "robot": robots[0]}
    payload["robots"] = robots
    return payload


def ask_withdraw(db: Session, user_id: UUID, request_id: UUID) -> dict:
    """Отзыв сам ничего не стирает. Администратор ещё должен его подтвердить."""
    row = _own_request(db, user_id, request_id)
    if row.status not in {"pending", "revision"}:
        raise ValueError("Отозвать можно заявку, которая ещё не записана в каталог")
    payload = dict(row.payload or {})
    payload["_before"] = row.status
    row.payload = payload
    row.status = "withdraw_pending"
    db.commit()
    profile = load_profile(db, user_id)
    return _request_view(row, profile.company_name, _process_titles(db))


def hide_request(db: Session, request_id: UUID, *, audience: str, user_id: UUID | None = None) -> None:
    row = db.get(VendorRequestRow, request_id)
    if row is None:
        raise KeyError(request_id)
    if audience == "vendor":
        if user_id is None or row.user_id != user_id:
            raise KeyError(request_id)
        if row.status in {"pending", "revision", "withdraw_pending"}:
            raise ValueError("Пока заявка не закрыта, её можно только отозвать")
        row.owner_hidden = True
    else:
        if row.status in {"pending", "withdraw_pending"}:
            raise ValueError("Сначала примите решение. Потом заявку можно убрать из списка")
        row.admin_hidden = True
    db.commit()


def _own_request(db: Session, user_id: UUID, request_id: UUID) -> VendorRequestRow:
    row = db.get(VendorRequestRow, request_id)
    if row is None or row.user_id != user_id:
        raise KeyError(request_id)
    return row


def read_remote_robots(db: Session, user_id: UUID, url: str) -> list[dict]:
    """Снимок с адреса вендора. В заявку кладём уже прочитанный список, а не ссылку, которая может измениться."""
    profile = load_profile(db, user_id)
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        raise ValueError("Нужна ссылка, которая начинается с http:// или https://")
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        raise ValueError("Ссылка должна вести на сайт вендора, а не на этот компьютер")
    request = Request(parsed.geturl(), headers={"User-Agent": "robots-platform-vendor"})
    try:
        with urlopen(request, timeout=8) as response:
            raw = response.read(2_000_001)
    except Exception as exc:
        raise ValueError("Не удалось прочитать ссылку. Проверьте адрес и что по нему отдаётся JSON.") from exc
    if len(raw) > 2_000_000:
        raise ValueError("Ответ больше 2 МБ. Пришлите файл или сократите выгрузку.")
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("По ссылке пришёл не JSON. Нужен список роботов.") from exc
    return normalize_robots(db, data, profile.manufacturer)


def robots_from_text(db: Session, user_id: UUID, text: str, fmt: str) -> list[dict]:
    profile = load_profile(db, user_id)
    if fmt == "json":
        try:
            data = json.loads(text.lstrip("\ufeff"))
        except json.JSONDecodeError as exc:
            raise ValueError("Файл не читается. Нужен список роботов, и у каждого должно быть название.") from exc
        return normalize_robots(db, data, profile.manufacturer)
    if fmt == "csv":
        return normalize_robots(db, _table_rows(text), profile.manufacturer)
    raise ValueError("Формат файла: json или csv")


def _process_codes(tokens: list[str], known: dict[str, str]) -> tuple[list[str], list[str]]:
    by_name: dict[str, str] = {}
    for code, title in known.items():
        by_name.setdefault(title.casefold(), code)
    found: list[str] = []
    missing: list[str] = []
    for token in tokens:
        clean = token.strip()
        if not clean:
            continue
        code = clean if clean in known else by_name.get(clean.casefold())
        if not code:
            missing.append(clean)
        elif code not in found:
            found.append(code)
    return found, missing


def normalize_robots(db: Session, data: object, manufacturer: str) -> list[dict]:
    if not isinstance(data, list) or not data:
        raise ValueError("Нужен непустой список роботов")
    if len(data) > 200:
        raise ValueError("За один раз можно отправить не больше 200 роботов")
    known = {row.code: row.name for row in db.scalars(select(ProcessRow))}
    robots = []
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Строка {index}: нужен объект с полями робота")
        name = str(item.get("name") or item.get("название") or "").strip()
        if not name:
            raise ValueError(f"Строка {index}: нет названия")
        foreign = str(item.get("manufacturer") or item.get("производитель") or "").strip()
        if foreign and not same_maker(manufacturer, foreign):
            raise ValueError(f"«{name}» указан как робот другого производителя. В кабинете можно загружать только свои модели.")
        processes = item.get("processes") or item.get("процессы") or []
        if isinstance(processes, str):
            processes = [part.strip() for part in processes.replace(";", ",").split(",") if part.strip()]
        if not isinstance(processes, list):
            raise ValueError(f"«{name}»: процессы напишите через запятую")
        # В файле можно писать и код, и обычное название. Человеку код не нужен.
        found, missing = _process_codes([str(code) for code in processes], known)
        if missing:
            raise ValueError(f"«{name}»: нет таких процессов: {', '.join(missing)}. Напишите название как в кабинете.")
        processes = found
        attrs = item.get("attrs") if isinstance(item.get("attrs"), dict) else {}
        extra = {
            key: value
            for key, value in item.items()
            if key not in {"name", "название", "summary", "описание", "price_rub", "цена", "processes", "процессы", "manufacturer", "производитель", "attrs"}
            and value not in (None, "")
        }
        attrs = {**extra, **attrs}
        clean_attrs = []
        for key, value in attrs.items():
            if value in (None, ""):
                continue
            label = str(key).strip()
            clean_attrs.append({"key": attr_key(label) if not re.fullmatch(r"[a-z0-9_]+", label) else label, "label": label, "value": value})
        price = item.get("price_rub", item.get("цена"))
        if price in (None, ""):
            price_value = None
        else:
            try:
                price_value = float(str(price).replace(" ", "").replace(",", "."))
            except ValueError as exc:
                raise ValueError(f"«{name}»: цена должна быть числом") from exc
        robots.append({
            "name": name,
            "summary": str(item.get("summary") or item.get("описание") or "").strip(),
            "price_rub": price_value,
            "processes": list(dict.fromkeys(str(code) for code in processes)),
            "attrs": clean_attrs,
        })
    return robots


def _table_rows(text: str) -> list[dict]:
    sample = text.lstrip("\ufeff")
    first = sample.splitlines()[0] if sample.splitlines() else ""
    delimiter = ";" if first.count(";") >= first.count(",") else ","
    rows = list(csv.DictReader(io.StringIO(sample), delimiter=delimiter))
    if not rows:
        raise ValueError("В таблице нет строк. Первая строка должна быть заголовком.")
    return rows


def _clean_payload(db: Session, profile: VendorProfileRow, kind: str, payload: dict) -> dict:
    if kind == "profile":
        return _clean_profile(profile, payload)
    if kind == "product_create":
        robots = normalize_robots(db, [payload], profile.manufacturer)
        return {"robots": robots}
    if kind == "product_update":
        return _clean_update(db, profile, payload)
    if kind == "import_batch":
        robots = payload.get("robots")
        return {"robots": normalize_robots(db, robots, profile.manufacturer), "source": str(payload.get("source") or "file")[:40]}
    if kind == "parse":
        code = str(payload.get("parser") or "")
        if code not in PARSERS:
            raise ValueError("Такого источника для обхода нет")
        title, summary, _runner = PARSERS[code]
        return {"parser": code, "title": title, "summary": summary}
    raise ValueError("Неизвестный тип заявки")


def _clean_profile(profile: VendorProfileRow, payload: dict) -> dict:
    company = str(payload.get("company_name") or "").strip()
    if not company:
        raise ValueError("Укажите название компании")
    website = str(payload.get("website") or "").strip()
    if website and not website.startswith(("http://", "https://")):
        raise ValueError("Сайт должен начинаться с http:// или https://")
    email = str(payload.get("email") or "").strip()
    if email and "@" not in email:
        raise ValueError("В почте нужен знак @")
    documents = []
    for item in payload.get("documents") or []:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind") if item.get("kind") in DOC_KINDS else "other"
        filename = str(item.get("filename") or "")
        if filename and not _FILE.match(filename):
            raise ValueError("Файл документа не найден. Загрузите его ещё раз.")
        title = str(item.get("title") or DOC_LABEL[kind]).strip() or DOC_LABEL[kind]
        documents.append({"kind": kind, "title": title[:160], "filename": filename, "note": str(item.get("note") or "").strip()[:400]})
    if len(documents) > 12:
        raise ValueError("Документов можно приложить не больше 12")
    logo = str(payload.get("logo") or "")
    if logo and not _FILE.match(logo):
        raise ValueError("Файл логотипа не найден. Загрузите его ещё раз.")
    return {
        "company_name": company[:200],
        "about": str(payload.get("about") or "").strip()[:2000],
        "website": website[:300],
        "email": email[:200],
        "phone": str(payload.get("phone") or "").strip()[:40],
        "city": str(payload.get("city") or "").strip()[:80],
        "logo": logo,
        "documents": documents,
        "manufacturer": profile.manufacturer,
    }


def _clean_update(db: Session, profile: VendorProfileRow, payload: dict) -> dict:
    slug = str(payload.get("slug") or "").strip()
    row = db.scalar(select(ProductRow).where(ProductRow.slug == slug))
    if row is None or row.manufacturer != profile.manufacturer:
        raise ValueError("Этот робот не принадлежит вашей компании")
    robots = normalize_robots(db, [{
        "name": payload.get("name") or row.name,
        "summary": payload.get("summary") if payload.get("summary") is not None else (row.summary or ""),
        "price_rub": payload.get("price_rub"),
        "processes": payload.get("processes") or [],
    }], profile.manufacturer)
    robot = robots[0]
    # Ключ характеристики оставляем как в справочнике, чтобы правка не плодила дубль поля.
    robot["attrs"] = []
    for item in payload.get("attrs") or []:
        if not isinstance(item, dict) or item.get("value") in (None, ""):
            continue
        label = str(item.get("label") or item.get("key") or "").strip()
        if not label:
            continue
        key = str(item.get("key") or "").strip()
        if not re.fullmatch(r"[a-z0-9_]+", key):
            key = attr_key(label)
        robot["attrs"].append({"key": key, "label": label, "value": item["value"]})
    return {"slug": slug, "robot": robot}


def _apply(db: Session, row: VendorRequestRow) -> None:
    profile = load_profile(db, row.user_id)
    payload = row.payload or {}
    if row.kind == "profile":
        profile.company_name = payload["company_name"]
        profile.about = payload.get("about") or ""
        profile.website = payload.get("website") or ""
        profile.email = payload.get("email") or ""
        profile.phone = payload.get("phone") or ""
        profile.city = payload.get("city") or ""
        if payload.get("logo"):
            profile.logo_url = f"/platform/api/v1/vendor-files/{payload['logo']}"
        profile.documents = [
            {**item, "url": f"/platform/api/v1/vendor-files/{item['filename']}" if item.get("filename") else ""}
            for item in payload.get("documents") or []
        ]
        return
    if row.kind == "parse":
        from app.config import get_settings
        from app.infrastructure.db.job_repo import enqueue

        folder = get_settings().upload_dir / "vendor-jobs"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{row.id}.json"
        path.write_text(json.dumps({"parser": payload["parser"], "manufacturer": profile.manufacturer}, ensure_ascii=False), encoding="utf-8")
        job = enqueue(db, kind="vendor_parser", parser_code=str(row.id), file_path=str(path))
        if job is None:
            raise ValueError("Такой обход уже стоит в очереди")
        payload = dict(payload)
        payload["job_id"] = str(job.id)
        row.payload = payload
        return
    robots = payload.get("robots") or ([payload["robot"]] if payload.get("robot") else [])
    for robot in robots:
        _write_robot(db, profile.manufacturer, robot, payload.get("slug"))


def _write_robot(db: Session, manufacturer: str, robot: dict, slug: str | None) -> None:
    source = {"kind": "vendor", "publisher": manufacturer, "title": "Заявка вендора, подтверждённая администратором"}
    attrs = {
        item["key"]: {"value": item["value"], "status": "known", "label": item.get("label") or item["key"], "confirmed": True}
        for item in robot.get("attrs") or []
    }
    columns = {"name": robot["name"], "summary": robot.get("summary") or None, "price_rub": robot.get("price_rub")}
    body = {"columns": columns, "attrs": attrs, "processes": robot.get("processes") or [], "source": source}
    if slug:
        patch_product(db, slug, body)
        return
    created = create_product(db, name=robot["name"], manufacturer=manufacturer, solution_type=None, source=source)
    patch_product(db, created, body)


def _title(kind: str, payload: dict) -> str:
    if kind == "profile":
        return f"Профиль: {payload.get('company_name')}"
    if kind == "parse":
        return f"Поиск на сайте: {payload.get('title')}"
    robots = payload.get("robots") or ([payload["robot"]] if payload.get("robot") else [])
    if kind == "product_update" and robots:
        return f"Характеристики: {robots[0]['name']}"
    if len(robots) == 1:
        return f"Новый робот: {robots[0]['name']}"
    return f"Загрузка роботов: {len(robots)}"


def _summary(row: VendorRequestRow) -> str:
    payload = row.payload or {}
    if row.kind == "profile":
        return f"{payload.get('company_name')}. {payload.get('city') or 'город не указан'}. Документов: {len(payload.get('documents') or [])}."
    if row.kind == "parse":
        queued = " Поиск поставлен в очередь." if payload.get("job_id") else ""
        return f"{payload.get('summary') or payload.get('title')}.{queued}"
    robots = payload.get("robots") or ([payload["robot"]] if payload.get("robot") else [])
    names = ", ".join(item["name"] for item in robots[:6])
    tail = "" if len(robots) <= 6 else f" и ещё {len(robots) - 6}"
    return f"{names}{tail}" if names else "Без карточек"


def _process_titles(db: Session) -> dict[str, str]:
    return {row.code: row.name for row in db.scalars(select(ProcessRow))}


def _money(value: object) -> str:
    if value in (None, ""):
        return "не указана"
    try:
        return f"{int(float(value)):,}".replace(",", " ") + " руб."
    except (TypeError, ValueError):
        return str(value)


def _facts(kind: str, payload: dict, process_names: dict[str, str]) -> list[dict[str, str]]:
    """Короткие строки для человека. Коды процессов здесь уже заменены названиями."""
    def procs(codes: object) -> str:
        labels = [process_names.get(str(code), str(code)) for code in (codes or [])]
        return ", ".join(labels) if labels else "не выбраны"

    if kind == "profile":
        rows = [
            ("Компания", payload.get("company_name") or ""),
            ("Город", payload.get("city") or "не указан"),
            ("Сайт", payload.get("website") or "не указан"),
            ("Почта", payload.get("email") or "не указана"),
            ("Телефон", payload.get("phone") or "не указан"),
        ]
        about = str(payload.get("about") or "").strip()
        if about:
            rows.append(("О компании", about[:240]))
        docs = payload.get("documents") or []
        if docs:
            rows.append(("Документы", ", ".join(str(item.get("title") or "файл") for item in docs[:6])))
        rows.append(("Логотип", "новая картинка" if payload.get("logo") else "без замены"))
        return [{"label": label, "value": str(value)} for label, value in rows]

    if kind == "parse":
        return [{"label": "Сайт", "value": str(payload.get("title") or "открытый каталог")}]

    robots = payload.get("robots") or ([payload["robot"]] if payload.get("robot") else [])
    if kind == "product_update" and robots:
        robot = robots[0]
        rows = [
            ("Модель", robot.get("name") or ""),
            ("Цена", _money(robot.get("price_rub"))),
            ("Коротко", str(robot.get("summary") or "пусто")[:240]),
            ("Что умеет", procs(robot.get("processes"))),
        ]
        attrs = robot.get("attrs") or []
        if attrs:
            shown = ", ".join(f"{item.get('label')}: {item.get('value')}" for item in attrs[:4])
            if len(attrs) > 4:
                shown += f" и ещё {len(attrs) - 4}"
            rows.append(("Характеристики", shown))
        return [{"label": str(label), "value": str(value)} for label, value in rows]

    lines = [{"label": str(robot.get("name") or "Без названия"), "value": procs(robot.get("processes"))} for robot in robots[:8]]
    if len(robots) > 8:
        lines.append({"label": "Ещё", "value": str(len(robots) - 8)})
    return lines


def _request_pictures(db: Session, rows: list[VendorRequestRow]) -> dict[UUID, dict]:
    """Фото для карточки заявки: снимок робота из каталога или логотип компании."""
    slugs = []
    user_ids = set()
    for row in rows:
        payload = row.payload or {}
        slug = str(payload.get("slug") or "")
        if slug:
            slugs.append(slug)
        if row.kind == "profile":
            user_ids.add(row.user_id)
    by_slug: dict[str, tuple[str | None, float | None]] = {}
    if slugs:
        found = db.execute(
            select(ProductRow.slug, ProductRow.image_url, ProductRow.price_rub).where(ProductRow.slug.in_(set(slugs)))
        )
        for slug, image, price in found:
            by_slug[slug] = (image, None if price is None else float(price))
    logos: dict[UUID, str | None] = {}
    if user_ids:
        profiles = db.scalars(select(VendorProfileRow).where(VendorProfileRow.user_id.in_(user_ids)))
        logos = {row.user_id: row.logo_url for row in profiles}
    result: dict[UUID, dict] = {}
    for row in rows:
        slug = str((row.payload or {}).get("slug") or "")
        image, price = by_slug.get(slug, (None, None))
        if image is None and row.kind == "profile":
            image = logos.get(row.user_id)
        result[row.id] = {"image_url": image, "price_rub": price}
    return result


def _request_view(row: VendorRequestRow, company: str, process_names: dict[str, str], picture: dict | None = None) -> dict:
    payload = {key: value for key, value in (row.payload or {}).items() if key != "_before"}
    shot = picture or {}
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "company": company,
        "kind": row.kind,
        "title": row.title,
        "summary": _summary(row),
        "facts": _facts(row.kind, payload, process_names),
        "subject_slug": str(payload.get("slug") or "") if row.kind == "product_update" else "",
        "payload": payload,
        "status": row.status,
        "catalog_applied": bool(row.catalog_applied),
        "admin_comment": row.admin_comment,
        "image_url": shot.get("image_url"),
        "price_rub": shot.get("price_rub"),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
    }


def _company_names(db: Session, user_ids: set[UUID]) -> dict[UUID, str]:
    if not user_ids:
        return {}
    rows = db.scalars(select(VendorProfileRow).where(VendorProfileRow.user_id.in_(user_ids)))
    return {row.user_id: row.company_name for row in rows}
