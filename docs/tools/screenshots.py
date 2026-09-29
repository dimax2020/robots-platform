"""Снимает экраны платформы для руководства пользователя и администратора.

Запуск (платформа должна работать на http://localhost):
    python docs/tools/screenshots.py

Нужны пакеты из docs/tools/requirements.txt и браузер: `playwright install chromium`.
Снимки складываются в docs/img и подписываются в документации.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost"
API = f"{BASE}/platform/api/v1"
OUT = Path(__file__).resolve().parents[1] / "img"
DEMO = "demo-warehouse"
ROBOT = "ronavi-h1500-gruzopodemnost-do-1-500-kg"

# (файл, адрес, нужен ли вход админом, полная страница, макс. высота для полной страницы)
GUEST = [
    ("01-home", "/", False, 2400),
    ("02-login", "/login", False, 0),
    ("03-catalog", "/catalog", False, 0),
    ("04-card", f"/catalog/card/{ROBOT}", False, 1800),
    ("05-projects-guest", "/projects", False, 0),
    ("06-new-project-guest", "/projects/new", False, 0),
]
ADMIN = [
    ("10-projects", "/projects", False, 0),
    ("11-project-cabinet", f"/projects/{DEMO}", False, 1600),
    ("12-params", f"/projects/{DEMO}/params", True, 2200),
    ("13-params-processes", f"/projects/{DEMO}/params?part=processes", False, 1600),
    ("14-match", f"/projects/{DEMO}/match", True, 2200),
    ("15-compare", f"/projects/{DEMO}/compare?process=pallet_storage", True, 1500),
    ("16-economics", f"/projects/{DEMO}/economics", True, 3000),
    ("17-what-if", f"/projects/{DEMO}/what-if", True, 2200),
    ("18-plan", f"/projects/{DEMO}/plan", False, 0),
    ("19-report", f"/projects/{DEMO}/report", True, 3200),
    ("30-admin-overview", "/admin", True, 1800),
    ("31-admin-demo", "/admin/demo", False, 0),
    ("32-admin-objects", "/admin/objects", True, 2000),
    ("33-admin-processes", "/admin/processes", False, 0),
    ("34-admin-filters", "/admin/filters", False, 0),
    ("35-admin-coverage", "/admin/coverage", False, 0),
    ("36-admin-norms", "/admin/norms", True, 2400),
    ("37-admin-norms-types", "/admin/norms/types", False, 0),
    ("38-admin-products", "/admin/products", False, 0),
    ("39-admin-attributes", "/admin/products/attributes", False, 0),
    ("40-admin-parsers", "/admin/parsers", False, 0),
    ("41-admin-tables", "/admin/tables", False, 0),
    ("42-admin-sources", "/admin/sources", False, 0),
    ("43-admin-tree", "/admin/catalog", False, 0),
    ("44-admin-industries", "/admin/catalog/industries", False, 0),
    ("45-admin-types", "/admin/catalog/types", False, 0),
]


def shoot(page, name: str, path: str, full: bool, cap: int) -> None:
    page.goto(BASE + path, wait_until="load", timeout=60000)
    page.wait_for_timeout(3500)
    target = OUT / f"{name}.png"
    if full:
        height = page.evaluate("document.documentElement.scrollHeight")
        page.screenshot(path=str(target), clip={"x": 0, "y": 0, "width": 1440, "height": min(height, cap or height)})
    else:
        page.screenshot(path=str(target))
    print("ok", name, path, file=sys.stderr)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ru-RU")
        page = ctx.new_page()
        for name, path, full, cap in [(n, u, bool(c), c) for n, u, _f, c in GUEST]:
            shoot(page, name, path, full, cap)
        reply = ctx.request.post(f"{API}/auth/login", data=json.dumps({"login": "admin", "password": "demo-2026"}), headers={"content-type": "application/json"})
        if not reply.ok:
            raise SystemExit("не удалось войти админом: " + reply.text())
        time.sleep(0.5)
        for name, path, full, cap in [(n, u, f, c) for n, u, f, c in ADMIN]:
            shoot(page, name, path, full, cap)
        browser.close()


if __name__ == "__main__":
    main()
