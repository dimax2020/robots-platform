"""data/catalog_normalized.json → Postgres.

    python -m scripts.seed          # засеять (идемпотентно)
    python -m scripts.seed --reset  # вычистить каталог и засеять заново

Запускается внутри контейнера api: читает только data/, которая смонтирована (§3.2).
Нормализованный файл готовит scripts/normalize.py на машине разработчика.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from api.config import get_settings
from api.db.models import (
    AttributeDef,
    CalcNorm,
    CatalogVersion,
    Industry,
    IndustryObject,
    ObjectProcess,
    ObjectType,
    Process,
    Product,
    ProductCase,
    ProcessSolution,
    SolutionType,
    Source,
)
from api.db.session import get_sessionmaker

SETTINGS = get_settings()
DATA_DIR = SETTINGS.data_dir
CATALOG_FILE = DATA_DIR / "catalog_normalized.json"
ATTRIBUTES_FILE = DATA_DIR / "attributes.json"
DEFAULT_RULES_FILE = DATA_DIR / "rules" / "_default.json"


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def attr(value: Any, source_id: int, *, note: str | None = None, unit: str | None = None) -> dict[str, Any]:
    """AttrValue по §6.3: значение ссылается на источник, достоверность выводится из него."""
    return {
        "status": "known" if value is not None else "unknown",
        "value": value,
        "unit": unit,
        "source_id": source_id,
        "quote": None,
        "note": note,
        "extracted_by": None,
    }


def reset_catalog(db: Session) -> None:
    """Вычистить каталог. Порядок обратный зависимостям; проекты и пользователи не трогаются."""
    for model in (
        ProductCase,
        CalcNorm,
        ProcessSolution,
        ObjectProcess,
        IndustryObject,
    ):
        db.execute(delete(model))
    db.execute(delete(Source).where(Source.ref_product_id.is_not(None)))
    db.execute(delete(Product))
    db.execute(delete(Source))
    db.execute(delete(SolutionType))
    db.execute(delete(Process))
    db.execute(delete(ObjectType))
    db.execute(delete(Industry))
    db.execute(delete(AttributeDef))
    db.execute(delete(CatalogVersion))
    db.commit()


def seed(db: Session, *, reset: bool) -> dict[str, int]:
    data = load_json(CATALOG_FILE)
    attributes = load_json(ATTRIBUTES_FILE)["attributes"]
    default_rules = load_json(DEFAULT_RULES_FILE)

    if reset:
        reset_catalog(db)

    if db.scalar(select(Product.id).limit(1)) is not None:
        print("Каталог уже засеян. Для пересева: python -m scripts.seed --reset")
        return {}

    # 1. Версия каталога (§6.5): прогоны расчёта ссылаются на неё, продукты живут интервалом
    version = CatalogVersion(
        published_by="scripts.seed",
        note=f"Первичный импорт: {data['source_file']}, {data['stats']['products']} продуктов",
    )
    db.add(version)
    db.flush()

    # 2. Источник (§6.4). Достоверность B выводится из kind='catalog', буква нигде не хранится
    source = Source(
        kind="catalog",
        url=None,
        publisher="ФЦ БАС",
        title=f"Каталог роботизированных решений, {data['source_file']}",
        captured_at=date.fromisoformat(data["generated_at"]),
    )
    db.add(source)
    db.flush()

    # 3. Справочник характеристик — из него строится вся работа с ТТХ (§6.2)
    for a in attributes:
        db.add(
            AttributeDef(
                key=a["key"],
                group_code=a["group_code"],
                label=a["label"],
                unit=a.get("unit"),
                datatype=a["datatype"],
                enum_values=a.get("enum_values"),
                required_for=a.get("required_for"),
                sort=a.get("sort"),
            )
        )

    # 4. Справочники иерархии (§6.1)
    industries: dict[str, Industry] = {}
    for row in data["industries"]:
        obj = Industry(code=row["code"], name=row["name"])
        db.add(obj)
        industries[row["code"]] = obj

    object_types: dict[str, ObjectType] = {}
    for row in data["object_types"]:
        obj = ObjectType(code=row["code"], name=row["name"])
        db.add(obj)
        object_types[row["code"]] = obj

    processes: dict[str, Process] = {}
    for row in data["processes"]:
        obj = Process(code=row["code"], name=row["name"])
        db.add(obj)
        processes[row["code"]] = obj

    solution_types: dict[str, SolutionType] = {}
    for row in data["solution_types"]:
        spec = dict(default_rules, solution_type=row["code"])
        spec["sizing"] = dict(default_rules["sizing"], family=row["family"])
        obj = SolutionType(code=row["code"], name=row["name"], family=row["family"], rule_spec=spec)
        db.add(obj)
        solution_types[row["code"]] = obj

    db.flush()

    # 5. Связи справочников — из них джойнами собирается дерево каталога
    for link in data["industry_objects"]:
        db.add(
            IndustryObject(
                industry_id=industries[link["industry"]].id,
                object_type_id=object_types[link["object_type"]].id,
            )
        )
    for link in data["object_processes"]:
        db.add(
            ObjectProcess(
                object_type_id=object_types[link["object_type"]].id,
                process_id=processes[link["process"]].id,
            )
        )
    for link in data["process_solutions"]:
        db.add(
            ProcessSolution(
                process_id=processes[link["process"]].id,
                solution_type_id=solution_types[link["solution_type"]].id,
            )
        )

    # 6. Продукты. Цена, регион и класс системы ложатся в attrs, а не в колонки (§6.2)
    cases = 0
    for p in data["products"]:
        attrs: dict[str, Any] = {
            "region": attr(p["region"], source.id),
            "system_class": attr(p["system_class"], source.id),
        }
        if p["price_rub"] is not None:
            attrs["price_rub"] = attr(p["price_rub"], source.id, note=p["price_note"], unit="₽")
        else:
            attrs["price_rub"] = {
                "status": "unknown",
                "value": None,
                "unit": "₽",
                "source_id": None,
                "quote": None,
                "note": "в исходном каталоге цена не указана",
                "extracted_by": None,
            }

        product = Product(
            id=p["id"],
            solution_type_id=solution_types[p["solution_type_code"]].id,
            slug=p["slug"],
            name=p["name"],
            manufacturer=p["manufacturer"],
            legal_entity=p["legal_entity"],
            country=p["country"],
            availability=p["availability"],
            trl=p["trl"],
            market_potential=p["market_potential"],
            summary=p["summary"],
            attrs=attrs,
            valid_from=version.id,
            valid_to=None,
        )
        db.add(product)

        for case in p["cases"]:
            process_code = case.get("process_code")
            db.add(
                ProductCase(
                    product_id=p["id"],
                    process_id=processes[process_code].id if process_code in processes else None,
                    object_type_id=None,
                    customer=None,
                    summary=case["summary"],
                    source_id=source.id,
                )
            )
            cases += 1

    db.commit()

    return {
        "catalog_version": version.id,
        "attribute_defs": len(attributes),
        "industries": len(industries),
        "object_types": len(object_types),
        "processes": len(processes),
        "solution_types": len(solution_types),
        "products": len(data["products"]),
        "cases": cases,
        "industry_objects": len(data["industry_objects"]),
        "object_processes": len(data["object_processes"]),
        "process_solutions": len(data["process_solutions"]),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Сид каталога в БД")
    parser.add_argument("--reset", action="store_true", help="вычистить каталог перед сидом")
    args = parser.parse_args(argv)

    for path in (CATALOG_FILE, ATTRIBUTES_FILE, DEFAULT_RULES_FILE):
        if not path.exists():
            print(f"Не найден файл данных: {path}", file=sys.stderr)
            if path == CATALOG_FILE:
                print("Сначала выполните: python -m scripts.normalize", file=sys.stderr)
            return 1

    with get_sessionmaker()() as db:
        stats = seed(db, reset=args.reset)

    if stats:
        width = max(len(k) for k in stats)
        for key, value in stats.items():
            print(f"  {key:<{width}}  {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
