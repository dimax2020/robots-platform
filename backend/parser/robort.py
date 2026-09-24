import json
import os
from pathlib import Path
import re
import time
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin


BASE_URL = "https://robort.ru"

URLS = [
    "https://robort.ru/product/servisnye-roboty/",
    "https://robort.ru/product/roboty-manipulyatory/",
    "https://robort.ru/product/roboty-uborshchiky/",
    "https://robort.ru/product/logisticheskie-i-skladskie-roboty/",
    "https://robort.ru/product/kolesnye-i-gusenichnie-roboty/",
]
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "robort_robots.json")

REQUEST_DELAY = 1
def main():
    robots = []
    processed_urls = set()

    try:
        for category_url in URLS:
            print()
            print("=" * 80)
            print(f"КАТЕГОРИЯ: {category_url}")
            print("=" * 80)

            for card in get_robot_cards(category_url):
                robot = parse_card(card)

                if not robot:
                    continue

                # Один робот может встретиться
                # сразу в нескольких категориях
                if robot["url"] in processed_urls:
                    print(f"Skip duplicate: {robot['name']}")
                    continue

                processed_urls.add(robot["url"])

                try:
                    full_specs, png_url = parse_full_specs(
                        robot["url"],
                        robot["specs"],
                    )

                    robot["specs"].update(full_specs)
                    robot["png_url"] = png_url

                except requests.RequestException as exc:
                    print(
                        f"Ошибка карточки {robot['name']}: {exc}"
                    )

                    robot["png_url"] = None

                robots.append(robot)

                print(
                    f"Parsed: {robot['name']} "
                    f"| всего: {len(robots)}"
                )

                # checkpoint после каждого робота
                save_json(robots)

                time.sleep(REQUEST_DELAY)

    except Exception as exc:
        print(f"Критическая ошибка: {exc}")
        raise

    finally:
        save_json(robots)

        print()
        print("=" * 80)
        print(f"ВСЕГО СОХРАНЕНО РОБОТОВ: {len(robots)}")
        print(f"Файл: {OUTPUT_FILE}")
        print("=" * 80)
def get_robot_cards(category_url):
    page = 1
    seen_urls = set()

    while True:
        print(f"\nПарсим страницу №{page}")

        response = requests.get(
            category_url,
            params={
                "PAGEN_1": page,
            },
            timeout=30,
        )

        # Страниц больше нет — нормальное завершение категории
        if response.status_code == 404:
            print(
                f"Страницы №{page} нет. "
                f"Категория закончилась."
            )
            break

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        catalog = soup.select_one(".catalog-list")

        if not catalog:
            print("Каталог не найден. Переходим к следующей категории.")
            break

        cards = catalog.select(
            ".catalog-list__wrapper"
        )

        if not cards:
            print("Карточек нет. Переходим к следующей категории.")
            break

        new_cards = 0

        for card in cards:
            link = card.select_one(
                "a[href*='/product/']"
            )

            if not link:
                continue

            product_url = urljoin(
                BASE_URL,
                link.get("href"),
            )

            if product_url in seen_urls:
                continue

            seen_urls.add(product_url)
            new_cards += 1

            yield card

        print(
            f"Новых товаров на странице: {new_cards}"
        )

        if new_cards == 0:
            print("Новых товаров нет.")
            break

        page += 1

def save_json(robots):
    Path(OUTPUT_FILE).parent.mkdir(parents=True, exist_ok=True)
    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            robots,
            file,
            ensure_ascii=False,
            indent=4,
        )

def parse_card(card):
    name = None
    product_url = None

    #
    # Название + URL
    #
    for link in card.select("a[href]"):
        href = link.get("href")
        text = link.get_text(
            " ",
            strip=True,
        )

        if not href:
            continue

        if "/product/" not in href:
            continue

        if product_url is None:
            product_url = urljoin(
                BASE_URL,
                href,
            )

        if text and name is None:
            name = text

    if not name or not product_url:
        return None

    #
    # Тип робота
    #
    robot_type_tag = card.select_one(
        ".catalog-list__info-section"
    )

    robot_type = (
        robot_type_tag.get_text(
            " ",
            strip=True,
        )
        if robot_type_tag
        else None
    )

    return {
        "name": name,
        "url": product_url,
        "type": robot_type,
        "price": parse_price(card),
        "specs": parse_card_specs(card),
    }

def parse_price(card):
    text = card.get_text(
        " ",
        strip=True,
    )

    if "по запросу" in text.casefold():
        return None

    match = re.search(
        r"(?:от\s*)?"
        r"(\d[\d\s\u00a0\u202f]*?)"
        r"\s*(?:₽|[Рр]|руб\.?)",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    price = re.sub(
        r"\D",
        "",
        match.group(1),
    )

    if not price:
        return None

    return int(price)


def parse_card_specs(card):
    """
    Базовые характеристики из карточки каталога:

        Размеры | — | 55 х 61 х 69 см
        Максимальная скорость | — | 0.8 м/c
    """

    text = card.get_text(
        " | ",
        strip=True,
    )

    parts = [
        part.strip()
        for part in text.split("|")
        if part.strip()
    ]

    specs = {}

    for index in range(len(parts) - 2):
        key = parts[index]
        separator = parts[index + 1]
        value = parts[index + 2]

        if separator != "—":
            continue

        specs[key] = value

    return specs

def parse_full_specs(product_url, base_specs):
    response = requests.get(
        product_url,
        timeout=30,
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser",
    )

    #
    # Картинка
    #
    png_url = None

    image = soup.select_one(
        "#big-photo-0 > a:nth-child(1) > img:nth-child(1)"
    )

    if image:
        src = (
            image.get("data-src")
            or image.get("src")
        )

        if src:
            png_url = urljoin(
                BASE_URL,
                src,
            )

    #
    # Характеристики
    #
    base_keys = set(base_specs.keys())

    best_specs = {}
    best_score = -1

    for table in soup.select("table"):
        table_specs = parse_specs_table(table)

        if not table_specs:
            continue

        overlap = len(
            base_keys.intersection(
                table_specs.keys()
            )
        )

        score = (
            overlap * 1000
            + len(table_specs)
        )

        if score > best_score:
            best_score = score
            best_specs = table_specs

    if not best_specs:
        print(
            f"WARNING: характеристики не найдены: "
            f"{product_url}"
        )

    return best_specs, png_url


def parse_specs_table(table):
    specs = {}

    for row in table.select("tr"):
        cells = row.find_all(
            ["td", "th"],
            recursive=False,
        )

        if len(cells) != 2:
            continue

        key = cells[0].get_text(
            " ",
            strip=True,
        )

        value = cells[1].get_text(
            " ",
            strip=True,
        )

        if not key:
            continue

        if not value:
            continue

        #
        # На всякий случай пропускаем
        # бессмысленные строки.
        #
        if key == value:
            continue

        specs[key] = value

    return specs


if __name__ == "__main__":
    main()