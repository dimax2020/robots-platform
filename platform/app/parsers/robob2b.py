"""Обход robob2b.ru. В базу не пишет: возвращает карточки реестру."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
from uuid import uuid5, NAMESPACE_URL

import requests
from bs4 import BeautifulSoup

from app.domain.csv_parse import attr_key
from app.domain.match import ParsedRecord

BASE_URL = "https://robob2b.ru"
CATALOG_URL = f"{BASE_URL}/catalog/"
CODE = "robob2b"
WORKERS = 4


def collect() -> list[ParsedRecord]:
    cards = list(_cards())
    records: list[ParsedRecord] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for record in pool.map(_record, cards):
            if record is not None:
                records.append(record)
    return records


def _cards() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    seen: set[str] = set()
    page = 1
    while True:
        response = requests.get(CATALOG_URL, params={"PAGEN_1": page, "SIZEN_1": 30}, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        listing = soup.select_one(".prod-all__list")
        if listing is None:
            break
        added = 0
        for card in listing.find_all(recursive=False):
            link = card.select_one(".prod-all__name a")
            slogan = card.select_one(".item-slogan")
            if link is None or slogan is None:
                continue
            url = urljoin(BASE_URL, link.get("href") or "")
            if url in seen:
                continue
            seen.add(url)
            added += 1
            found.append((slogan.get_text(" ", strip=True), url))
        if added == 0:
            break
        page += 1
    return found


def _record(item: tuple[str, str]) -> ParsedRecord | None:
    name, url = item
    if not name:
        return None
    specs, image = _page(url)
    attributes = {attr_key(key): value for key, value in specs.items() if value}
    return ParsedRecord(
        platform=CODE,
        external_id=str(uuid5(NAMESPACE_URL, url)),
        source_kind="parser",
        source_publisher="robob2b.ru",
        source_url=url,
        parser_code=CODE,
        name=name,
        image_url=image,
        attributes=attributes,
        attribute_labels={attr_key(key): key for key in specs},
        raw={"url": url},
    )


def _page(url: str) -> tuple[dict[str, str], str | None]:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    image = soup.select_one(".product-item-detail-slider-image.active img")
    image_url = urljoin(BASE_URL, image.get("src")) if image is not None and image.get("src") else None
    specs: dict[str, str] = {}
    properties = soup.select_one("#properties")
    if properties is None:
        return specs, image_url
    for row in properties.select("tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 2:
            continue
        key = cells[0].get_text(" ", strip=True)
        value = cells[1].get_text(" ", strip=True)
        if key and value:
            specs[key] = value
    return specs, image_url
