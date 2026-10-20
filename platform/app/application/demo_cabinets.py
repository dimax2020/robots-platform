"""Наполнение кабинетов вендора и интегратора для показа платформы.

Запускается при старте после демо-учёток. Каждая часть заполняется один раз: если у вендора уже есть заявки,
журнал подбора не пуст, а у интегратора есть запросы — ничего не трогаем. Всё создаётся теми же функциями,
что и из интерфейса, поэтому заявки и запросы проходят обычные проверки.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import func, inspect as sa_inspect, select
from sqlalchemy.orm import Session

from app.infrastructure.db.models import (
    AppUserRow,
    IntegrationMessageRow,
    IntegrationRequestRow,
    IntegratorProfileRow,
    MatchJournalRow,
    ProductRow,
    ProjectRow,
    VendorProfileRow,
    VendorRequestRow,
)

VENDOR_LOGIN = "ronavi"
INTEGRATOR_LOGIN = "integrator"
CUSTOMER_LOGIN = "user"


def seed_cabinets(db: Session) -> None:
    bind = db.get_bind()
    if bind is None:
        return
    tables = set(sa_inspect(bind).get_table_names())
    if {"vendor_request", "vendor_profile"} <= tables:
        _vendor(db)
    if "match_journal" in tables:
        _journal(db)
    if {"integration_request", "integration_message", "integrator_profile"} <= tables:
        _integrator(db)


def _user(db: Session, login: str) -> AppUserRow | None:
    return db.scalar(select(AppUserRow).where(AppUserRow.login == login))


def _ago(days: float) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days)


# --- Вендор: контакты в профиле и заявки во всех статусах --------------------------------------------------

def _vendor(db: Session) -> None:
    from app.infrastructure.db.vendor_repo import submit_request

    user = _user(db, VENDOR_LOGIN)
    profile = db.get(VendorProfileRow, user.id) if user else None
    if user is None or profile is None:
        return
    if not profile.email:
        profile.email = "sales@ronavi.ru"
    if not profile.phone:
        profile.phone = "+7 495 120-45-67"
    db.flush()
    if db.scalar(select(func.count()).select_from(VendorRequestRow).where(VendorRequestRow.user_id == user.id)):
        db.commit()
        return
    own = {row.slug: row for row in db.scalars(select(ProductRow).where(ProductRow.manufacturer == profile.manufacturer))}

    def pick(*parts: str) -> ProductRow | None:
        return next((row for slug, row in own.items() if all(part in slug for part in parts)), None)

    plans: list[tuple[str, dict, str, str, float]] = []
    h1500 = pick("h1500")
    if h1500:
        plans.append(("product_update", {
            "slug": h1500.slug, "name": h1500.name, "summary": h1500.summary or "",
            "attrs": [
                {"key": "work_time_h", "label": "Время работы", "value": 10},
                {"key": "charge_time_h", "label": "Время зарядки", "value": 1.5},
                {"key": "speed_loaded_ms", "label": "Скорость с грузом", "value": 1.2},
            ],
        }, "pending", "", 1.5))
    plans.append(("product_create", {
        "name": "Ronavi H3000 (грузоподъемность до 3 000 кг)",
        "summary": "Автономный паллетный робот для тяжёлых поддонов: лидар, подъём до 120 мм, работа в две смены.",
        "price_rub": 3200000,
        "processes": ["pallet_transport"],
        "attrs": {"Грузоподъёмность, кг": 3000, "Скорость с грузом, м/с": 1.0},
    }, "revision", "Добавьте время работы от батареи и время зарядки: без них платформа не посчитает, сколько роботов нужно.", 4))
    sr = pick("sr-")
    if sr:
        plans.append(("product_update", {
            "slug": sr.slug, "name": sr.name, "summary": sr.summary or "",
            "price_rub": 920000,
            "attrs": [{"key": "work_time_h", "label": "Время работы", "value": 8}],
        }, "approved", "Цена подтверждена прайсом от 01.10. Внесём в каталог вместе со следующей проверкой.", 9))
    plans.append(("profile", {
        "company_name": profile.company_name, "about": profile.about, "website": profile.website or "https://ronavi.ru",
        "email": "sales@ronavi.ru", "phone": "+7 495 120-45-67", "city": profile.city or "Москва",
    }, "pending", "", 0.5))
    rcm = pick("rcm")
    if rcm:
        plans.append(("product_update", {
            "slug": rcm.slug, "name": rcm.name, "summary": rcm.summary or "", "price_rub": 1200000,
        }, "rejected", "Цена ниже прайса на сайте в полтора раза. Пришлите коммерческое предложение — тогда примем.", 14))
    for kind, payload, status, comment, days in plans:
        try:
            view = submit_request(db, user.id, kind, payload)
        except ValueError:
            continue
        row = db.get(VendorRequestRow, UUID(str(view["id"]))) if isinstance(view, dict) and view.get("id") else None
        if row is None:
            continue
        row.status = status
        row.admin_comment = comment
        row.created_at = _ago(days)
        row.decided_at = _ago(max(0.0, days - 1)) if status != "pending" else None
    db.commit()


# --- Журнал подбора: реальные запуски подбора по демо, в том числе на жёстких условиях -------------------------

# Запуски подбора для журнала: полный расчёт по демо (их большинство) и заказчики, которые почти ничего не заполнили
# или работают в холоде, — у таких подбор пустой, и в аналитике видно почему.
_RUNS = (
    ("full", {}),
    ("full", {}),
    ("full", {}),
    ("sparse", {"area_m2": 3000}),
    ("sparse", {"area_m2": 3000, "temp_min_c": -25, "temp_max_c": 0}),
)


def _journal(db: Session) -> None:
    from app.infrastructure.db.analytics_repo import remember_project_match
    from app.infrastructure.db.taxonomy_repo import _public_site, _split_site, run_match

    if db.scalar(select(func.count()).select_from(MatchJournalRow)):
        return
    demos = list(db.scalars(select(ProjectRow).where(ProjectRow.is_demo.is_(True)).order_by(ProjectRow.slug)))
    runs = 0
    for demo in demos:
        stored, tasks = _split_site(demo.site or {})
        base = _public_site(stored)
        for kind, extra in _RUNS:
            try:
                if kind == "full":
                    site = {**base, **extra}
                    result = run_match(db, demo.id, site, tasks)
                else:
                    # Как новый проект без данных: условия демо не подставляются.
                    site = dict(extra)
                    result = run_match(db, demo.id, site, [], _prepared=True)
                remember_project_match(db, demo, site, result.get("groups"))
                runs += 1
            except Exception:  # noqa: BLE001 — наполнение для показа не должно ронять старт платформы
                db.rollback()
    if not runs:
        return
    # Разносим запуски по последнему месяцу, чтобы графики аналитики выглядели как живые.
    rows = list(db.scalars(select(MatchJournalRow).order_by(MatchJournalRow.created_at)))
    for index, row in enumerate(rows):
        row.created_at = _ago(28 - index * 28 / max(1, len(rows) - 1))
    db.commit()


# --- Интегратор: три проекта заказчика в разных статусах и переписка ------------------------------------------

_REQUESTS = (
    ("demo-warehouse", "Склад «Подольск-Логистик», 12 000 м²",
     "Нужна полная оценка перевозки паллет и инвентаризации. Хотим запуститься до конца первого квартала.",
     "answered",
     "Проект понятный, берём. Предлагаем пилот на 3 роботах MULE в зоне приёмки на 6 недель, затем расширение. "
     "Ориентир по КП — 2 недели после обследования.", 6,
     (
         ("customer", "Добрый день! Можете приехать на обследование на следующей неделе?", 5),
         ("integrator", "Да, предлагаем среду или четверг с 10:00. Возьмём лазерный дальномер и сделаем замеры проходов.", 4.8),
         ("customer", "Четверг подходит. Пропуск закажем на двоих.", 4.5),
         ("integrator", "Отлично. Пришлите, пожалуйста, план склада в DWG или DXF — сразу привяжем маршруты.", 4.4),
     )),
    ("demo-hospital", "Больница № 12, хирургический корпус",
     "Интересует доставка лекарств и биоматериалов между этажами. Важна работа с лифтами.",
     "sent", "", 1.2,
     (("customer", "Лифты в корпусе — Otis 2019 года, есть диспетчеризация.", 1.1),)),
    ("demo-airport", "Аэропорт «Северный», терминал А",
     "Нужна оценка перевозки багажа на перроне.",
     "declined", "", 11,
     (
         ("customer", "Подскажите, работаете ли вы с перроном и допусками на лётное поле?", 10.5),
         ("integrator", "К сожалению, допуска на перрон у нас нет — проект передадим партнёрам, если захотите.", 10),
     )),
)


def _integrator(db: Session) -> None:
    from app.infrastructure.db.integrator_repo import send_project
    from app.infrastructure.db.taxonomy_repo import copy_project

    integrator = _user(db, INTEGRATOR_LOGIN)
    customer = _user(db, CUSTOMER_LOGIN)
    if integrator is None or customer is None or db.get(IntegratorProfileRow, integrator.id) is None:
        return
    if db.scalar(select(func.count()).select_from(IntegrationRequestRow).where(IntegrationRequestRow.integrator_user_id == integrator.id)):
        return
    profile = db.get(IntegratorProfileRow, integrator.id)
    if profile.nda_accepted_at is None:
        profile.nda_accepted_at = _ago(20)
    db.flush()
    for slug, name, note, status, answer, days, chat in _REQUESTS:
        demo = db.scalar(select(ProjectRow).where(ProjectRow.slug == slug, ProjectRow.is_demo.is_(True)))
        if demo is None:
            continue
        try:
            copy = copy_project(db, demo.id, owner_id=customer.id)
            project = db.get(ProjectRow, UUID(str(copy["id"])))
            project.name = name
            db.flush()
            view = send_project(db, customer.id, project, integrator.id, note)
        except (ValueError, KeyError, PermissionError):
            db.rollback()
            continue
        row = db.get(IntegrationRequestRow, UUID(str(view["id"])))
        row.status = status
        if status == "answered":
            row.feedback = answer
        if status == "declined":
            row.decline_comment = "Нет допуска на работу на перроне. Готовы передать проект партнёру с допуском."
        row.created_at = _ago(days)
        row.updated_at = _ago(min(days, min(item[2] for item in chat)) if chat else days)
        for author, body, ago in chat:
            db.add(IntegrationMessageRow(
                id=uuid4(), request_id=row.id,
                author_user_id=customer.id if author == "customer" else integrator.id,
                body=body, files=[], created_at=_ago(ago),
            ))
    db.commit()
