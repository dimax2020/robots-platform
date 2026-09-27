"""Фоновый исполнитель прогонов. Очередь — таблица job."""

import time
from datetime import datetime
from zoneinfo import ZoneInfo

from app.application.reference_data import assign_missing_types
from app.config import get_settings
from app.infrastructure.db.catalog_repo import untyped_count
from app.domain.csv_parse import parse_catalog_csv, parse_manual_csv
from app.infrastructure.db.ingest import ingest_records, overlay_rows
from app.infrastructure.db.job_repo import claim, due_parsers, finish
from app.infrastructure.db.session import session_factory
from app.parsers import collect


def main() -> None:
    settings = get_settings()
    zone = ZoneInfo("Europe/Moscow")
    while True:
        with session_factory()() as db:
            job = claim(db, settings.job_stale_s)
        if job is None:
            now = datetime.now(zone)
            with session_factory()() as db:
                due_parsers(db, now)
            time.sleep(5)
            continue
        try:
            counters = _run(job.kind, job.parser_code, job.file_path)
        except Exception as exc:
            with session_factory()() as db:
                finish(db, job.id, status="error", error=str(exc), counters={})
        else:
            with session_factory()() as db:
                finish(db, job.id, status="success", error=None, counters=counters)


def _typed(counters: dict) -> dict:
    """Новым карточкам тип решения ставится сразу; число оставшихся без типа видно в итогах прогона."""
    with session_factory()() as db:
        counters["typed"] = assign_missing_types(db)
        db.commit()
        counters["untyped"] = untyped_count(db)
    return counters


def _run(kind: str, parser_code: str, file_path: str | None) -> dict:
    if kind == "import_catalog":
        text = open(file_path, encoding="utf-8-sig").read()
        records = parse_catalog_csv(text)
        with session_factory()() as db:
            counters = ingest_records(db, records)
        return _typed({"created": counters.created, "updated": counters.updated, "skipped": counters.skipped, "rows": len(records)})
    if kind == "import_manual":
        text = open(file_path, encoding="utf-8-sig").read()
        rows = parse_manual_csv(text)
        with session_factory()() as db:
            counters = overlay_rows(db, rows)
        return {"updated": counters.updated, "skipped": counters.skipped, "rows": len(rows)}
    if kind == "parser":
        records = collect(parser_code)
        with session_factory()() as db:
            counters = ingest_records(db, records)
        return _typed({"created": counters.created, "updated": counters.updated, "rows": len(records)})
    raise RuntimeError(f"неизвестный прогон {kind}")


if __name__ == "__main__":
    main()
