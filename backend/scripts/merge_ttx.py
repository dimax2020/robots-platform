"""Сборка частей ручного поиска ТТХ в единую таблицу data/ttx_manual.csv.

Части data/manual_dump/part_*.csv — входные данные, а не генерируемый артефакт:
свободный текст вроде «грузоподъёмность до 1500 кг; габариты 1044×654×380 мм»
разбирался по файлам вручную и заново скриптом не воспроизводится.

Части разбирались независимо, поэтому здесь единственное место, где проверяется
согласованность: ключи против справочника, типы значений, дубликаты характеристики
у одного продукта. Импорт читает уже только результат.
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
DUMP = ROOT / "data" / "manual_dump"
OUT = ROOT / "data" / "ttx_manual.csv"

COLUMNS = [
    "product_slug",
    "product_name",
    "attr_key",
    "value",
    "status",
    "source_kind",
    "source_url",
    "quote",
]
SOURCE_KINDS = {"vendor", "dealer", "media", "catalog", "analogue", "assumption"}
# Продукт может встретиться в двух частях (в исходных таблицах он попал в две категории).
# Побеждает запись с более надёжным источником, при равенстве — с более подробной цитатой.
KIND_RANK = {"vendor": 5, "catalog": 4, "dealer": 3, "media": 2, "analogue": 1, "assumption": 0}
STATUSES = {"known", "not_applicable"}
# Пустые по смыслу значения: разборщики должны были их отбросить, но проверяем и здесь
BLANK = {
    "",
    "-",
    "—",
    "нет данных",
    "не определено",
    "по запросу",
    "не опубликована",
    "уточнить",
    "н/д",
}


def load_schema() -> dict[str, dict]:
    raw = json.loads((ROOT / "data" / "attributes.json").read_text(encoding="utf-8"))
    return {a["key"]: a for a in raw["attributes"]}


def load_products() -> dict[str, str]:
    rows = (DUMP / "_products.tsv").read_text(encoding="utf-8").splitlines()
    out = {}
    for line in rows[1:]:
        slug, name, *_ = line.split("\t")
        out[slug] = name
    return out


def main() -> int:
    schema = load_schema()
    products = load_products()
    parts = sorted(DUMP.glob("part_*.csv"))
    if not parts:
        print("части part_*.csv не найдены", file=sys.stderr)
        return 1

    best: dict[tuple[str, str], tuple[tuple[int, int, int], str, dict[str, str]]] = {}
    errors: list[str] = []
    resolved: list[str] = []

    for part in parts:
        with part.open(encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            if reader.fieldnames != COLUMNS:
                errors.append(f"{part.name}: заголовок {reader.fieldnames}, ожидался {COLUMNS}")
                continue
            for n, row in enumerate(reader, start=2):
                where = f"{part.name}:{n}"
                key = (row["attr_key"] or "").strip()
                slug = (row["product_slug"] or "").strip()
                value = (row["value"] or "").strip()
                status = (row["status"] or "").strip() or "known"
                kind = (row["source_kind"] or "").strip()

                if key not in schema:
                    errors.append(f"{where}: неизвестный ключ «{key}»")
                    continue
                if slug and slug not in products:
                    errors.append(f"{where}: slug «{slug}» отсутствует в платформе")
                    continue
                if not slug:
                    errors.append(f"{where}: продукт «{row['product_name']}» не сопоставлен")
                    continue
                if status not in STATUSES:
                    errors.append(f"{where}: статус «{status}»")
                    continue
                if kind not in SOURCE_KINDS:
                    errors.append(f"{where}: тип источника «{kind}»")
                    continue

                if status == "known":
                    if value.lower() in BLANK:
                        errors.append(f"{where}: пустое значение у {slug}.{key}")
                        continue
                    datatype = schema[key]["datatype"]
                    if datatype == "number":
                        try:
                            float(value)
                        except ValueError:
                            errors.append(f"{where}: {slug}.{key} не число: «{value}»")
                            continue
                    elif datatype == "bool" and value not in {"true", "false"}:
                        errors.append(f"{where}: {slug}.{key} не bool: «{value}»")
                        continue
                    elif datatype == "enum" and value not in schema[key].get("enum_values", []):
                        errors.append(f"{where}: {slug}.{key} вне enum: «{value}»")
                        continue
                elif value:
                    errors.append(f"{where}: у not_applicable должно быть пустое значение")
                    continue

                clean = {c: (row[c] or "").strip() for c in COLUMNS}
                rank = (1 if clean["source_url"] else 0, KIND_RANK[kind], len(clean["quote"]))
                prev = best.get((slug, key))
                if prev is None:
                    best[(slug, key)] = (rank, where, clean)
                elif rank > prev[0]:
                    best[(slug, key)] = (rank, where, clean)
                    resolved.append(f"{slug}.{key}: взят {where} вместо {prev[1]}")
                else:
                    resolved.append(f"{slug}.{key}: оставлен {prev[1]}, отброшен {where}")

    if errors:
        print(f"ошибок: {len(errors)}", file=sys.stderr)
        for e in errors:
            print("  ", e, file=sys.stderr)
        return 1

    rows = [clean for _, _, clean in best.values()]
    rows.sort(key=lambda r: (r["product_slug"], r["attr_key"]))
    with OUT.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    per_product = Counter(r["product_slug"] for r in rows)
    by_kind = Counter(r["source_kind"] for r in rows)
    by_group: Counter[str] = Counter()
    for r in rows:
        by_group[schema[r["attr_key"]]["group_code"]] += 1

    print(f"собрано частей: {len(parts)} → {OUT.relative_to(ROOT)}")
    if resolved:
        print(f"конфликтов между частями: {len(resolved)}")
        for r in resolved:
            print("  ", r)
    print(f"продуктов: {len(per_product)}, характеристик: {len(rows)}")
    print(f"в среднем на продукт: {len(rows) / len(per_product):.1f}")
    print("по группам:", ", ".join(f"{k} {v}" for k, v in by_group.most_common()))
    print("по достоверности источника:", ", ".join(f"{k} {v}" for k, v in by_kind.most_common()))
    thin = [s for s, c in per_product.items() if c < 3]
    if thin:
        print(f"продуктов с менее чем 3 характеристиками: {len(thin)} — {', '.join(sorted(thin))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
