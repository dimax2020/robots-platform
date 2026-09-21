"""catalog_export_v4.csv + data/mapping/*.json → data/catalog_normalized.json.

Шаг подготовки данных перед сидом. Запускается на машине разработчика, потому что исходный
файл организатора лежит в resources/ и в контейнер не монтируется:

    python -m scripts.normalize

Все правки исходных данных печатаются отчётом — молча не чинится ничего (§12.2).
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CSV_DEFAULT = ROOT / "resources" / "Датасет" / "catalog_export_v4.csv"
MAPPING_DIR = ROOT / "data" / "mapping"
OUT_DEFAULT = ROOT / "data" / "catalog_normalized.json"

CYRILLIC = re.compile(r"[а-яёА-ЯЁ]")
SCENARIO_SPLIT = re.compile(r",\s+(?=[А-ЯЁA-Z])")

TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}

SYSTEM_CLASS_LABEL = {
    "brs": "БРС, беспилотная робототехническая система",
    "bas": "БАС, беспилотная авиационная система",
    "software": "Программное обеспечение",
}


class Report:
    """Собирает дефекты исходных данных, чтобы они попали в вывод, а не потерялись."""

    def __init__(self) -> None:
        self.items: list[dict[str, Any]] = []

    def add(self, kind: str, message: str) -> None:
        self.items.append({"kind": kind, "message": message})

    def counts(self) -> dict[str, int]:
        return dict(Counter(it["kind"] for it in self.items))

    def print(self) -> None:
        by_kind: dict[str, list[str]] = defaultdict(list)
        for it in self.items:
            by_kind[it["kind"]].append(it["message"])
        print("\n── Отчёт по дефектам исходных данных ──")
        for kind, msgs in sorted(by_kind.items(), key=lambda kv: -len(kv[1])):
            print(f"\n[{kind}] {len(msgs)}")
            for m in sorted(set(msgs))[:10]:
                print(f"   · {m}")
            if len(set(msgs)) > 10:
                print(f"   … ещё {len(set(msgs)) - 10}")


# ---------------------------------------------------------------------------
# Нормализация строк
# ---------------------------------------------------------------------------


def canon(s: str | None) -> str:
    """Каноническая форма для сопоставления с маппингами: ё→е, нижний регистр, сжатые пробелы и дефисы."""
    s = (s or "").strip().replace("ё", "е").replace("Ё", "Е").lower()
    return re.sub(r"[\s\-–—]+", " ", s).strip()


def normalize_space(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def fix_homoglyphs(s: str, table: dict[str, str], report: Report) -> str:
    """Латинские буквы внутри русских слов: АО «НПO «Высoкoтoчные кoмплексы» набрано латинской O."""
    out = []
    for word in s.split(" "):
        if CYRILLIC.search(word):
            fixed = "".join(table.get(ch, ch) for ch in word)
            if fixed != word:
                report.add("латинские гомоглифы в русских словах", f"«{word}» → «{fixed}»")
            out.append(fixed)
        else:
            out.append(word)
    return " ".join(out)


def normalize_quotes(s: str) -> str:
    """Кавычки к единому виду «…»: в исходнике смешаны \" и «»."""
    parts = s.split('"')
    if len(parts) > 1:
        rebuilt = parts[0]
        for i, part in enumerate(parts[1:]):
            rebuilt += ("«" if i % 2 == 0 else "»") + part
        s = rebuilt
    return normalize_space(s)


def slugify(name: str, taken: set[str]) -> str:
    s = name.lower().replace("ё", "е")
    s = "".join(TRANSLIT.get(ch, ch) for ch in s)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")[:60].strip("-") or "product"
    base, n = s, 2
    while s in taken:
        s = f"{base}-{n}"
        n += 1
    taken.add(s)
    return s


def parse_price(raw: str, report: Report, product: str) -> float | None:
    """«2 700 000,00» → 2700000.0. Пробелы в исходнике в том числе неразрывные."""
    s = re.sub(r"[\s\u00a0\u202f]", "", (raw or "").strip()).replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        report.add("цена не разобрана", f"{product}: «{raw}»")
        return None


def parse_int(raw: str) -> int | None:
    s = (raw or "").strip()
    if not s:
        return None
    try:
        return int(round(float(s.replace(",", "."))))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Маппинги
# ---------------------------------------------------------------------------


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


class Mappings:
    def __init__(self, mapping_dir: Path) -> None:
        industries = load_json(mapping_dir / "industries.json")["industries"]
        object_types = load_json(mapping_dir / "object_types.json")["object_types"]
        process_object = load_json(mapping_dir / "process_object.json")
        solution_types = load_json(mapping_dir / "solution_types.json")
        vendors = load_json(mapping_dir / "vendors.json")

        self.industries = {canon(i["name"]): i for i in industries}
        self.object_types = {o["code"]: o for o in object_types}
        self.processes = {canon(p["name"]): p for p in process_object["processes"]}
        self.scenario_aliases = {k: v for k, v in process_object["aliases"].items() if not k.startswith("_")}
        self.scenario_splits = {k: v for k, v in process_object["split_extra"].items() if not k.startswith("_")}
        self.solution_pairs = {
            (canon(e["type"]), canon(e["subtype"])): e for e in solution_types["by_pair"]
        }
        self.solution_fallback = {
            k: v for k, v in solution_types["fallback"].items() if not k.startswith("_")
        }
        self.vendor_aliases = {k: v for k, v in vendors["aliases"].items() if not k.startswith("_")}
        self.homoglyphs = {k: v for k, v in vendors["homoglyphs"].items() if not k.startswith("_")}

    def split_scenarios(self, raw: str, report: Report) -> list[str]:
        """Одна ячейка «Сценарий» может содержать несколько сценариев через запятую (§12.2)."""
        s = normalize_space(raw)
        key = canon(s)
        if key in self.scenario_splits:
            parts = self.scenario_splits[key]
            report.add("несколько сценариев в одной ячейке", f"«{s}» → {len(parts)} шт.")
            return parts
        parts = [p.strip().rstrip(".") for p in SCENARIO_SPLIT.split(s) if p.strip()]
        if len(parts) > 1:
            report.add("несколько сценариев в одной ячейке", f"«{s[:70]}…» → {len(parts)} шт.")
        return parts

    def process(self, scenario: str, report: Report) -> dict[str, Any] | None:
        key = canon(scenario)
        if key in self.scenario_aliases:
            fixed = self.scenario_aliases[key]
            report.add("название сценария исправлено", f"«{scenario}» → «{fixed}»")
            key = canon(fixed)
        proc = self.processes.get(key)
        if proc is None:
            report.add("сценарий вне маппинга", f"«{scenario}»")
        return proc

    def solution_type(self, type_: str, subtype: str, system_class: str, report: Report) -> dict[str, Any]:
        key = (canon(type_), canon(subtype))
        if entry := self.solution_pairs.get(key):
            return entry
        fallback = self.solution_fallback.get(system_class) or self.solution_fallback["brs"]
        report.add(
            "тип решения не указан, взят резервный",
            f"тип «{type_ or '—'}» / подтип «{subtype or '—'}» / класс {system_class} → {fallback['code']}",
        )
        return fallback

    def vendor(self, company: str, report: Report) -> tuple[str, str]:
        """Возвращает (юрлицо, отображаемое имя производителя)."""
        cleaned = fix_homoglyphs(normalize_space(company), self.homoglyphs, report)
        cleaned = normalize_quotes(cleaned)
        key = canon(cleaned).replace("«", "").replace("»", "")
        if entry := self.vendor_aliases.get(key):
            return entry["legal_entity"], entry["manufacturer"]
        display = re.sub(
            r"^(ООО|АО|ЗАО|ПАО|АНО ВО|АНО|ГК|ФГАОУ ВО|ФГБОУ ВО|ФГОБУ ВО|НИУ|ООО НПП|АО ГК)\s+",
            "",
            cleaned,
        ).strip("«» ")
        return cleaned, display or cleaned


# ---------------------------------------------------------------------------
# Основной проход
# ---------------------------------------------------------------------------


def normalize(csv_path: Path, mapping_dir: Path) -> tuple[dict[str, Any], Report]:
    report = Report()
    maps = Mappings(mapping_dir)

    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter=";"))

    # Файл денормализован: одна строка на пару (отрасль × сценарий), 187 продуктов в 223 строках.
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    order: list[str] = []
    for row in rows:
        pid = row["id"].strip()
        if pid not in grouped:
            order.append(pid)
        grouped[pid].append(row)

    for pid, group in grouped.items():
        if len(group) > 1:
            report.add(
                "строки одного продукта склеены",
                f"{normalize_space(group[0]['Название'])[:50]} — {len(group)} строк",
            )

    used_processes: dict[str, dict[str, Any]] = {}
    used_solution_types: dict[str, dict[str, Any]] = {}
    used_industries: dict[str, dict[str, Any]] = {}
    industry_objects: set[tuple[str, str]] = set()
    object_processes: set[tuple[str, str]] = set()
    process_solutions: set[tuple[str, str]] = set()

    products: list[dict[str, Any]] = []
    slugs: set[str] = set()

    for pid in order:
        group = grouped[pid]
        head = group[0]
        name = normalize_space(head["Название"])

        legal_entity, manufacturer = maps.vendor(head["компания"], report)
        system_class = canon(head["тип"]) or "brs"
        solution = maps.solution_type(head["Тип"], head["Подтип"], system_class, report)
        used_solution_types[solution["code"]] = solution

        # Цена может расходиться между строками одного продукта — берём минимальную и фиксируем разброс.
        prices = {p for r in group if (p := parse_price(r["Цена изделия"], report, name)) is not None}
        price = min(prices) if prices else None
        price_note = None
        if len(prices) > 1:
            price_note = "в исходном файле у позиции указаны разные цены: " + ", ".join(
                f"{int(p):,}".replace(",", " ") + " ₽" for p in sorted(prices)
            )
            report.add("расхождение цены между строками", f"{name}: {sorted(prices)}")

        region_raw = head["Регион"]
        region = normalize_space(region_raw)
        if region != region_raw.strip() or region_raw != region_raw.strip():
            report.add("регион с лишними пробелами", f"«{region_raw}» → «{region}»")

        industry_codes: list[str] = []
        process_codes: list[str] = []
        cases: list[dict[str, str]] = []

        for row in group:
            industry = maps.industries.get(canon(row["Отрасль"]))
            if industry is None:
                report.add("отрасль вне маппинга", f"«{row['Отрасль']}»")
                continue
            used_industries[industry["code"]] = industry
            if industry["code"] not in industry_codes:
                industry_codes.append(industry["code"])

            row_processes: list[str] = []
            for scenario in maps.split_scenarios(row["Сценарий"], report):
                proc = maps.process(scenario, report)
                if proc is None:
                    continue
                used_processes[proc["code"]] = proc
                row_processes.append(proc["code"])
                if proc["code"] not in process_codes:
                    process_codes.append(proc["code"])
                process_solutions.add((proc["code"], solution["code"]))
                for obj in proc["objects"]:
                    object_processes.add((obj, proc["code"]))

            case_text = normalize_space(row["Кейсы"])
            if case_text and all(case_text != c["summary"] for c in cases):
                cases.append({"summary": case_text, "process_code": row_processes[0] if row_processes else None})

        if not head["описание"].strip():
            report.add("нет описания", name)

        trl = parse_int(head["УГТ"])
        market_potential = parse_int(head["Рын Потенциал"])
        if market_potential is None:
            report.add("нет рыночного потенциала", name)

        availability = canon(head["статус"])
        if availability not in ("operation", "piloting", "rnd"):
            report.add("неизвестный статус", f"{name}: «{head['статус']}»")
            availability = "rnd"

        products.append(
            {
                "id": pid,
                "slug": slugify(name, slugs),
                "name": name,
                "manufacturer": manufacturer,
                "legal_entity": legal_entity,
                "country": "Россия",
                "region": region,
                "availability": availability,
                "trl": trl,
                "market_potential": market_potential,
                "summary": normalize_space(head["описание"]) or None,
                "solution_type_code": solution["code"],
                "system_class": system_class,
                "price_rub": price,
                "price_note": price_note,
                "industry_codes": industry_codes,
                "process_codes": process_codes,
                "cases": cases,
                "source_rows": len(group),
            }
        )

    # Отрасль → тип объекта берётся из заявленного состава отрасли, а не из побочных сценариев:
    # иначе в дереве появляется «ТЭК → Склад» из-за одного сценария доставки грузов.
    objects_with_processes = {o for o, _ in object_processes}
    for industry in used_industries.values():
        declared = industry.get("objects", [])
        for obj in declared:
            if obj in objects_with_processes:
                industry_objects.add((industry["code"], obj))
            else:
                report.add(
                    "тип объекта заявлен у отрасли, но ни один процесс на него не вышел",
                    f"{industry['name']} → {obj}",
                )

    # Продукт должен быть достижим по цепочке отрасль → объект → процесс → тип решения (§6.1)
    reachable_solutions = {
        s
        for p, s in process_solutions
        if any(
            (o, p) in object_processes and any((i, o) in industry_objects for i in used_industries)
            for o in maps.object_types
        )
    }
    for product in products:
        if product["solution_type_code"] not in reachable_solutions:
            report.add("продукт недостижим в дереве каталога", product["name"])

    data = {
        "source_file": csv_path.name,
        "generated_at": date.today().isoformat(),
        "stats": {
            "csv_rows": len(rows),
            "products": len(products),
            "industries": len(used_industries),
            "processes": len(used_processes),
            "solution_types": len(used_solution_types),
            "object_types": len({o for o, _ in object_processes}),
            "cases": sum(len(p["cases"]) for p in products),
            "products_without_price": sum(1 for p in products if p["price_rub"] is None),
            "defects": report.counts(),
        },
        "industries": sorted(used_industries.values(), key=lambda i: i["name"]),
        "object_types": [
            maps.object_types[code] for code in sorted({o for o, _ in object_processes})
        ],
        "processes": [
            {"code": p["code"], "name": p["name"]}
            for p in sorted(used_processes.values(), key=lambda p: p["name"])
        ],
        "solution_types": sorted(
            (
                {"code": s["code"], "name": s["name"], "family": s["family"]}
                for s in used_solution_types.values()
            ),
            key=lambda s: s["name"],
        ),
        "industry_objects": [{"industry": i, "object_type": o} for i, o in sorted(industry_objects)],
        "object_processes": [{"object_type": o, "process": p} for o, p in sorted(object_processes)],
        "process_solutions": [{"process": p, "solution_type": s} for p, s in sorted(process_solutions)],
        "products": products,
        "defects": report.items,
    }
    return data, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Нормализация каталога организатора")
    parser.add_argument("--csv", type=Path, default=CSV_DEFAULT)
    parser.add_argument("--mapping", type=Path, default=MAPPING_DIR)
    parser.add_argument("--out", type=Path, default=OUT_DEFAULT)
    parser.add_argument("--quiet", action="store_true", help="не печатать отчёт по дефектам")
    args = parser.parse_args(argv)

    if not args.csv.exists():
        print(f"Не найден исходный файл: {args.csv}", file=sys.stderr)
        return 1

    data, report = normalize(args.csv, args.mapping)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    st = data["stats"]
    print(f"{args.csv.name}: {st['csv_rows']} строк → {st['products']} продуктов")
    print(
        f"справочники: {st['industries']} отраслей, {st['object_types']} типов объектов, "
        f"{st['processes']} процессов, {st['solution_types']} типов решений, {st['cases']} кейсов"
    )
    print(f"связи: {len(data['industry_objects'])} отрасль→объект, "
          f"{len(data['object_processes'])} объект→процесс, "
          f"{len(data['process_solutions'])} процесс→тип решения")
    if not args.quiet:
        report.print()
    print(f"\n→ {args.out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
