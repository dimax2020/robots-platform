"""Аудит/нормализация каталога: python -m app.normalize_catalog --report report.json [--apply]."""
import argparse
import json
from pathlib import Path

from app.infrastructure.db.ingest import normalize_stored
from app.infrastructure.db.session import session_factory


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Записать изменения (по умолчанию откат)')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    with session_factory()() as db:
        report = normalize_stored(db)
        report['applied'] = args.apply
        # Ошибка записи отчёта не должна оставлять изменения без отчёта.
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        if args.apply:
            db.commit()
        else:
            db.rollback()
    print(json.dumps({k: v for k, v in report.items() if k != 'issues'}, ensure_ascii=False))
    print(f"Замечаний: {len(report['issues'])}; отчёт: {args.report}")


if __name__ == '__main__':
    main()
