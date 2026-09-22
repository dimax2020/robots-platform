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

from argon2 import PasswordHasher
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from api.config import get_settings
from api.db.models import (
    AppUser,
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
from api.deps import DEMO_USER_ID, DEMO_USER_LOGIN
from engine.rules import validate_rule_spec

SETTINGS = get_settings()
DATA_DIR = SETTINGS.data_dir
CATALOG_FILE = DATA_DIR / "catalog_normalized.json"
ATTRIBUTES_FILE = DATA_DIR / "attributes.json"
NORMS_FILE = DATA_DIR / "norms" / "calc_norms.json"
RULES_DIR = DATA_DIR / "rules"
DEFAULT_RULES_FILE = RULES_DIR / "_default.json"


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _strip_private(value: Any) -> Any:
    """Ключи с «_» — заметки для людей, в rule_spec их нет (§4.1)."""
    if isinstance(value, dict):
        return {k: _strip_private(v) for k, v in value.items() if not str(k).startswith("_")}
    if isinstance(value, list):
        return [_strip_private(item) for item in value]
    return value


def resolve_rule_spec(code: str, family: str, default_rules: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Файл типа → шаблон семейства → _default (§4.1). Файла семейства может ещё не быть."""
    type_path = RULES_DIR / f"{code}.json"
    family_path = RULES_DIR / f"_family_{family}.json"
    if type_path.exists():
        raw, origin, path = load_json(type_path), "type", type_path
    elif family_path.exists():
        raw, origin, path = load_json(family_path), "family", family_path
    else:
        raw, origin, path = default_rules, "default", DEFAULT_RULES_FILE

    spec = _strip_private(raw)
    spec["solution_type"] = code
    spec["sizing"] = dict(spec.get("sizing") or {}, family=family)
    try:
        validate_rule_spec(spec)
    except Exception as exc:
        raise ValueError(f"Битый RuleSpec для типа {code} (файл {path}): {exc}") from exc
    return spec, origin


def seed_calc_norms(
    db: Session,
    rows: list[dict[str, Any]],
    solution_types: dict[str, SolutionType],
    captured_at: date,
) -> int:
    """Каждое число — source с непустым rationale (ТЗ 3.5.1). Уникальность calc_norm — (solution_type_id, key)."""
    cache: dict[tuple[str, str | None, str], Source] = {}
    seen: set[tuple[int | None, str]] = set()
    inserted = 0
    for row in rows:
        src = row["source"]
        rationale = (src.get("rationale") or "").strip()
        if not rationale:
            raise ValueError(f"Пустой source.rationale у норматива {row['key']}")
        triple = (src["kind"], src.get("publisher"), rationale)
        source = cache.get(triple)
        if source is None:
            source = Source(
                kind=src["kind"],
                publisher=src.get("publisher"),
                rationale=rationale,
                captured_at=captured_at,
                title="Норматив расчёта количества",
            )
            db.add(source)
            db.flush()
            cache[triple] = source

        st_code = row.get("solution_type_code")
        st_id = solution_types[st_code].id if st_code else None
        uniq = (st_id, row["key"])
        if uniq in seen:
            continue
        seen.add(uniq)
        db.add(
            CalcNorm(
                solution_type_id=st_id,
                key=row["key"],
                value=row["value"],
                unit=row.get("unit"),
                source_id=source.id,
                editable=bool(row.get("editable", True)),
            )
        )
        inserted += 1
    return inserted


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


def seed_demo_user(db: Session) -> AppUser:
    """Демо-пользователь с фиксированным UUID. Авторизации нет — заглушка (§0, §7.1)."""
    user = db.scalar(
        select(AppUser).where(
            (AppUser.id == DEMO_USER_ID) | (AppUser.login == DEMO_USER_LOGIN)
        )
    )
    if user is not None:
        return user
    user = AppUser(
        id=DEMO_USER_ID,
        login=DEMO_USER_LOGIN,
        password_hash=PasswordHasher().hash("demo"),
        role="admin",
    )
    db.add(user)
    db.flush()
    return user


def seed(db: Session, *, reset: bool) -> dict[str, int]:
    data = load_json(CATALOG_FILE)
    attributes = load_json(ATTRIBUTES_FILE)["attributes"]
    default_rules = load_json(DEFAULT_RULES_FILE)
    norm_rows = load_json(NORMS_FILE)["norms"]

    seed_demo_user(db)

    if reset:
        reset_catalog(db)

    if db.scalar(select(Product.id).limit(1)) is not None:
        print("Каталог уже засеян. Для пересева: python -m scripts.seed --reset")
        db.commit()
        return {"demo_user": 1}

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

    # RuleSpec: файл типа, иначе _family_<family>, иначе _default (§4.1)
    rule_specs_real = 0
    rule_specs_placeholder = 0
    solution_types: dict[str, SolutionType] = {}
    for row in data["solution_types"]:
        spec, origin = resolve_rule_spec(row["code"], row["family"], default_rules)
        if origin == "default":
            rule_specs_placeholder += 1
        else:
            rule_specs_real += 1
        obj = SolutionType(code=row["code"], name=row["name"], family=row["family"], rule_spec=spec)
        db.add(obj)
        solution_types[row["code"]] = obj

    db.flush()

    # Нормативы подбора (ТЗ 3.5.1, §3). Источник с той же тройкой kind+publisher+rationale не дублируем
    n_norms = seed_calc_norms(
        db, norm_rows, solution_types, date.fromisoformat(data["generated_at"])
    )

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
        "calc_norms": n_norms,
        "rule_specs": rule_specs_real,
        "rule_specs_placeholder": rule_specs_placeholder,
        "demo_user": 1,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Сид каталога в БД")
    parser.add_argument("--reset", action="store_true", help="вычистить каталог перед сидом")
    args = parser.parse_args(argv)

    for path in (CATALOG_FILE, ATTRIBUTES_FILE, DEFAULT_RULES_FILE, NORMS_FILE):
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
