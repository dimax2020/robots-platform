"""Строит приложения документации из живой платформы или из снимка JSON.

Живая платформа (нужен вход администратором, пароль демо):
    python docs/tools/gen_appendices.py --api http://localhost/platform/api/v1

Снимок (файлы norms.json, proc_setups.json, fields_<объект>.json, catalog_tree.json):
    python docs/tools/gen_appendices.py --from-dir /путь/к/снимку

Результат:
    docs/appendix-A-assumptions.md, docs/assumptions-register.xlsx,
    docs/appendix-D-rules.md, docs/appendix-Zh-site-fields.md
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1]
DATE = "29.09.2026"

# Влияние норматива на итог. Оценка команды по анализу чувствительности и размеру статьи.
IMPACT = {
    "infra_pct": "Среднее", "software_pct": "Среднее", "integration_pct": "Среднее",
    "commissioning_pct": "Низкое", "training_pct": "Низкое", "reserve_pct": "Среднее",
    "service_pct": "Высокое", "license_pct": "Среднее", "comms_pct": "Низкое",
    "consumables_pct": "Низкое", "repair_pct": "Низкое", "energy_kwh": "Низкое",
    "energy_tariff": "Низкое", "replacement_pct": "Высокое", "robots_per_operator": "Среднее",
    "raas_rate_pct": "Высокое", "horizon_years": "Высокое", "price_factor": "Высокое",
    "salary_factor": "Высокое", "load_factor": "Высокое", "mpt_rate_pct": "Среднее",
    "mpt_limit_mln": "Среднее", "frp_rate_pct": "Низкое", "market_rate_pct": "Низкое",
    "frp_share_pct": "Низкое", "frp_term_years": "Низкое", "leasing_discount_pct": "Среднее",
    "moscow_rate_pct": "Среднее", "moscow_limit_mln": "Среднее", "accel_factor": "Низкое",
    "service_life_years": "Среднее", "profit_tax_pct": "Низкое",
}
GROUP_TITLE = {
    "capex": "Экономика: CAPEX", "opex": "Экономика: OPEX", "staff": "Экономика: персонал",
    "raas": "Экономика: RaaS", "horizon": "Экономика: горизонт", "whatif": "Экономика: what-if",
    "subsidy": "Экономика: господдержка и налоги",
}
GROUP_USED = {
    "capex": "economy.py, статья CAPEX «{label}» (закупка и RaaS)",
    "opex": "economy.py, статья OPEX «{label}» (закупка)",
    "staff": "economy.py, экономия ФОТ и персонал эксплуатации",
    "raas": "economy.py, арендный платёж RaaS",
    "horizon": "economy.py, TCO, ROI и окупаемость",
    "whatif": "economy.py, множители сценария what-if",
    "subsidy": "economy.py, блок «Господдержка» (только сценарий «Покупка»)",
}
# Значения и смысл констант, которые зашиты в код и не приходят ни от пользователя, ни из каталога.
CONSTANTS = [
    ("C-001", "Расчёт", "Множитель чувствительности, нижний", "0,8", "доля", "Отклонение параметра на минус 20% в анализе чувствительности.", "Допущение команды", "Среднее", "economy.py, _sensitivity"),
    ("C-002", "Расчёт", "Множитель чувствительности, верхний", "1,2", "доля", "Отклонение параметра на плюс 20% в анализе чувствительности.", "Допущение команды", "Среднее", "economy.py, _sensitivity"),
    ("C-003", "Расчёт", "Порог вердикта: целесообразно", "3", "лет", "Окупаемость до 3 лет: «по ТЗ решение целесообразно».", "ТЗ п. 3.5.7 (интервалы)", "Высокое", "economy.py, _verdict"),
    ("C-004", "Расчёт", "Порог вердикта: нужен анализ рисков", "5", "лет", "Окупаемость 3–5 лет: «требуется анализ рисков»; больше 5 лет: «нужно отдельное обоснование».", "ТЗ п. 3.5.7 (интервалы)", "Высокое", "economy.py, _verdict"),
    ("C-005", "Расчёт", "Месяцев в году", "12", "мес.", "Годовой ФОТ, оператор, арендный платёж.", "Календарь", "Низкое", "economy.py"),
    ("C-006", "Расчёт", "Запасной ФОТ-коэффициент начислений", "1,0", "коэфф.", "Применяется, если площадка не задала payroll_burden.", "Допущение команды", "Среднее", "economy.py, ФОТ"),
    ("C-007", "Расчёт", "Количество роботов, если формула не дала числа", "1", "шт.", "Робот с ценой, но без формулы количества, считается одной машиной, в отчёте пометка «нет расчёта количества».", "Допущение команды", "Среднее", "economy.py, парк"),
    ("C-008", "Расчёт", "Максимум лет в цикле окупаемости", "200", "лет", "Защита цикла от бесконечного счёта.", "Техническое", "Низкое", "economy.py, PBP"),
    ("C-009", "Расчёт", "Максимум подсказок по параметрам", "3", "шт.", "Сколько предложений «что изменить, чтобы процесс окупился» показывать.", "Допущение команды", "Низкое", "economy.py, подсказки"),
    ("C-010", "Расчёт", "Шагов двоичного поиска подсказки", "24", "итераций", "Точность подбора значения параметра в подсказке.", "Техническое", "Низкое", "economy.py, подсказки"),
    ("C-011", "Формула количества", "Коэффициент загрузки робота", "0,82", "доля", "В формулах количества роботов по потоку, обходу и инвентаризации. Учитывает простои, зарядку и доступность.", "Допущение команды", "Высокое", "seed: process.count_formula"),
    ("C-012", "Формула количества", "Время обработки на пункте (погрузка и выгрузка)", "80", "с", "Слагаемое цикла рейса в формулах перевозки паллет и подобных потоков.", "Допущение команды", "Высокое", "seed: process.count_formula"),
    ("C-013", "Формула количества", "Резерв парка", "+1", "шт.", "В большинстве формул к расчётному числу роботов добавляется один запасной.", "Допущение команды", "Среднее", "seed: process.count_formula"),
    ("C-014", "Формула количества", "Время выстоя робота при обходе периметра", "240", "с", "Время на точку в формуле охраны и патрулирования.", "Допущение команды", "Среднее", "seed: perimeter_security"),
    ("C-015", "Формула количества", "Длина периметра от площади", "4·√S", "м", "Периметр квадратной площадки той же площади, когда реальная длина неизвестна.", "Допущение команды", "Среднее", "seed: perimeter_security"),
    ("C-016", "Формула количества", "Фиксированные суточные потоки аэропорта и медучреждения", "420 / 850 / 1200", "операций в сутки", "В формулах процессов аэропорта и медучреждения объём зашит числом, а не берётся из параметров площадки.", "Допущение команды", "Высокое", "seed: process.count_formula"),
    ("C-017", "Формула количества", "Фиксированная длина маршрута аэропорта и медучреждения", "584 / 360", "м", "То же: маршрут зашит числом.", "Допущение команды", "Высокое", "seed: process.count_formula"),
    ("C-018", "Подбор", "Минимальный УГТ для автоподбора", "6", "уровень", "Робот ниже порога не отсеивается, а попадает во вкладку «Уточнить». Настраивается в админке.", "Допущение команды", "Высокое", "match.py, Readiness; таблица match_setting"),
    ("C-019", "Подбор", "Стадии, отправляемые на проверку", "Разработка (R&D)", "—", "Робот в стадии R&D не отсеивается, а уходит в «Уточнить». Настраивается в админке.", "Допущение команды", "Высокое", "match.py, Readiness"),
    ("C-020", "Симуляция", "Шаг модели", "0,5", "с", "Дискретный шаг имитации смены.", "Техническое", "Низкое", "frontend/app/pages/projects/[id]/sim/engine.ts"),
    ("C-021", "Симуляция", "Зерно генератора случайных чисел", "20260926", "—", "Делает прогон воспроизводимым: тот же план даёт те же цифры.", "Техническое", "Низкое", "sim/engine.ts"),
    ("C-022", "Симуляция", "Размер клетки маршрутной сетки", "1", "м", "Один метр на клетку при поиске маршрута A*.", "Допущение команды", "Среднее", "sim/grid.ts"),
    ("C-023", "Симуляция", "Порог «расчёт подтверждён»: время прогона", "min(1800 с, длительность смены)", "с", "Прогон короче порога не считается достаточным для вывода.", "Допущение команды", "Высокое", "sim/engine.ts, confirmed"),
    ("C-024", "Симуляция", "Порог «расчёт подтверждён»: очередь", "не более max(3, 900·λ) заданий", "шт.", "Для перевозок: невыполненный хвост не больше заявок за 15 минут, и что-то выполнено.", "Допущение команды", "Высокое", "sim/engine.ts, confirmed"),
    ("C-025", "Симуляция", "Порог «расчёт подтверждён»: выработка", "не менее 95% от требуемой", "доля", "Для уборки и патрулирования: выработка в час не ниже 95% потребности.", "Допущение команды", "Высокое", "sim/engine.ts, confirmed"),
    ("C-026", "Данные", "Срок жизни сессии", "7", "суток", "Cookie platform_session.", "Допущение команды", "Низкое", "auth.py, MAX_AGE"),
    ("C-027", "Данные", "Предельный размер подложки схемы", "20", "МБ", "PNG, JPG, WebP.", "Допущение команды", "Низкое", "main.py, layout/background"),
    ("C-028", "Данные", "Предельный размер фото карточки", "10", "МБ", "PNG, JPG, WebP.", "Допущение команды", "Низкое", "admin_products.py"),
]

KIND_LEVEL = {
    "Демо-проект склада": "B", "Демо-норматив": "C", "Файл экономической модели": "B",
    "Допущение команды": "D", "ТЗ организатора": "B", "Меры господдержки: формулы": "C",
    "НК РФ": "A", "Базовое значение": "—",
}


def fetch_live(api: str) -> dict:
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

    def call(path: str, body: dict | None = None):
        req = urllib.request.Request(api + path, data=json.dumps(body).encode() if body is not None else None,
                                     headers={"content-type": "application/json"})
        with opener.open(req) as reply:
            return json.load(reply)

    call("/auth/login", {"login": "admin", "password": "demo-2026"})
    procs = call("/admin/processes")
    return {
        "norms": call("/economy/norms"),
        "proc_setups": {p["code"]: call("/admin/processes/" + p["code"]) for p in procs},
        "fields": {code: call(f"/catalog/objects/{code}/fields") for code in ("warehouse", "airport", "hospital")},
    }


def load_snapshot(folder: Path) -> dict:
    load = lambda name: json.loads((folder / name).read_text(encoding="utf-8"))  # noqa: E731
    return {
        "norms": load("norms.json"),
        "proc_setups": load("proc_setups.json"),
        "fields": {code: load(f"fields_{code}.json") for code in ("warehouse", "airport", "hospital")},
    }


def num(value: float) -> str:
    text = f"{value:,.2f}".replace(",", " ").replace(".", ",")
    return text.rstrip("0").rstrip(",") if "," in text else text


def build_assumptions(data: dict) -> tuple[list[list[str]], str]:
    rows: list[list[str]] = []
    for idx, item in enumerate(data["norms"]["items"], start=1):
        origin = item.get("origin") or "—"
        level = KIND_LEVEL.get(origin, "D")
        rows.append([
            f"D-{idx:03d}", GROUP_TITLE.get(item["group"], item["group"]), item["label"], num(item["value"]), item["unit"],
            (item.get("rationale") or "—").strip(), origin, DATE, level, IMPACT.get(item["key"], "Среднее"),
            GROUP_USED.get(item["group"], "economy.py").format(label=item["label"].lower()),
        ])
    for c in CONSTANTS:
        origin = c[6]
        level = "B" if origin.startswith("ТЗ") else ("D" if origin.startswith("Допущение") else "—")
        rows.append([c[0], c[1], c[2], c[3], c[4], c[5], origin, DATE, level, c[7], c[8]])

    head = [
        "# Приложение А. Реестр допущений и нормативов",
        "",
        "Реестр закрывает пп. 3.5.1, 3.2.5 и 7.5 ТЗ. В него входят все числа расчётной модели, подбора и симуляции, которые не пришли из данных пользователя или каталога. Таблица выгружена из работающей платформы (`GET /api/v1/economy/norms`) и из кода, в Excel лежит копия: [assumptions-register.xlsx](assumptions-register.xlsx).",
        "",
        "Нормативы D-001…D-%03d можно менять в админке (раздел «Нормативы»), а на проекте переопределять на шаге what-if. Изменение админом попадает в журнал (`economy_norm_log`) с заметкой. Константы C-001…C-%03d зашиты в код или в формулы процессов, их меняет только разработчик." % (len(data["norms"]["items"]), len(CONSTANTS)),
        "",
        "**Шкала достоверности** (шкала команды, для нормативов выводится из происхождения значения):",
        "",
        "| Уровень | Смысл | Происхождение в реестре |",
        "|---|---|---|",
        "| A | Первоисточник: нормативный акт | НК РФ |",
        "| B | Данные организатора или согласованный с ТЗ параметр | Демо-проект склада, файл экономической модели, ТЗ организатора |",
        "| C | Оценка по аналогу или расчётная оценка по открытым программам | Меры господдержки (формулы), демо-норматив |",
        "| D | Допущение команды без внешнего подтверждения | Допущение команды |",
        "| — | Нейтральное значение (множитель 100%) или техническая константа | Базовое значение, техническое |",
        "",
        "Значение «Влияние на результат» — оценка команды: «Высокое», если изменение на ±20% заметно двигает срок окупаемости или число роботов.",
        "",
        f"Дата сверки с кодом и данными платформы: {DATE}.",
        "",
        "| ID | Категория | Параметр | Значение | Единица | Обоснование | Источник | Дата | Достоверность | Влияние | Где используется |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    body = ["| " + " | ".join(cell.replace("|", "/").replace("\n", " ") for cell in row) + " |" for row in rows]
    return rows, "\n".join(head + body) + "\n"


def write_xlsx(rows: list[list[str]], path: Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Реестр допущений"
    header = ["ID", "Категория", "Параметр", "Значение", "Единица", "Обоснование", "Источник", "Дата", "Уровень достоверности", "Влияние на результат", "Где используется"]
    ws.append(header)
    for row in rows:
        ws.append(row)
    fill = PatternFill("solid", fgColor="1F3A34")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    widths = [8, 26, 34, 14, 22, 70, 26, 12, 14, 14, 46]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    wb.save(path)


def tex_free(formula: str) -> str:
    return formula.replace("|", "\\|")


def build_rules(data: dict) -> str:
    setups = data["proc_setups"]
    with_filters = [s for s in setups.values() if s["filters"]]
    with_count = [s for s in setups.values() if s["count_formula"]]
    with_rank = [s for s in setups.values() if s["rank_key"]]
    lines = [
        "# Приложение Д. Правила подбора, формулы количества и ранжирование по процессам",
        "",
        "Приложение закрывает п. 7.1 дополнений к ТЗ («условия исключения неподходящих решений») и п. 3.4.2 ТЗ. Таблицы выгружены из работающей платформы (`GET /api/v1/admin/processes/{code}`) на " + DATE + ". Правила и формулы редактируются в админке («Процессы»), поэтому после правок приложение надо перегенерировать: `python docs/tools/gen_appendices.py`.",
        "",
        f"**Сводка.** Процессов в справочнике: {len(setups)}. Настроены фильтры у {len(with_filters)} процессов (всего правил: {sum(len(s['filters']) for s in with_filters)}), формула количества роботов у {len(with_count)}, ключ ранжирования у {len(with_rank)}. У остальных процессов настройки нет: все назначенные им роботы получат вердикт «Подходит» без проверки, а число роботов не рассчитывается (в экономике берётся одна машина, если у неё есть цена).",
        "",
        "## Как читать правило",
        "",
        "- **Режим `hard`** (жёсткое): невыполнение даёт вердикт «Не подходит». **Режим `conditional`** (с условием): невыполнение даёт «С условием» и причину в списке замечаний.",
        "- В формуле `robot.<ключ>` — характеристика робота из каталога, остальные имена — входы, привязанные к параметрам площадки (столбец «Входы»). Если параметр площадки пуст, правило пропускается. Если у робота нет нужной характеристики, вердикт «Уточнить».",
        "- Допустимы операции `+ - * /`, сравнения `< <= > >= == !=`, логика `and`, `or`, функции `ceil floor abs round min max sqrt`.",
        "",
        "## Правила исключения (фильтры)",
        "",
        "| Процесс | Правило | Режим | Формула | Входы (параметры площадки) |",
        "|---|---|---|---|---|",
    ]
    for setup in sorted(with_filters, key=lambda s: s["name"]):
        for flt in setup["filters"]:
            inputs = ", ".join(f"`{i['key']}` ({i['label']})" for i in flt.get("inputs", [])) or "—"
            lines.append(f"| {setup['name']} | {flt['name']} | {flt['mode']} | `{tex_free(flt['formula'])}` | {inputs} |")
    lines += [
        "",
        "## Формулы количества роботов",
        "",
        "Формула считает число машин выбранной модели для процесса. Переменные `robot.*` берутся из карточки робота, остальные из параметров площадки. Числа `0,82`, `80`, `240` и другие зашитые константы перечислены в приложении А (C-011…C-017).",
        "",
        "| Процесс | Формула | Входы |",
        "|---|---|---|",
    ]
    for setup in sorted(with_count, key=lambda s: s["name"]):
        inputs = ", ".join(f"`{i['key']}`" for i in setup.get("count_inputs", [])) or "—"
        lines.append(f"| {setup['name']} | `{tex_free(setup['count_formula'])}` | {inputs} |")
    lines += [
        "",
        "## Ранжирование: какой робот считается лучшим",
        "",
        "Взвешенной оценки нет (см. раздел 4 документации). Для каждого процесса можно задать характеристику, по которой среди роботов с вердиктом «Подходит» (а если таких нет, «С условием») выбирается один «лучший». Он ставится в сравнении по умолчанию и идёт в экономику. Если ключ не задан, лучшим считается самый дешёвый.",
        "",
        "| Процесс | Характеристика | Порядок |",
        "|---|---|---|",
    ]
    for setup in sorted(with_rank, key=lambda s: s["name"]):
        order = "по убыванию" if setup["rank_order"] == "desc" else "по возрастанию"
        lines.append(f"| {setup['name']} | `{setup['rank_key']}` | {order} |")
    lines += ["", "## Процессы без настроенных правил", ""]
    bare = sorted(s["name"] for s in setups.values() if not s["filters"] and not s["count_formula"])
    lines.append(f"Ниже процессы ({len(bare)}), для которых нет ни фильтров, ни формулы количества. Это задел каталога: роботы назначены, правила подбора добавляются в админке.")
    lines.append("")
    lines.append(", ".join(bare) + ".")
    return "\n".join(lines) + "\n"


def build_fields(data: dict) -> str:
    lines = [
        "# Приложение Ж. Параметры площадки по типам объектов",
        "",
        "Приложение закрывает п. 3.2.1 ТЗ (минимальный состав параметров). Таблицы выгружены из `GET /api/v1/catalog/objects/{code}/fields` на " + DATE + ". Значения по умолчанию взяты из демонстрационных наборов организатора (`Датасеты_хакатон.xlsx`), источник каждого значения указан в интерфейсе рядом с полем (п. 3.2.5).",
        "",
        "Границы `min`/`max` проверяются при вводе вручную и при загрузке файла. Тип `number` — число, `int` — целое, `bool` — да/нет, `text` — строка.",
        "",
    ]
    titles = {"warehouse": "Склад", "airport": "Аэропорт", "hospital": "Медицинское учреждение"}
    for code, title in titles.items():
        payload = data["fields"][code]
        fields = payload["fields"]
        lines += [f"## {title} (`{code}`), полей: {len(fields)}", "", "| Ключ | Поле | Группа | Ед. | Тип | Диапазон | Обязательное | По умолчанию | Источник значения |", "|---|---|---|---|---|---|---|---|---|"]
        for f in fields:
            low, high = f.get("min"), f.get("max")
            rng = "—" if low is None and high is None else f"{'' if low is None else num(low)} … {'' if high is None else num(high)}"
            default = "—" if f.get("default") in (None, "") else str(f["default"])
            source = (f.get("source") or "—").replace("|", "/").replace("\n", " ")
            lines.append(f"| `{f['key']}` | {f['label']} | {f.get('group') or '—'} | {f.get('unit') or '—'} | {f['kind']} | {rng} | {'да' if f.get('required') else 'нет'} | {default} | {source} |")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api", help="адрес API, например http://localhost/platform/api/v1")
    parser.add_argument("--from-dir", help="папка со снимком JSON")
    args = parser.parse_args()
    if bool(args.api) == bool(args.from_dir):
        raise SystemExit("нужен ровно один из ключей: --api или --from-dir")
    data = fetch_live(args.api) if args.api else load_snapshot(Path(args.from_dir))
    rows, md = build_assumptions(data)
    (DOCS / "appendix-A-assumptions.md").write_text(md, encoding="utf-8")
    write_xlsx(rows, DOCS / "assumptions-register.xlsx")
    (DOCS / "appendix-D-rules.md").write_text(build_rules(data), encoding="utf-8")
    (DOCS / "appendix-Zh-site-fields.md").write_text(build_fields(data), encoding="utf-8")
    print("готово: приложения А, Д, Ж и assumptions-register.xlsx")


if __name__ == "__main__":
    main()
