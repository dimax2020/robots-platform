import json
import os
from pathlib import Path
import time
import uuid
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://robob2b.ru"
CATALOG_URL = f"{BASE_URL}/catalog/"

session = requests.Session()


def main():
    robots = []

    for robot_card in get_robots():
        try:
            data_robot = parse_robot(robot_card)

            if not data_robot:
                continue

            robots.append(data_robot)

            print(f"Parsed: {data_robot['name']}")

            #time.sleep(0.5)

        except Exception as exc:
            print(f"Request error: {exc}")

    output = Path(os.environ.get("OUTPUT_FILE", "robots.json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as file:
        json.dump(
            robots,
            file,
            ensure_ascii=False,
            indent=4
        )

    print(f"Всего сохранено роботов: {len(robots)}")


def get_robots():
    page = 1
    seen_robots = set()

    while True:
        print(f"Парсим страницу №{page}")

        # Новая сессия для каждой страницы
        with requests.Session() as session:
            response = session.get(
                CATALOG_URL,
                params={
                    "PAGEN_1": page,
                    "SIZEN_1": 30,
                },
                timeout=30,
            )

            response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        robot_list = soup.select_one(".prod-all__list")

        if not robot_list:
            break

        new_robots = 0

        for card in robot_list.find_all(recursive=False):
            name_tag = card.select_one(".prod-all__name a")

            if not name_tag:
                continue

            robot_url = urljoin(BASE_URL, name_tag.get("href"))

            if robot_url in seen_robots:
                continue

            seen_robots.add(robot_url)
            new_robots += 1

            yield card

        if new_robots == 0:
            break

        print(f"Новых роботов: {new_robots}")
        print(f"Всего найдено: {len(seen_robots)}")

        page += 1

def parse_robot(card):
    name_tag = card.select_one(".item-slogan")
    link_tag = card.select_one(".prod-all__name a")

    if not name_tag or not link_tag:
        return None

    name = name_tag.get_text(" ", strip=True)
    product_url = urljoin(BASE_URL, link_tag["href"])

    specs, png_url = parse_product_page(product_url, name)

    integrators = card.select_one(".integrator-count span")

    return {
        "id": str(uuid.uuid5(uuid.NAMESPACE_URL, product_url)),
        "name": name,
        "url": product_url,
        "png_url": png_url,
        "integrators": (
            integrators.get_text(strip=True)
            if integrators else None
        ),
        "specs": specs,
    }

def parse_product_page(product_url, robot_name):
    response = session.get(product_url, timeout=30)
    time.sleep(1)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Изображение робота. На части карточек слайдера нет — это не повод бросать весь обход.
    png_url = None
    image = soup.select_one(".product-item-detail-slider-image.active img")
    if image is not None and image.get("src"):
        png_url = urljoin(BASE_URL, image["src"])

    # Полные характеристики
    specs = {}

    properties = soup.select_one("#properties")

    if properties is None:
        print(f"WARNING: Не найдены характеристики: {product_url}")
        return specs, png_url

    for tbody in properties.select("tbody"):
        header = tbody.select_one("th")

        section_name = (
            header.get_text(" ", strip=True)
            if header else "Общие характеристики"
        )

        section_data = {}

        for row in tbody.select("tr"):
            cells = row.find_all("td", recursive=False)

            if len(cells) != 2:
                continue

            key = cells[0].get_text(" ", strip=True)
            value = cells[1].get_text(" ", strip=True)

            if key:
                section_data[key] = value

        if section_data:
            specs.setdefault(section_name, {}).update(section_data)

    return specs, png_url


if __name__ == "__main__":
    main()