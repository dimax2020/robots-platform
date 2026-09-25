"""Каталог robot.moscow из HTML. В базу попадают только карточки с ценой.
Характеристики берутся со страницы робота: в общем списке каталога их нет.
"""

from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup

from app.domain.csv_parse import attr_key
from app.domain.match import ParsedRecord

CATALOG_URL = "https://robot.moscow/catalog"
CODE = "robot_moscow"
WORKERS = 4


def collect() -> list[ParsedRecord]:
    response = requests.get(CATALOG_URL, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    records = records_from_html(response.text)
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        list(pool.map(_attach_page_specs, records))
    return records


def records_from_html(html: str) -> list[ParsedRecord]:
    records = []
    for row in rows_from_html(html):
        price = row.get("priceValue")
        if price is None:
            continue
        image = row.get("image") or ""
        if image.startswith("/"):
            image = "https://robot.moscow" + image
        industries = ", ".join(row.get("industries") or [])
        slug = row.get("slug") or row["id"]
        attributes = {
            "country": row.get("country") or "",
            "robot_class": row.get("categoryName") or "",
            "industry_name": industries,
        }
        attributes = {key: value for key, value in attributes.items() if value}
        records.append(
            ParsedRecord(
                platform=CODE,
                external_id=str(row["id"]),
                source_kind="parser",
                source_publisher="robot.moscow",
                source_url=f"https://robot.moscow/robots/{slug}",
                parser_code=CODE,
                name=row["name"],
                manufacturer=row.get("maker") or None,
                price_rub=float(price),
                image_url=image or None,
                summary=row.get("description") or None,
                attributes=attributes,
                attribute_labels={
                    "country": "Страна",
                    "robot_class": "Категория",
                    "industry_name": "Отрасли",
                },
                raw={"slug": slug, "category": row.get("categorySlug")},
            )
        )
    return records


def specs_from_html(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    grid = soup.select_one(".rd-specgrid")
    if grid is None:
        return {}
    specs: dict[str, str] = {}
    for cell in grid.find_all(recursive=False):
        texts = [part.strip() for part in cell.stripped_strings if part.strip()]
        if len(texts) < 2:
            continue
        label, value = texts[0], texts[1]
        if label and value:
            specs[label] = value
    return specs


def _attach_page_specs(record: ParsedRecord) -> None:
    if not record.source_url:
        return
    try:
        response = requests.get(record.source_url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        if response.status_code == 404:
            return
        response.raise_for_status()
    except requests.RequestException:
        return
    for label, value in specs_from_html(response.text).items():
        key = attr_key(label)
        record.attributes[key] = value
        record.attribute_labels[key] = label


def rows_from_html(html: str) -> list[dict]:
    text = html.replace('\\"', '"')
    pattern = re.compile(
        r'\{"id":"[^"]+","name":".*?"priceValue":(?:null|\d+(?:\.\d+)?),'
        r'"offersCount":\d+,"featured":(?:true|false),"isNew":(?:true|false)\}'
    )
    rows = []
    for match in pattern.finditer(text):
        try:
            rows.append(json.loads(match.group(0)))
        except json.JSONDecodeError:
            continue
    return rows
