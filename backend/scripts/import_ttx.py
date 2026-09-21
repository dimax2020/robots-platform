"""Импорт ТТХ из data/ttx_manual.csv в product.attrs.

Источник создаётся не один на весь файл, а по одному на каждую ссылку: достоверность
значения выводится из вида его источника (§6.3), поэтому страница производителя и
отраслевой каталог обязаны стать разными записями source.

Повторный прогон перезаписывает только те ключи, что есть в CSV, и переиспользует
уже созданные источники, так что импорт идемпотентен.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import date
from urllib.parse import urlsplit

from sqlalchemy import select

from api.config import get_settings
from api.db.models import AttributeDef, Product, Source
from api.db.session import get_sessionmaker

DATA_DIR = get_settings().data_dir
CSV_PATH = DATA_DIR / "ttx_manual.csv"
ATTRIBUTES_FILE = DATA_DIR / "attributes.json"
TITLE = "Ручной поиск ТТХ"
# Вид источника определяет букву достоверности, а у оценок и допущений обоснование
# обязательно — так же, как в форме админки (api/routers/admin.py)
RATIONALE = {
    "analogue": "Значение получено оценкой по близкому аналогу при ручном поиске ТТХ",
    "assumption": "Значение принято командой как допущение при ручном поиске ТТХ",
}


def load_schema() -> dict[str, dict]:
    raw = json.loads(ATTRIBUTES_FILE.read_text(encoding="utf-8"))
    return {a["key"]: a for a in raw["attributes"]}


def publisher_of(url: str) -> str:
    if not url:
        return "Команда проекта"
    host = urlsplit(url).netloc
    return host[4:] if host.startswith("www.") else host


def cast(value: str, datatype: str) -> float | bool | str:
    if datatype == "number":
        return float(value)
    if datatype == "bool":
        return value == "true"
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="не писать в базу, только отчёт")
    args = parser.parse_args()

    schema = load_schema()
    with CSV_PATH.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    with get_sessionmaker()() as db:
        known_keys = set(db.scalars(select(AttributeDef.key)).all())
        if unknown := sorted({r["attr_key"] for r in rows} - known_keys):
            print(f"характеристик нет в справочнике attribute_def: {', '.join(unknown)}")
            return 1

        products = {
            p.slug: p
            for p in db.scalars(select(Product).where(Product.valid_to.is_(None))).all()
        }
        if missing := sorted({r["product_slug"] for r in rows} - products.keys()):
            print(f"решений нет в каталоге: {', '.join(missing)}")
            return 1

        sources: dict[tuple[str, str], Source] = {}
        created_sources = 0
        for row in rows:
            key = (row["source_kind"], row["source_url"])
            if key in sources:
                continue
            kind, url = key
            stmt = select(Source).where(Source.kind == kind)
            stmt = (
                stmt.where(Source.url == url)
                if url
                else stmt.where(Source.url.is_(None), Source.title == TITLE)
            )
            if existing := db.scalar(stmt.limit(1)):
                sources[key] = existing
                continue
            source = Source(
                kind=kind,
                url=url or None,
                publisher=publisher_of(url),
                title=TITLE,
                captured_at=date.today(),
                rationale=RATIONALE.get(kind),
            )
            db.add(source)
            sources[key] = source
            created_sources += 1
        db.flush()

        touched: dict[str, dict] = {}
        for row in rows:
            product = products[row["product_slug"]]
            attrs = touched.setdefault(product.slug, dict(product.attrs))
            definition = schema[row["attr_key"]]
            known = row["status"] == "known"
            attrs[row["attr_key"]] = {
                "status": row["status"],
                "value": cast(row["value"], definition["datatype"]) if known else None,
                "unit": definition.get("unit"),
                "source_id": sources[(row["source_kind"], row["source_url"])].id,
                "quote": row["quote"] or None,
                "note": None,
                "extracted_by": "разбор таблиц ручного поиска",
            }

        for slug, attrs in touched.items():
            products[slug].attrs = attrs

        by_kind = Counter(r["source_kind"] for r in rows)
        print(f"решений затронуто: {len(touched)}, характеристик записано: {len(rows)}")
        print(f"источников создано: {created_sources}, всего задействовано: {len(sources)}")
        print("по видам источников:", ", ".join(f"{k} {v}" for k, v in by_kind.most_common()))

        if args.dry_run:
            db.rollback()
            print("холостой прогон: изменения откачены")
            return 0

        db.commit()
        print("записано")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
