"""Обход разделов robort.ru. В базу не пишет."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app.domain.csv_parse import attr_key, parse_price
from app.domain.match import ParsedRecord

BASE_URL = "https://robort.ru"
URLS = [
    "https://robort.ru/product/servisnye-roboty/",
    "https://robort.ru/product/roboty-manipulyatory/",
    "https://robort.ru/product/roboty-uborshchiky/",
    "https://robort.ru/product/logisticheskie-i-skladskie-roboty/",
    "https://robort.ru/product/kolesnye-i-gusenichnie-roboty/",
]
CODE = "robort"
WORKERS = 4


def collect() -> list[ParsedRecord]:
    cards = _cards()
    records: list[ParsedRecord] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for record in pool.map(_record, cards):
            if record is not None:
                records.append(record)
    return records


def _cards() -> list[dict]:
    seen: set[str] = set()
    found: list[dict] = []
    for category in URLS:
        page = 1
        while True:
            response = requests.get(category, params={"PAGEN_1": page}, timeout=30)
            if response.status_code == 404:
                break
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            catalog = soup.select_one(".catalog-list")
            if catalog is None:
                break
            added = 0
            for card in catalog.select(".catalog-list__wrapper"):
                item = _card(card)
                if item is None or item["url"] in seen:
                    continue
                seen.add(item["url"])
                added += 1
                found.append(item)
            if added == 0:
                break
            page += 1
    return found


def _card(card) -> dict | None:
    name = None
    url = None
    for link in card.select("a[href]"):
        href = link.get("href") or ""
        if "/product/" not in href:
            continue
        url = url or urljoin(BASE_URL, href)
        text = link.get_text(" ", strip=True)
        if text and name is None:
            name = text
    if not name or not url:
        return None
    kind = card.select_one(".catalog-list__info-section")
    return {
        "name": name,
        "url": url,
        "type": kind.get_text(" ", strip=True) if kind else None,
        "price": _price(card.get_text(" ", strip=True)),
        "specs": _card_specs(card),
    }


def _price(text: str) -> int | None:
    if "по запросу" in text.casefold():
        return None
    match = re.search(r"(?:от\s*)?(\d[\d\s\u00a0\u202f]*?)\s*(?:₽|[Рр]|руб\.?)", text, flags=re.IGNORECASE)
    if not match:
        return None
    digits = re.sub(r"\D", "", match.group(1))
    return int(digits) if digits else None


def _card_specs(card) -> dict[str, str]:
    parts = [part.strip() for part in card.get_text(" | ", strip=True).split("|") if part.strip()]
    specs = {}
    for index in range(len(parts) - 2):
        if parts[index + 1] == "—":
            specs[parts[index]] = parts[index + 2]
    return specs


def _record(card: dict) -> ParsedRecord | None:
    specs = dict(card["specs"])
    image = None
    try:
        extra, image = _full(card["url"], specs)
        specs.update(extra)
    except requests.RequestException:
        image = None
    attributes = {attr_key(key): value for key, value in specs.items() if value}
    if card.get("type"):
        attributes["robot_kind"] = card["type"]
    price = card.get("price")
    return ParsedRecord(
        platform=CODE,
        external_id=card["url"],
        source_kind="parser",
        source_publisher="robort.ru",
        source_url=card["url"],
        parser_code=CODE,
        name=card["name"],
        price_rub=float(price) if price else parse_price(str(price) if price else None),
        image_url=image,
        attributes=attributes,
        attribute_labels={attr_key(key): key for key in specs},
        raw={"url": card["url"]},
    )


def _full(url: str, base: dict[str, str]) -> tuple[dict[str, str], str | None]:
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    image = soup.select_one("#big-photo-0 > a:nth-child(1) > img:nth-child(1)")
    image_url = None
    if image is not None:
        src = image.get("data-src") or image.get("src")
        if src:
            image_url = urljoin(BASE_URL, src)
    best: dict[str, str] = {}
    best_score = -1
    base_keys = set(base)
    for table in soup.select("table"):
        specs = {}
        for row in table.select("tr"):
            cells = row.find_all(["td", "th"], recursive=False)
            if len(cells) != 2:
                continue
            key = cells[0].get_text(" ", strip=True)
            value = cells[1].get_text(" ", strip=True)
            if key and value and key != value:
                specs[key] = value
        if not specs:
            continue
        score = len(base_keys.intersection(specs)) * 1000 + len(specs)
        if score > best_score:
            best_score = score
            best = specs
    return best, image_url
