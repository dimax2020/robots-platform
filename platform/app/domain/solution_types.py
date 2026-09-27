"""Тип решения по колонкам «Тип» и «Подтип» каталога. Базы здесь нет."""

from __future__ import annotations

import re
from dataclasses import dataclass


def canon(text: object) -> str:
    """trim, ё→е, нижний регистр, сжатые пробелы и дефисы: «Робот-штабелёр» и «робот штабелер» совпадают."""
    value = str(text or "").strip().replace("ё", "е").replace("Ё", "Е").lower()
    return re.sub(r"[\s\-]+", " ", value).strip()


@dataclass(frozen=True)
class TypeSpec:
    code: str
    name: str
    group: str
    family: str


@dataclass(frozen=True)
class Mapping:
    types: tuple[TypeSpec, ...]
    pairs: dict[tuple[str, str], str]
    fallback: dict[str, str]


def read_mapping(raw: dict) -> Mapping:
    types: dict[str, TypeSpec] = {}
    pairs: dict[tuple[str, str], str] = {}
    for row in raw.get("by_pair") or []:
        code = row["code"]
        group = row.get("type") or ""
        if code not in types:
            types[code] = TypeSpec(code, row["name"], group or _group_of(row), row.get("family") or "")
        pairs[(canon(row.get("type")), canon(row.get("subtype")))] = code
    fallback: dict[str, str] = {}
    for system_class, row in (raw.get("fallback") or {}).items():
        if not isinstance(row, dict) or "code" not in row:
            continue
        fallback[system_class] = row["code"]
        if row["code"] not in types:
            types[row["code"]] = TypeSpec(row["code"], row["name"], "Тип не уточнён", row.get("family") or "")
    return Mapping(tuple(types.values()), pairs, fallback)


def _group_of(row: dict) -> str:
    subtype = canon(row.get("subtype"))
    if subtype in {"vtol", "мультиротор", "самолет"}:
        return "БАС"
    return ""


def raw_key(robot_class: object, subtype: object, robot_kind: object) -> str:
    """Ключ группы продуктов без типа: по нему админ назначает тип сразу всей категории."""
    return "|".join(canon(part) for part in (robot_class, subtype, robot_kind))


def classify(
    mapping: Mapping,
    rules: dict[str, str],
    *,
    robot_class: object,
    subtype: object,
    system_class: object,
    robot_kind: object = "",
) -> str | None:
    pair = (canon(robot_class), canon(subtype))
    if pair in mapping.pairs:
        return mapping.pairs[pair]
    rule = rules.get(raw_key(robot_class, subtype, robot_kind))
    if rule:
        return rule
    if not pair[0] and not pair[1]:
        return mapping.fallback.get(canon(system_class))
    return None
