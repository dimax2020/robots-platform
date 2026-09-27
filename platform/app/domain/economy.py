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
)

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


def calculate(
    rows: list[dict],
    site: dict | None = None,
    standard: dict[str, float] | None = None,
    overrides: dict | None = None,
    tasks: list[dict] | None = None,
    meta: dict[str, dict] | None = None,
) -> dict:
    site = site or {}
    params = resolve(standard, overrides, site, meta)
    report = _compute(rows, site, tasks or [], params)
    report["sensitivity"] = _sensitivity(rows, site, tasks or [], params, report)
    return report


def _compute(rows: list[dict], site: dict, tasks: list[dict], params: dict[str, dict]) -> dict:
    p = {key: item["value"] for key, item in params.items()}
    horizon = max(1, int(round(p["horizon_years"])))
    hours = _hours(site)
    tariff = _norm_var(params, "energy_tariff")
    fleet = [_line(row, params, hours, tariff) for row in rows]
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
    }
    scenarios = [_asis(shared), _purchase(shared), _raas(shared)]
    return {
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


def _line(row: dict, params: dict[str, dict], hours: dict, tariff: dict) -> dict:
    p = {key: item["value"] for key, item in params.items()}
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
            _norm_var_fraction(p, "price_factor", params),
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
    params, equipment = s["params"], s["equipment"]
    equipment_fig = _equipment_fig(s)
    extras = [_pct_fig(params, key, equipment, "обор") for key in ("infra_pct", "software_pct", "integration_pct", "commissioning_pct", "training_pct")]
    subtotal = equipment + sum(item["value"] for item in extras)
    reserve = _reserve_fig(params, subtotal)
    capex_value = subtotal + reserve["value"]
    capex = _fig(
        "capex", "CAPEX", capex_value, "₽",
        r"\text{CAPEX} = C_{\text{обор}} + C_{\text{инфр}} + C_{\text{ПО}} + C_{\text{интегр}} + C_{\text{ПНР}} + C_{\text{обуч}} + C_{\text{рез}}",
        " + ".join(_t(item["value"]) for item in [equipment_fig, *extras, reserve]) + rf" = {_t(capex_value)}\ \text{{₽}}",
        [_var(item["symbol"], item["label"], item["value"], "₽", "calc") for item in [equipment_fig, *extras, reserve]],
        "Доп. статьи — доли от оборудования: каталог их не даёт, стандарт задаётся в админке.",
    )
    opex_lines = [
        _pct_fig(params, "service_pct", equipment, "обор"),
        _pct_fig(params, "license_pct", equipment, "обор"),
        _energy_fig(s),
        _pct_fig(params, "comms_pct", equipment, "обор"),
        _pct_fig(params, "consumables_pct", equipment, "обор"),
        _pct_fig(params, "repair_pct", equipment, "обор"),
        _operators_fig(s),
    ]
    return _robot_scenario(
        s, "purchase", "Покупка", "Полное владение оборудованием",
        capex, [equipment_fig, *extras, reserve], opex_lines,
        r"\text{OPEX} = C_{\text{серв}} + C_{\text{лиц}} + C_{\text{эл}} + C_{\text{связь}} + C_{\text{расх}} + C_{\text{рем}} + C_{\text{опер}}",
        note="" if s["included"] else "В парке нет роботов с ценой.",
    )


def _raas(s: dict) -> dict:
    p, params, equipment = s["p"], s["params"], s["equipment"]
    extras = [_pct_fig(params, key, equipment, "обор") for key in ("infra_pct", "integration_pct", "commissioning_pct", "training_pct")]
    subtotal = sum(item["value"] for item in extras)
    reserve = _reserve_fig(params, subtotal)
    capex_value = subtotal + reserve["value"]
    capex = _fig(
        "capex", "CAPEX", capex_value, "₽",
        r"\text{CAPEX}_{\text{RaaS}} = C_{\text{инфр}} + C_{\text{интегр}} + C_{\text{ПНР}} + C_{\text{обуч}} + C_{\text{рез}}",
        " + ".join(_t(item["value"]) for item in [*extras, reserve]) + rf" = {_t(capex_value)}\ \text{{₽}}",
        [_var(item["symbol"], item["label"], item["value"], "₽", "calc") for item in [*extras, reserve]],
        "Оборудование и ПО не покупаются: они в арендном платеже. Внедрение на площадке остаётся на заказчике.",
    )
    rate = p["raas_rate_pct"] / 100
    payment = equipment * rate * 12
    rate_var = _norm_var(params, "raas_rate_pct")
    payment_fig = _fig(
        "raas_payment", "Арендный платёж", payment, "₽/год",
        r"C_{\text{RaaS}} = \sum_i N_i \times P_i \times f_{\text{цена}} \times k_{\text{RaaS}} \times 12",
        rf"{_t(equipment)} \times {_t(p['raas_rate_pct'], 2)}\% \times 12 = {_t(payment)}\ \text{{₽}}",
        [
            _var(r"\sum N_i P_i f_{\text{цена}}", "Стоимость парка по ценам карточек", equipment, "₽", "calc"),
            rate_var,
            _var("12", "Месяцев в году", 12, "мес.", "calc"),
        ],
        "Файл модели: Платёж = Ставка_фикс + Ставка_за_использование × Объём. Здесь только фиксированная часть: ставок за использование в каталоге нет.",
    )
    opex_lines = [payment_fig, _energy_fig(s), _pct_fig(params, "comms_pct", equipment, "обор"), _operators_fig(s)]
    confirmed = sum(1 for item in s["included"] if item["raas_available"])
    total = len(s["included"])
    note = (
        f"Аренду подтверждает вендор у {confirmed} из {total} роботов, для остальных ставка — стандарт."
        if total else "В парке нет роботов с ценой."
    )
    return _robot_scenario(
        s, "raas", "Аренда (RaaS)", "Роботы как услуга, платёж вместо покупки",
        capex, [*extras, reserve], opex_lines,
        r"\text{OPEX}_{\text{RaaS}} = C_{\text{RaaS}} + C_{\text{эл}} + C_{\text{связь}} + C_{\text{опер}}",
        note=note,
    )


def _robot_scenario(s, key, title, subtitle, capex, capex_lines, opex_lines, opex_tex, note) -> dict:
    p, horizon = s["p"], s["horizon"]
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
    effect_value = saved - opex_value
    effect = _fig(
        "effect", "Эффект в год", effect_value, "₽/год",
        r"\text{Эффект} = \Delta\text{ФОТ} - \text{OPEX}",
        rf"{_t(saved)} - {_t(opex_value)} = {_t(effect_value)}\ \text{{₽}}",
        [_var(r"\Delta\text{ФОТ}", "Экономия ФОТ", saved, "₽/год", "calc"), _var(r"\text{OPEX}", "Затраты на эксплуатацию парка", opex_value, "₽/год", "calc")],
        "Файл модели: Эффект = ΔЗатраты + доп. доход − ΔOPEX. Доп. дохода и предотвращённых потерь в данных площадки нет.",
    )
    capex_value = capex["value"]
    payback_value = capex_value / effect_value if effect_value > 0 and capex_value > 0 else None
    payback = _fig(
        "payback", "Срок окупаемости", payback_value, "лет",
        r"\text{PBP} = \dfrac{\text{CAPEX}}{\text{Эффект}}",
        rf"\dfrac{{{_t(capex_value)}}}{{{_t(effect_value)}}} = {_t(payback_value, 1)}\ \text{{лет}}" if payback_value is not None else r"\text{Эффект} \le 0 \Rightarrow \text{срока нет}",
        [_var(r"\text{CAPEX}", "Капитальные затраты", capex_value, "₽", "calc"), _var(r"\text{Эффект}", "Эффект в год", effect_value, "₽/год", "calc")],
        "" if payback_value is not None else "Эффект не покрывает вложения: срока окупаемости нет.",
    )
    roi_value = effect_value * horizon / capex_value * 100 if capex_value > 0 else None
    roi = _fig(
        "roi", f"ROI за {horizon} лет", roi_value, "%",
        r"\text{ROI} = \dfrac{\text{Эффект} \times T}{\text{CAPEX}} \times 100\%",
        rf"\dfrac{{{_t(effect_value)} \times {horizon}}}{{{_t(capex_value)}}} \times 100\% = {_t(roi_value, 0)}\%" if roi_value is not None else "",
        [_var(r"\text{Эффект}", "Эффект в год", effect_value, "₽/год", "calc"), _t_var(s), _var(r"\text{CAPEX}", "Капитальные затраты", capex_value, "₽", "calc")],
    )
    annual = opex_value + after_value
    tco_value = capex_value + annual * horizon
    tco = _fig(
        "tco", f"TCO за {horizon} лет", tco_value, "₽",
        r"\text{TCO} = \text{CAPEX} + (\text{OPEX} + \text{ФОТ}_{\text{после}}) \times T",
        rf"{_t(capex_value)} + ({_t(opex_value)} + {_t(after_value)}) \times {horizon} = {_t(tco_value)}\ \text{{₽}}",
        [
            _var(r"\text{CAPEX}", "Капитальные затраты", capex_value, "₽", "calc"),
            _var(r"\text{OPEX}", "Эксплуатация парка", opex_value, "₽/год", "calc"),
            _var(r"\text{ФОТ}_{\text{после}}", "ФОТ оставшихся людей", after_value, "₽/год", "calc"),
            _t_var(s),
        ],
        "Оставшийся ФОТ входит в TCO, чтобы сценарии сравнивались с базой на одной шкале. Замена узлов не добавлена: срока службы в карточках нет.",
    )
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
        "effect_lines": [saving, _negate(opex)],
        "payback": payback,
        "roi": roi,
        "tco": tco,
        "years": [
            {"year": year, "cost_rub": capex_value + annual * year, "net_rub": effect_value * year - capex_value}
            for year in range(1, horizon + 1)
        ],
        "verdict": _verdict(payback_value),
    }


def _equipment_fig(s: dict) -> dict:
    included = s["included"]
    factor = s["p"]["price_factor"] / 100
    if len(included) <= 4:
        terms = " + ".join(rf"{_t(item['count_used'], 1)} \times {_t(item['price_rub'])}" for item in included) or "0"
        sub = rf"\left({terms}\right) \times {_t(factor, 2)} = {_t(s['equipment'])}\ \text{{₽}}"
    else:
        sub = rf"\sum_{{i=1}}^{{{len(included)}}} N_i P_i \times {_t(factor, 2)} = {_t(s['equipment'])}\ \text{{₽}}"
    skipped = [item for item in s["fleet"] if not item["included"]]
    note = f"{len(included)} роботов с ценой, {_t_plain(s['robots'])} шт."
    if skipped:
        note += f" Без цены и не входят: {', '.join(item['name'] for item in skipped)}."
    fig = _fig(
        "equipment", "Оборудование", s["equipment"], "₽",
        r"C_{\text{обор}} = \sum_i N_i \times P_i \times f_{\text{цена}}", sub,
        [
            _var("N_i", "Количество роботов процесса", None, "шт.", "fleet"),
            _var("P_i", "Цена робота за единицу", None, "₽", "card"),
            _norm_var_fraction(s["p"], "price_factor", s["params"]),
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


def _sensitivity(rows: list[dict], site: dict, tasks: list[dict], params: dict[str, dict], report: dict) -> list[dict]:
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
            values.append(_metric(_compute(rows, site, tasks, changed)))
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
