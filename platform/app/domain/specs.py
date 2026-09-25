"""Известные подписи характеристик парсеров → поля, которые читает подбор."""

from __future__ import annotations

import re

CANON_LABELS = {
    "payload_kg": "Грузоподъёмность",
    "speed_loaded_ms": "Скорость с грузом",
    "dimensions_mm": "Габариты",
    "min_aisle_width_m": "Минимальная ширина прохода",
    "work_time_h": "Время работы",
    "charge_time_h": "Время зарядки",
    "mass_kg": "Масса",
    "lift_height_mm": "Высота подъёма",
}


def expand_known_specs(attributes: dict[str, str], labels: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    extra: dict[str, str] = {}
    extra_labels: dict[str, str] = {}
    for key, value in attributes.items():
        canon = _canon_key(labels.get(key) or key)
        if canon is None or canon in attributes or canon in extra:
            continue
        parsed = _parse(canon, value)
        if parsed is None:
            continue
        extra[canon] = parsed
        extra_labels[canon] = CANON_LABELS[canon]
    if not extra:
        return attributes, labels
    merged = dict(attributes)
    merged.update(extra)
    merged_labels = dict(labels)
    merged_labels.update(extra_labels)
    return merged, merged_labels


def _canon_key(label: str) -> str | None:
    text = label.casefold().replace("ё", "е")
    if text.startswith("грузоподъемность"):
        return "payload_kg"
    if "ширина проезда" in text or text.startswith("минимальная ширина прохода"):
        return "min_aisle_width_m"
    if text.startswith("максимальная скорость") or text == "скорость":
        return "speed_loaded_ms"
    if text in {"размеры", "габариты", "габариты, д×ш×в"} or text.startswith("габариты"):
        return "dimensions_mm"
    if text.startswith("время работы"):
        return "work_time_h"
    if text.startswith("время зарядки"):
        return "charge_time_h"
    if text in {"вес", "масса"} or text.startswith("вес "):
        return "mass_kg"
    if "высота подъема" in text or "высота подьема" in text:
        return "lift_height_mm"
    return None


def _parse(canon: str, value: str) -> str | None:
    if canon == "dimensions_mm":
        return value.strip() or None
    number = _number(value)
    if number is None:
        return None
    unit = value.casefold().replace("ё", "е")
    if canon == "min_aisle_width_m" and "см" in unit:
        number = number / 100
    if canon == "min_aisle_width_m" and "мм" in unit:
        number = number / 1000
    if canon == "lift_height_mm" and re.search(r"\d\s*м(?!м)", unit):
        number = number * 1000
    if canon == "payload_kg" and not re.search(r"(кг|kg|\d\s*т\b)", unit):
        return None
    if canon == "mass_kg" and not re.search(r"(кг|kg|\d\s*т\b)", unit):
        return None
    if canon in {"payload_kg", "mass_kg"} and re.search(r"\d\s*т\b", unit):
        number = number * 1000
    if canon in {"payload_kg", "mass_kg", "lift_height_mm"}:
        return str(int(number)) if number.is_integer() else str(number)
    return str(number)


def _number(value: str) -> float | None:
    match = re.search(r"\d+(?:[.,]\d+)?", value.replace(" ", "").replace("\u00a0", ""))
    if match is None:
        return None
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return None
