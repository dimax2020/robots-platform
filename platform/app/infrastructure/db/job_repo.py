from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from uuid import UUID, uuid4

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.infrastructure.db.models import JobRow, ParserSettingRow


def enqueue(db: Session, *, kind: str, parser_code: str = "", file_path: str | None = None, job_id: UUID | None = None) -> JobRow | None:
    live = db.scalar(
        select(JobRow).where(
            JobRow.kind == kind,
            JobRow.parser_code == parser_code,
            JobRow.status.in_(("pending", "running")),
        )
    )
    if live is not None:
        return None
    job = JobRow(id=job_id or uuid4(), kind=kind, parser_code=parser_code, status="pending", file_path=file_path, counters={})
    db.add(job)
    db.commit()
    return job


def claim(db: Session, stale_s: int) -> JobRow | None:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=stale_s)
    db.execute(
        text(
            "UPDATE job SET status = 'pending', started_at = NULL "
            "WHERE status = 'running' AND started_at IS NOT NULL AND started_at < :cutoff"
        ),
        {"cutoff": cutoff},
    )
    row = db.scalar(
        select(JobRow)
        .where(JobRow.status == "pending")
        .order_by(JobRow.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if row is None:
        db.commit()
        return None
    row.status = "running"
    row.started_at = datetime.now(timezone.utc)
    db.commit()
    return row


def finish(db: Session, job_id: UUID, *, status: str, error: str | None, counters: dict) -> None:
    job = db.get(JobRow, job_id)
    if job is None:
        return
    job.status = status
    job.error = error
    job.counters = counters
    job.finished_at = datetime.now(timezone.utc)
    db.commit()


def get_job(db: Session, job_id: UUID) -> dict | None:
    job = db.get(JobRow, job_id)
    if job is None:
        return None
    return _job(job)


def recent_jobs(db: Session, *, prefix: str = "", limit: int = 20) -> list[dict]:
    stmt = select(JobRow).order_by(JobRow.created_at.desc()).limit(limit)
    if prefix:
        stmt = stmt.where(JobRow.kind.startswith(prefix))
    return [_job(row) for row in db.scalars(stmt)]


def due_parsers(db: Session, now: datetime) -> list[str]:
    """Один запуск в сутки, в окне двух часов после назначенного времени по Москве."""
    today = now.date()
    codes = []
    for row in db.scalars(select(ParserSettingRow).where(ParserSettingRow.enabled.is_(True))):
        if row.last_enqueued_on == today:
            continue
        slot = now.replace(hour=row.hour, minute=row.minute or 0, second=0, microsecond=0)
        if now < slot or now > slot + timedelta(hours=2):
            continue
        created = enqueue(db, kind="parser", parser_code=row.code)
        if created is not None:
            row.last_enqueued_on = today
            db.commit()
            codes.append(row.code)
    return codes


def parser_settings(db: Session, now: datetime | None = None) -> list[dict]:
    moment = now or datetime.now(ZoneInfo("Europe/Moscow"))
    rows = []
    for row in db.scalars(select(ParserSettingRow).order_by(ParserSettingRow.code)):
        last = db.scalar(
            select(JobRow)
            .where(JobRow.kind == "parser", JobRow.parser_code == row.code)
            .order_by(JobRow.created_at.desc())
            .limit(1)
        )
        rows.append({
            "code": row.code,
            "enabled": row.enabled,
            "hour": row.hour,
            "minute": row.minute or 0,
            "next_run": _next_run(row, moment).isoformat(),
            "last_enqueued_on": row.last_enqueued_on.isoformat() if row.last_enqueued_on else None,
            "last_job": None if last is None else _job(last),
        })
    return rows


def set_schedule(db: Session, code: str, *, enabled: bool | None, hour: int | None, minute: int | None) -> dict:
    row = db.get(ParserSettingRow, code)
    if row is None:
        raise KeyError(code)
    if enabled is not None:
        row.enabled = enabled
    if hour is not None:
        row.hour = hour
    if minute is not None:
        row.minute = minute
    db.commit()
    found = next(item for item in parser_settings(db) if item["code"] == code)
    return found


def _next_run(row: ParserSettingRow, now: datetime) -> datetime:
    slot = now.replace(hour=row.hour, minute=row.minute or 0, second=0, microsecond=0)
    if row.last_enqueued_on == now.date() or now >= slot:
        return slot + timedelta(days=1)
    return slot


def _job(job: JobRow) -> dict:
    return {
        "id": str(job.id),
        "kind": job.kind,
        "parser_code": job.parser_code or None,
        "status": job.status,
        "error": job.error,
        "counters": job.counters,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }
