"""Запросы на интеграцию и карточка интегратора. Каталог роботов отсюда не меняется."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import (
    AppUserRow,
    IntegrationMessageRow,
    IntegrationRequestRow,
    IntegratorProfileRow,
    ObjectTypeRow,
    ProjectRow,
)

# Уведомление до открытия проекта заказчика. Это отметка демо, не договор с подписью.
NDA_TEXT = (
    "Сведения о проекте заказчика относятся к его коммерческой информации: параметры площадки, "
    "процессы, подобранные роботы и экономика. Статья 10 Федерального закона от 29 июля 2004 года "
    "№ 98-ФЗ «О коммерческой тайне» требует хранить такие сведения в тайне и не передавать их третьим лицам "
    "без согласия обладателя. Статья 727 Гражданского кодекса Российской Федерации запрещает сообщать "
    "полученные технические и экономические сведения другим лицам. Это уведомление демо-платформы, "
    "а не подписанный договор. Примите его, чтобы открыть проекты и чат."
)
NDA_LAW_TITLE = "Федеральный закон от 29.07.2004 № 98-ФЗ «О коммерческой тайне»"
# Официальный текст на портале правовой информации.
NDA_LAW_URL = "http://pravo.gov.ru/proxy/ips/?docbody=&nd=102088315"

SPECIALIZATIONS = ("Склад", "Производство", "Медицина", "Аэропорт", "Сварка", "Паллетирование")
DOC_KINDS = ("charter", "permit", "certificate", "partner", "other")
FILE_URL = "/platform/api/v1/integration/files/"


def public_cards(db: Session) -> list[dict]:
    rows = db.scalars(select(IntegratorProfileRow).order_by(IntegratorProfileRow.company_name)).all()
    return [_public(row) for row in rows if row.company_name.strip()]


def own_profile(db: Session, user_id: UUID) -> dict:
    row = db.get(IntegratorProfileRow, user_id)
    if row is None:
        user = db.get(AppUserRow, user_id)
        row = IntegratorProfileRow(user_id=user_id, company_name=user.login if user else "")
        db.add(row)
        db.commit()
    return _private(row)


def save_profile(db: Session, user_id: UUID, payload: dict) -> dict:
    row = db.get(IntegratorProfileRow, user_id)
    if row is None:
        row = IntegratorProfileRow(user_id=user_id, company_name="")
        db.add(row)
    company = str(payload.get("company_name") or "").strip()
    if not company:
        raise ValueError("Укажите название компании")
    specs = [item for item in payload.get("specializations") or [] if item in SPECIALIZATIONS]
    years = payload.get("experience_years")
    if years is not None and not (0 <= int(years) <= 80):
        raise ValueError("Стаж укажите числом от 0 до 80")
    docs = _own_documents(user_id, payload.get("documents") or [])
    logo = payload.get("logo")
    row.company_name = company[:200]
    row.brand = _clip(payload.get("brand"), 120)
    row.about = _clip(payload.get("about"), 2000)
    row.website = _clip(payload.get("website"), 200)
    row.email = _clip(payload.get("email"), 200)
    row.phone = _clip(payload.get("phone"), 40)
    row.city = _clip(payload.get("city"), 80)
    row.address = _clip(payload.get("address"), 200)
    row.inn = _clip(payload.get("inn"), 12)
    row.ogrn = _clip(payload.get("ogrn"), 15)
    row.regions = _clip(payload.get("regions"), 300)
    row.contact_name = _clip(payload.get("contact_name"), 120)
    row.experience_years = None if years is None else int(years)
    row.specializations = specs
    row.documents = docs
    if isinstance(logo, str) and logo.strip():
        _own_filename(user_id, logo.strip())
        row.logo_url = FILE_URL + logo.strip()
    db.commit()
    return _private(row)


def accept_nda(db: Session, user_id: UUID) -> dict:
    row = db.get(IntegratorProfileRow, user_id)
    if row is None:
        raise KeyError(str(user_id))
    if row.nda_accepted_at is None:
        row.nda_accepted_at = datetime.now(timezone.utc)
        db.commit()
    return _private(row)


def list_for_integrator(db: Session, user_id: UUID) -> list[dict]:
    _need_nda(db, user_id)
    rows = db.scalars(
        select(IntegrationRequestRow)
        .where(IntegrationRequestRow.integrator_user_id == user_id)
        .order_by(IntegrationRequestRow.updated_at.desc())
    ).all()
    return [_request_view(db, row, for_integrator=True) for row in rows]


def list_for_owner(db: Session, user_id: UUID) -> list[dict]:
    rows = db.scalars(
        select(IntegrationRequestRow)
        .where(IntegrationRequestRow.owner_user_id == user_id)
        .order_by(IntegrationRequestRow.updated_at.desc())
    ).all()
    return [_request_view(db, row, for_integrator=False) for row in rows]


def send_project(db: Session, user_id: UUID, project: ProjectRow, integrator_id: UUID, note: str) -> dict:
    if project.owner_id != user_id:
        raise PermissionError("Отправить проект может только его автор")
    if project.is_demo:
        raise ValueError("Учебный объект сначала скопируйте в свои проекты")
    integrator = db.get(AppUserRow, integrator_id)
    if integrator is None or integrator.role != "integrator":
        raise KeyError(str(integrator_id))
    profile = db.get(IntegratorProfileRow, integrator_id)
    if profile is None or not profile.company_name.strip():
        raise ValueError("У этого интегратора ещё нет карточки компании")
    text = _clip(note, 2000)
    row = db.scalar(
        select(IntegrationRequestRow).where(
            IntegrationRequestRow.project_id == project.id,
            IntegrationRequestRow.integrator_user_id == integrator_id,
        )
    )
    now = datetime.now(timezone.utc)
    if row is None:
        row = IntegrationRequestRow(
            id=uuid4(),
            project_id=project.id,
            owner_user_id=user_id,
            integrator_user_id=integrator_id,
            status="sent",
            user_note=text,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        # Повторная отправка того же проекта не плодит вторую карточку.
        row.user_note = text
        row.status = "sent"
        row.feedback = ""
        row.decline_comment = ""
        row.updated_at = now
    db.commit()
    return _request_view(db, row, for_integrator=False)


def leave_feedback(db: Session, user_id: UUID, request_id: UUID, comment: str) -> dict:
    _need_nda(db, user_id)
    row = _integrator_request(db, user_id, request_id)
    if row.status == "declined":
        raise ValueError("Запрос уже отклонён. Если нужно продолжить, напишите в чат.")
    text = comment.strip()
    if not text:
        raise ValueError("Напишите, что думаете о проекте")
    row.feedback = text[:2000]
    row.status = "answered"
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _request_view(db, row, for_integrator=True)


def decline_request(db: Session, user_id: UUID, request_id: UUID, comment: str) -> dict:
    _need_nda(db, user_id)
    row = _integrator_request(db, user_id, request_id)
    text = comment.strip()
    if not text:
        raise ValueError("Напишите, почему проект не берёте")
    row.decline_comment = text[:2000]
    row.status = "declined"
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return _request_view(db, row, for_integrator=True)


def list_messages(db: Session, user_id: UUID, role: str, request_id: UUID) -> list[dict]:
    row = _party_request(db, user_id, role, request_id)
    if role == "integrator":
        _need_nda(db, user_id)
    found = db.scalars(
        select(IntegrationMessageRow)
        .where(IntegrationMessageRow.request_id == row.id)
        .order_by(IntegrationMessageRow.created_at.desc())
        .limit(200)
    ).all()
    return [_message_view(item, user_id) for item in reversed(found)]


def add_message(db: Session, user_id: UUID, role: str, request_id: UUID, body: str, files: list[dict]) -> dict:
    row = _party_request(db, user_id, role, request_id)
    if role == "integrator":
        _need_nda(db, user_id)
    text = body.strip()[:4000]
    if not text and not files:
        raise ValueError("Напишите сообщение или приложите файл")
    message = IntegrationMessageRow(
        id=uuid4(),
        request_id=row.id,
        author_user_id=user_id,
        body=text,
        files=files,
        created_at=datetime.now(timezone.utc),
    )
    db.add(message)
    row.updated_at = message.created_at
    db.commit()
    return _message_view(message, user_id)


def file_allowed(db: Session, user_id: UUID, role: str, name: str) -> bool:
    if role == "admin":
        return True
    if name.startswith(f"{user_id.hex}_"):
        return True
    # Логотип и документы карточки интегратор публикует сам, их видит вошедший пользователь.
    if role != "guest":
        logo = db.scalar(select(IntegratorProfileRow.user_id).where(IntegratorProfileRow.logo_url.contains(name)))
        if logo is not None:
            return True
        docs = db.scalar(
            select(IntegratorProfileRow.user_id).where(IntegratorProfileRow.documents.contains([{"filename": name}]))
        )
        if docs is not None:
            return True
    message = db.scalar(
        select(IntegrationMessageRow).where(IntegrationMessageRow.files.contains([{"name": name}]))
    )
    if message is None:
        return False
    request = db.get(IntegrationRequestRow, message.request_id)
    return request is not None and user_id in (request.owner_user_id, request.integrator_user_id)


def _need_nda(db: Session, user_id: UUID) -> None:
    row = db.get(IntegratorProfileRow, user_id)
    if row is None or row.nda_accepted_at is None:
        raise PermissionError("Сначала примите уведомление о неразглашении.")


def _integrator_request(db: Session, user_id: UUID, request_id: UUID) -> IntegrationRequestRow:
    row = db.get(IntegrationRequestRow, request_id)
    if row is None or row.integrator_user_id != user_id:
        raise KeyError(str(request_id))
    return row


def _party_request(db: Session, user_id: UUID, role: str, request_id: UUID) -> IntegrationRequestRow:
    row = db.get(IntegrationRequestRow, request_id)
    if row is None:
        raise KeyError(str(request_id))
    if role == "integrator" and row.integrator_user_id == user_id:
        return row
    if row.owner_user_id == user_id:
        return row
    raise KeyError(str(request_id))


def _request_view(db: Session, row: IntegrationRequestRow, *, for_integrator: bool) -> dict:
    project = db.get(ProjectRow, row.project_id)
    obj = db.get(ObjectTypeRow, project.object_type_id) if project else None
    profile = db.get(IntegratorProfileRow, row.integrator_user_id)
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "project_name": project.name if project else "Проект удалён",
        "object_name": obj.name if obj else "",
        "integrator_id": str(row.integrator_user_id),
        "integrator_name": profile.company_name if profile else "",
        "status": row.status,
        "user_note": row.user_note,
        "feedback": row.feedback,
        "decline_comment": row.decline_comment,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        "side": "integrator" if for_integrator else "user",
    }


def _public(row: IntegratorProfileRow) -> dict:
    return {
        "id": str(row.user_id),
        "company_name": row.company_name,
        "brand": row.brand,
        "about": row.about,
        "website": row.website,
        "email": row.email,
        "phone": row.phone,
        "city": row.city,
        "regions": row.regions,
        "contact_name": row.contact_name,
        "experience_years": row.experience_years,
        "specializations": list(row.specializations or []),
        "logo_url": row.logo_url,
        "documents": [
            {"kind": item.get("kind", "other"), "title": item.get("title", "")}
            for item in (row.documents or [])
            if isinstance(item, dict) and item.get("title")
        ],
    }


def _private(row: IntegratorProfileRow) -> dict:
    view = _public(row)
    view.update({
        "address": row.address,
        "inn": row.inn,
        "ogrn": row.ogrn,
        "documents": list(row.documents or []),
        "nda_accepted": row.nda_accepted_at is not None,
        "nda_text": NDA_TEXT,
        "nda_law_title": NDA_LAW_TITLE,
        "nda_law_url": NDA_LAW_URL,
    })
    return view


def _message_view(row: IntegrationMessageRow, reader_id: UUID) -> dict:
    return {
        "id": str(row.id),
        "author": "me" if row.author_user_id == reader_id else "peer",
        "body": row.body,
        "files": [
            {"name": item.get("name", ""), "title": item.get("title", ""), "url": FILE_URL + str(item.get("name", ""))}
            for item in (row.files or [])
            if isinstance(item, dict) and item.get("name")
        ],
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


def _own_documents(user_id: UUID, raw: list) -> list[dict]:
    out = []
    for item in raw[:12]:
        if not isinstance(item, dict):
            continue
        kind = item.get("kind") if item.get("kind") in DOC_KINDS else "other"
        title = _clip(item.get("title"), 160)
        filename = str(item.get("filename") or "").strip()
        if not title or not filename:
            continue
        _own_filename(user_id, filename)
        out.append({"kind": kind, "title": title, "filename": filename, "url": FILE_URL + filename})
    return out


def _own_filename(user_id: UUID, name: str) -> None:
    if not name.startswith(f"{user_id.hex}_"):
        raise ValueError("Файл не принадлежит этой учётке")


def _clip(value, limit: int) -> str:
    return str(value or "").strip()[:limit]
