"""Импорт роботов без перезаписи заполненных данных; robort.ru с ценой может создавать product.

Запуск из backend: python -m scripts.import_robots ../robots.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5


# (раздел, название в JSON): (ключ attrs, тип, единица БД, множитель).
MAPPING = {
    ("Основные характеристики", "Вес, кг"): ("mass_kg", "number", "кг", 1),
    ("Основные характеристики", "Грузоподъёмность, кг"): ("payload_kg", "number", "кг", 1),
    ("Основные характеристики", "Габариты (ДxШxВ), мм"): ("dimensions_mm", "text", "мм", 1),
    ("Основные характеристики", "Количество осей (cуставов)"): ("axes", "number", None, 1),
    ("Основные характеристики", "Досягаемость (радиус действия), мм"): ("reach_mm", "number", "мм", 1),
    ("Основные характеристики", "Высота подъема, мм"): ("lift_height_mm", "number", "мм", 1),
    ("Основные характеристики", "Минимальная ширина проезда, мм"): ("min_aisle_width_m", "number", "м", 0.001),
    ("Основные характеристики", "Тип поддона"): ("container_type", "text", None, 1),
    ("Батарея", "Время работы на одном заряде, час."): ("work_time_h", "number", "ч", 1),
    ("Батарея", "Время автономной работы, час."): ("work_time_h", "number", "ч", 1),
    ("Батарея", "Время заряда батареи, час."): ("charge_time_h", "number", "ч", 1),
    ("Батарея", "Способ зарядки"): ("charging_type", "text", None, 1),
    ("Навигация", "Тип навигации"): ("navigation", "text", None, 1),
    ("Навигация", "Точность позиционирования / стыковки, ±мм"): ("accuracy_mm", "text", "мм", 1),
    ("Скорость", "Максимальная скорость движения (без груза), м/c"): ("speed_empty_ms", "number", "м/с", 1),
    ("Скорость", "Максимальная скорость движения (с грузом), м/c"): ("speed_loaded_ms", "number", "м/с", 1),
    ("Питание", "Потребляемая мощность, кВт"): ("power_watt", "number", "Вт", 1000),
    ("Питание", "Подключение, В"): ("power_supply", "text", None, 1),
    ("Интерфейсы", "Интерфейсы подключения"): ("connectivity", "text", None, 1),
    ("Требования к условиям", "Тип защиты IP"): ("ip_rating", "text", None, 1),
}
COLUMNS = {
    ("Общие характеристики", "Бренд"): "manufacturer",
    ("Общие характеристики", "Страна производства"): "country",
}


# Плоские характеристики robort.ru. Единицы числа проверяются целиком.
ROBORT_FIELDS = {
    "Вес": ("mass_kg", "number", "кг", 1),
    "Вес (с аккумулятором)": ("mass_kg", "number", "кг", 1),
    "Масса, кг": ("mass_kg", "number", "кг", 1),
    "Грузоподъемность (максимальная)": ("payload_kg", "number", "кг", 1),
    "Допустимая нагрузка, кг": ("payload_kg", "number", "кг", 1),
    "Время работы на одном заряде": ("work_time_h", "number", "ч", 1),
    "Время работы": ("work_time_h", "number", "ч", 1),
    "Время зарядки": ("charge_time_h", "number", "ч", 1),
    "Количество степеней свободы": ("axes", "number", None, 1),
    "Степени свободы (отдельные моторы):": ("axes", "number", None, 1),
    "Минимальная ширина проезда": ("min_aisle_width_m", "number", "м", 1),
    "Мощность, л.с.": ("power_watt", "number", "Вт", 1),
    "Класс защиты": ("ip_rating", "text", None, 1),
    "Электропитание": ("power_supply", "text", None, 1),
    "Беспроводные интерфейсы": ("connectivity", "text", None, 1),
    "Гарантия": ("warranty", "text", None, 1),
    "price": ("price_rub", "number", "₽", 1),
}
MAPPING.update({("robort", label): spec for label, spec in ROBORT_FIELDS.items()})
ROBORT_UNITS = {
    "кг": {"кг": 1}, "ч": {"ч": 1, "мин": 1 / 60},
    "м": {"м": 1, "см": 0.01, "мм": 0.001},
    "Вт": {"Вт": 1, "кВт": 1000}, "₽": {"₽": 1}, None: {},
}


def is_robort(row):
    return urlparse(row.get("url") or "").hostname in {"robort.ru", "www.robort.ru"} or any(
        not isinstance(v, dict) for v in row.get("specs", {}).values()
    )


def empty(value):
    return value is None or isinstance(value, str) and not value.strip()


def load_rows(path):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Корень JSON должен быть массивом")
    for i, row in enumerate(rows, 1):
        if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not row["name"].strip():
            raise ValueError(f"Строка {i}: требуется непустой name")
        if not isinstance(row.get("specs", {}), dict):
            raise ValueError(f"Строка {i}: specs должен быть словарём")
        flat = is_robort(row)
        for section in row.get("specs", {}).values():
            if (flat and not isinstance(section, (str, type(None)))) or (not flat and (
                not isinstance(section, dict) or any(not isinstance(v, (str, type(None))) for v in section.values())
            )):
                raise ValueError(f"Строка {i}: разделы specs должны содержать строки или null")
    return rows


def map_row(row):
    columns, attrs, skipped = {}, {}, []
    png_url = row.get("png_url")
    if not empty(png_url):
        if isinstance(png_url, str):
            columns["png_url"] = png_url.strip()
        else:
            skipped.append("png_url: ожидается строка")
    robort = is_robort(row)
    specs = row.get("specs", {})
    if robort:
        specs = {"robort": {**specs, "price": str(row["price"]) if row.get("price") is not None else None}}
    for section, values in specs.items():
        for label, raw in values.items():
            if empty(raw):
                continue
            path = (section, label)
            if path in COLUMNS:
                columns[COLUMNS[path]] = raw.strip()
                continue
            if path not in MAPPING:
                skipped.append(f"specs.{section}.{label}: нет маппинга")
                continue
            key, datatype, unit, factor = MAPPING[path]
            value = raw.strip()
            if datatype == "number":
                normalized = value.replace(",", ".")
                if robort:
                    match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d+)?|\.\d+))\s*([^\d\s]*)", normalized)
                    if match:
                        number, suffix = match.groups()
                        units = ROBORT_UNITS[unit]
                        # У мощности заголовок в л.с.; голое число нельзя считать ваттами.
                        if suffix in units:
                            normalized = number
                            factor = units[suffix]
                        elif not suffix and label != "Мощность, л.с." and (
                            unit is None or label in {"Масса, кг", "Допустимая нагрузка, кг", "price"}
                        ):
                            normalized = number
                        else:
                            normalized = "invalid unit"
                # Диапазоны, «до 10» и числа с пояснениями нельзя превращать в точное значение.
                if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)", normalized):
                    skipped.append(f"{section}.{label}: неоднозначное число {raw!r}")
                    continue
                value = float(normalized) * factor
                if not math.isfinite(value):
                    skipped.append(f"{section}.{label}: число вне допустимого диапазона")
                    continue
            if key in attrs:
                skipped.append(f"{section}.{label}: повторное соответствие {key}")
                continue
            attrs[key] = dict(status="known", value=value, unit=unit,
                              source_id=None, quote=f"{section}: {label}: {raw}",
                              note=None, extracted_by="robort_robots.json / robort" if robort else "robots.json / robob2b")
    for key in row.keys() - {"name", "specs", "url", "png_url"} - ({"price"} if robort else set()):
        if not empty(row[key]):
            skipped.append(f"{key}: нет маппинга (id JSON не является product.id)")
    return columns, attrs, skipped


def additions(product, columns, attrs):
    """Наличие ключа защищает весь AttrValue, включая unknown, null и {}."""
    return (
        {k: v for k, v in columns.items() if empty(getattr(product, k))},
        {k: v for k, v in attrs.items() if k not in (product.attrs or {})},
    )


def robort_solution_code(row):
    """Классификация по явно указанному типу, категории и названию."""
    text = " ".join(str(v or "") for v in (
        row.get("type"), row.get("name"), row.get("url"),
        row.get("specs", {}).get("Тип"), row.get("category_url"),
    )).casefold()
    rules = [
        ("humanoid_robot", ("гуманоид", "антропоморф")),
        ("cleaning_robot", ("уборщик", "уборщики", "uborshchik", "kleenbot", "поломоеч")),
        ("cobot", ("коллаборатив", "kollaborativ")),
        ("robot_manipulator", ("манипулятор", "manipulyator", "roboruki", "роботизированная рука")),
        ("courier_robot", ("доставщик", "официант", "dostavshchik", "dinerbot")),
        ("mobile_robot_generic", ("складск", "логистич", "грузчик", "платформа", "seriya-limo", "seriya-scout", "seriya-bunker", "колесн", "гусенич", "пожарн")),
    ]
    return next((code for code, words in rules if any(word in text for word in words)), "robotic_installation")


def import_rows(db, rows, *, dry_run=False):
    from sqlalchemy import select, text
    from api.db.models import AttributeDef, Product, Source, CatalogVersion, SolutionType

    # Сериализуем импорты, включая случай ещё отсутствующего продукта.
    db.execute(text("SELECT pg_advisory_xact_lock(7242401)"))
    version = None

    definitions = {d.key: d for d in db.scalars(select(AttributeDef))}
    report = []
    for row in rows:
        entry = {"name": row["name"]}
        report.append(entry)
        # Экранируем спецсимволы LIKE: имя — буквальный префикс, а не SQL-шаблон.
        prefix = row["name"].replace("!", "!!").replace("%", "!%").replace("_", "!_")
        stmt = (
            select(Product)
            .where(Product.valid_to.is_(None), Product.name.ilike(prefix + "%", escape="!"))
            .order_by(Product.id)
            .with_for_update()
        )
        matches = db.scalars(stmt).all()
        if len(matches) > 1:
            entry["status"] = "ambiguous"
            continue
        creating = not matches
        columns, attrs, skipped = map_row(row)
        if creating:
            price = attrs.get("price_rub", {}).get("value")
            if not is_robort(row) or price is None or price <= 0:
                entry.update(status="not_found", skipped=skipped + ["Для создания нужна положительная цена robort.ru"])
                continue
            product = None
        else:
            product = matches[0]
            columns, attrs = additions(product, columns, attrs)
        for key in list(attrs):
            expected = next(v for v in MAPPING.values() if v[0] == key)
            definition = definitions.get(key)
            if definition is None or (definition.datatype, definition.unit) != expected[1:3]:
                skipped.append(f"{key}: отсутствует или несовместим attribute_def")
                del attrs[key]
        if creating:
            url = row.get("url")
            if "price_rub" not in attrs or not isinstance(url, str) or urlparse(url).hostname not in {"robort.ru", "www.robort.ru"}:
                entry.update(status="not_found", skipped=skipped + ["Для создания нужны цена с attribute_def и URL robort.ru"])
                continue
            code = robort_solution_code(row)
            solution = db.scalar(select(SolutionType).where(SolutionType.code == code))
            if solution is None:
                raise ValueError(f"В справочнике отсутствует тип решения {code}")
            product_id = uuid5(NAMESPACE_URL, url.rstrip("/"))
            slug = "robort-" + product_id.hex
            # Не создаём дубль архивной записи или уже импортированного URL с новым именем.
            existing = db.scalar(select(Product).where(Product.slug == slug))
            if existing is not None:
                if existing.valid_to is not None:
                    entry.update(status="archived", skipped=["Этот URL уже принадлежит архивной записи"])
                    continue
                product = existing
                creating = False
                columns, attrs = additions(product, columns, attrs)
            else:
                if version is None:
                    version = CatalogVersion(published_by="scripts.import_robots", note="Новые роботы из robort.ru")
                    db.add(version)
                    db.flush()
                product = Product(
                    id=product_id, slug=slug, name=row["name"], solution_type_id=solution.id,
                    manufacturer="Не указан", availability="operation", valid_from=version.id,
                    attrs={}, summary="Импорт robort.ru; тип определён по карточке, производитель не указан.",
                )
                db.add(product)
        entry["product_id"] = str(product.id)
        entry["matched_name"] = product.name
        if attrs:
            url = row.get("url")
            if not isinstance(url, str) or not url.startswith(("https://", "http://")):
                skipped.append("attrs: нет URL источника")
                attrs = {}
            else:
                source = db.scalar(select(Source).where(Source.kind == "catalog", Source.url == url).order_by(Source.id).limit(1))
                if source is None:
                    source = Source(kind="catalog", url=url, publisher="robort.ru" if is_robort(row) else "robob2b.ru",
                                    title=row["name"], captured_at=date.today())
                    db.add(source)
                    db.flush()
                for value in attrs.values():
                    value["source_id"] = source.id
        for key, value in columns.items():
            setattr(product, key, value)
        if attrs:
            product.attrs = {**(product.attrs or {}), **attrs}
        entry.update(status="created" if creating else "updated" if columns or attrs else "unchanged",
                     columns=list(columns), attrs=list(attrs), skipped=skipped)
    if dry_run:
        db.rollback()
    else:
        db.commit()
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="рассчитать изменения и откатить транзакцию")
    parser.add_argument("--report", type=Path, help="сохранить подробный JSON-отчёт")
    args = parser.parse_args()
    rows = load_rows(args.file)
    from api.db.session import get_sessionmaker

    with get_sessionmaker()() as db:
        report = import_rows(db, rows, dry_run=args.dry_run)
    output = json.dumps({"dry_run": args.dry_run, "rows": report}, ensure_ascii=False, indent=2)
    if args.report:
        args.report.write_text(output + "\n", encoding="utf-8")
    updated_ids = set()
    created_ids = set()
    for entry in report:
        if entry["status"] not in {"updated", "created"}:
            continue
        (created_ids if entry["status"] == "created" else updated_ids).add(entry["product_id"])
        action = "Будет обновлён" if args.dry_run else "Обновлён"
        if entry["status"] == "created":
            action = "Будет создан" if args.dry_run else "Создан"
        fields = entry["columns"] + [f"attrs.{key}" for key in entry["attrs"]]
        print(f"{action}: {entry['name']} — {', '.join(fields)}")
    if args.dry_run:
        print(f"Будет обновлено роботов: {len(updated_ids)} (dry-run, изменения не сохранены)")
    else:
        print(f"Успешно обновлено роботов: {len(updated_ids)}")
    print(f"{'Будет создано' if args.dry_run else 'Создано'} роботов: {len(created_ids)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
