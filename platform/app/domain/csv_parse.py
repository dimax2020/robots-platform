"""Разбор текста каталога и ручной таблицы. Без базы."""

from __future__ import annotations

import csv
import io
import re
import unicodedata
from collections import defaultdict
from uuid import UUID

from app.domain.match import OverlayRow, ParsedRecord

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def slugify(name: str, taken: set[str]) -> str:
    folded = unicodedata.normalize("NFKC", name).casefold()
    chars = []
    for ch in folded:
        if ch in _TRANSLIT:
            chars.append(_TRANSLIT[ch])
        elif ch.isascii() and ch.isalnum():
            chars.append(ch)
        else:
            chars.append("-")
    base = re.sub(r"-+", "-", "".join(chars)).strip("-") or "robot"
    base = base[:72]
    slug = base
    n = 2
    while slug in taken:
        slug = f"{base}-{n}"
        n += 1
    taken.add(slug)
    return slug


def attr_key(label: str) -> str:
    key = slugify(label, set()).replace("-", "_")
    return key[:80] or "attr"


def parse_price(raw: str | None) -> float | None:
    if raw is None:
        return None
    text = raw.strip()
    if not text or text.casefold() in {"по запросу", "-", "—"}:
        return None
    digits = re.sub(r"[^\d,.-]", "", text).replace(",", ".")
    if digits.count(".") > 1:
        digits = digits.replace(".", "", digits.count(".") - 1)
    try:
        value = float(digits)
    except ValueError:
        return None
    return value if value > 0 else None


def parse_catalog_csv(text: str) -> list[ParsedRecord]:
    rows = list(csv.DictReader(io.StringIO(text), delimiter=";"))
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    order: list[str] = []
    for row in rows:
        pid = (row.get("id") or "").strip()
        if not pid:
            continue
        if pid not in grouped:
            order.append(pid)
        grouped[pid].append(row)
    records: list[ParsedRecord] = []
    for pid in order:
        group = grouped[pid]
        head = group[0]
        name = (head.get("Название") or "").strip()
        if not name:
            continue
        try:
            UUID(pid)
        except ValueError:
            continue
        scenarios = []
        cases = []
        industries = []
        for row in group:
            scenario = (row.get("Сценарий") or "").strip()
            if scenario and scenario not in scenarios:
                scenarios.append(scenario)
            case = (row.get("Кейсы") or "").strip()
            if case and case not in cases:
                cases.append(case)
            industry = (row.get("Отрасль") or "").strip()
            if industry and industry not in industries:
                industries.append(industry)
        attributes = {
            "region": (head.get("Регион") or "").strip(),
            "system_class": (head.get("тип") or "").strip(),
            "robot_class": (head.get("Тип") or "").strip(),
            "subtype": (head.get("Подтип") or "").strip(),
            "scenario": "; ".join(scenarios),
            "industry_name": "; ".join(industries),
            "case_summary": "\n".join(cases),
            "market_potential": (head.get("Рын Потенциал") or "").strip(),
        }
        attributes = {key: value for key, value in attributes.items() if value}
        trl_raw = (head.get("УГТ") or "").strip()
        try:
            trl = int(float(trl_raw.replace(",", "."))) if trl_raw else None
        except ValueError:
            trl = None
        records.append(
            ParsedRecord(
                platform="fc_bas",
                external_id=pid,
                source_kind="catalog",
                source_publisher="ФЦ БАС",
                source_url=None,
                parser_code=None,
                name=name,
                manufacturer=(head.get("компания") or "").strip() or None,
                price_rub=parse_price(head.get("Цена изделия")),
                availability=(head.get("статус") or "").strip() or None,
                trl=trl,
                summary=(head.get("описание") or "").strip() or None,
                attributes=attributes,
                attribute_labels={
                    "region": "Регион",
                    "system_class": "Класс системы",
                    "robot_class": "Тип",
                    "subtype": "Подтип",
                    "scenario": "Сценарий",
                    "industry_name": "Отрасль",
                    "case_summary": "Кейсы",
                    "market_potential": "Рыночный потенциал",
                },
                raw={"rows": group},
            )
        )
    return records


def parse_manual_csv(text: str) -> list[OverlayRow]:
    rows = csv.DictReader(io.StringIO(text))
    out: list[OverlayRow] = []
    for row in rows:
        slug = (row.get("product_slug") or "").strip()
        key = (row.get("attr_key") or "").strip()
        if not slug or not key:
            continue
        out.append(
            OverlayRow(
                product_slug=slug,
                attr_key=key,
                label=key,
                value=(row.get("value") or "").strip(),
                status=(row.get("status") or "known").strip() or "known",
                source_kind=(row.get("source_kind") or "dealer").strip() or "dealer",
                source_url=(row.get("source_url") or "").strip() or None,
                quote=(row.get("quote") or "").strip() or None,
            )
        )
    return out
