"""Экономика трёх сценариев: без роботизации, покупка, аренда. Вход — парк, площадка и нормативы, без базы."""

from __future__ import annotations

import math
from dataclasses import dataclass

NO_PRICE = "Не будет использоваться в расчётах, не хватает цены."
NO_COUNT = "Количество посчитать не удалось, поэтому в расчёте экономики участвует только один робот."
DISCLAIMER = "Результат является предварительной оценкой и требует верификации при обследовании объекта."

SOURCES = {
    "card": "карточка робота",
    "fleet": "подбор",
    "site": "параметры площадки",
    "norm": "стандарт",
    "project": "значение проекта",
    "calc": "расчёт",
}


@dataclass(frozen=True)
class Norm:
    key: str
    group: str
    label: str
    symbol: str
    value: float
    unit: str
    rationale: str
    source: str
    min: float
    max: float
    step: float


NORMS: tuple[Norm, ...] = (
    Norm("infra_pct", "capex", "Инфраструктура", r"k_{\text{инфр}}", 11.5, "% от оборудования",
         "Зарядные станции, разметка, Wi-Fi. Демо-склад: 8,2 млн ₽ при оборудовании 71,4 млн ₽.", "Демо-проект склада", 0, 40, 0.1),
    Norm("software_pct", "capex", "ПО", r"k_{\text{ПО}}", 9.1, "% от оборудования",
         "Система управления парком. Демо-склад: 6,5 млн ₽ при оборудовании 71,4 млн ₽.", "Демо-проект склада", 0, 40, 0.1),
    Norm("integration_pct", "capex", "Интеграция с WMS и ERP", r"k_{\text{интегр}}", 13.7, "% от оборудования",
         "Демо-склад: 9,8 млн ₽ при оборудовании 71,4 млн ₽.", "Демо-проект склада", 0, 40, 0.1),
    Norm("commissioning_pct", "capex", "Пусконаладка", r"k_{\text{ПНР}}", 6.4, "% от оборудования",
         "Демо-склад: 4,6 млн ₽ при оборудовании 71,4 млн ₽. Цена карточки идёт без пусконаладки.", "Демо-проект склада", 0, 30, 0.1),
    Norm("training_pct", "capex", "Обучение", r"k_{\text{обуч}}", 1.7, "% от оборудования",
         "Демо-склад: 1,2 млн ₽ при оборудовании 71,4 млн ₽.", "Демо-проект склада", 0, 10, 0.1),
    Norm("reserve_pct", "capex", "Резерв", r"k_{\text{рез}}", 6.0, "% от суммы статей",
         "Демо-склад: резерв 6% от суммы статей CAPEX.", "Демо-проект склада", 0, 20, 0.5),
    Norm("service_pct", "opex", "Сервис", r"k_{\text{серв}}", 8.0, "% от оборудования в год",
         "Поле «Сервис_%_в_год» пустое у всех позиций каталога. Демо-норматив: медиана по 6 вендорам класса.", "Демо-норматив", 0, 20, 0.5),
    Norm("license_pct", "opex", "Лицензии", r"k_{\text{лиц}}", 4.9, "% от оборудования в год",
         "Подписка на ПО парка. Демо-склад: 3,5 млн ₽ в год при оборудовании 71,4 млн ₽.", "Демо-проект склада", 0, 15, 0.1),
    Norm("comms_pct", "opex", "Связь", r"k_{\text{связь}}", 0.3, "% от оборудования в год",
         "Файл модели: SIM-карты, Wi-Fi, каналы связи — 0,2–0,5% стоимости оборудования в год, заложено 0,3%.", "Файл экономической модели", 0, 2, 0.05),
    Norm("consumables_pct", "opex", "Расходные материалы", r"k_{\text{расх}}", 1.0, "% от оборудования в год",
         "Файл модели: аккумуляторные элементы, ролики, датчики — 0,5–1,5% в год, заложено 1,0%.", "Файл экономической модели", 0, 5, 0.1),
    Norm("repair_pct", "opex", "Ремонт вне сервиса", r"k_{\text{рем}}", 1.5, "% от оборудования в год",
         "Файл модели: запчасти и аварийные выезды — 1–2% в год, заложено 1,5%.", "Файл экономической модели", 0, 5, 0.1),
    Norm("energy_kwh", "opex", "Энергопотребление робота", r"e", 0.9, "кВт·ч за час работы",
         "Демо-склад: 0,9 кВт·ч на машину в час. Если в карточке робота есть мощность, берётся она.", "Демо-проект склада", 0, 10, 0.1),
    Norm("energy_tariff", "opex", "Тариф на электроэнергию", r"\tau", 7.2, "₽/кВт·ч",
         "Средний коммерческий тариф Московской области. Если тариф задан на площадке, берётся он.", "Демо-норматив", 1, 20, 0.1),
    Norm("replacement_pct", "staff", "Доля замещаемого персонала", r"s", 63.0, "% ФОТ ролей",
         "Демо-склад: 24 ставки из 38 переходят на роботов. Остальные люди остаются на исключениях и контроле.", "Демо-проект склада", 0, 100, 1),
    Norm("robots_per_operator", "staff", "Роботов на одного оператора", r"m", 10.0, "шт.",
         "Каталог не говорит, сколько людей нужно парку. Допущение: один оператор или диспетчер на 10 машин.", "Допущение команды", 1, 50, 1),
    Norm("raas_rate_pct", "raas", "Ставка аренды", r"k_{\text{RaaS}}", 2.2, "% цены робота в месяц",
         "Выведено из демо: аренда дороже покупки на 19 млн ₽ в год при оборудовании 71,4 млн ₽, это около 26,6% в год или 2,2% в месяц. "
         "В ставку входят сервис, ремонт, расходники и лицензии.", "Демо-проект склада", 0.5, 6, 0.1),
    Norm("horizon_years", "horizon", "Горизонт расчёта", r"T", 5.0, "лет",
         "ТЗ: не меньше 5 лет. Если на площадке задан больший горизонт окупаемости, берётся он.", "ТЗ организатора", 3, 15, 1),
    Norm("price_factor", "whatif", "Стоимость оборудования", r"f_{\text{цена}}", 100.0, "% от цены карточки",
         "Базово цена из карточки. Меньше 100% — скидка вендора, больше — удорожание.", "Базовое значение", 50, 150, 5),
    Norm("salary_factor", "whatif", "Стоимость персонала", r"f_{\text{ФОТ}}", 100.0, "% от зарплат площадки",
         "Базово зарплаты площадки. Больше 100% — рост зарплат или дефицит персонала.", "Базовое значение", 50, 200, 5),
    Norm("load_factor", "whatif", "Нагрузка площадки", r"f_{\text{нагр}}", 100.0, "% от суточных потоков",
         "Умножает суточные потоки площадки: паллеты, строки и штуки. Количество роботов пересчитывается подбором. "
         "Пиковый сезон по файлу модели — 150–200%.", "Базовое значение", 50, 200, 5),
    Norm("mpt_rate_pct", "subsidy", "Ставка субсидии Минпромторга", r"k_{\text{МПТ}}", 15.0, "% от оборудования",
         "Единая ставка не установлена. Среднестатистическая оценка по действующим программам Минпромторга — около 15% "
         "стоимости оборудования. Точная ставка берётся из акта конкретной программы.", "Меры господдержки: формулы", 0, 50, 1),
    Norm("mpt_limit_mln", "subsidy", "Лимит субсидии Минпромторга", r"L_{\text{МПТ}}", 80.0, "млн ₽",
         "Устанавливается ежегодно в пределах бюджетных ассигнований программы. Сейчас 80 млн ₽, может измениться.",
         "Меры господдержки: формулы", 0, 1000, 5),
    Norm("frp_rate_pct", "subsidy", "Ставка займа ФРП", r"r_{\text{ФРП}}", 3.0, "% годовых",
         "Базовая ставка ФРП — 3% годовых, снижена с 5% с 1 января 2021 г. По отдельным программам, например "
         "«Цифровизация промышленности», — 1% или 5%.", "Меры господдержки: формулы", 0, 10, 0.5),
    Norm("market_rate_pct", "subsidy", "Рыночная ставка кредита", r"r_{\text{рын}}", 18.0, "% годовых",
         "Нормативом не задана. Средняя ставка по кредитам юрлицам — 16–20% годовых по данным Банка России, взята середина.",
         "Меры господдержки: формулы", 5, 35, 0.5),
    Norm("frp_share_pct", "subsidy", "Доля CAPEX за счёт займа ФРП", r"d_{\text{ФРП}}", 50.0, "% от CAPEX",
         "Сумма займа нормативом не задана. Допущение: заём закрывает половину вложений, уточняется по заявке в фонд.",
         "Допущение команды", 0, 100, 5),
    Norm("frp_term_years", "subsidy", "Срок займа ФРП", r"T_{\text{ФРП}}", 5.0, "лет",
         "Выгода по ставке считается только в годы действия займа. Допущение: 5 лет, уточняется по условиям программы.",
         "Допущение команды", 1, 10, 1),
    Norm("leasing_discount_pct", "subsidy", "Скидка по льготному лизингу", r"k_{\text{лиз}}", 10.0, "% стоимости техники",
         "ПП № 649 от 08.05.2020: скидка обычно 10–15% стоимости техники, для отдельных категорий — до 35%. "
         "Размер утверждается ежегодно. Скидка единовременная, в счёт аванса по договору лизинга.", "Меры господдержки: формулы", 0, 35, 1),
    Norm("moscow_rate_pct", "subsidy", "Ставка субсидии Москвы на лизинг", r"k_{\text{Мск}}", 30.0, "% от базы лизинга",
         "Точный процент в открытом акте не зафиксирован. Оценка по программам возмещения части лизинговых платежей "
         "промышленным предприятиям Москвы — около 30%. База — стоимость оборудования в лизинге.", "Меры господдержки: формулы", 0, 50, 1),
    Norm("moscow_limit_mln", "subsidy", "Лимит субсидии Москвы", r"L_{\text{Мск}}", 100.0, "млн ₽ в год",
         "По действующей программе — до 100 млн ₽ в год на предприятие.", "Меры господдержки: формулы", 0, 500, 5),
    Norm("accel_factor", "subsidy", "Коэффициент ускоренной амортизации", r"K_{\text{уск}}", 3.0, "коэфф.",
         "Ст. 259.3 НК РФ: специальный коэффициент не выше 3. Значение зависит от категории оборудования и договора.",
         "Меры господдержки: формулы", 1, 3, 0.1),
    Norm("service_life_years", "subsidy", "Срок службы оборудования", r"T_{\text{сл}}", 7.0, "лет",
         "Срока службы в карточках нет. Допущение: 7 лет, уточняется по паспорту оборудования.", "Допущение команды", 2, 20, 1),
    Norm("profit_tax_pct", "subsidy", "Ставка налога на прибыль", r"t_{\text{приб}}", 25.0, "%",
         "25%: 8% в федеральный бюджет и 17% в региональный, ст. 284 НК РФ, действует с 2025 г.", "НК РФ", 0, 40, 1),
)

# code, название, подпись, разовая или годовая, коэффициенты меры.
SUBSIDIES: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    ("mpt", "Субсидия Минпромторга", "На приобретение и интеграцию роботов", "once", ("mpt_rate_pct", "mpt_limit_mln")),
    ("leasing", "Льготный лизинг, ПП № 649", "Единовременная скидка на технику", "once", ("leasing_discount_pct",)),
    ("moscow", "Субсидия Москвы на лизинг", "Возмещение части лизинга оборудования", "once", ("moscow_rate_pct", "moscow_limit_mln")),
    ("frp", "Льготный заём ФРП", "Разница ставок на сумму займа", "year", ("frp_rate_pct", "market_rate_pct", "frp_share_pct", "frp_term_years")),
    ("amort", "Ускоренная амортизация, ст. 259.3 НК РФ", "Экономия налога на прибыль", "year", ("accel_factor", "service_life_years", "profit_tax_pct")),
)
SUBSIDY_CODES = tuple(item[0] for item in SUBSIDIES)
SUPPORT_NOTE = "Право на меру и её размер подтверждаются условиями конкретной программы."

NORM_BY_KEY = {norm.key: norm for norm in NORMS}
LOAD_KEYS = ("inbound_pallets_per_day", "outbound_pallets_per_day", "pick_lines_per_day", "pick_units_per_day")

_ROLES = (
    ("pickers_count", "picker_salary_month_rub", "Отборщики", r"\text{отб}"),
    ("forklift_operators", "forklift_salary_month_rub", "Операторы погрузчиков", r"\text{погр}"),
    ("pack_operators", "pack_salary_month_rub", "Операторы упаковки", r"\text{упак}"),
)

_SENSITIVE = ("price_factor", "salary_factor", "replacement_pct", "service_pct", "license_pct", "robots_per_operator", "energy_tariff")


TYPE_NORMS = (
    "infra_pct", "software_pct", "integration_pct", "commissioning_pct", "training_pct",
    "service_pct", "license_pct", "comms_pct", "consumables_pct", "repair_pct", "raas_rate_pct",
)

# Коэффициенты, которые можно задать одному процессу, не двигая весь парк.
PROCESS_TUNABLE = frozenset(("price_factor", "energy_kwh", *TYPE_NORMS))
_CAPEX_EXTRAS = ("infra_pct", "software_pct", "integration_pct", "commissioning_pct", "training_pct")
_RAAS_EXTRAS = ("infra_pct", "integration_pct", "commissioning_pct", "training_pct")
# direction -1: процессу помогает меньшее значение, +1: большее.
_SUGGEST = (
    ("price_factor", -1, "process"),
    ("service_pct", -1, "process"),
    ("license_pct", -1, "process"),
    ("infra_pct", -1, "process"),
    ("software_pct", -1, "process"),
    ("integration_pct", -1, "process"),
    ("commissioning_pct", -1, "process"),
    ("training_pct", -1, "process"),
    ("reserve_pct", -1, "process"),
    ("comms_pct", -1, "process"),
    ("consumables_pct", -1, "process"),
    ("repair_pct", -1, "process"),
    ("energy_kwh", -1, "process"),
    ("salary_factor", 1, "site"),
    ("replacement_pct", 1, "site"),
    ("energy_tariff", -1, "site"),
    ("robots_per_operator", 1, "site"),
)
_SHARE_EQUAL = (
    "Численность не привязана к процессам, поэтому экономия на персонале поделена между ними поровну. "
    "Процесс посчитан отдельно: как если бы роботизировали только его."
)
_SHARE_FTE = (
    "Экономия на персонале распределена по численности на задаче процесса. "
    "Процесс посчитан отдельно: как если бы роботизировали только его."
)


def blend_by_type(
    standard: dict[str, float],
    rows: list[dict],
    by_type: dict[str, dict[str, float]],
    type_names: dict[str, str] | None = None,
    base_meta: dict[str, dict] | None = None,
) -> tuple[dict[str, float], dict[str, dict]]:
    """Нормативы типа решения поверх стандарта.

    Все TYPE_NORMS — доли от стоимости оборудования, поэтому средневзвешенная по стоимости
    даёт ту же сумму, что расчёт по каждому роботу со своим нормативом.
    """
    blended = dict(standard)
    notes: dict[str, dict] = {}
    names = type_names or {}
    priced = []
    for row in rows:
        price = _num(row.get("price_rub"))
        if price is None:
            continue
        count = _num(row.get("count"))
        priced.append((row.get("solution_type") or "", price * (count if count is not None else 1.0)))
    total = sum(weight for _code, weight in priced)
    if not total:
        return blended, notes
    for key in TYPE_NORMS:
        base = _num(standard.get(key))
        base = NORM_BY_KEY[key].value if base is None else base
        used = [(code, by_type[code][key]) for code, _weight in priced if code in by_type and key in by_type[code]]
        if not used:
            continue
        value = sum(weight * by_type.get(code, {}).get(key, base) for code, weight in priced) / total
        blended[key] = value
        parts = sorted({f"{names.get(code, code)} {_t_plain(own)}%" for code, own in used})
        rationale = ((base_meta or {}).get(key) or {}).get("rationale") or NORM_BY_KEY[key].rationale
        notes[key] = {
            "rationale": f"{rationale} С поправкой по типам решений: {', '.join(parts)}; остальным — стандарт {_t_plain(base)}%. Взвешено по стоимости парка.",
            "origin": "Нормативы по типам решений",
        }
    return blended, notes


def scale_load(site: dict, load_pct: float) -> dict:
    if load_pct == 100:
        return dict(site)
    scaled = dict(site)
    for key in LOAD_KEYS:
        value = _num(site.get(key))
        if value is not None:
            scaled[key] = value * load_pct / 100
    return scaled


def resolve(standard: dict[str, float] | None, overrides: dict | None, site: dict | None = None, meta: dict[str, dict] | None = None) -> dict[str, dict]:
    standard = standard or {}
    overrides = overrides or {}
    site = site or {}
    meta = meta or {}
    out = {}
    for norm in NORMS:
        own = meta.get(norm.key) or {}
        base = _num(standard.get(norm.key))
        base = norm.value if base is None else base
        mine = _num(overrides.get(norm.key))
        value, source = (mine, "project") if mine is not None else (base, "norm")
        if norm.key == "horizon_years" and mine is None:
            site_years = _num(site.get("payback_years"))
            if site_years is not None and site_years > base:
                value, source = site_years, "site"
        if norm.key == "energy_tariff" and mine is None:
            tariff = _num(site.get("energy_tariff_rub_kwh"))
            if tariff is not None and tariff > 0:
                value, source = tariff, "site"
        out[norm.key] = {
            "key": norm.key,
            "group": norm.group,
            "label": norm.label,
            "symbol": norm.symbol,
            "unit": norm.unit,
            "value": value,
            "standard": base,
            "source": source,
            "overridden": mine is not None,
            "rationale": own.get("rationale") or norm.rationale,
            "origin": own.get("origin") or norm.source,
            "min": norm.min,
            "max": norm.max,
            "step": norm.step,
        }
    return out


def split_process_overrides(overrides: dict | None) -> tuple[dict, dict[str, dict[str, float]]]:
    """Ключ process:код:норматив задаёт коэффициент одному процессу. Остальное — на весь парк."""
    global_overrides: dict = {}
    by_process: dict[str, dict[str, float]] = {}
    for key, raw in (overrides or {}).items():
        if isinstance(key, str) and key.startswith("subsidy:"):
            continue
        if not isinstance(key, str) or not key.startswith("process:"):
            global_overrides[key] = raw
            continue
        parts = key.split(":")
        if len(parts) != 3 or not parts[1] or parts[2] not in PROCESS_TUNABLE:
            continue
        value = _num(raw)
        if value is None:
            continue
        norm = NORM_BY_KEY[parts[2]]
        by_process.setdefault(parts[1], {})[parts[2]] = min(norm.max, max(norm.min, value))
    return global_overrides, by_process


def enabled_subsidies(overrides: dict | None) -> frozenset[str]:
    """Ключ subsidy:код = 1 включает меру господдержки в расчёт покупки."""
    on = set()
    for code in SUBSIDY_CODES:
        value = _num((overrides or {}).get(f"subsidy:{code}"))
        if value:
            on.add(code)
    return frozenset(on)


def clamp_overrides(values: dict | None) -> dict:
    """Оставляет нормативы парка, ключи process:код:норматив и включённые меры subsidy:код."""
    global_overrides, by_process = split_process_overrides(values)
    clean: dict[str, float] = {f"subsidy:{code}": 1.0 for code in enabled_subsidies(values)}
    for key, raw in global_overrides.items():
        if key not in NORM_BY_KEY:
            continue
        value = _num(raw)
        if value is not None:
            clean[key] = value
    for code, items in by_process.items():
        for key, value in items.items():
            clean[f"process:{code}:{key}"] = value
    return clean


def calculate(
    rows: list[dict],
    site: dict | None = None,
    standard: dict[str, float] | None = None,
    overrides: dict | None = None,
    tasks: list[dict] | None = None,
    meta: dict[str, dict] | None = None,
) -> dict:
    site = site or {}
    global_overrides, by_process = split_process_overrides(overrides)
    subsidies = enabled_subsidies(overrides)
    params = resolve(standard, global_overrides, site, meta)
    report = _compute(rows, site, tasks or [], params, by_process, with_processes=True, subsidies=subsidies)
    report["sensitivity"] = _sensitivity(rows, site, tasks or [], params, report, by_process, subsidies)
    return report


def _compute(
    rows: list[dict],
    site: dict,
    tasks: list[dict],
    params: dict[str, dict],
    by_process: dict[str, dict[str, float]] | None = None,
    with_processes: bool = False,
    subsidies: frozenset[str] = frozenset(),
) -> dict:
    by_process = by_process or {}
    p = {key: item["value"] for key, item in params.items()}
    horizon = max(1, int(round(p["horizon_years"])))
    hours = _hours(site)
    tariff = _norm_var(params, "energy_tariff")
    fleet = [_line(row, params, hours, tariff, by_process) for row in rows]
    payroll = _payroll(site, tasks, params)
    operator = _operator_cost(site, params)

    included = [item for item in fleet if item["included"]]
    robots = sum(item["count_used"] for item in included)
    equipment = sum(item["cost_rub"] for item in included)
    shared = {
        "fleet": fleet,
        "included": included,
        "robots": robots,
        "equipment": equipment,
        "hours": hours,
        "payroll": payroll,
        "operator": operator,
        "params": params,
        "p": p,
        "horizon": horizon,
        "by_process": by_process,
        "site": site,
        "tasks": tasks,
        "subsidies": subsidies,
    }
    scenarios = [_asis(shared), _purchase(shared), _raas(shared)]
    result = {
        "subsidies": scenarios[1].pop("support_items", []),
        "disclaimer": DISCLAIMER,
        "fleet": fleet,
        "horizon_years": horizon,
        "robots": robots,
        "payroll": payroll["fig"],
        "hours": hours,
        "operator": operator,
        "scenarios": scenarios,
        "params": list(params.values()),
    }
    if with_processes:
        result["processes"] = _process_views(shared)
    return result


def _line(row: dict, params: dict[str, dict], hours: dict, tariff: dict, by_process: dict | None = None) -> dict:
    local = _merge_params(params, (by_process or {}).get(row.get("process_code") or "") or {})
    p = {key: item["value"] for key, item in local.items()}
    price = _num(row.get("price_rub"))
    count = _num(row.get("count"))
    power_w = _num(row.get("power_w"))
    item = {
        "process_code": row.get("process_code") or "",
        "process_name": row.get("process_name") or "",
        "product_id": row.get("product_id") or "",
        "name": row.get("name") or "",
        "slug": row.get("slug") or "",
        "image_url": row.get("image_url"),
        "price_rub": price,
        "price_used": None,
        "count": count,
        "count_used": None,
        "included": False,
        "note": "",
        "cost_rub": None,
        "raas_available": bool(row.get("raas_available")),
        "kwh_per_hour": None,
        "kwh_source": "",
        "energy_rub": 0.0,
        "fig": None,
    }
    if price is None:
        item["note"] = NO_PRICE
        return item
    n = count if count is not None else 1.0
    if count is None:
        item["note"] = NO_COUNT
    factor = p["price_factor"] / 100
    item["price_used"] = price * factor
    item["count_used"] = n
    item["included"] = True
    item["cost_rub"] = n * price * factor
    kwh, kwh_source = (power_w / 1000, "card") if power_w else (p["energy_kwh"], "norm")
    item["kwh_per_hour"] = kwh
    item["kwh_source"] = kwh_source
    if hours["value"]:
        item["energy_rub"] = n * kwh * hours["value"] * tariff["value"]
    item["fig"] = _fig(
        f"cost:{item['process_code']}",
        item["name"],
        item["cost_rub"],
        "₽",
        r"C_i = N_i \times P_i \times f_{\text{цена}}",
        rf"{_t(n, 1)} \times {_t(price)} \times {_t(factor, 2)} = {_t(item['cost_rub'])}\ \text{{₽}}",
        [
            _var("N_i", "Количество роботов", n, "шт.", "fleet", NO_COUNT if count is None else "Формула количества процесса по параметрам площадки."),
            _var("P_i", "Цена за единицу", price, "₽", "card", "С НДС, без доставки, пусконаладки и интеграции."),
            _norm_var_fraction(p, "price_factor", local),
        ],
    )
    return item


def _payroll(site: dict, tasks: list[dict], params: dict[str, dict]) -> dict:
    p = {key: item["value"] for key, item in params.items()}
    burden_raw = _num(site.get("payroll_burden"))
    burden = burden_raw if burden_raw is not None else 1.0
    factor = p["salary_factor"] / 100
    lines = []
    terms = []
    subst = []
    vars_ = []
    skipped = []
    for count_key, salary_key, label, tag in _ROLES:
        headcount = _num(site.get(count_key))
        salary = _num(site.get(salary_key))
        if headcount is None or headcount <= 0:
            continue
        if salary is None or salary <= 0:
            skipped.append(label)
            continue
        amount = headcount * salary * 12 * burden * factor
        lines.append({"label": label, "headcount": headcount, "salary_month_rub": salary, "rub": amount})
        terms.append(rf"L_{{{tag}}} \times W_{{{tag}}}")
        subst.append(rf"{_t(headcount)} \times {_t(salary)}")
        vars_.append(_var(f"L_{{{tag}}}", f"{label}: численность", headcount, "чел.", "site"))
        vars_.append(_var(f"W_{{{tag}}}", f"{label}: зарплата gross", salary, "₽/мес", "site"))
    if lines:
        total = sum(line["rub"] for line in lines)
        tex = rf"\text{{ФОТ}}_{{\text{{база}}}} = \left({' + '.join(terms)}\right) \times 12 \times k_{{\text{{нач}}}} \times f_{{\text{{ФОТ}}}}"
        sub = rf"\left({' + '.join(subst)}\right) \times 12 \times {_t(burden, 3)} \times {_t(factor, 2)} = {_t(total)}\ \text{{₽}}"
        vars_.append(_var(r"12", "Месяцев в году", 12, "мес.", "calc"))
        vars_.append(_var(r"k_{\text{нач}}", "Коэффициент начислений на ФОТ", burden, "", "site" if burden_raw is not None else "calc",
                          "" if burden_raw is not None else "На площадке не задан, взят 1."))
        vars_.append(_norm_var_fraction(p, "salary_factor", params))
        note = "Роли площадки с численностью и зарплатой."
        if skipped:
            note += f" Без зарплаты на площадке, в ФОТ не входят: {', '.join(item.lower() for item in skipped)}."
        return {"total": total, "lines": lines, "fig": _fig("payroll", "ФОТ ролей до роботизации", total, "₽/год", tex, sub, vars_, note)}

    fte = sum(_num(task.get("staff_fte_now")) or 0 for task in tasks if isinstance(task, dict))
    year_cost = _num(site.get("staff_salary_year_rub"))
    if fte > 0 and year_cost:
        total = fte * year_cost * factor
        lines.append({"label": "Персонал задач объекта", "headcount": fte, "salary_month_rub": year_cost / 12, "rub": total})
        return {
            "total": total,
            "lines": lines,
            "fig": _fig(
                "payroll",
                "ФОТ персонала задач до роботизации",
                total,
                "₽/год",
                r"\text{ФОТ}_{\text{база}} = \sum L_{\text{задач}} \times W_{\text{год}} \times f_{\text{ФОТ}}",
                rf"{_t(fte)} \times {_t(year_cost)} \times {_t(factor, 2)} = {_t(total)}\ \text{{₽}}",
                [
                    _var(r"L_{\text{задач}}", "Сотрудники на задачах объекта сейчас", fte, "чел.", "site"),
                    _var(r"W_{\text{год}}", "Годовая стоимость сотрудника целевой группы с начислениями", year_cost, "₽/год", "site"),
                    _norm_var_fraction(p, "salary_factor", params),
                ],
                "Численность задач объекта и годовая ставка целевой группы.",
            ),
        }
    return {
        "total": 0.0,
        "lines": [],
        "fig": _fig("payroll", "ФОТ ролей до роботизации", 0.0, "₽/год", r"\text{ФОТ}_{\text{база}} = 0", "0", [],
                    "На площадке нет численности и зарплаты ролей. Эффект от замещения не считается.", included=False),
    }


def _operator_cost(site: dict, params: dict[str, dict]) -> dict:
    factor = params["salary_factor"]["value"] / 100
    burden_raw = _num(site.get("payroll_burden"))
    burden = burden_raw if burden_raw is not None else 1.0
    forklift = _num(site.get("forklift_salary_month_rub"))
    if forklift:
        value = forklift * 12 * burden * factor
        return {
            "value": value,
            "tex": r"W_{\text{опер}} = W_{\text{погр}} \times 12 \times k_{\text{нач}} \times f_{\text{ФОТ}}",
            "subst": rf"{_t(forklift)} \times 12 \times {_t(burden, 3)} \times {_t(factor, 2)} = {_t(value)}\ \text{{₽}}",
            "vars": [
                _var(r"W_{\text{погр}}", "Зарплата оператора погрузчика: ближайшая по квалификации роль", forklift, "₽/мес", "site"),
                _var(r"k_{\text{нач}}", "Коэффициент начислений на ФОТ", burden, "", "site" if burden_raw is not None else "calc"),
            ],
        }
    year_cost = _num(site.get("staff_salary_year_rub"))
    if year_cost:
        value = year_cost * factor
        return {
            "value": value,
            "tex": r"W_{\text{опер}} = W_{\text{год}} \times f_{\text{ФОТ}}",
            "subst": rf"{_t(year_cost)} \times {_t(factor, 2)} = {_t(value)}\ \text{{₽}}",
            "vars": [_var(r"W_{\text{год}}", "Годовая стоимость сотрудника целевой группы", year_cost, "₽/год", "site")],
        }
    return {"value": None, "tex": "", "subst": "", "vars": []}


def _hours(site: dict) -> dict:
    shift = _num(site.get("shift_hours"))
    shifts = _num(site.get("shifts_per_day"))
    days = _num(site.get("days_year"))
    if not (shift and shifts and days):
        return {"value": None, "tex": "", "subst": "", "vars": [], "note": "На площадке нет смены, числа смен или рабочих дней."}
    value = shift * shifts * days
    return {
        "value": value,
        "tex": r"H = t_{\text{смены}} \times n_{\text{смен}} \times D",
        "subst": rf"{_t(shift, 1)} \times {_t(shifts)} \times {_t(days)} = {_t(value)}\ \text{{ч}}",
        "vars": [
            _var(r"t_{\text{смены}}", "Длительность смены", shift, "ч", "site"),
            _var(r"n_{\text{смен}}", "Смен в сутки", shifts, "шт.", "site"),
            _var("D", "Рабочих дней в году", days, "дн.", "site"),
        ],
        "note": "",
    }


def _asis(s: dict) -> dict:
    payroll = s["payroll"]["total"]
    horizon = s["horizon"]
    opex = _fig("opex", "Затраты в год", payroll, "₽/год",
                r"\text{OPEX}_{\text{AS-IS}} = \text{ФОТ}_{\text{база}}", rf"= {_t(payroll)}\ \text{{₽}}",
                [_var(r"\text{ФОТ}_{\text{база}}", "ФОТ ролей до роботизации", payroll, "₽/год", "calc")],
                "Текущие эксплуатационные затраты без ФОТ в данных площадки не заданы.")
    tco = payroll * horizon
    return {
        "key": "asis",
        "title": "Без роботизации",
        "subtitle": "Текущие ручные операции, точка сравнения",
        "available": True,
        "note": "",
        "capex": _fig("capex", "CAPEX", 0.0, "₽", r"\text{CAPEX}_{\text{AS-IS}} = 0", "= 0", [], "Вложений нет."),
        "capex_lines": [],
        "opex": opex,
        "opex_lines": [opex],
        "payroll_after": s["payroll"]["fig"],
        "annual_cost": payroll,
        "effect": _fig("effect", "Эффект в год", 0.0, "₽/год", r"\text{Эффект}_{\text{AS-IS}} = 0", "= 0", [], "Базовая точка сравнения."),
        "effect_lines": [],
        "payback": _fig("payback", "Срок окупаемости", None, "лет", r"\text{PBP}_{\text{AS-IS}}\ \text{не считается}", "", [], "Вложений нет."),
        "roi": _fig("roi", "ROI", None, "%", r"\text{ROI}_{\text{AS-IS}}\ \text{не считается}", "", []),
        "tco": _fig("tco", f"TCO за {horizon} лет", tco, "₽", r"\text{TCO}_{\text{AS-IS}} = \text{ФОТ}_{\text{база}} \times T",
                    rf"{_t(payroll)} \times {horizon} = {_t(tco)}\ \text{{₽}}",
                    [_var(r"\text{ФОТ}_{\text{база}}", "ФОТ ролей до роботизации", payroll, "₽/год", "calc"), _t_var(s)]),
        "years": [{"year": year, "cost_rub": payroll * year, "net_rub": 0.0} for year in range(1, horizon + 1)],
        "verdict": "",
    }


def _purchase(s: dict) -> dict:
    equipment = s["equipment"]
    equipment_fig = _equipment_fig(s)
    extras = [_cost_pct_fig(s, key, "обор") for key in _CAPEX_EXTRAS]
    subtotal = equipment + sum(item["value"] or 0 for item in extras)
    reserve_params, reserve_mixed = _param_for_key(s, "reserve_pct")
    reserve = _mixed_reserve(s, _CAPEX_EXTRAS, True) if reserve_mixed else _reserve_fig(reserve_params, subtotal)
    capex_value = subtotal + reserve["value"]
    capex = _fig(
        "capex", "CAPEX", capex_value, "₽",
        r"\text{CAPEX} = C_{\text{обор}} + C_{\text{инфр}} + C_{\text{ПО}} + C_{\text{интегр}} + C_{\text{ПНР}} + C_{\text{обуч}} + C_{\text{рез}}",
        " + ".join(_t(item["value"]) for item in [equipment_fig, *extras, reserve]) + rf" = {_t(capex_value)}\ \text{{₽}}",
        [_var(item["symbol"], item["label"], item["value"], "₽", "calc") for item in [equipment_fig, *extras, reserve]],
        "Доп. статьи — доли от оборудования: каталог их не даёт, стандарт задаётся в админке.",
    )
    support = _support(s, capex_value, equipment)
    capex_lines = [equipment_fig, *extras, reserve]
    if support["once"]:
        net = max(0.0, capex_value - support["once"])
        applied = [item["fig"] for item in support["items"] if item["enabled"] and item["kind"] == "once"]
        capex = _fig(
            "capex", "CAPEX с господдержкой", net, "₽",
            r"\text{CAPEX} = \sum \text{статей} - S_{\text{разовые}}",
            rf"{_t(capex_value)} - {_t(support['once'])} = {_t(net)}\ \text{{₽}}",
            [
                _var(r"\sum \text{статей}", "CAPEX до господдержки", capex_value, "₽", "calc", capex["subst"]),
                *[_var(fig["symbol"], fig["label"], fig["value"], "₽", "calc", fig["subst"]) for fig in applied],
            ],
            f"Разовые меры поддержки уменьшают вложения. {SUPPORT_NOTE}",
        )
        capex_lines += [_negate_support(fig) for fig in applied]
    opex_lines = [
        _cost_pct_fig(s, "service_pct", "обор"),
        _cost_pct_fig(s, "license_pct", "обор"),
        _energy_fig(s),
        _cost_pct_fig(s, "comms_pct", "обор"),
        _cost_pct_fig(s, "consumables_pct", "обор"),
        _cost_pct_fig(s, "repair_pct", "обор"),
        _operators_fig(s),
    ]
    scenario = _robot_scenario(
        s, "purchase", "Покупка", "Полное владение оборудованием",
        capex, capex_lines, opex_lines,
        r"\text{OPEX} = C_{\text{серв}} + C_{\text{лиц}} + C_{\text{эл}} + C_{\text{связь}} + C_{\text{расх}} + C_{\text{рем}} + C_{\text{опер}}",
        note="" if s["included"] else "В парке нет роботов с ценой.",
        support=support,
    )
    scenario["support_items"] = support["items"]
    return scenario


def _raas(s: dict) -> dict:
    extras = [_cost_pct_fig(s, key, "обор") for key in _RAAS_EXTRAS]
    subtotal = sum(item["value"] or 0 for item in extras)
    reserve_params, reserve_mixed = _param_for_key(s, "reserve_pct")
    reserve = _mixed_reserve(s, _RAAS_EXTRAS, False) if reserve_mixed else _reserve_fig(reserve_params, subtotal)
    capex_value = subtotal + reserve["value"]
    capex = _fig(
        "capex", "CAPEX", capex_value, "₽",
        r"\text{CAPEX}_{\text{RaaS}} = C_{\text{инфр}} + C_{\text{интегр}} + C_{\text{ПНР}} + C_{\text{обуч}} + C_{\text{рез}}",
        " + ".join(_t(item["value"]) for item in [*extras, reserve]) + rf" = {_t(capex_value)}\ \text{{₽}}",
        [_var(item["symbol"], item["label"], item["value"], "₽", "calc") for item in [*extras, reserve]],
        "Оборудование и ПО не покупаются: они в арендном платеже. Внедрение на площадке остаётся на заказчике.",
    )
    payment_fig = _raas_payment_fig(s)
    opex_lines = [payment_fig, _energy_fig(s), _cost_pct_fig(s, "comms_pct", "обор"), _operators_fig(s)]
    confirmed = sum(1 for item in s["included"] if item["raas_available"])
    total = len(s["included"])
    note = (
        f"Аренду подтверждает вендор у {confirmed} из {total} роботов, для остальных ставка — стандарт."
        if total else "В парке нет роботов с ценой."
    )
    if s.get("subsidies"):
        note += " Меры господдержки считаются только для покупки."
    return _robot_scenario(
        s, "raas", "Аренда (RaaS)", "Роботы как услуга, платёж вместо покупки",
        capex, [*extras, reserve], opex_lines,
        r"\text{OPEX}_{\text{RaaS}} = C_{\text{RaaS}} + C_{\text{эл}} + C_{\text{связь}} + C_{\text{опер}}",
        note=note,
    )


def _robot_scenario(s, key, title, subtitle, capex, capex_lines, opex_lines, opex_tex, note, support: dict | None = None) -> dict:
    p, horizon = s["p"], s["horizon"]
    support = support or {"once": 0.0, "by_year": lambda _year: 0.0, "year_lines": [], "last_year": 0}
    by_year = support["by_year"]
    payroll = s["payroll"]["total"]
    share = p["replacement_pct"] / 100
    opex_value = sum(item["value"] or 0 for item in opex_lines if item["included"])
    opex = _fig(
        "opex", "OPEX в год", opex_value, "₽/год", opex_tex,
        " + ".join(_t(item["value"] or 0) for item in opex_lines if item["included"]) + rf" = {_t(opex_value)}\ \text{{₽}}",
        [_var(item["symbol"], item["label"], item["value"], "₽/год", "calc") for item in opex_lines if item["included"]],
        "Не вошли: " + ", ".join(item["label"].lower() for item in opex_lines if not item["included"]) + "." if any(not item["included"] for item in opex_lines) else "",
    )
    after_value = payroll * (1 - share)
    after = _fig(
        "payroll_after", "ФОТ после роботизации", after_value, "₽/год",
        r"\text{ФОТ}_{\text{после}} = \text{ФОТ}_{\text{база}} \times (1 - s)",
        rf"{_t(payroll)} \times (1 - {_t(share, 2)}) = {_t(after_value)}\ \text{{₽}}",
        [_var(r"\text{ФОТ}_{\text{база}}", "ФОТ ролей до роботизации", payroll, "₽/год", "calc"), _norm_var_fraction(p, "replacement_pct", s["params"])],
        "Люди, которые остаются на исключениях и контроле.",
    )
    saved = payroll - after_value
    saving = _fig(
        "saving", "Экономия ФОТ", saved, "₽/год",
        r"\Delta\text{ФОТ} = \text{ФОТ}_{\text{база}} - \text{ФОТ}_{\text{после}} = \text{ФОТ}_{\text{база}} \times s",
        rf"{_t(payroll)} \times {_t(share, 2)} = {_t(saved)}\ \text{{₽}}",
        [_var(r"\text{ФОТ}_{\text{база}}", "ФОТ ролей до роботизации", payroll, "₽/год", "calc"), _norm_var_fraction(p, "replacement_pct", s["params"])],
    )
    operational = saved - opex_value
    first_support = by_year(1)
    effect_value = operational + first_support
    effect_vars = [_var(r"\Delta\text{ФОТ}", "Экономия ФОТ", saved, "₽/год", "calc"), _var(r"\text{OPEX}", "Затраты на эксплуатацию парка", opex_value, "₽/год", "calc")]
    if support["year_lines"]:
        effect_vars.append(_var(r"S_{\text{год}}", "Господдержка в первый год", first_support, "₽/год", "calc"))
        effect = _fig(
            "effect", "Эффект в год", effect_value, "₽/год",
            r"\text{Эффект} = \Delta\text{ФОТ} - \text{OPEX} + S_{\text{год}}",
            rf"{_t(saved)} - {_t(opex_value)} + {_t(first_support)} = {_t(effect_value)}\ \text{{₽}}",
            effect_vars,
            f"Первый год. Годовые меры поддержки действуют ограниченный срок, срок окупаемости посчитан по годам. {SUPPORT_NOTE}",
        )
    else:
        effect = _fig(
            "effect", "Эффект в год", effect_value, "₽/год",
            r"\text{Эффект} = \Delta\text{ФОТ} - \text{OPEX}",
            rf"{_t(saved)} - {_t(opex_value)} = {_t(effect_value)}\ \text{{₽}}",
            effect_vars,
            "Файл модели: Эффект = ΔЗатраты + доп. доход − ΔOPEX. Доп. дохода и предотвращённых потерь в данных площадки нет.",
        )
    capex_value = capex["value"]
    payback_value = _payback_years(capex_value, operational, by_year, support["last_year"])
    if support["year_lines"]:
        payback_tex = r"\text{PBP}:\ \sum_{t=1}^{\text{PBP}} \left(\text{Эффект}_0 + S_t\right) = \text{CAPEX}"
        payback_sub = rf"\text{{CAPEX}} = {_t(capex_value)}\ \text{{₽}} \Rightarrow {_t(payback_value, 1)}\ \text{{лет}}" if payback_value is not None else r"\text{Эффект} \le 0 \Rightarrow \text{срока нет}"
    else:
        payback_tex = r"\text{PBP} = \dfrac{\text{CAPEX}}{\text{Эффект}}"
        payback_sub = rf"\dfrac{{{_t(capex_value)}}}{{{_t(effect_value)}}} = {_t(payback_value, 1)}\ \text{{лет}}" if payback_value is not None else r"\text{Эффект} \le 0 \Rightarrow \text{срока нет}"
    payback = _fig(
        "payback", "Срок окупаемости", payback_value, "лет",
        payback_tex,
        payback_sub,
        [_var(r"\text{CAPEX}", "Капитальные затраты", capex_value, "₽", "calc"), _var(r"\text{Эффект}", "Эффект в год", effect_value, "₽/год", "calc")],
        "" if payback_value is not None else "Эффект не покрывает вложения: срока окупаемости нет.",
    )
    support_total = sum(by_year(year) for year in range(1, horizon + 1))
    gain = operational * horizon + support_total
    roi_value = gain / capex_value * 100 if capex_value > 0 else None
    roi = _fig(
        "roi", f"ROI за {horizon} лет", roi_value, "%",
        r"\text{ROI} = \dfrac{\text{Эффект} \times T + \sum S_t}{\text{CAPEX}} \times 100\%" if support_total else r"\text{ROI} = \dfrac{\text{Эффект} \times T}{\text{CAPEX}} \times 100\%",
        rf"\dfrac{{{_t(gain)}}}{{{_t(capex_value)}}} \times 100\% = {_t(roi_value, 0)}\%" if roi_value is not None else "",
        [_var(r"\text{Эффект}", "Эффект в год", operational, "₽/год", "calc"), _t_var(s), _var(r"\text{CAPEX}", "Капитальные затраты", capex_value, "₽", "calc")],
    )
    annual = opex_value + after_value
    tco_value = capex_value + annual * horizon - support_total
    tco = _fig(
        "tco", f"TCO за {horizon} лет", tco_value, "₽",
        r"\text{TCO} = \text{CAPEX} + (\text{OPEX} + \text{ФОТ}_{\text{после}}) \times T - \sum S_t" if support_total else r"\text{TCO} = \text{CAPEX} + (\text{OPEX} + \text{ФОТ}_{\text{после}}) \times T",
        rf"{_t(capex_value)} + ({_t(opex_value)} + {_t(after_value)}) \times {horizon}" + (rf" - {_t(support_total)}" if support_total else "") + rf" = {_t(tco_value)}\ \text{{₽}}",
        [
            _var(r"\text{CAPEX}", "Капитальные затраты", capex_value, "₽", "calc"),
            _var(r"\text{OPEX}", "Эксплуатация парка", opex_value, "₽/год", "calc"),
            _var(r"\text{ФОТ}_{\text{после}}", "ФОТ оставшихся людей", after_value, "₽/год", "calc"),
            _t_var(s),
            *([_var(r"\sum S_t", "Годовая господдержка за горизонт", support_total, "₽", "calc")] if support_total else []),
        ],
        "Оставшийся ФОТ входит в TCO, чтобы сценарии сравнивались с базой на одной шкале. Замена узлов не добавлена: срока службы в карточках нет.",
    )
    cumulative = [0.0]
    for year in range(1, horizon + 1):
        cumulative.append(cumulative[-1] + by_year(year))
    return {
        "key": key,
        "title": title,
        "subtitle": subtitle,
        "available": bool(s["included"]),
        "note": note,
        "capex": capex,
        "capex_lines": capex_lines,
        "opex": opex,
        "opex_lines": opex_lines,
        "payroll_after": after,
        "annual_cost": annual,
        "effect": effect,
        "effect_lines": [saving, _negate(opex), *support["year_lines"]],
        "payback": payback,
        "roi": roi,
        "tco": tco,
        "years": [
            {"year": year, "cost_rub": capex_value + annual * year - cumulative[year], "net_rub": operational * year + cumulative[year] - capex_value}
            for year in range(1, horizon + 1)
        ],
        "verdict": _verdict(payback_value),
    }


def _equipment_fig(s: dict) -> dict:
    included = s["included"]
    params, mixed = _param_for_key(s, "price_factor")
    factor = params["price_factor"]["value"] / 100
    if mixed:
        terms = " + ".join(_t(item["cost_rub"]) for item in included) or "0"
        sub = rf"{terms} = {_t(s['equipment'])}\ \text{{₽}}"
        tex = r"C_{\text{обор}} = \sum_i N_i \times P_i \times f_{\text{цена},i}"
        factor_var = _var(r"f_{\text{цена},i}", "Коэффициент цены процесса", None, "", "project", "Задан отдельно по процессам.")
    elif len(included) <= 4:
        terms = " + ".join(rf"{_t(item['count_used'], 1)} \times {_t(item['price_rub'])}" for item in included) or "0"
        sub = rf"\left({terms}\right) \times {_t(factor, 2)} = {_t(s['equipment'])}\ \text{{₽}}"
        tex = r"C_{\text{обор}} = \sum_i N_i \times P_i \times f_{\text{цена}}"
        factor_var = _norm_var_fraction({"price_factor": params["price_factor"]["value"]}, "price_factor", params)
    else:
        sub = rf"\sum_{{i=1}}^{{{len(included)}}} N_i P_i \times {_t(factor, 2)} = {_t(s['equipment'])}\ \text{{₽}}"
        tex = r"C_{\text{обор}} = \sum_i N_i \times P_i \times f_{\text{цена}}"
        factor_var = _norm_var_fraction({"price_factor": params["price_factor"]["value"]}, "price_factor", params)
    skipped = [item for item in s["fleet"] if not item["included"]]
    note = f"{len(included)} роботов с ценой, {_t_plain(s['robots'])} шт."
    if skipped:
        note += f" Без цены и не входят: {', '.join(item['name'] for item in skipped)}."
    fig = _fig(
        "equipment", "Оборудование", s["equipment"], "₽",
        tex, sub,
        [
            _var("N_i", "Количество роботов процесса", None, "шт.", "fleet"),
            _var("P_i", "Цена робота за единицу", None, "₽", "card"),
            factor_var,
        ],
        note,
    )
    fig["symbol"] = r"C_{\text{обор}}"
    return fig


def _pct_fig(params: dict, key: str, base: float, base_tag: str) -> dict:
    norm = params[key]
    rate = norm["value"] / 100
    value = base * rate
    tag = norm["symbol"].replace("k_", "C_", 1)
    fig = _fig(
        key.replace("_pct", ""), norm["label"], value, "₽/год" if norm["group"] == "opex" else "₽",
        rf"{tag} = C_{{\text{{{base_tag}}}}} \times {norm['symbol']}",
        rf"{_t(base)} \times {_t(norm['value'], 2)}\% = {_t(value)}\ \text{{₽}}",
        [_var(rf"C_{{\text{{{base_tag}}}}}", "Стоимость оборудования", base, "₽", "calc"), _norm_var(params, key)],
        norm["rationale"],
    )
    fig["symbol"] = tag
    return fig


def _reserve_fig(params: dict, subtotal: float) -> dict:
    norm = params["reserve_pct"]
    value = subtotal * norm["value"] / 100
    fig = _fig(
        "reserve", "Резерв", value, "₽",
        r"C_{\text{рез}} = \left(\sum \text{статей}\right) \times k_{\text{рез}}",
        rf"{_t(subtotal)} \times {_t(norm['value'], 2)}\% = {_t(value)}\ \text{{₽}}",
        [_var(r"\sum \text{статей}", "Сумма статей CAPEX до резерва", subtotal, "₽", "calc"), _norm_var(params, "reserve_pct")],
        norm["rationale"],
    )
    fig["symbol"] = r"C_{\text{рез}}"
    return fig


def _energy_fig(s: dict) -> dict:
    hours = s["hours"]
    tariff = _norm_var(s["params"], "energy_tariff")
    if not hours["value"]:
        fig = _fig("energy", "Электроэнергия", None, "₽/год", r"C_{\text{эл}} = \sum_i N_i \times e_i \times H \times \tau", "", [], hours["note"], included=False)
        fig["symbol"] = r"C_{\text{эл}}"
        return fig
    value = sum(item["energy_rub"] for item in s["included"])
    kwh = sum(item["count_used"] * item["kwh_per_hour"] for item in s["included"])
    from_card = [item["name"] for item in s["included"] if item["kwh_source"] == "card"]
    fig = _fig(
        "energy", "Электроэнергия", value, "₽/год",
        r"C_{\text{эл}} = \sum_i N_i \times e_i \times H \times \tau",
        rf"{_t(kwh, 1)} \times {_t(hours['value'])} \times {_t(tariff['value'], 2)} = {_t(value)}\ \text{{₽}}",
        [
            _var(r"\sum N_i e_i", "Потребление парка за час работы", kwh, "кВт·ч", "calc"),
            _norm_var(s["params"], "energy_kwh"),
            *hours["vars"],
            _var("H", "Часов работы в год", hours["value"], "ч", "calc", hours["subst"]),
            tariff,
        ],
        ("Мощность из карточки: " + ", ".join(from_card) + ". Остальным — стандарт e.") if from_card else "Мощности в карточках нет, у всех роботов стандарт e.",
    )
    fig["symbol"] = r"C_{\text{эл}}"
    return fig


def _operators_fig(s: dict) -> dict:
    if "operator_fixed" in s:
        value = s["operator_fixed"] or 0
        if value <= 0:
            fig = _fig("operators", "Персонал эксплуатации", None, "₽/год", r"C_{\text{опер}} = 0", "", [],
                       "Доля персонала эксплуатации на этот процесс не выделяется.", included=False)
            fig["symbol"] = r"C_{\text{опер}}"
            return fig
        fig = _fig(
            "operators", "Персонал эксплуатации", value, "₽/год",
            r"C_{\text{опер}} = C_{\text{опер парка}} \times \dfrac{N_i}{N}",
            rf"= {_t(value)}\ \text{{₽}}",
            [_var(r"C_{\text{опер парка}}", "Персонал эксплуатации парка, доля процесса по числу роботов", value, "₽/год", "calc")],
            "Доля общего персонала эксплуатации парка, пропорционально числу роботов процесса.",
        )
        fig["symbol"] = r"C_{\text{опер}}"
        return fig
    per = s["p"]["robots_per_operator"]
    operator = s["operator"]
    if not s["robots"] or operator["value"] is None:
        fig = _fig("operators", "Персонал эксплуатации", None, "₽/год", r"C_{\text{опер}} = \lceil N / m \rceil \times W_{\text{опер}}", "", [],
                   "Нет зарплаты подходящей роли на площадке." if s["robots"] else "Роботов нет.", included=False)
        fig["symbol"] = r"C_{\text{опер}}"
        return fig
    people = math.ceil(s["robots"] / per)
    value = people * operator["value"]
    fig = _fig(
        "operators", "Персонал эксплуатации", value, "₽/год",
        r"C_{\text{опер}} = \left\lceil \dfrac{N}{m} \right\rceil \times W_{\text{опер}}",
        rf"\left\lceil \dfrac{{{_t(s['robots'])}}}{{{_t(per)}}} \right\rceil \times {_t(operator['value'])} = {people} \times {_t(operator['value'])} = {_t(value)}\ \text{{₽}}",
        [
            _var("N", "Роботов в парке", s["robots"], "шт.", "fleet"),
            _norm_var(s["params"], "robots_per_operator"),
            _var(r"W_{\text{опер}}", "Годовая стоимость оператора", operator["value"], "₽/год", "calc", operator["subst"]),
            *operator["vars"],
        ],
        f"{people} операторов или диспетчеров парка.",
    )
    fig["symbol"] = r"C_{\text{опер}}"
    return fig


def _negate(fig: dict) -> dict:
    out = dict(fig)
    out["key"] = "opex_minus"
    out["label"] = "Минус OPEX парка"
    out["value"] = -(fig["value"] or 0)
    return out


def _negate_support(fig: dict) -> dict:
    out = dict(fig)
    out["label"] = f"Минус {fig['label'].lower()}"
    out["value"] = -(fig["value"] or 0)
    return out


def _payback_years(capex: float, operational: float, by_year, last_year: int) -> float | None:
    if capex <= 0:
        return None
    total = 0.0
    year = 0
    while year < 200:
        year += 1
        gain = operational + by_year(year)
        if gain > 0 and total + gain >= capex:
            return year - 1 + (capex - total) / gain
        total += gain
        if year >= last_year and operational <= 0:
            return None
    return None


def _support(s: dict, capex_gross: float, equipment: float) -> dict:
    """Меры господдержки для покупки. Считаются все, в расчёт входят только включённые."""
    params = s["params"]
    v = {key: params[key]["value"] for key in params if params[key]["group"] == "subsidy"}
    on = s.get("subsidies") or frozenset()
    items: list[dict] = []

    mpt_limit = v["mpt_limit_mln"] * 1_000_000
    mpt_raw = equipment * v["mpt_rate_pct"] / 100
    mpt = min(mpt_raw, mpt_limit)
    mpt_fig = _fig(
        "subsidy_mpt", "Субсидия Минпромторга", mpt, "₽",
        r"S_{\text{МПТ}} = \min\left(k_{\text{МПТ}} \times C_{\text{обор}},\ L_{\text{МПТ}}\right)",
        rf"\min\left({_t(v['mpt_rate_pct'], 1)}\% \times {_t(equipment)},\ {_t(mpt_limit)}\right) = {_t(mpt)}\ \text{{₽}}",
        [_var(r"C_{\text{обор}}", "Стоимость оборудования", equipment, "₽", "calc"), _norm_var(params, "mpt_rate_pct"), _norm_var(params, "mpt_limit_mln")],
        "Упёрлись в лимит программы." if mpt_raw > mpt_limit else "",
    )
    mpt_fig["symbol"] = r"S_{\text{МПТ}}"

    leasing = equipment * v["leasing_discount_pct"] / 100
    leasing_fig = _fig(
        "subsidy_leasing", "Скидка по ПП № 649", leasing, "₽",
        r"S_{\text{лиз}} = k_{\text{лиз}} \times C_{\text{обор}}",
        rf"{_t(v['leasing_discount_pct'], 1)}\% \times {_t(equipment)} = {_t(leasing)}\ \text{{₽}}",
        [_var(r"C_{\text{обор}}", "Стоимость техники", equipment, "₽", "calc"), _norm_var(params, "leasing_discount_pct")],
        "Скидка единовременная, в счёт аванса по договору лизинга.",
    )
    leasing_fig["symbol"] = r"S_{\text{лиз}}"

    moscow_limit = v["moscow_limit_mln"] * 1_000_000
    moscow_raw = equipment * v["moscow_rate_pct"] / 100
    moscow = min(moscow_raw, moscow_limit)
    moscow_fig = _fig(
        "subsidy_moscow", "Субсидия Москвы на лизинг", moscow, "₽",
        r"S_{\text{Мск}} = \min\left(k_{\text{Мск}} \times B_{\text{лиз}},\ L_{\text{Мск}}\right)",
        rf"\min\left({_t(v['moscow_rate_pct'], 1)}\% \times {_t(equipment)},\ {_t(moscow_limit)}\right) = {_t(moscow)}\ \text{{₽}}",
        [_var(r"B_{\text{лиз}}", "База лизинга: стоимость оборудования", equipment, "₽", "calc"), _norm_var(params, "moscow_rate_pct"), _norm_var(params, "moscow_limit_mln")],
        "Упёрлись в годовой лимит на предприятие." if moscow_raw > moscow_limit else "",
    )
    moscow_fig["symbol"] = r"S_{\text{Мск}}"

    once_values = {"mpt": (mpt, mpt_fig), "leasing": (leasing, leasing_fig), "moscow": (moscow, moscow_fig)}
    once = sum(value for code, (value, _fig_) in once_values.items() if code in on)
    capex_net = max(0.0, capex_gross - once)

    spread = max(0.0, v["market_rate_pct"] - v["frp_rate_pct"]) / 100
    loan = capex_net * v["frp_share_pct"] / 100
    frp_year = spread * loan
    frp_term = max(1, int(round(v["frp_term_years"])))
    frp_fig = _fig(
        "subsidy_frp", "Выгода займа ФРП", frp_year, "₽/год",
        r"S_{\text{ФРП}} = (r_{\text{рын}} - r_{\text{ФРП}}) \times d_{\text{ФРП}} \times \text{CAPEX}",
        rf"({_t(v['market_rate_pct'], 1)}\% - {_t(v['frp_rate_pct'], 1)}\%) \times {_t(v['frp_share_pct'])}\% \times {_t(capex_net)} = {_t(frp_year)}\ \text{{₽}}",
        [_norm_var(params, "market_rate_pct"), _norm_var(params, "frp_rate_pct"), _norm_var(params, "frp_share_pct"), _var(r"\text{CAPEX}", "Вложения после разовых мер", capex_net, "₽", "calc"), _norm_var(params, "frp_term_years")],
        f"Каждый год в течение {frp_term} лет займа.",
    )
    frp_fig["symbol"] = r"S_{\text{ФРП}}"

    life = max(1.0, v["service_life_years"])
    factor = max(1.0, v["accel_factor"])
    tax = v["profit_tax_pct"] / 100
    normal = capex_gross / life
    fast = capex_gross * factor / life
    amort_years: list[float] = []
    left = capex_gross
    while left > 1e-6 and len(amort_years) < 200:
        deduction = min(fast, left)
        left -= deduction
        amort_years.append(max(0.0, deduction - normal) * tax)
    amort_first = amort_years[0] if amort_years else 0.0
    amort_fig = _fig(
        "subsidy_amort", "Экономия на налоге", amort_first, "₽/год",
        r"S_{\text{ам}} = \left(\dfrac{\text{CAPEX}}{T_{\text{сл}}} \times K_{\text{уск}} - \dfrac{\text{CAPEX}}{T_{\text{сл}}}\right) \times t_{\text{приб}}",
        rf"\left(\dfrac{{{_t(capex_gross)}}}{{{_t(life)}}} \times {_t(factor, 1)} - \dfrac{{{_t(capex_gross)}}}{{{_t(life)}}}\right) \times {_t(v['profit_tax_pct'])}\% = {_t(amort_first)}\ \text{{₽}}",
        [_var(r"\text{CAPEX}", "Вложения до господдержки", capex_gross, "₽", "calc"), _norm_var(params, "service_life_years"), _norm_var(params, "accel_factor"), _norm_var(params, "profit_tax_pct")],
        f"Первый год. Экономия идёт {sum(1 for value in amort_years if value > 0)} г., пока оборудование не списано полностью, потом становится 0.",
    )
    amort_fig["symbol"] = r"S_{\text{ам}}"

    def year_value(code: str, year: int) -> float:
        if code == "frp":
            return frp_year if year <= frp_term else 0.0
        if code == "amort":
            return amort_years[year - 1] if year <= len(amort_years) else 0.0
        return 0.0

    def by_year(year: int) -> float:
        return sum(year_value(code, year) for code in ("frp", "amort") if code in on)

    horizon = s["horizon"]
    figs = {"mpt": mpt_fig, "leasing": leasing_fig, "moscow": moscow_fig, "frp": frp_fig, "amort": amort_fig}
    for code, label, subtitle, kind, keys in SUBSIDIES:
        fig = figs[code]
        total = fig["value"] if kind == "once" else sum(year_value(code, year) for year in range(1, horizon + 1))
        items.append({
            "code": code,
            "label": label,
            "subtitle": subtitle,
            "kind": kind,
            "enabled": code in on,
            "value": fig["value"],
            "total": total,
            "params": list(keys),
            "fig": fig,
        })
    year_lines = [figs[code] for code in ("frp", "amort") if code in on]
    last_year = max([frp_term if "frp" in on else 0, len(amort_years) if "amort" in on else 0])
    return {"once": once, "by_year": by_year, "year_lines": year_lines, "last_year": last_year, "items": items}


def _sensitivity(
    rows: list[dict],
    site: dict,
    tasks: list[dict],
    params: dict[str, dict],
    report: dict,
    by_process: dict[str, dict[str, float]] | None = None,
    subsidies: frozenset[str] = frozenset(),
) -> list[dict]:
    base = _metric(report)
    out = []
    for key in _SENSITIVE:
        current = params[key]["value"]
        if not current:
            continue
        values = []
        for mult in (0.8, 1.2):
            changed = {k: dict(v) for k, v in params.items()}
            changed[key]["value"] = current * mult
            values.append(_metric(_compute(rows, site, tasks, changed, by_process, subsidies=subsidies)))
        out.append({
            "key": key,
            "label": params[key]["label"],
            "unit": params[key]["unit"],
            "value": current,
            "low_value": current * 0.8,
            "high_value": current * 1.2,
            "payback_low": values[0]["payback"],
            "payback_high": values[1]["payback"],
            "effect_low": values[0]["effect"],
            "effect_high": values[1]["effect"],
            "payback": base["payback"],
            "effect": base["effect"],
            "swing": _swing(values[0]["payback"], values[1]["payback"]),
        })
    out.sort(key=lambda item: (item["swing"] is not None, -(item["swing"] or 0)))
    return out


def _swing(low: float | None, high: float | None) -> float | None:
    if low is None or high is None:
        return None
    return abs(high - low)


def _metric(report: dict) -> dict:
    purchase = next(item for item in report["scenarios"] if item["key"] == "purchase")
    return {"payback": purchase["payback"]["value"], "effect": purchase["effect"]["value"]}


def _verdict(payback: float | None) -> str:
    if payback is None:
        return "Окупаемости нет: эффект не покрывает вложения."
    if payback <= 3:
        return "До 3 лет: по ТЗ решение целесообразно."
    if payback <= 5:
        return "3–5 лет: по ТЗ требуется анализ рисков."
    return "Больше 5 лет: по ТЗ нужно отдельное обоснование."


def _fig(key, label, value, unit, tex, subst, vars_, note="", included=True) -> dict:
    return {"key": key, "label": label, "value": value, "unit": unit, "tex": tex, "subst": subst, "vars": vars_, "note": note, "included": included, "symbol": ""}


def _var(symbol: str, label: str, value, unit: str, source: str, note: str = "") -> dict:
    return {"symbol": symbol, "label": label, "value": value, "unit": unit, "source": source, "source_label": SOURCES.get(source, source), "note": note}


def _norm_var(params: dict, key: str) -> dict:
    norm = params[key]
    note = norm["rationale"]
    if norm["source"] == "project":
        note = f"Стандарт {_t_plain(norm['standard'])} {norm['unit']}. {note}"
    return _var(norm["symbol"], norm["label"], norm["value"], norm["unit"], norm["source"], note)


def _norm_var_fraction(p: dict, key: str, params: dict | None = None) -> dict:
    norm = NORM_BY_KEY[key]
    value = p[key] / 100
    source = params[key]["source"] if params else "norm"
    rationale = params[key]["rationale"] if params else norm.rationale
    return _var(norm.symbol, f"{norm.label}, доля", value, "", source, f"{_t_plain(p[key])} {norm.unit}. {rationale}")


def _t_var(s: dict) -> dict:
    return _norm_var(s["params"], "horizon_years")


def _t(value, digits: int = 0) -> str:
    if value is None:
        return r"\text{—}"
    text = f"{value:,.{digits}f}"
    if digits:
        text = text.rstrip("0").rstrip(".")
    return text.replace(",", "\x00").replace(".", "{,}").replace("\x00", r"\,")


def _t_plain(value) -> str:
    if value is None:
        return "—"
    text = f"{value:,.2f}".rstrip("0").rstrip(".")
    return text.replace(",", " ").replace(".", ",")


def _num(raw: object) -> float | None:
    if raw is None or raw == "" or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    try:
        return float(str(raw).replace(" ", "").replace(",", "."))
    except ValueError:
        return None


def _merge_params(params: dict[str, dict], own: dict[str, float]) -> dict[str, dict]:
    if not own:
        return params
    merged = dict(params)
    for key, raw in own.items():
        if key not in params or key not in PROCESS_TUNABLE:
            continue
        norm = NORM_BY_KEY[key]
        value = min(norm.max, max(norm.min, float(raw)))
        item = dict(params[key])
        item["value"] = value
        item["source"] = "project"
        item["overridden"] = True
        merged[key] = item
    return merged


def _local_params(s: dict, process_code: str) -> dict[str, dict]:
    own = (s.get("by_process") or {}).get(process_code) or {}
    return _merge_params(s["params"], own)


def _param_for_key(s: dict, key: str) -> tuple[dict[str, dict], bool]:
    included = s.get("included") or []
    if not included:
        return s["params"], False
    locals_ = [_local_params(s, item["process_code"]) for item in included]
    first = locals_[0][key]["value"]
    mixed = any(abs(item[key]["value"] - first) > 1e-6 for item in locals_[1:])
    if mixed:
        return s["params"], True
    return locals_[0], False


def _cost_pct_fig(s: dict, key: str, base_tag: str) -> dict:
    params, mixed = _param_for_key(s, key)
    if not mixed:
        return _pct_fig(params, key, s["equipment"], base_tag)
    total = 0.0
    for item in s["included"]:
        local = _local_params(s, item["process_code"])
        total += (item["cost_rub"] or 0) * local[key]["value"] / 100
    norm = s["params"][key]
    tag = norm["symbol"].replace("k_", "C_", 1)
    fig = _fig(
        key.replace("_pct", ""),
        norm["label"],
        total,
        "₽/год" if norm["group"] == "opex" else "₽",
        rf"{tag} = \sum_i C_i \times {norm['symbol']}_i",
        rf"= {_t(total)}\ \text{{₽}}",
        [_var(norm["symbol"], norm["label"], None, norm["unit"], "project", "Ставка задана отдельно по процессам.")],
        f"{norm['rationale']} Ставки различаются по процессам.",
    )
    fig["symbol"] = tag
    return fig


def _mixed_reserve(s: dict, extra_keys: tuple[str, ...], include_equipment: bool) -> dict:
    total = 0.0
    for item in s["included"]:
        local = _local_params(s, item["process_code"])
        cost = item["cost_rub"] or 0
        part = cost if include_equipment else 0.0
        part += sum(cost * local[key]["value"] / 100 for key in extra_keys)
        total += part * local["reserve_pct"]["value"] / 100
    norm = s["params"]["reserve_pct"]
    fig = _fig(
        "reserve", "Резерв", total, "₽",
        r"C_{\text{рез}} = \sum_i \left(\text{статьи}_i \times k_{\text{рез},i}\right)",
        rf"= {_t(total)}\ \text{{₽}}",
        [_norm_var(s["params"], "reserve_pct")],
        f"{norm['rationale']} Ставка резерва различается по процессам.",
    )
    fig["symbol"] = r"C_{\text{рез}}"
    return fig


def _raas_payment_fig(s: dict) -> dict:
    equipment = s["equipment"]
    params, mixed = _param_for_key(s, "raas_rate_pct")
    if not mixed:
        rate = params["raas_rate_pct"]["value"]
        payment = equipment * rate / 100 * 12
        return _fig(
            "raas_payment", "Арендный платёж", payment, "₽/год",
            r"C_{\text{RaaS}} = \sum_i N_i \times P_i \times f_{\text{цена}} \times k_{\text{RaaS}} \times 12",
            rf"{_t(equipment)} \times {_t(rate, 2)}\% \times 12 = {_t(payment)}\ \text{{₽}}",
            [
                _var(r"\sum N_i P_i f_{\text{цена}}", "Стоимость парка по ценам карточек", equipment, "₽", "calc"),
                _norm_var(params, "raas_rate_pct"),
                _var("12", "Месяцев в году", 12, "мес.", "calc"),
            ],
            "Файл модели: Платёж = Ставка_фикс + Ставка_за_использование × Объём. Здесь только фиксированная часть: ставок за использование в каталоге нет.",
        ) | {"symbol": r"C_{\text{RaaS}}"}
    payment = 0.0
    for item in s["included"]:
        local = _local_params(s, item["process_code"])
        payment += (item["cost_rub"] or 0) * local["raas_rate_pct"]["value"] / 100 * 12
    fig = _fig(
        "raas_payment", "Арендный платёж", payment, "₽/год",
        r"C_{\text{RaaS}} = \sum_i C_i \times k_{\text{RaaS},i} \times 12",
        rf"= {_t(payment)}\ \text{{₽}}",
        [_var(r"k_{\text{RaaS},i}", "Ставка аренды процесса", None, "% цены робота в месяц", "project", "Задана отдельно по процессам.")],
        "Ставка аренды различается по процессам. В каталоге нет ставки за использование, только фиксированная часть.",
    )
    fig["symbol"] = r"C_{\text{RaaS}}"
    return fig


def _shares(included: list[dict], tasks: list[dict]) -> tuple[dict[str, float], str]:
    codes: list[str] = []
    for item in included:
        if item["process_code"] not in codes:
            codes.append(item["process_code"])
    ftes: dict[str, float] = {}
    for task in tasks:
        if not isinstance(task, dict):
            continue
        code = str(task.get("process_code") or "")
        fte = _num(task.get("staff_fte_now"))
        if code in codes and fte and fte > 0:
            ftes[code] = ftes.get(code, 0.0) + fte
    if ftes:
        total = sum(ftes.values())
        return {code: ftes.get(code, 0.0) / total for code in codes}, _SHARE_FTE
    n = len(codes) or 1
    return {code: 1 / n for code in codes}, _SHARE_EQUAL


def _reprice(item: dict, params: dict[str, dict], s: dict) -> dict:
    clone = dict(item)
    factor = params["price_factor"]["value"] / 100
    count = item["count_used"] or 0
    price = item["price_rub"] or 0
    kwh = item["kwh_per_hour"] or 0 if item.get("kwh_source") == "card" else params["energy_kwh"]["value"]
    hours = (s.get("hours") or {}).get("value") or 0
    clone["cost_rub"] = count * price * factor
    clone["price_used"] = price * factor
    clone["kwh_per_hour"] = kwh
    clone["energy_rub"] = count * kwh * hours * params["energy_tariff"]["value"]
    return clone


def _scaled_payroll(payroll: dict, share: float, note: str) -> dict:
    total = payroll["total"] * share
    fig = _fig(
        "payroll",
        "Доля ФОТ процесса",
        total,
        "₽/год",
        r"\text{ФОТ}_{\text{проц}} = \text{ФОТ}_{\text{база}} \times \alpha",
        rf"{_t(payroll['total'])} \times {_t(share, 2)} = {_t(total)}\ \text{{₽}}",
        [
            _var(r"\text{ФОТ}_{\text{база}}", "ФОТ площадки до роботизации", payroll["total"], "₽/год", "calc"),
            _var(r"\alpha", "Доля процесса в экономии на персонале", share, "", "calc", note),
        ],
        note,
    )
    return {"total": total, "lines": [], "fig": fig}


def _process_bundle(
    s: dict,
    item: dict,
    share: float,
    note: str,
    params: dict[str, dict],
    full: bool = True,
    subsidies: frozenset[str] | None = None,
) -> tuple[dict, dict, dict, dict]:
    payroll = _payroll(s["site"], s["tasks"], params)
    operator = _operator_cost(s["site"], params)
    probe = {
        "p": {key: value["value"] for key, value in params.items()},
        "params": params,
        "robots": s["robots"],
        "operator": operator,
        "included": s["included"],
    }
    operator_total = _operators_fig(probe)["value"] or 0
    robots = s["robots"] or 0
    allocated = (item["count_used"] / robots * operator_total) if robots else 0
    clone = _reprice(item, params, s)
    one = {
        "fleet": [clone],
        "included": [clone],
        "robots": clone["count_used"] or 0,
        "equipment": clone["cost_rub"] or 0,
        "hours": s["hours"],
        "payroll": _scaled_payroll(payroll, share, note),
        "operator": operator,
        "params": params,
        "p": {key: value["value"] for key, value in params.items()},
        "horizon": s["horizon"],
        "by_process": {},
        "operator_fixed": allocated,
        "site": s["site"],
        "tasks": s["tasks"],
        "subsidies": (s.get("subsidies") or frozenset()) if subsidies is None else subsidies,
    }
    purchase = _purchase(one)
    if not full:
        return one, {}, purchase, {}
    return one, _asis(one), purchase, _raas(one)


def _meets(purchase: dict, horizon: int) -> bool:
    effect = purchase["effect"]["value"] or 0
    capex = purchase["capex"]["value"] or 0
    payback = purchase["payback"]["value"]
    if effect <= 0:
        return False
    if capex <= 0:
        return True
    return payback is not None and payback <= horizon + 1e-6


def _profit_status(purchase: dict, horizon: int) -> tuple[bool, str]:
    if _meets(purchase, horizon):
        payback = purchase["payback"]["value"]
        if payback is None:
            return True, "Вложений нет, эффект в год положительный."
        return True, f"Покупка окупается за {_t_plain(payback)} лет — в пределах горизонта {horizon} лет."
    effect = purchase["effect"]["value"] or 0
    if effect <= 0:
        return False, "Покупка невыгодна: годовые затраты процесса больше его доли экономии на персонале."
    payback = purchase["payback"]["value"]
    if payback is None:
        return False, "Покупка не окупается: эффект не покрывает вложения."
    return False, f"Покупка не окупается за горизонт {horizon} лет: срок {_t_plain(payback)} лет."


def _snap(value: float, step: float, lo: float, hi: float) -> float:
    if step <= 0:
        return min(hi, max(lo, value))
    steps = int((value - lo) / step + 1e-9 + 0.5)
    snapped = min(hi, max(lo, lo + steps * step))
    return round(snapped, 6)


def _round_step(value: float, step: float) -> float:
    if step >= 1:
        return float(round(value))
    return float(round(value, 1 if step >= 0.1 else 2))


def _with_param(params: dict[str, dict], key: str, value: float) -> dict[str, dict]:
    out = {name: dict(item) for name, item in params.items()}
    item = dict(out[key])
    item["value"] = value
    item["source"] = "project"
    item["overridden"] = True
    out[key] = item
    return out


def _closest(lo: float, hi: float, step: float, current: float, direction: int, meets) -> float | None:
    left = lo if direction < 0 else current
    right = current if direction < 0 else hi
    best = None
    for _ in range(24):
        if right - left < step * 0.5:
            break
        mid = _snap((left + right) / 2, step, lo, hi)
        if mid <= left + 1e-9 or mid >= right - 1e-9:
            mid = _snap(left + step if direction > 0 else right - step, step, lo, hi)
            if mid <= left + 1e-9 or mid >= right - 1e-9:
                break
        if meets(mid):
            best = mid
            if direction < 0:
                left = mid
            else:
                right = mid
        elif direction < 0:
            right = mid
        else:
            left = mid
    bound = _snap(lo if direction < 0 else hi, step, lo, hi)
    if best is None and meets(bound):
        best = bound
    if best is None or abs(best - current) < step * 0.5:
        return None
    return best


def _suggestions(s: dict, item: dict, share: float, note: str, params: dict[str, dict]) -> list[dict]:
    found = []
    horizon = s["horizon"]
    for key, direction, scope in _SUGGEST:
        if key == "energy_kwh" and item.get("kwh_source") == "card":
            continue
        if key == "energy_tariff" and not (s.get("hours") or {}).get("value"):
            continue
        norm = params[key]
        current = norm["value"]
        lo, hi, step = norm["min"], norm["max"], norm["step"] or 1

        def meets(value: float, key: str = key) -> bool:
            _one, _asis, purchase, _raas = _process_bundle(s, item, share, note, _with_param(params, key, value), full=False)
            return _meets(purchase, horizon)

        target = _closest(lo, hi, step, current, direction, meets)
        if target is None:
            continue
        _one, _asis, purchase, _raas = _process_bundle(s, item, share, note, _with_param(params, key, target), full=False)
        span = hi - lo or 1
        found.append({
            "key": key,
            "label": norm["label"],
            "unit": norm["unit"],
            "scope": scope,
            "from": _round_step(current, step),
            "to": _round_step(target, step),
            "effect": purchase["effect"]["value"],
            "payback": purchase["payback"]["value"],
            "_rank": abs(target - current) / span + (0 if scope == "process" else 0.01),
        })
    found.sort(key=lambda row: row["_rank"])
    found = found[:3]
    on = s.get("subsidies") or frozenset()
    labels = {code: label for code, label, _subtitle, _kind, _keys in SUBSIDIES}
    singles = []
    for code in SUBSIDY_CODES:
        if code in on:
            continue
        _one, _asis, purchase, _raas = _process_bundle(s, item, share, note, params, full=False, subsidies=on | {code})
        singles.append((code, purchase))
        if _meets(purchase, horizon):
            found.append(_subsidy_hint([code], labels, purchase))
    if singles and not any(row["scope"] == "subsidy" for row in found):
        order = sorted(singles, key=lambda pair: (pair[1]["payback"]["value"] is None, pair[1]["payback"]["value"] or 0, -(pair[1]["effect"]["value"] or 0)))
        picked: list[str] = []
        for code, _purchase in order:
            picked.append(code)
            _one, _asis, purchase, _raas = _process_bundle(s, item, share, note, params, full=False, subsidies=on | set(picked))
            if _meets(purchase, horizon):
                found.append(_subsidy_hint(picked, labels, purchase))
                break
    for row in found:
        row.pop("_rank", None)
    return found


def _subsidy_hint(codes: list[str], labels: dict[str, str], purchase: dict) -> dict:
    return {
        "key": ",".join(codes),
        "label": labels[codes[0]] if len(codes) == 1 else "Несколько мер вместе: " + ", ".join(labels[code] for code in codes),
        "unit": "",
        "scope": "subsidy",
        "from": 0,
        "to": 1,
        "effect": purchase["effect"]["value"],
        "payback": purchase["payback"]["value"],
    }


def _process_views(s: dict) -> list[dict]:
    shares, share_note = _shares(s["included"], s.get("tasks") or [])
    out = []
    for item in s["fleet"]:
        base = {
            "process_code": item["process_code"],
            "process_name": item["process_name"],
            "robot_name": item["name"],
            "image_url": item["image_url"],
            "count": item["count_used"],
            "cost_rub": item["cost_rub"],
            "included": bool(item["included"]),
            "note": item["note"],
            "share": 0,
            "share_note": "",
            "profitable": None,
            "reason": item["note"],
            "payroll": None,
            "scenarios": [],
            "suggestions": [],
        }
        if not item["included"]:
            out.append(base)
            continue
        params = _local_params(s, item["process_code"])
        share = shares.get(item["process_code"], 0)
        one, asis, purchase, raas = _process_bundle(s, item, share, share_note, params)
        purchase.pop("support_items", None)
        ok, reason = _profit_status(purchase, s["horizon"])
        base.update({
            "share": share,
            "share_note": share_note,
            "profitable": ok,
            "reason": reason,
            "payroll": one["payroll"]["fig"],
            "scenarios": [asis, purchase, raas],
            "suggestions": [] if ok else _suggestions(s, item, share, share_note, params),
        })
        out.append(base)
    return out
