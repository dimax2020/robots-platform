"""Экономика трёх сценариев: без роботизации, покупка, аренда. Вход — парк, площадка и нормативы, без базы.

Высвобождение считается из данных площадки, деньги — годовым потоком после налога с дисконтированием."""

from __future__ import annotations

import math
import random

from app.domain.assessment import valid_count

from app.domain.specs import normalize_value
from dataclasses import dataclass

NO_PRICE = "Не будет использоваться в расчётах, не хватает цены."
NO_COUNT = "Количество не посчитано: формуле не хватает данных площадки. В расчёте 1 робот — укажите своё количество."
OWN_COUNT = "Количество задано вручную."
COUNT_MAX = 10_000
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
    Norm("reserve_pct", "capex", "Резерв", r"k_{\text{рез}}", 0.0, "% от суммы статей",
         "Неопределённость показывается интервалом результата, а не надбавкой к вложениям. "
         "Демо-проект организатора закладывал 6% — можно вернуть, если нужен запас в бюджете.", "Демо-проект склада", 0, 20, 0.5),
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
    Norm("robots_per_operator", "staff", "Роботов на один пост диспетчера", r"m", 10.0, "шт.",
         "Каталог не говорит, сколько машин ведёт один диспетчер. Допущение: один пост на 10 машин. Уточняется у вендора.", "Допущение команды", 1, 50, 1),
    Norm("fte_hours", "staff", "Годовой фонд рабочего времени сотрудника", r"h_{\text{чел}}", 1810.0, "ч в год",
         "Около 1 970 ч по производственному календарю при 40-часовой неделе (ст. 91 ТК РФ) минус ежегодный отпуск "
         "28 календарных дней, около 160 ч (ст. 115 ТК РФ). Нужен, чтобы перевести круглосуточный пост в людей.", "ТК РФ", 1000, 3000, 10),
    Norm("raas_rate_pct", "raas", "Ставка аренды", r"k_{\text{RaaS}}", 2.2, "% цены робота в месяц",
         "Выведено из демо: аренда дороже покупки на 19 млн ₽ в год при оборудовании 71,4 млн ₽, это около 26,6% в год или 2,2% в месяц. "
         "В ставку входят сервис, ремонт, расходники и лицензии.", "Демо-проект склада", 0.5, 6, 0.1),
    Norm("raas_growth_pct", "raas", "Рост платежа аренды", r"g_{\text{RaaS}}", 4.0, "% в год",
         "Насколько в год дорожает арендный платёж по договору. По умолчанию — на инфляцию (цель Банка России 4%): "
         "расчёт идёт в постоянных ценах, и такой рост платёж не меняет. Если договор индексирует быстрее инфляции, "
         "платёж в постоянных ценах растёт на (1 + g) / (1 + π*) − 1 в год.", "Условие договора аренды", 0, 30, 0.5),
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
    Norm("market_rate_pct", "finance", "Ключевая ставка Банка России", r"r_{\text{КС}}", 14.0, "% годовых",
         "Ключевая ставка 14% — решение Банка России, сентябрь 2026 г. Основа ставки дисконтирования и выгоды займа ФРП. "
         "Кредит бизнесу обычно дороже ключевой на несколько пунктов: это проверяют торнадо и стресс-сценарий "
         "«Дорогие деньги» (21% — максимум 2024–2025 гг.).", "Банк России", 5, 35, 0.5),
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
    Norm("service_life_years", "finance", "Срок полезного использования", r"T_{\text{сл}}", 7.0, "лет",
         "Срока службы в карточках нет. Допущение: 7 лет, пока тип решения не сопоставлен с амортизационной группой "
         "Классификации основных средств (ПП РФ № 1). Остаток стоимости на конец горизонта возвращается в расчёт.", "Допущение команды", 2, 20, 1),
    Norm("profit_tax_pct", "finance", "Ставка налога на прибыль", r"t_{\text{приб}}", 25.0, "%",
         "25%: 8% в федеральный бюджет и 17% в региональный, ст. 284 НК РФ, действует с 2025 г. "
         "Экономия увеличивает прибыль, амортизация и выплаты её уменьшают.", "НК РФ", 0, 40, 1),
    Norm("vat_pct", "finance", "НДС к вычету", r"k_{\text{НДС}}", 22.0, "%",
         "Цены карточек с НДС. Плательщик НДС принимает его к вычету, поэтому вложения и расходы считаются без НДС: "
         "22% с 1 января 2026 г., ст. 164 НК РФ. Для упрощённой системы налогообложения поставьте 0.", "НК РФ", 0, 22, 1),
    Norm("inflation_target_pct", "finance", "Цель Банка России по инфляции", r"\pi^{*}", 4.0, "% в год",
         "Расчёт идёт в постоянных ценах, поэтому ключевая ставка переводится в реальную: "
         "r = (1 + r_КС) / (1 + π*) − 1. Цель по инфляции — 4%.", "Банк России", 0, 15, 0.5),
    Norm("notice_months", "finance", "Срок уведомления о сокращении", r"t_{\text{увед}}", 2.0, "мес.",
         "Работника предупреждают о сокращении не менее чем за 2 месяца (ст. 180 ТК РФ): "
         "экономия ФОТ в первый год начинается после этого срока.", "ТК РФ", 0, 12, 1),
    Norm("severance_months", "finance", "Выплаты при сокращении", r"t_{\text{вых}}", 2.0, "средних заработка",
         "Выходное пособие и сохранение заработка на время трудоустройства — в сумме до 2 средних месячных заработков "
         "(ст. 178 ТК РФ). Страховые взносы на них не начисляются (ст. 422 НК РФ).", "ТК РФ", 0, 6, 0.5),
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
# Лизинговые меры относятся к схеме «Лизинг»: в покупке за свои средства их нет, иначе скидка считается без договора лизинга.
PURCHASE_SUBSIDIES = ("mpt", "frp", "amort")
SUPPORT_NOTE = "Право на меру и её размер подтверждаются условиями конкретной программы."

NORM_BY_KEY = {norm.key: norm for norm in NORMS}
LOAD_KEYS = ("flow_per_day", "inbound_pallets_per_day", "outbound_pallets_per_day", "pick_lines_per_day", "pick_units_per_day")

_ROLES = (
    ("pickers_count", "picker_salary_month_rub", "Отборщики", r"\text{отб}"),
    ("forklift_operators", "forklift_salary_month_rub", "Операторы погрузчиков", r"\text{погр}"),
    ("pack_operators", "pack_salary_month_rub", "Операторы упаковки", r"\text{упак}"),
)

# Поля площадки, которые экономика читает при любом наборе процессов: часы парка, ФОТ, тариф и горизонт.
SITE_KEYS = frozenset((
    "shift_hours", "shifts_per_day", "days_year", "payroll_burden", "staff_salary_year_rub", "staff_total",
    "energy_tariff_rub_kwh", "payback_years", "budget_rub", *LOAD_KEYS, *(key for role in _ROLES for key in role[:2]),
))

_SENSITIVE = (
    "price_factor", "salary_factor", "robots_per_operator", "service_pct", "license_pct", "infra_pct", "software_pct",
    "integration_pct", "commissioning_pct", "comms_pct", "consumables_pct", "repair_pct", "energy_tariff",
    "market_rate_pct", "service_life_years",
)
# Диапазоны, которые указаны в самих источниках нормативов. Остальным — ширина по уровню достоверности.
RANGES: dict[str, tuple[float, float, str]] = {
    "comms_pct": (0.2, 0.5, "Файл модели: 0,2–0,5% стоимости оборудования в год."),
    "consumables_pct": (0.5, 1.5, "Файл модели: 0,5–1,5% в год."),
    "repair_pct": (1.0, 2.0, "Файл модели: 1–2% в год."),
    "market_rate_pct": (14.0, 21.0, "Банк России: от текущей ключевой ставки 14% до максимума 2024–2025 гг. — 21%."),
    "frp_rate_pct": (1.0, 5.0, "ФРП: 1–5% по отдельным программам."),
    "leasing_discount_pct": (10.0, 15.0, "ПП № 649: обычно 10–15%."),
}
# Уровень достоверности: A — закон и паспорт, B — данные и документ, C — оценка по аналогу, D — допущение команды.
LEVELS: dict[str, str] = {
    "price_factor": "B", "salary_factor": "B", "robots_per_operator": "D", "service_pct": "C", "license_pct": "B",
    "infra_pct": "C", "software_pct": "C", "integration_pct": "C", "commissioning_pct": "C", "energy_tariff": "C",
    "service_life_years": "D", "fte_hours": "A", "raas_growth_pct": "C",
}
LEVEL_WIDTH = {"A": 0.05, "B": 0.10, "C": 0.20, "D": 0.35}
# Точки безубыточности: ключ, подпись, единица, границы поиска, целое ли значение.
_BREAKEVEN = (
    ("price_factor", "Цена парка", "% от цены карточки", 1.0, 500.0, False),
    ("release", "Высвобождение людей", "чел.", 0.0, 0.0, True),
    ("robots_per_operator", "Машин на один пост диспетчера", "шт.", 1.0, 200.0, True),
    ("salary_factor", "Уровень зарплат", "% от зарплат площадки", 1.0, 500.0, False),
    ("market_rate_pct", "Ключевая ставка", "% годовых", 0.0, 80.0, False),
)

# Работа процесса в операциях: единица, суточный объём и как считается выработка робота. Повторяет формулы
# количества подбора, чтобы экономика и подбор считали одну и ту же работу. Объём задачи (flow_per_day) важнее.
#   kind move — рейсы туда и обратно: 3600 / (маршрут / скорость + 80 с на пункте);
#   kind patrol — обход периметра площадки: 3600 / (4·√S / скорость + 240 с);
#   kind area — убираемая площадь: паспортная производительность, м²/ч;
#   kind scan — паллетоместа в час по паспорту.
_PALLET = ("паллета", "паллеты", "паллет")
WORK: dict[str, dict] = {
    **{code: {"unit": _PALLET, "volume": ("inbound_pallets_per_day", "outbound_pallets_per_day"), "kind": "move", "route": "picker_route_m"}
       for code in ("pallet_transport", "cart_towing", "pallet_storage", "rack_placement", "packing", "palletizing")},
    "order_picking": {"unit": ("строка заказа", "строки заказа", "строк заказа"), "volume": ("pick_lines_per_day",), "kind": "move", "route": "picker_route_m"},
    **{code: {"unit": ("штука", "штуки", "штук"), "volume": ("pick_units_per_day",), "kind": "move", "route": "picker_route_m"}
       for code in ("tote_delivery", "parcel_sorting")},
    "floor_cleaning": {"unit": ("м² уборки", "м² уборки", "м² уборки"), "volume": ("clean_area_m2",), "kind": "area"},
    **{code: {"unit": ("обход", "обхода", "обходов"), "volume": 24, "kind": "patrol"}
       for code in ("perimeter_security", "territory_inspection", "roof_inspection")},
    "warehouse_inventory": {"unit": ("паллетоместо", "паллетоместа", "паллетомест"), "volume": ("pallet_places",), "kind": "scan"},
    **{code: {"unit": ("рейс", "рейса", "рейсов"), "volume": 420, "kind": "move", "route": 584}
       for code in ("baggage_transport", "apron_transport", "passenger_service")},
    **{code: {"unit": ("доставка", "доставки", "доставок"), "volume": 1200, "kind": "move", "route": 360}
       for code in ("biomaterial_delivery", "medicine_delivery")},
    "ward_service": {"unit": ("поручение", "поручения", "поручений"), "volume": 850, "kind": "move", "route": 360},
}
# Характеристики робота, из которых считается его выработка.
WORK_SPECS = ("speed_loaded_ms", "proizvoditelnost", "throughput")
# Готовность робота — та же, что в формулах количества подбора (C-011).
READY = 0.82

# Метки правок платформы: auto:count:код хранит прежнее количество, auto:off:код и auto:on:код — исключение и возврат.
AUTO_PREFIXES = ("auto:count:", "auto:off:", "auto:on:")

# Начисления на ФОТ, если площадка их не задала: страховые взносы 30% (ст. 425 НК РФ) и взнос на травматизм 0,2%.
LAW_BURDEN = 1.302
# Ориентир демо-проекта организатора: какая доля персонала переходит на роботов. Только контроль, в расчёт не входит.
CHECK_SHARE = 0.63

# Роль площадки склада и процессы, которые забирают её работу. Если в парке несколько процессов роли,
# численность делится между ними поровну: у них один поток паллет, и один человек не высвобождается дважды.
ROLE_PROCESSES: dict[str, tuple[str, ...]] = {
    "forklift_operators": ("pallet_transport", "rack_placement", "pallet_storage"),
    "pack_operators": ("packing", "palletizing"),
}
# Поле площадки с долей работы, которую робот не берёт.
MANUAL_SHARE = {
    "pallet_transport": ("oversized_share_pct", "негабаритные паллеты"),
    "rack_placement": ("oversized_share_pct", "негабаритные паллеты"),
    "pallet_storage": ("oversized_share_pct", "негабаритные паллеты"),
    "palletizing": ("oversized_share_pct", "негабаритные грузы"),
}
# Процессы, где человек остаётся на операции, а робот ускоряет его: без выработки до и после высвобождение не считается.
ASSISTED = {
    "order_picking": "Комплектация «товар к человеку»: отборщик остаётся на месте, робот забирает только переходы.",
    "tote_delivery": "Робот возит грузы, но погрузку и выгрузку делает человек.",
}


TYPE_NORMS = (
    "infra_pct", "software_pct", "integration_pct", "commissioning_pct", "training_pct",
    "service_pct", "license_pct", "comms_pct", "consumables_pct", "repair_pct", "raas_rate_pct",
)

# Коэффициенты, которые можно задать одному процессу, не двигая весь парк.
PROCESS_TUNABLE = frozenset(("price_factor", "energy_kwh", "robots_per_operator", *TYPE_NORMS))
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
    ("energy_tariff", -1, "site"),
    ("robots_per_operator", 1, "site"),
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
        if price is None or price <= 0:
            continue
        count = _num(row.get("count"))
        if count is not None and not valid_count(count):
            continue
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


def scale_task_flows(tasks: list | None, load_pct: float) -> list:
    """Та же нагрузка, что у паллет склада, для суточного объёма задач аэропорта и медучреждения."""
    rows = [task for task in (tasks or [])]
    if load_pct == 100:
        return rows
    scaled = []
    for task in rows:
        if not isinstance(task, dict):
            scaled.append(task)
            continue
        row = dict(task)
        flow = _num(row.get("flow_per_day"))
        if flow is not None:
            row["flow_per_day"] = flow * load_pct / 100
        passes = _num(row.get("cleaning_passes_per_day"))
        if passes is not None:
            row["cleaning_passes_per_day"] = passes * load_pct / 100
        scaled.append(row)
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
    """Ключ process:код:норматив задаёт коэффициент одному процессу, count:код — количество роботов,
    off:код исключает процесс из расчёта. Остальное — на весь парк."""
    global_overrides: dict = {}
    by_process: dict[str, dict[str, float]] = {}
    for key, raw in (overrides or {}).items():
        if isinstance(key, str) and (key.startswith("subsidy:") or key == "auto" or key.startswith("auto:")):
            continue
        if isinstance(key, str) and key.startswith("count:"):
            value = _num(raw)
            if key[6:] and value is not None:
                by_process.setdefault(key[6:], {})["count"] = float(min(COUNT_MAX, max(1, round(value))))
            continue
        if isinstance(key, str) and key.startswith("off:"):
            if key[4:] and _num(raw):
                by_process.setdefault(key[4:], {})["off"] = 1.0
            continue
        if isinstance(key, str) and key.startswith("rate:"):
            value = _num(raw)
            if key[5:] and value and value > 0:
                by_process.setdefault(key[5:], {})["rate"] = min(1e6, value)
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
    # Метки правок платформы: что она поменяла сама и с какого значения — чтобы показать и дать вернуть.
    for key, raw in (values or {}).items():
        if isinstance(key, str) and (key == "auto" or key.startswith(AUTO_PREFIXES)):
            value = _num(raw)
            if value is not None:
                clean[key] = value
    for key, raw in global_overrides.items():
        if key not in NORM_BY_KEY:
            continue
        value = _num(raw)
        if value is not None:
            clean[key] = value
    for code, items in by_process.items():
        for key, value in items.items():
            clean[{"count": f"count:{code}", "off": f"off:{code}", "rate": f"rate:{code}"}.get(key, f"process:{code}:{key}")] = value
    return clean


def calculate(
    rows: list[dict],
    site: dict | None = None,
    standard: dict[str, float] | None = None,
    overrides: dict | None = None,
    tasks: list[dict] | None = None,
    meta: dict[str, dict] | None = None,
    blockers: list[dict] | None = None,
) -> dict:
    site = site or {}
    global_overrides, by_process = split_process_overrides(overrides)
    subsidies = enabled_subsidies(overrides)
    params = resolve(standard, global_overrides, site, meta)
    report = _compute(rows, site, tasks or [], params, by_process, with_processes=True, subsidies=subsidies)
    _completeness(report, rows, blockers)
    report["sensitivity"] = _sensitivity(rows, site, tasks or [], params, report, by_process, subsidies)
    report["interval"] = _interval(report)
    report["breakeven"] = _breakeven(rows, site, tasks or [], params, report, by_process, subsidies)
    report["stress"] = _stress(rows, site, tasks or [], params, report, by_process, subsidies)
    report["chance"] = _chance(report)
    auto_off = frozenset(key[len("auto:off:"):] for key, value in (overrides or {}).items() if isinstance(key, str) and key.startswith("auto:off:") and _num(value))
    report["plan"] = _plan(rows, site, tasks or [], params, report, by_process, subsidies, auto_off)
    return report


def _compute(
    rows: list[dict],
    site: dict,
    tasks: list[dict],
    params: dict[str, dict],
    by_process: dict[str, dict[str, float]] | None = None,
    with_processes: bool = False,
    subsidies: frozenset[str] = frozenset(),
    release_scale: float = 1.0,
) -> dict:
    by_process = by_process or {}
    p = {key: item["value"] for key, item in params.items()}
    horizon = max(1, int(round(p["horizon_years"])))
    hours = _hours(site)
    tariff = _norm_var(params, "energy_tariff")
    fleet = [_line(row, params, hours, tariff, by_process) for row in rows]
    priced = [item for item in fleet if item["included"]]
    # Исключённый пользователем процесс остаётся в списке со своей экономикой, но в расчёт объекта не входит.
    included = [item for item in priced if not item["off"]]
    payroll = _payroll(site, tasks, params, included, hours)
    release = _release(site, tasks, included, params, hours)
    if release_scale != 1.0:
        for row in release["items"]:
            row["fte"] *= release_scale
    operator = _operator_cost(site, params)

    robots = sum(item["count_used"] for item in included)
    equipment = sum(item["cost_rub"] for item in included)
    shared = {
        "fleet": fleet,
        "included": included,
        "robots": robots,
        "equipment": equipment,
        "hours": hours,
        "payroll": payroll,
        "release": release["items"],
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
        "release": release["summary"],
        "story": _story(release["items"], p),
        "discount": _rate_fig(params),
        "requests": _requests(shared),
        "hours": hours,
        "operator": operator,
        "scenarios": scenarios,
        "switch": _switch(scenarios[1], scenarios[2]),
        "params": list(params.values()),
    }
    if with_processes:
        result["processes"] = _process_views(shared, priced)
    return result


def _line(row: dict, params: dict[str, dict], hours: dict, tariff: dict, by_process: dict | None = None) -> dict:
    own = (by_process or {}).get(row.get("process_code") or "") or {}
    local = _merge_params(params, own)
    p = {key: item["value"] for key, item in local.items()}
    price = _num(row.get("price_rub"))
    formula_count = _num(row.get("count"))
    zero_need = formula_count == 0
    if formula_count is not None and (formula_count <= 0 or not valid_count(formula_count)):
        formula_count = None
    count = own.get("count") or formula_count
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
        "count": formula_count,
        "count_used": None,
        "count_source": "project" if own.get("count") else "formula" if formula_count is not None else "default",
        "off": bool(own.get("off")),
        "included": False,
        "note": "",
        "cost_rub": None,
        "raas_available": bool(row.get("raas_available")),
        "specs": row.get("specs") or {},
        "rate_own": own.get("rate"),
        "operating_hours_per_day": row.get("operating_hours_per_day"),
        "kwh_per_hour": None,
        "kwh_source": "",
        "energy_rub": 0.0,
        "fig": None,
    }
    if price is None or price <= 0:
        item["note"] = NO_PRICE
        return item
    if zero_need and not own.get("count"):
        item["count_used"] = 0
        item["note"] = "При нулевой потребности парк роботизации не формируется."
        return item
    if row.get("technical_ready") is False:
        item["note"] = "Техническая применимость не подтверждена."
        return item
    if count is None:
        count = 1.0
        item["note"] = NO_COUNT
    elif own.get("count"):
        item["note"] = OWN_COUNT
    factor = p["price_factor"] / 100
    vat = p["vat_pct"] / 100
    net = price * factor / (1 + vat)
    item["price_used"] = net
    item["count_used"] = count
    item["included"] = True
    item["cost_rub"] = count * net
    kwh, kwh_source = (power_w / 1000, "card") if power_w else (p["energy_kwh"], "norm")
    item["kwh_per_hour"] = kwh
    item["kwh_source"] = kwh_source
    if hours["value"]:
        daily = _num(row.get("operating_hours_per_day"))
        days = next((var["value"] for var in hours.get("vars", []) if var["symbol"] == "D"), None)
        operating = daily * days if daily is not None and days else hours["value"]
        item["operating_hours_year"] = operating
        item["energy_rub"] = count * kwh * operating * tariff["value"]
    item["fig"] = _fig(
        f"cost:{item['process_code']}",
        item["name"],
        item["cost_rub"],
        "₽",
        r"C_i = \dfrac{N_i \times P_i \times f_{\text{цена}}}{1 + k_{\text{НДС}}}",
        rf"\dfrac{{{_t(count, 1)} \times {_t(price)} \times {_t(factor, 2)}}}{{1 + {_t(vat, 2)}}} = {_t(item['cost_rub'])}\ \text{{₽}}",
        [
            _var("N_i", "Количество роботов", count, "шт.", "project" if item["count_source"] == "project" else "fleet",
                 {"project": OWN_COUNT, "formula": "Формула количества процесса по параметрам площадки.", "default": NO_COUNT}[item["count_source"]]),
            _var("P_i", "Цена за единицу", price, "₽", "card", "С НДС, без доставки, пусконаладки и интеграции."),
            _norm_var_fraction(p, "price_factor", local),
            _norm_var_fraction(p, "vat_pct", local),
        ],
        "НДС принимается к вычету, поэтому вложения считаются без него." if vat else "",
    )
    return item


def _payroll(site: dict, tasks: list[dict], params: dict[str, dict], included: list[dict] | None = None, hours: dict | None = None) -> dict:
    p = {key: item["value"] for key, item in params.items()}
    factor = p["salary_factor"] / 100
    staffed = _task_staff(tasks, _num(site.get("payroll_burden")) or LAW_BURDEN)
    if staffed and included is not None:
        return _payroll_by_process(site, staffed, included, params, hours or {})

    burden_raw = _num(site.get("payroll_burden"))
    burden = burden_raw if burden_raw is not None else LAW_BURDEN
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
        vars_.append(_var(r"k_{\text{нач}}", "Коэффициент начислений на ФОТ", burden, "", "site" if burden_raw is not None else "norm",
                          "" if burden_raw is not None else "На площадке не задан: взносы 30% (ст. 425 НК РФ) и 0,2% на травматизм."))
        vars_.append(_norm_var_fraction(p, "salary_factor", params))
        note = "Роли площадки с численностью и зарплатой."
        if skipped:
            note += f" Без зарплаты на площадке, в ФОТ не входят: {', '.join(item.lower() for item in skipped)}."
        return {"total": total, "lines": lines, "fig": _fig("payroll", "ФОТ ролей до роботизации", total, "₽/год", tex, sub, vars_, note)}

    loose = sum(_num(task.get("staff_fte_now")) or 0 for task in tasks if isinstance(task, dict) and not task.get("process_code"))
    year_cost = _num(site.get("staff_salary_year_rub"))
    if loose > 0 and year_cost:
        total = loose * year_cost * factor
        return {
            "total": total,
            "lines": [{"label": "Персонал задач объекта", "headcount": loose, "salary_month_rub": year_cost / 12, "rub": total}],
            "fig": _fig(
                "payroll",
                "ФОТ персонала задач до роботизации",
                total,
                "₽/год",
                r"\text{ФОТ}_{\text{база}} = \sum L_{\text{задач}} \times W_{\text{год}} \times f_{\text{ФОТ}}",
                rf"{_t(loose)} \times {_t(year_cost)} \times {_t(factor, 2)} = {_t(total)}\ \text{{₽}}",
                [
                    _var(r"L_{\text{задач}}", "Сотрудники на задачах объекта сейчас", loose, "чел.", "site"),
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


def _task_staff(tasks: list[dict], burden: float = LAW_BURDEN) -> dict[str, dict]:
    """Численность задач, привязанных к процессу. Ставка задачи, если она задана, важнее ставки площадки.
    Зарплата в месяц до НДФЛ переводится в годовую стоимость с начислениями."""
    staffed: dict[str, dict] = {}
    for task in tasks or []:
        if not isinstance(task, dict):
            continue
        code = str(task.get("process_code") or "")
        fte = _num(task.get("staff_fte_now"))
        cost = _num(task.get("staff_cost_month_rub"))
        if code and (not fte or fte <= 0) and cost and cost > 0:
            # Людей не знаем, знаем, сколько процесс стоит в месяц: экономия — доля затрат по доле операций у роботов.
            staffed[code] = {"fte": 1.0, "rate": cost * 12, "wage_month": None, "by_cost": True, "cost_month": cost,
                             "name": str(task.get("name") or code), "flow": _num(task.get("flow_per_day")), "route": _num(task.get("route_len_m"))}
            continue
        if not code or not fte or fte <= 0:
            continue
        row = staffed.setdefault(code, {"fte": 0.0, "rate": None, "wage_month": None, "by_cost": False, "cost_month": None, "other_month": None,
                                        "name": str(task.get("name") or code), "flow": _num(task.get("flow_per_day")), "route": _num(task.get("route_len_m"))})
        row["fte"] += fte
        other = _num(task.get("other_cost_month_rub"))
        if other and other > 0:
            row["other_month"] = (row["other_month"] or 0) + other
        month = _num(task.get("staff_salary_month_rub"))
        own = _num(task.get("staff_salary_year_rub"))
        if month:
            row["rate"] = month * 12 * burden
            row["wage_month"] = month
        elif own:
            row["rate"] = own
    # Техника и прочие расходы ручной работы раскладываются на людей: с каждым ушедшим уходит его доля.
    for row in staffed.values():
        if row.get("other_month") and row["rate"] and row["fte"] and not row.get("by_cost"):
            row["rate"] += row["other_month"] * 12 / row["fte"]
    return staffed


def _default_rate(site: dict) -> tuple[float | None, str]:
    year_cost = _num(site.get("staff_salary_year_rub"))
    if year_cost:
        return year_cost, "Годовая стоимость сотрудника целевой группы с начислениями."
    burden = _num(site.get("payroll_burden")) or LAW_BURDEN
    for _count_key, salary_key, label, _tag in _ROLES:
        salary = _num(site.get(salary_key))
        if salary:
            return salary * 12 * burden, f"{label}: зарплата × 12 × начисления."
    return None, ""


def _payroll_by_process(site: dict, staffed: dict[str, dict], included: list[dict], params: dict[str, dict], hours: dict) -> dict:
    """ФОТ процессов парка по численности их задач. Процесс без численности в базу не входит: людей из часов роботов не придумываем."""
    p = {key: item["value"] for key, item in params.items()}
    factor = p["salary_factor"] / 100
    rate_default, rate_note = _default_rate(site)
    lines: list[dict] = []
    by_process: dict[str, float] = {}
    vars_: list[dict] = []
    parts: list[str] = []
    for item in included:
        code = item["process_code"]
        if code in by_process:
            continue
        task = staffed.get(code)
        if not task:
            by_process[code] = 0.0
            continue
        fte = task["fte"]
        rate = task["rate"] or rate_default
        amount = fte * rate * factor if rate else 0.0
        by_process[code] = amount
        name = task["name"]
        lines.append({
            "label": name,
            "process_code": code,
            "headcount": fte,
            "salary_month_rub": (rate or 0) / 12,
            "rub": amount,
            "estimated": False,
            "robots": item.get("count_used") or 0,
            "factor": factor,
            "rate_note": rate_note,
        })
        index = len(lines)
        parts.append(rf"L_{{{index}}} \times W_{{{index}}}")
        vars_.append(_var(f"L_{{{index}}}", f"{name}: численность", fte, "чел.", "site", "Численность задачи на площадке."))
        vars_.append(_var(f"W_{{{index}}}", f"{name}: стоимость сотрудника в год", rate, "₽/год", "site", "Ставка задачи." if task["rate"] else rate_note))
    total = sum(by_process.values())
    missing = sum(1 for value in by_process.values() if not value)
    note = "У каждого процесса свой ФОТ: численность его задачи."
    if missing:
        note += f" У {missing} процессов численности в данных нет: их ФОТ и экономия не считаются."
    return {
        "total": total,
        "lines": lines,
        "by_process": by_process,
        "fig": _fig(
            "payroll",
            "ФОТ процессов парка до роботизации",
            total,
            "₽/год",
            rf"\text{{ФОТ}}_{{\text{{база}}}} = \left({' + '.join(parts) or '0'}\right) \times f_{{\text{{ФОТ}}}}",
            rf"{_t(total)}\ \text{{₽}}",
            [*vars_, _norm_var_fraction(p, "salary_factor", params)],
            note,
        ),
    }


def _operator_cost(site: dict, params: dict[str, dict]) -> dict:
    factor = params["salary_factor"]["value"] / 100
    burden_raw = _num(site.get("payroll_burden"))
    burden = burden_raw if burden_raw is not None else LAW_BURDEN
    forklift = _num(site.get("forklift_salary_month_rub"))
    if forklift:
        value = forklift * 12 * burden * factor
        return {
            "value": value,
            "tex": r"W_{\text{опер}} = W_{\text{погр}} \times 12 \times k_{\text{нач}} \times f_{\text{ФОТ}}",
            "subst": rf"{_t(forklift)} \times 12 \times {_t(burden, 3)} \times {_t(factor, 2)} = {_t(value)}\ \text{{₽}}",
            "vars": [
                _var(r"W_{\text{погр}}", "Зарплата оператора погрузчика: ближайшая по квалификации роль", forklift, "₽/мес", "site"),
                _var(r"k_{\text{нач}}", "Коэффициент начислений на ФОТ", burden, "", "site" if burden_raw is not None else "norm",
                     "" if burden_raw is not None else "На площадке не задан: взносы 30% (ст. 425 НК РФ) и 0,2% на травматизм."),
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
    none = "База сравнения: вложений и денежного потока проекта нет."
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
        "roi": _fig("roi", "Чистый ROI", None, "%", r"\text{ROI}_{\text{AS-IS}}\ \text{не считается}", "", []),
        "net_profit": _fig("net_profit", f"Чистая прибыль за {horizon} лет", 0.0, "₽", r"\text{ЧП}_{\text{AS-IS}} = 0", "= 0", [], "Базовая точка: без роботов ни вложений, ни экономии."),
        "roe": _fig("roe", "ROE в год", None, "%", r"\text{ROE}_{\text{AS-IS}}\ \text{не считается}", "", [], "Вложений нет."),
        "npv": _fig("npv", "NPV", 0.0, "₽", r"\text{NPV}_{\text{AS-IS}} = 0", "= 0", [], none),
        "irr": _fig("irr", "IRR", None, "%", r"\text{IRR}_{\text{AS-IS}}\ \text{не считается}", "", [], none),
        "dpp": _fig("dpp", "Дисконтированная окупаемость", None, "лет", r"\text{DPP}_{\text{AS-IS}}\ \text{не считается}", "", [], none),
        "pi": _fig("pi", "Индекс доходности", None, "", r"\text{PI}_{\text{AS-IS}}\ \text{не считается}", "", [], none),
        "eac": _eac_fig(s, 0.0, _real_rate(s["p"])),
        "tco": _fig("tco", f"TCO за {horizon} лет", tco, "₽", r"\text{TCO}_{\text{AS-IS}} = \text{ФОТ}_{\text{база}} \times T",
                    rf"{_t(payroll)} \times {horizon} = {_t(tco)}\ \text{{₽}}",
                    [_var(r"\text{ФОТ}_{\text{база}}", "ФОТ ролей до роботизации", payroll, "₽/год", "calc"), _t_var(s)]),
        "cashflow": [],
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
    training = next((item["value"] or 0 for item in extras if item["key"] == "training"), 0.0)
    capex = _fig(
        "capex", "CAPEX", capex_value, "₽",
        r"\text{CAPEX} = C_{\text{обор}} + C_{\text{инфр}} + C_{\text{ПО}} + C_{\text{интегр}} + C_{\text{ПНР}} + C_{\text{обуч}} + C_{\text{рез}}",
        " + ".join(_t(item["value"]) for item in [equipment_fig, *extras, reserve]) + rf" = {_t(capex_value)}\ \text{{₽}}",
        [_var(item["symbol"], item["label"], item["value"], "₽", "calc") for item in [equipment_fig, *extras, reserve]],
        "Без НДС: он принимается к вычету. Доп. статьи — доли от оборудования: каталог их не даёт, стандарт задаётся в админке.",
    )
    support = _support(s, capex_value, equipment, capex_value - training)
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
            f"Разовые меры поддержки уменьшают вложения и базу амортизации. {SUPPORT_NOTE}",
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
        note="" if s["included"] else "В парке нет роботов с ценой и количеством.",
        support=support,
        dep_base=max(0.0, capex_value - training - support["once"]),
        expensed=training,
    )
    scenario["support_items"] = support["items"]
    return scenario


def _raas(s: dict) -> dict:
    extras = [_cost_pct_fig(s, key, "обор") for key in _RAAS_EXTRAS]
    subtotal = sum(item["value"] or 0 for item in extras)
    reserve_params, reserve_mixed = _param_for_key(s, "reserve_pct")
    reserve = _mixed_reserve(s, _RAAS_EXTRAS, False) if reserve_mixed else _reserve_fig(reserve_params, subtotal)
    capex_value = subtotal + reserve["value"]
    training = next((item["value"] or 0 for item in extras if item["key"] == "training"), 0.0)
    capex = _fig(
        "capex", "CAPEX", capex_value, "₽",
        r"\text{CAPEX}_{\text{RaaS}} = C_{\text{инфр}} + C_{\text{интегр}} + C_{\text{ПНР}} + C_{\text{обуч}} + C_{\text{рез}}",
        " + ".join(_t(item["value"]) for item in [*extras, reserve]) + rf" = {_t(capex_value)}\ \text{{₽}}",
        [_var(item["symbol"], item["label"], item["value"], "₽", "calc") for item in [*extras, reserve]],
        "Оборудование и ПО не покупаются: они в арендном платеже. Внедрение на площадке остаётся на заказчике.",
    )
    payment_fig = _raas_payment_fig(s)
    growth = _raas_growth(s["p"])
    if abs(growth) > 1e-9:
        payment_fig = {**payment_fig, "note": payment_fig["note"] + f" По договору платёж индексируется на {_t_plain(s['p']['raas_growth_pct'])}% в год: "
                       f"в постоянных ценах он {'дорожает' if growth > 0 else 'дешевеет'} на {_t_plain(abs(round(growth * 100, 1)))}% в год."}
    opex_lines = [payment_fig, _energy_fig(s), _cost_pct_fig(s, "comms_pct", "обор"), _operators_fig(s)]
    confirmed = sum(1 for item in s["included"] if item["raas_available"])
    total = len(s["included"])
    note = (
        f"Аренду подтверждает вендор у {confirmed} из {total} роботов, для остальных ставка — стандарт."
        if total else "В парке нет роботов с ценой и количеством."
    )
    if s.get("subsidies"):
        note += " Меры господдержки считаются только для покупки."
    return _robot_scenario(
        s, "raas", "Аренда (RaaS)", "Роботы как услуга, платёж вместо покупки",
        capex, [*extras, reserve], opex_lines,
        r"\text{OPEX}_{\text{RaaS}} = C_{\text{RaaS}} + C_{\text{эл}} + C_{\text{связь}} + C_{\text{опер}}",
        note=note,
        dep_base=max(0.0, capex_value - training),
        expensed=training,
        owned=False,
        growing=(payment_fig["value"] or 0.0, growth) if abs(growth) > 1e-9 else None,
    )


def _raas_growth(p: dict) -> float:
    """Рост арендного платежа в постоянных ценах: индексация по договору сверх цели по инфляции."""
    return (1 + p.get("raas_growth_pct", 0) / 100) / (1 + p["inflation_target_pct"] / 100) - 1


def _robot_scenario(
    s, key, title, subtitle, capex, capex_lines, opex_lines, opex_tex, note,
    support: dict | None = None, dep_base: float = 0.0, expensed: float = 0.0, owned: bool = True,
    growing: tuple[float, float] | None = None,
) -> dict:
    p, horizon = s["p"], s["horizon"]
    support = support or _no_support()
    payroll = s["payroll"]["total"]
    opex_value = sum(item["value"] or 0 for item in opex_lines if item["included"])
    opex = _fig(
        "opex", "OPEX в год", opex_value, "₽/год", opex_tex,
        " + ".join(_t(item["value"] or 0) for item in opex_lines if item["included"]) + rf" = {_t(opex_value)}\ \text{{₽}}",
        [_var(item["symbol"], item["label"], item["value"], "₽/год", "calc") for item in opex_lines if item["included"]],
        "Без НДС. Не вошли: " + ", ".join(item["label"].lower() for item in opex_lines if not item["included"]) + "."
        if any(not item["included"] for item in opex_lines) else "Без НДС: он принимается к вычету.",
    )
    saving = _saving_fig(s)
    saved = saving["value"]
    after_value = max(0.0, payroll - saved)
    after = _fig(
        "payroll_after", "ФОТ после роботизации", after_value, "₽/год",
        r"\text{ФОТ}_{\text{после}} = \text{ФОТ}_{\text{база}} - \Delta\text{ФОТ}",
        rf"{_t(payroll)} - {_t(saved)} = {_t(after_value)}\ \text{{₽}}",
        [_var(r"\text{ФОТ}_{\text{база}}", "ФОТ до роботизации", payroll, "₽/год", "calc"), _var(r"\Delta\text{ФОТ}", "Экономия ФОТ", saved, "₽/год", "calc")],
        "Люди, которые остаются: их работу роботы не берут.",
    )
    operational = saved - opex_value
    first_support = support["frp"](1)
    effect_value = operational + first_support
    effect_vars = [_var(r"\Delta\text{ФОТ}", "Экономия ФОТ", saved, "₽/год", "calc"), _var(r"\text{OPEX}", "Затраты на эксплуатацию парка", opex_value, "₽/год", "calc")]
    if support["year_lines"]:
        effect_vars.append(_var(r"S_{\text{ФРП}}", "Выгода займа ФРП в первый год", first_support, "₽/год", "calc"))
        effect = _fig(
            "effect", "Эффект в год", effect_value, "₽/год",
            r"\text{Эффект} = \Delta\text{ФОТ} - \text{OPEX} + S_{\text{ФРП}}",
            rf"{_t(saved)} - {_t(opex_value)} + {_t(first_support)} = {_t(effect_value)}\ \text{{₽}}",
            effect_vars,
            f"Полный год до налога. Выгода займа снижается вместе с остатком долга. {SUPPORT_NOTE}",
        )
    else:
        effect = _fig(
            "effect", "Эффект в год", effect_value, "₽/год",
            r"\text{Эффект} = \Delta\text{ФОТ} - \text{OPEX}",
            rf"{_t(saved)} - {_t(opex_value)} = {_t(effect_value)}\ \text{{₽}}",
            effect_vars,
            "Полный год до налога. Доп. дохода и предотвращённых потерь в данных площадки нет.",
        )
    capex_value = capex["value"]
    flow = _cashflow(s, capex_value, saved, opex_value, dep_base, expensed, support, growing)
    # Сколько сверх первого года добавит рост платежа к каждому году.
    extra = [0.0] + [-row["growth_rub"] for row in flow["rows"]]
    rate = flow["rate"]
    capex_var = _var(r"\text{CAPEX}", "Вложения", capex_value, "₽", "calc")
    cf_var = _var(r"CF_t", "Денежный поток года после налога", None, "₽", "calc", "Таблица денежного потока по годам.")
    rate_var = _var("r", "Реальная ставка дисконтирования", rate * 100, "%", "calc", "(1 + r_КС) / (1 + π*) − 1")
    npv = _fig(
        "npv", "NPV", flow["npv"], "₽",
        r"\text{NPV} = -\text{CAPEX} + \sum_{t=1}^{T} \dfrac{CF_t}{(1 + r)^t} + \dfrac{V_T}{(1 + r)^T}",
        rf"-{_t(capex_value)} + {_t(flow['npv'] + capex_value)} = {_t(flow['npv'])}\ \text{{₽}}",
        [capex_var, cf_var, rate_var, _var("V_T", "Остаточная стоимость на конец горизонта", flow["residual"], "₽", "calc", "База амортизации минус линейный износ за горизонт; при ускоренной амортизации — минус налог с разницы с балансом."), _t_var(s)],
        "Сколько денег проект приносит сверх вложений с учётом их стоимости во времени. Больше нуля — выгодно.",
    )
    if not owned:
        flow["irr"] = flow["dpp"] = None
    irr = _fig(
        "irr", "IRR", flow["irr"] * 100 if flow["irr"] is not None else None, "%",
        r"\text{IRR}:\ \text{NPV}(\text{IRR}) = 0",
        rf"\text{{IRR}} = {_t(flow['irr'] * 100, 1)}\%" if flow["irr"] is not None else r"\text{поток не меняет знак}",
        [capex_var, cf_var],
        f"Доходность вложений. Сравнивается со ставкой {_t_plain(rate * 100)}%: выше — проект выгоден.",
    )
    dpp = _fig(
        "dpp", "Дисконтированная окупаемость", flow["dpp"], "лет",
        r"\text{DPP}:\ -\text{CAPEX} + \sum_{t=1}^{\text{DPP}} \dfrac{CF_t}{(1 + r)^t} = 0",
        rf"{_t(flow['dpp'], 1)}\ \text{{лет}}" if flow["dpp"] is not None else r"\text{за горизонт не окупается}",
        [capex_var, cf_var, rate_var],
        "Окупаемость с учётом стоимости денег, без остаточной стоимости.",
    )
    payback_value = flow["pbp"] if owned else None
    payback = _fig(
        "payback", "Срок окупаемости", payback_value, "лет",
        r"\text{PBP}:\ -\text{CAPEX} + \sum_{t=1}^{\text{PBP}} CF_t = 0",
        (rf"{_t(payback_value, 1)}\ \text{{лет}}" if payback_value is not None else r"\text{за горизонт не окупается}") if owned else "",
        [capex_var, cf_var],
        ("Денежный поток после налога, с выплатами при сокращении и сроком уведомления. Остаточная стоимость не учитывается."
         if payback_value is not None else "Денежный поток за горизонт не покрывает вложения.")
        if owned else "Для аренды срок окупаемости не считается: техника не покупается. Сравнивайте по NPV.",
    )
    roi_value = flow["roi"] if owned else None
    roi = _fig(
        "roi", f"Чистый ROI за {horizon} лет", roi_value, "%",
        r"\text{ROI} = \dfrac{\sum_{t=1}^{T} CF_t + V_T - \text{CAPEX}}{\text{CAPEX}} \times 100\%",
        rf"\dfrac{{{_t(flow['inflow'])} - {_t(capex_value)}}}{{{_t(capex_value)}}} \times 100\% = {_t(roi_value, 0)}\%" if roi_value is not None else "",
        [_var(r"\sum CF_t + V_T", "Денежный поток за горизонт с остаточной стоимостью", flow["inflow"], "₽", "calc"), capex_var, _t_var(s)],
        (f"Чистая прибыль на вложенный рубль за {horizon} лет, после возврата CAPEX. В среднем за год — {_t_plain(roi_value / horizon)}%."
         if roi_value is not None else "") if owned else "Для аренды ROI не считается: своих вложений в технику нет.",
    )
    pi = _pi_fig(flow["npv"], capex_value, rate, owned)
    eac = _eac_fig(s, flow["npv"], rate)
    net_profit, roe = _profit_figs(s, flow, capex_value, capex_var, owned)
    support_total = sum(support["frp"](year) for year in range(1, horizon + 1))
    annual = opex_value + after_value
    grown = sum(extra)
    tco_value = capex_value + annual * horizon + grown - support_total
    tco = _fig(
        "tco", f"TCO за {horizon} лет", tco_value, "₽",
        (r"\text{TCO} = \text{CAPEX} + (\text{OPEX} + \text{ФОТ}_{\text{после}}) \times T"
         + (r" + \Delta_{\text{рост}}" if grown else "") + (r" - \sum S_t" if support_total else "")),
        rf"{_t(capex_value)} + ({_t(opex_value)} + {_t(after_value)}) \times {horizon}" + (rf" + {_t(grown)}" if grown else "")
        + (rf" - {_t(support_total)}" if support_total else "") + rf" = {_t(tco_value)}\ \text{{₽}}",
        [
            *([_var(r"\Delta_{\text{рост}}", "Рост арендного платежа за горизонт сверх первого года", grown, "₽", "calc")] if grown else []),
            _var(r"\text{CAPEX}", "Капитальные затраты", capex_value, "₽", "calc"),
            _var(r"\text{OPEX}", "Эксплуатация парка", opex_value, "₽/год", "calc"),
            _var(r"\text{ФОТ}_{\text{после}}", "ФОТ оставшихся людей", after_value, "₽/год", "calc"),
            _t_var(s),
            *([_var(r"\sum S_t", "Выгода займа ФРП за горизонт", support_total, "₽", "calc")] if support_total else []),
        ],
        "Простая сумма затрат без налогов и дисконтирования: сценарии сравниваются с базой на одной шкале.",
    )
    cumulative = [0.0]
    for year in range(1, horizon + 1):
        cumulative.append(cumulative[-1] + support["frp"](year) - extra[year])
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
        "net_profit": net_profit,
        "roe": roe,
        # У аренды вложения — только во внедрение на площадке: их окупаемость и ROI — для сравнения по единым показателям.
        "implementation_payback": None if owned else flow["pbp"],
        "implementation_roi": None if owned else flow["roi"],
        "npv": npv,
        "irr": irr,
        "dpp": dpp,
        "pi": pi,
        "eac": eac,
        "tco": tco,
        "cashflow": flow["rows"],
        "asset_start": flow["asset_start"],
        "years": [
            {"year": row["year"], "cost_rub": capex_value + annual * row["year"] - cumulative[row["year"]], "net_rub": row["cumulative"]}
            for row in flow["rows"]
        ],
        "verdict": _verdict(payback_value, flow["npv"], owned),
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
    per = s["p"]["robots_per_operator"]
    operator = s["operator"]
    if not s["robots"] or operator["value"] is None:
        fig = _fig("operators", "Персонал эксплуатации", None, "₽/год", r"C_{\text{опер}} = L_{\text{дисп}} \times W_{\text{опер}}", "", [],
                   "Нет зарплаты подходящей роли на площадке." if s["robots"] else "Роботов нет.", included=False)
        fig["symbol"] = r"C_{\text{опер}}"
        return fig
    # Доля поста без округления: диспетчерская одна на весь парк, и каждый робот занимает 1/m поста.
    # Так процессы складываются в итог объекта без скачков, а один робот не тянет за собой целый пост.
    posts = s["robots"] / per
    hours = (s.get("hours") or {}).get("value")
    fte_hours = s["p"]["fte_hours"]
    people = posts * hours / fte_hours if hours and fte_hours else posts
    value = people * operator["value"]
    if hours and fte_hours:
        tex = r"C_{\text{опер}} = \dfrac{N}{m} \times \dfrac{H}{h_{\text{чел}}} \times W_{\text{опер}}"
        subst = (rf"\dfrac{{{_t(s['robots'])}}}{{{_t(per)}}} \times \dfrac{{{_t(hours)}}}{{{_t(fte_hours)}}} \times {_t(operator['value'])}"
                 rf" = {_t(people, 1)} \times {_t(operator['value'])} = {_t(value)}\ \text{{₽}}")
        extra = [_var("H", "Часов работы парка в год", hours, "ч", "calc", (s.get("hours") or {}).get("subst", "")), _norm_var(s["params"], "fte_hours")]
        note = (f"{_t_plain(posts)} поста диспетчера на всё время работы парка: {_t_plain(people)} чел. со сменами и отпусками. "
                "Диспетчерская общая на парк, поэтому считается доля поста, а не целый пост на каждый процесс.")
    else:
        tex = r"C_{\text{опер}} = \dfrac{N}{m} \times W_{\text{опер}}"
        subst = rf"\dfrac{{{_t(s['robots'])}}}{{{_t(per)}}} \times {_t(operator['value'])} = {_t(value)}\ \text{{₽}}"
        extra = []
        note = f"{_t_plain(posts)} поста диспетчера. Часов работы площадки нет: на пост считаем одного человека."
    fig = _fig(
        "operators", "Персонал эксплуатации", value, "₽/год", tex, subst,
        [
            _var("N", "Роботов в парке", s["robots"], "шт.", "fleet"),
            _norm_var(s["params"], "robots_per_operator"),
            *extra,
            _var(r"W_{\text{опер}}", "Годовая стоимость диспетчера", operator["value"], "₽/год", "calc", operator["subst"]),
            *operator["vars"],
        ],
        note,
    )
    fig["symbol"] = r"C_{\text{опер}}"
    fig["count"] = people
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


def _support(s: dict, capex_gross: float, equipment: float, dep_gross: float) -> dict:
    """Меры господдержки для покупки за свои средства. Лизинговые меры относятся к схеме «Лизинг» и здесь не считаются."""
    params = s["params"]
    v = {key: params[key]["value"] for key in params}
    on = (s.get("subsidies") or frozenset()) & frozenset(PURCHASE_SUBSIDIES)
    items: list[dict] = []
    horizon = s["horizon"]

    mpt_limit = v["mpt_limit_mln"] * 1_000_000
    mpt_raw = equipment * v["mpt_rate_pct"] / 100
    mpt = min(mpt_raw, mpt_limit)
    mpt_fig = _fig(
        "subsidy_mpt", "Субсидия Минпромторга", mpt, "₽",
        r"S_{\text{МПТ}} = \min\left(k_{\text{МПТ}} \times C_{\text{обор}},\ L_{\text{МПТ}}\right)",
        rf"\min\left({_t(v['mpt_rate_pct'], 1)}\% \times {_t(equipment)},\ {_t(mpt_limit)}\right) = {_t(mpt)}\ \text{{₽}}",
        [_var(r"C_{\text{обор}}", "Стоимость оборудования без НДС", equipment, "₽", "calc"), _norm_var(params, "mpt_rate_pct"), _norm_var(params, "mpt_limit_mln")],
        ("Упёрлись в лимит программы. " if mpt_raw > mpt_limit else "") + "Уменьшает и вложения, и базу амортизации: одна сумма не даёт налоговую выгоду дважды.",
    )
    mpt_fig["symbol"] = r"S_{\text{МПТ}}"
    once = mpt if "mpt" in on else 0.0
    capex_net = max(0.0, capex_gross - once)

    spread = max(0.0, v["market_rate_pct"] - v["frp_rate_pct"]) / 100
    loan = capex_net * v["frp_share_pct"] / 100
    frp_term = max(1, int(round(v["frp_term_years"])))

    def frp_year(year: int) -> float:
        if year > frp_term:
            return 0.0
        return spread * loan * (frp_term - year + 0.5) / frp_term

    frp_first = frp_year(1)
    frp_fig = _fig(
        "subsidy_frp", "Выгода займа ФРП", frp_first, "₽/год",
        r"S_{\text{ФРП},t} = (r_{\text{КС}} - r_{\text{ФРП}}) \times d_{\text{ФРП}} \times \text{CAPEX} \times \dfrac{T_{\text{ФРП}} - t + 0{,}5}{T_{\text{ФРП}}}",
        rf"({_t(v['market_rate_pct'], 1)}\% - {_t(v['frp_rate_pct'], 1)}\%) \times {_t(v['frp_share_pct'])}\% \times {_t(capex_net)} \times \dfrac{{{frp_term} - 0{{,}}5}}{{{frp_term}}} = {_t(frp_first)}\ \text{{₽}}",
        [_norm_var(params, "market_rate_pct"), _norm_var(params, "frp_rate_pct"), _norm_var(params, "frp_share_pct"), _var(r"\text{CAPEX}", "Вложения после разовых мер", capex_net, "₽", "calc"), _norm_var(params, "frp_term_years")],
        f"Первый год. Заём гасится равными долями {frp_term} лет: выгода считается на средний остаток долга и снижается год от года.",
    )
    frp_fig["symbol"] = r"S_{\text{ФРП}}"

    life = max(1.0, v["service_life_years"])
    factor = max(1.0, v["accel_factor"])
    tax = v["profit_tax_pct"] / 100
    base = max(0.0, dep_gross - once)
    normal = base / life
    fast = min(base, base * factor / life)
    amort_first = (fast - normal) * tax
    amort_fig = _fig(
        "subsidy_amort", "Налог переносится на потом", amort_first, "₽/год",
        r"\Delta\text{Налог}_1 = \left(\min\left(B \times \dfrac{K_{\text{уск}}}{T_{\text{сл}}},\ B\right) - \dfrac{B}{T_{\text{сл}}}\right) \times t_{\text{приб}}",
        rf"\left({_t(fast)} - {_t(normal)}\right) \times {_t(v['profit_tax_pct'])}\% = {_t(amort_first)}\ \text{{₽}}",
        [_var("B", "База амортизации: CAPEX без обучения и субсидии", base, "₽", "calc"), _norm_var(params, "service_life_years"), _norm_var(params, "accel_factor"), _norm_var(params, "profit_tax_pct")],
        "Первый год. Это не отдельный доход, а другой график амортизации: налог меньше в первые годы и больше потом. Уже учтено в денежном потоке.",
    )
    amort_fig["symbol"] = r"\Delta\text{Налог}"

    figs = {"mpt": mpt_fig, "frp": frp_fig, "amort": amort_fig}
    for code, label, subtitle, kind, keys in SUBSIDIES:
        if code not in figs:
            continue
        fig = figs[code]
        if code == "frp":
            total = sum(frp_year(year) for year in range(1, horizon + 1))
        elif code == "amort":
            total = amort_first
        else:
            total = fig["value"]
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
    return {
        "once": once,
        "frp": (lambda year: frp_year(year)) if "frp" in on else (lambda _year: 0.0),
        "accelerated": "amort" in on,
        "accel": factor,
        "year_lines": [frp_fig] if "frp" in on else [],
        "items": items,
    }


def _sensitivity(
    rows: list[dict],
    site: dict,
    tasks: list[dict],
    params: dict[str, dict],
    report: dict,
    by_process: dict[str, dict[str, float]] | None = None,
    subsidies: frozenset[str] = frozenset(),
) -> list[dict]:
    """Торнадо: NPV и окупаемость покупки на границах диапазона каждого параметра."""
    base = _metric(report)
    out = []

    def row(key, label, unit, value, low, high, level, note, values):
        swing = abs(values[1]["npv"] - values[0]["npv"]) if values[0]["npv"] is not None and values[1]["npv"] is not None else None
        return {
            "key": key, "label": label, "unit": unit, "value": value, "low_value": low, "high_value": high,
            "level": level, "range_note": note,
            "payback_low": values[0]["payback"], "payback_high": values[1]["payback"],
            "effect_low": values[0]["effect"], "effect_high": values[1]["effect"],
            "npv_low": values[0]["npv"], "npv_high": values[1]["npv"],
            "rent_npv_low": values[0].get("rent_npv"), "rent_npv_high": values[1].get("rent_npv"), "rent_npv": base.get("rent_npv"),
            "payback": base["payback"], "effect": base["effect"], "npv": base["npv"],
            "swing": swing,
        }

    for key in _SENSITIVE:
        current = params[key]["value"]
        if not current:
            continue
        low, high, level, note = _range(params, key)
        values = []
        for bound in (low, high):
            changed = {k: dict(v) for k, v in params.items()}
            changed[key]["value"] = bound
            values.append(_metric(_compute(rows, site, tasks, changed, by_process, subsidies=subsidies)))
        out.append(row(key, params[key]["label"], params[key]["unit"], current, low, high, level, note, values))
    fte = (report.get("release") or {}).get("fte") or 0
    if fte:
        width = LEVEL_WIDTH["B"]
        values = [_metric(_compute(rows, site, tasks, params, by_process, subsidies=subsidies, release_scale=scale)) for scale in (1 - width, 1 + width)]
        out.append(row("release", "Высвобождение людей", "чел.", fte, fte * (1 - width), fte * (1 + width), "B",
                       "Данные площадки, уровень B: ±10%. Сужается, если заказчик подтвердит численность на операциях.", values))
    total = sum((item["swing"] or 0) ** 2 for item in out)
    for item in out:
        item["share"] = (item["swing"] or 0) ** 2 / total if total else 0
    out.sort(key=lambda item: (item["swing"] is not None, item["swing"] or 0), reverse=True)
    return out


def _swing(low: float | None, high: float | None) -> float | None:
    if low is None or high is None:
        return None
    return abs(high - low)


def _metric(report: dict) -> dict:
    purchase = next(item for item in report["scenarios"] if item["key"] == "purchase")
    rent = next((item for item in report["scenarios"] if item["key"] == "raas"), None)
    return {"payback": purchase["payback"]["value"], "effect": purchase["effect"]["value"], "npv": purchase["npv"]["value"],
            "rent_npv": rent["npv"]["value"] if rent else None}


def _verdict(payback: float | None, npv: float | None = None, owned: bool = True) -> str:
    if not owned:
        if npv is None:
            return ""
        if npv >= 0:
            return f"Аренда выгоднее ручной работы: NPV {_t_plain(npv / 1_000_000)} млн ₽."
        return f"Аренда дороже ручной работы: NPV {_t_plain(npv / 1_000_000)} млн ₽."
    if payback is None:
        text = "Окупаемости нет: денежный поток за горизонт не покрывает вложения."
    elif payback <= 3:
        text = "До 3 лет: по ТЗ решение целесообразно."
    elif payback <= 5:
        text = "3–5 лет: по ТЗ требуется анализ рисков."
    else:
        text = "Больше 5 лет: по ТЗ нужно отдельное обоснование."
    if npv is not None and payback is not None and npv < 0:
        text += " NPV отрицательный: с учётом стоимости денег вложения не возвращаются."
    return text


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
        try:
            value = float(raw)
        except OverflowError:
            return None
        return value if math.isfinite(value) else None
    try:
        value = float(str(raw).replace(" ", "").replace(",", "."))
    except ValueError:
        return None
    return value if math.isfinite(value) else None


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


def _reprice(item: dict, params: dict[str, dict], s: dict) -> dict:
    clone = dict(item)
    factor = params["price_factor"]["value"] / 100
    vat = params["vat_pct"]["value"] / 100
    count = item["count_used"] or 0
    price = item["price_rub"] or 0
    kwh = item["kwh_per_hour"] or 0 if item.get("kwh_source") == "card" else params["energy_kwh"]["value"]
    hours = item.get("operating_hours_year", (s.get("hours") or {}).get("value")) or 0
    clone["price_used"] = price * factor / (1 + vat)
    clone["cost_rub"] = count * clone["price_used"]
    clone["kwh_per_hour"] = kwh
    clone["energy_rub"] = count * kwh * hours * params["energy_tariff"]["value"]
    return clone


def _process_bundle(
    s: dict,
    item: dict,
    share: float,
    note: str,
    params: dict[str, dict],
    full: bool = True,
    subsidies: frozenset[str] | None = None,
) -> tuple[dict, dict, dict, dict]:
    """Процесс отдельно: как если бы роботизировали только его. Высвобождение и посты диспетчеров — свои."""
    code = item["process_code"]
    release = [row for row in s.get("release") or [] if row["process_code"] == code]
    operator = _operator_cost(s["site"], params)
    clone = _reprice(item, params, s)
    factor = params["salary_factor"]["value"] / 100
    staff_cost = sum(row["staff"] * (row["rate"] or 0) * factor for row in release)
    payroll = {
        "total": staff_cost,
        "lines": [],
        "fig": _fig("payroll", "ФОТ процесса до роботизации", staff_cost, "₽/год",
                    r"\text{ФОТ}_{\text{проц}} = L \times W_{\text{год}} \times f_{\text{ФОТ}}", rf"= {_t(staff_cost)}\ \text{{₽}}", [], note),
    }
    one = {
        "fleet": [clone],
        "included": [clone],
        "robots": clone["count_used"] or 0,
        "equipment": clone["cost_rub"] or 0,
        "hours": s["hours"],
        "payroll": payroll,
        "release": release,
        "operator": operator,
        "params": params,
        "p": {key: value["value"] for key, value in params.items()},
        "horizon": s["horizon"],
        "by_process": {},
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
    npv = purchase["npv"]["value"]
    return effect > 0 and npv is not None and npv >= 0


def _profit_status(purchase: dict, horizon: int) -> tuple[bool, str]:
    npv = purchase["npv"]["value"] or 0
    payback = purchase["payback"]["value"]
    npv_text = f"NPV {'+' if npv >= 0 else ''}{_t_plain(npv / 1_000_000)} млн ₽"
    if _meets(purchase, horizon):
        if payback is None:
            return True, f"Вложений нет, эффект в год положительный: {npv_text}."
        return True, f"Покупка окупается за {_t_plain(payback)} лет, {npv_text}."
    effect = purchase["effect"]["value"] or 0
    if effect <= 0:
        return False, "Покупка невыгодна: годовые затраты процесса больше его экономии на персонале."
    if payback is None:
        return False, f"Покупка не окупается за горизонт {horizon} лет: {npv_text}."
    return False, f"Покупка окупается за {_t_plain(payback)} лет, но с учётом стоимости денег не возвращает вложения: {npv_text}."


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
    for code in PURCHASE_SUBSIDIES:
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
    # Комбинацию ищем, если среди подсказок нет реалистичного изменения самого процесса или меры поддержки.
    if not any(row["scope"] != "site" and _realistic(row) for row in found):
        combo = _combo_hint(s, item, share, note, params, on, labels)
        if combo:
            found.append(combo)
    for row in found:
        row.pop("_rank", None)
    return found


def _combo_hint(s: dict, item: dict, share: float, note: str, params: dict[str, dict], on: frozenset[str], labels: dict[str, str]) -> dict | None:
    """Если ни одно изменение по отдельности не помогает — скидка вендора вместе со всеми мерами господдержки.
    Ищем наименьшую скидку, при которой процесс окупается; не помогает и это — процесс невыгоден."""
    horizon = s["horizon"]
    every = frozenset(on) | frozenset(PURCHASE_SUBSIDIES)
    extra = [code for code in PURCHASE_SUBSIDIES if code not in on]
    norm = params["price_factor"]

    def meets(value: float) -> bool:
        _one, _asis, purchase, _raas = _process_bundle(s, item, share, note, _with_param(params, "price_factor", value), full=False, subsidies=every)
        return _meets(purchase, horizon)

    current = norm["value"]
    target = current if meets(current) else _closest(norm["min"], norm["max"], norm["step"] or 1, current, -1, meets)
    if target is None:
        return None
    _one, _asis, purchase, _raas = _process_bundle(s, item, share, note, _with_param(params, "price_factor", target), full=False, subsidies=every)
    return {
        "key": "price_factor",
        "label": "Скидка вендора и меры господдержки вместе" if extra else norm["label"],
        "unit": norm["unit"],
        "scope": "combo" if extra else "process",
        "with": extra,
        "with_labels": [labels[code] for code in extra],
        "from": _round_step(current, norm["step"] or 1),
        "to": _round_step(target, norm["step"] or 1),
        "effect": purchase["effect"]["value"],
        "payback": purchase["payback"]["value"],
    }


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


def _process_views(s: dict, priced: list[dict] | None = None) -> list[dict]:
    """Каждый процесс так, будто роботизируют только его: вся его роль или задача и свои посты диспетчеров.
    Исключённый пользователем процесс тоже считается — чтобы было видно, почему он невыгоден."""
    release = {row["process_code"]: row for row in s.get("release") or []}
    factor = s["p"]["salary_factor"] / 100
    savings = {code: row["fte"] * (row["rate"] or 0) * factor for code, row in release.items()}
    total = sum(savings.values())
    # С кем процесс делит роль площадки в парке: роботизировать оба — люди всё равно уйдут один раз.
    shared: dict[str, list[str]] = {}
    for row in release.values():
        if row["source"] == "role" and row["split"] > 1:
            shared[row["process_code"]] = [other["process_name"] for other in release.values() if other["group"] == row["group"] and other is not row]
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
            "off": bool(item.get("off")),
            "note": item["note"],
            "share": 0,
            "share_note": "",
            "release": None,
            "story": None,
            "status": "none",
            "condition": None,
            "profitable": None,
            "reason": item["note"],
            "payroll": None,
            "scenarios": [],
            "suggestions": [],
        }
        if not item["included"]:
            out.append(base)
            continue
        code = item["process_code"]
        params = _local_params(s, code)
        solo = _release(s["site"], s["tasks"], [item], params, s["hours"])["items"]
        ctx = {**s, "release": solo}
        row = solo[0] if solo else None
        share = 0 if item.get("off") else (savings.get(code, 0) / total if total else 0)
        note = (row["note"] or _release_how(row)) if row else ""
        one, asis, purchase, raas = _process_bundle(ctx, item, share, note, params)
        purchase.pop("support_items", None)
        saving = (row["fte"] * (row["rate"] or 0) * factor) if row else 0
        if saving <= 0:
            ok, reason = False, (row["note"] if row and row["note"] else "Высвобождения нет: экономии на персонале не будет.")
        else:
            ok, reason = _profit_status(purchase, s["horizon"])
        story = _process_story(row, item, purchase, factor, shared.get(code, []))
        story["unit"] = _unit_cost(s, item, story)
        suggestions = [] if ok or saving <= 0 else _suggestions(ctx, item, share, note, params)
        # Вывод по процессу: выгоден; окупится с условием — есть ближайшее изменение, при котором NPV ≥ 0;
        # нет данных о людях; невыгоден.
        condition = _condition(suggestions)
        status = "ok" if ok else "no_staff" if story["needs_staff"] else "conditional" if condition else "bad"
        # Невыгоден при нынешнем числе роботов — ищем число, при котором он выгоден: это решает сама платформа.
        tuning = None if ok or saving <= 0 else _best_count(ctx, item, params, row)
        base.update({
            "share": share,
            "share_note": note,
            "release": {key: row[key] for key in ("source", "role", "staff", "split", "auto", "fte", "capped", "rate", "wage_month", "note")} if row else None,
            "story": story,
            "status": status,
            "condition": condition if status == "conditional" else None,
            "profitable": ok,
            "reason": reason,
            "payroll": _saving_fig(one),
            "scenarios": [asis, purchase, raas],
            "suggestions": suggestions,
            "tuning": tuning,
        })
        out.append(base)
    return out


def _best_count(s: dict, item: dict, params: dict[str, dict], row: dict | None) -> dict | None:
    """Число роботов, при котором процесс сам по себе даёт наибольший NPV. Больше людей, чем есть на процессе,
    роботы не заменят, поэтому лишние машины только добавляют вложения и расходы."""
    if not row or not row["staff"]:
        return None
    current = int(round(item["count_used"] or 0))
    hours = (s.get("hours") or {}).get("value") or 0
    fte_hours = params["fte_hours"]["value"]
    # Сколько роботов нужно, чтобы забрать всю автоматизируемую работу людей процесса.
    enough = math.ceil(row["staff"] * row["auto"] * fte_hours / hours) if hours and fte_hours else current
    upper = int(min(COUNT_MAX, max(current, enough, 1)))
    if upper <= 1 and current <= 1:
        candidates = [1]
    elif upper <= 60:
        candidates = list(range(1, upper + 1))
    else:
        candidates = sorted({1, current, enough, *(max(1, round(upper * step / 40)) for step in range(1, 41))})

    def npv_at(count: int) -> tuple[float | None, dict]:
        clone = {**item, "count_used": float(count)}
        solo = _release(s["site"], s["tasks"], [clone], params, s["hours"])["items"]
        if not solo or solo[0]["fte"] <= 0:
            return None, {}
        _one, _asis_, purchase, _raas_ = _process_bundle({**s, "release": solo}, clone, 0, "", params, full=False)
        return purchase["npv"]["value"], purchase

    best = None
    for count in candidates:
        npv, purchase = npv_at(count)
        if npv is not None and (best is None or npv > best[1] + 1):
            best = (count, npv, purchase)
    if best is None or best[0] == current or best[1] < 0:
        return None
    count, npv, purchase = best
    return {"from": current, "to": count, "npv": npv, "payback": purchase["payback"]["value"],
            "capex": purchase["capex"]["value"] or 0, "enough": enough}


def _release(site: dict, tasks: list[dict], included: list[dict], params: dict[str, dict], hours: dict) -> dict:
    """Сколько людей уходит с каждого процесса парка. Только из данных: численность задачи или роли площадки,
    доля работы, которую берут роботы, и целые ставки в каждой смене. Нет численности — нет и экономии."""
    p = {key: item["value"] for key, item in params.items()}
    burden_raw = _num(site.get("payroll_burden"))
    burden = burden_raw if burden_raw else LAW_BURDEN
    staffed = _task_staff(tasks, burden)
    shifts = max(1, int(_num(site.get("shifts_per_day")) or 1))
    robot_hours = (hours or {}).get("value")
    fte_hours = p["fte_hours"]
    rate_default, _rate_note = _default_rate(site)
    codes: list[str] = []
    names: dict[str, str] = {}
    robots: dict[str, float] = {}
    specs: dict[str, dict] = {}
    for item in included:
        code = item["process_code"]
        if code not in robots:
            codes.append(code)
            names[code] = item.get("process_name") or code
            robots[code] = 0.0
            specs[code] = {**(item.get("specs") or {}), "_rate_own": item.get("rate_own")}
        robots[code] += item.get("count_used") or 0
    roles = {role[0]: role for role in _ROLES}
    members = {role: [code for code in codes if code in procs and code not in staffed] for role, procs in ROLE_PROCESSES.items()}
    role_of = {code: role for role, items in members.items() for code in items}

    items: list[dict] = []
    for code in codes:
        name = names[code]
        cap = robots[code] * robot_hours / fte_hours if robot_hours and fte_hours else None
        row = {
            "process_code": code, "process_name": name, "robots": robots[code], "source": "", "role": "",
            "staff": 0.0, "split": 1, "auto": 1.0, "auto_note": "", "cap": cap, "capped": False, "raw": 0.0, "fte": 0.0,
            "rate": None, "wage_month": None, "group": "", "shifts": shifts, "note": "", "request": None,
            "by_cost": False, "cost_month": None, "other_month": None, "work": None,
        }
        task = staffed.get(code)
        row["work"] = _work(code, specs.get(code) or {}, site, task, robots[code], robot_hours)
        role = role_of.get(code)
        if task:
            rate = task["rate"] or rate_default
            row.update(source="task", staff=task["fte"], group=f"task:{code}", rate=rate, by_cost=bool(task.get("by_cost")), cost_month=task.get("cost_month"),
                       other_month=task.get("other_month"),
                       wage_month=None if task.get("by_cost") else task["wage_month"] or (rate / 12 / burden if rate else None))
            if not rate:
                row["note"] = "Нет стоимости сотрудника: экономию посчитать не из чего."
                row["request"] = {"to": "customer", "question": f"Сколько стоит в год сотрудник на процессе «{name}»?"}
        elif role:
            count_key, salary_key, label, _tag = roles[role]
            headcount = _num(site.get(count_key)) or 0.0
            salary = _num(site.get(salary_key))
            split = len(members[role])
            row.update(source="role", role=label, staff=headcount / split, split=split, group=f"role:{role}",
                       rate=salary * 12 * burden if salary else None, wage_month=salary)
            if not headcount:
                row["note"] = f"На площадке не задана численность роли «{label}»."
                row["request"] = {"to": "customer", "question": f"Сколько человек работает в роли «{label}»?"}
            elif not salary:
                row["note"] = f"У роли «{label}» не задана зарплата: экономию посчитать не из чего."
                row["request"] = {"to": "customer", "question": f"Какая зарплата у роли «{label}»?"}
        elif code in ASSISTED:
            row["note"] = f"{ASSISTED[code]} Высвобождение не считается, пока вендор не даст выработку человека до и после."
            row["request"] = {"to": "vendor", "question": f"Во сколько раз растёт выработка человека на процессе «{name}» с вашим решением?"}
        else:
            row["note"] = "В данных площадки нет численности на этой операции: высвобождение не считается."
            row["request"] = {"to": "customer", "question": f"Сколько человек сейчас работает на процессе «{name}» и сколько стоит сотрудник в год?"}
        if row["staff"] > 0:
            field = MANUAL_SHARE.get(code)
            pct = _num(site.get(field[0])) if field else None
            if field and pct:
                row["auto"] = min(1.0, max(0.0, 1 - pct / 100))
                row["auto_note"] = f"{_t_plain(pct)}% — {field[1]}: их робот не берёт."
            raw = row["staff"] * row["auto"]
            work = row["work"]
            if work and work["volume_year"] and work["robot_year"]:
                # Роботы забирают операции: сколько их делает парк за год против автоматизируемого объёма.
                coverage = min(row["auto"], work["capacity_year"] / work["volume_year"])
                work.update(auto=row["auto"], coverage=coverage, taken_year=coverage * work["volume_year"],
                            robots_full=math.ceil(row["auto"] * work["volume_year"] / work["robot_year"] - 1e-9))
                if not row["by_cost"]:
                    work["person_rate"] = work["volume_year"] / (row["staff"] * fte_hours) if fte_hours else None
                    work["replaces"] = work["robot_year"] / (work["person_rate"] * fte_hours) if work["person_rate"] and fte_hours else None
                raw = row["staff"] * coverage
                row["capped"] = coverage < row["auto"] - 1e-9
                row["cap"] = None
                cap = None
            elif cap is not None and raw > cap:
                raw = cap
                row["capped"] = True
                row["request"] = row["request"] or {
                    "to": "vendor",
                    "question": f"Сколько человеко-часов заменяет час работы робота на процессе «{name}»?",
                }
            row["raw"] = raw
        items.append(row)

    # Люди уходят целыми ставками в каждой смене: округление по роли или задаче, затем доля процесса.
    groups: dict[str, list[dict]] = {}
    for row in items:
        if row["group"] and row["raw"] > 0:
            groups.setdefault(row["group"], []).append(row)
    for rows_ in groups.values():
        total = sum(row["raw"] for row in rows_)
        if any(row["by_cost"] for row in rows_):
            # Затраты суммой: людей не знаем, округлять до ставок нечего — экономия пропорциональна операциям.
            for row in rows_:
                row["fte"] = row["raw"]
            continue
        real = shifts * math.floor(total / shifts + 1e-9)
        for row in rows_:
            row["fte"] = real * row["raw"] / total if total else 0.0
            if not real:
                row["note"] = row["note"] or f"Робот забирает меньше одного человека на смену ({_t_plain(total)} чел. на {shifts} смен): целой ставки не освобождается."
    staff_total = _num(site.get("staff_total"))
    released = sum(row["fte"] for row in items)
    if staff_total and released > staff_total:
        for row in items:
            row["fte"] *= staff_total / released
        released = staff_total

    base = sum(task["fte"] for task in staffed.values())
    if not base:
        base = sum(_num(site.get(role[0])) or 0 for role in _ROLES)
    share = released / base if base else None
    check = ""
    if share is not None and share > CHECK_SHARE + 1e-9:
        check = (f"Высвобождается {_t_plain(share * 100)}% персонала — больше ориентира демо-проекта организатора "
                 f"({_t_plain(CHECK_SHARE * 100)}%). Проверьте численность и покрытие процессов.")
    summary = {
        "fte": released,
        "base_fte": base,
        "share": share,
        "check": check,
        "items": [
            {key: row[key] for key in ("process_code", "process_name", "source", "role", "staff", "split", "auto", "auto_note", "capped", "cap", "fte", "rate",
                                       "wage_month", "group", "note", "by_cost", "cost_month", "other_month", "work")}
            for row in items
        ],
    }
    return {"items": items, "summary": summary}


def _spec(specs: dict, key: str) -> float | None:
    raw = specs.get(key)
    if raw is None or raw == "":
        return None
    normalized = normalize_value(key, raw)
    value = _num(normalized[1] if normalized else raw)
    return value if value and value > 0 else None


def _work(code: str, specs: dict, site: dict, task: dict | None, robots: float, robot_hours: float | None) -> dict | None:
    """Работа процесса в операциях: объём в сутки и в год, выработка одного робота в час и парка за год."""
    model = WORK.get(code)
    if not model:
        return None
    days = _num(site.get("days_year"))
    per_day = (task or {}).get("flow")
    source = "задача"
    if not per_day:
        volume = model["volume"]
        per_day = sum(_num(site.get(key)) or 0 for key in volume) if isinstance(volume, tuple) else float(volume)
        source = "площадка" if isinstance(volume, tuple) else "норма формулы подбора"
    speed = _spec(specs, "speed_loaded_ms")
    rate, how = None, ""
    own_rate = _num(specs.get("_rate_own"))
    if own_rate:
        rate, how = own_rate, "указано в проекте"
    elif model["kind"] == "move" and speed:
        route_task = (task or {}).get("route")
        route_site = model["route"] if isinstance(model["route"], (int, float)) else _num(site.get(model["route"]))
        one_way = route_task or route_site
        if one_way:
            route = (2 * one_way) if route_task or not isinstance(model["route"], (int, float)) else one_way
            rate = 3600 / (route / speed + 80)
            how = f"3600 / ({_t_plain(route)} м / {_t_plain(speed)} м/с + 80 с на погрузку и выгрузку)"
    elif model["kind"] == "patrol" and speed:
        area = _num(site.get("area_m2"))
        if area:
            rate = 3600 / (4 * math.sqrt(area) / speed + 240)
            how = f"3600 / (периметр {_t_plain(round(4 * math.sqrt(area)))} м / {_t_plain(speed)} м/с + 240 с)"
    elif model["kind"] == "area":
        rate = _spec(specs, "proizvoditelnost")
        how = "паспортная производительность, м²/ч" if rate else ""
    elif model["kind"] == "scan":
        rate = _spec(specs, "throughput")
        how = "паспортная производительность, паллетомест в час" if rate else ""
    hours = robot_hours or 0
    effective = rate * READY if rate else None
    volume_year = per_day * days if per_day and days else None
    robot_year = effective * hours if effective and hours else None
    capacity = robots * robot_year if robot_year else 0.0
    return {
        "unit": list(model["unit"]),
        "per_day": per_day or None,
        "volume_year": volume_year,
        "volume_source": source,
        "robot_rate": effective,
        "robot_rate_how": f"{how} × готовность {_t_plain(READY)}" if how else "",
        "robot_rate_own": bool(own_rate),
        "robot_rate_raw": rate,
        "robot_year": robot_year,
        "robots": robots,
        "capacity_year": capacity,
        "robots_full": math.ceil(volume_year / robot_year - 1e-9) if volume_year and robot_year else None,
        "auto": 1.0,
        "coverage": min(1.0, capacity / volume_year) if volume_year and robot_year else None,
        "taken_year": min(volume_year, capacity) if volume_year and robot_year else None,
        "person_rate": None,
        "replaces": None,
    }


def _saving_fig(s: dict) -> dict:
    """Экономия ФОТ: высвобожденные ставки на стоимость сотрудника."""
    factor = s["p"]["salary_factor"] / 100
    rows = [row for row in s.get("release") or []]
    value = sum(row["fte"] * (row["rate"] or 0) * factor for row in rows)
    fte = sum(row["fte"] for row in rows)
    factor_var = _norm_var_fraction(s["p"], "salary_factor", s["params"])
    if len(rows) == 1:
        row = rows[0]
        how = _release_how(row)
        fig = _fig(
            "saving", "Экономия ФОТ", value, "₽/год",
            r"\Delta\text{ФОТ} = \Delta L \times W_{\text{год}} \times f_{\text{ФОТ}}",
            rf"{_t(row['fte'], 1)} \times {_t(row['rate'] or 0)} \times {_t(factor, 2)} = {_t(value)}\ \text{{₽}}",
            [
                _var(r"\Delta L", "Высвобождается людей", row["fte"], "чел.", "site" if row["source"] else "calc", how),
                _var(r"W_{\text{год}}", "Стоимость сотрудника в год с начислениями", row["rate"], "₽/год", "site"),
                factor_var,
            ],
            row["note"] or how,
        )
    else:
        vars_ = [
            _var(rf"\Delta L_{{{index}}}", f"{row['process_name']}: высвобождается", row["fte"], "чел.", "site" if row["source"] else "calc",
                 row["note"] or _release_how(row))
            for index, row in enumerate(rows, start=1)
        ]
        fig = _fig(
            "saving", "Экономия ФОТ", value, "₽/год",
            r"\Delta\text{ФОТ} = \sum_p \Delta L_p \times W_p \times f_{\text{ФОТ}}",
            rf"{_t(fte, 1)}\ \text{{чел.}} \Rightarrow {_t(value)}\ \text{{₽}}",
            [*vars_, factor_var],
            "Люди, чью работу забирают роботы: численность задачи или роли площадки, без нестандартных грузов, целыми ставками по сменам.",
        )
    fig["symbol"] = r"\Delta\text{ФОТ}"
    return fig


def _release_how(row: dict) -> str:
    if not row["source"]:
        return row["note"]
    parts = []
    if row["source"] == "task":
        parts.append(f"На задаче {_t_plain(row['staff'])} чел.")
    else:
        parts.append(f"{row['role']}: {_t_plain(row['staff'] * row['split'])} чел." + (f", поровну на {row['split']} процесса парка" if row["split"] > 1 else ""))
    if row["auto"] < 1:
        parts.append(f"роботы берут {_t_plain(row['auto'] * 100)}% работы ({row['auto_note']})")
    if row["capped"]:
        parts.append(f"не больше, чем людей на часы работы роботов: {_t_plain(row['cap'])} чел.")
    parts.append(f"целыми ставками на {row['shifts']} смен → {_t_plain(row['fte'])} чел.")
    return "; ".join(parts) + "."


def _no_support() -> dict:
    return {"once": 0.0, "frp": lambda _year: 0.0, "accelerated": False, "accel": 1.0, "year_lines": [], "items": []}


def _real_rate(p: dict) -> float:
    return (1 + p["market_rate_pct"] / 100) / (1 + p["inflation_target_pct"] / 100) - 1


def _rate_fig(params: dict[str, dict]) -> dict:
    p = {key: item["value"] for key, item in params.items()}
    rate = _real_rate(p)
    fig = _fig(
        "discount", "Ставка дисконтирования", rate * 100, "%",
        r"r = \dfrac{1 + r_{\text{КС}}}{1 + \pi^{*}} - 1",
        rf"\dfrac{{1 + {_t(p['market_rate_pct'] / 100, 3)}}}{{1 + {_t(p['inflation_target_pct'] / 100, 3)}}} - 1 = {_t(rate * 100, 1)}\%",
        [_norm_var(params, "market_rate_pct"), _norm_var(params, "inflation_target_pct")],
        "Расчёт в постоянных ценах: зарплаты и тарифы не индексируются, поэтому ставка реальная, без инфляции.",
    )
    fig["symbol"] = "r"
    return fig


def _cashflow(s: dict, capex: float, saved: float, opex: float, dep_base: float, expensed: float, support: dict,
              growing: tuple[float, float] | None = None) -> dict:
    """Годовой денежный поток после налога: уведомление и выплаты при сокращении, амортизация, остаточная стоимость."""
    p, horizon = s["p"], s["horizon"]
    factor = p["salary_factor"] / 100
    tax = p["profit_tax_pct"] / 100
    notice = min(12.0, max(0.0, p["notice_months"]))
    payouts = sum(row["fte"] * (row["wage_month"] or 0) * factor for row in s.get("release") or []) * p["severance_months"]
    life = max(1.0, p["service_life_years"])
    cycle = max(1, int(round(life)))
    linear = dep_base / life
    yearly_dep = min(dep_base, dep_base * support["accel"] / life) if support["accelerated"] else linear
    rate = _real_rate(p)
    left = dep_base
    rows = []
    cumulative = -capex
    discounted = -capex
    pbp = dpp = None
    npv = -capex
    inflow = 0.0
    flows = [-capex]
    base_opex = opex
    # Чистая прибыль по годам: CAPEX входит в расходы долями через амортизацию, налог на прибыль вычтен.
    net_income = 0.0
    for year in range(1, horizon + 1):
        # Платёж, который дорожает по договору: в год t он больше на (1 + g)^(t−1).
        opex = base_opex + (growing[0] * ((1 + growing[1]) ** (year - 1) - 1) if growing else 0.0)
        months = 12 - notice if year == 1 else 12.0
        saving = saved * months / 12
        paid = payouts if year == 1 else 0.0
        # Срок службы кончился, а горизонт нет: парк покупается заново по тем же ценам, амортизация начинается снова.
        reinvest = capex if year > 1 and (year - 1) % cycle == 0 else 0.0
        if reinvest:
            left = dep_base
        age = (year - 1) % cycle + 1
        dep = min(yearly_dep, left)
        left -= dep
        frp = support["frp"](year)
        cost = expensed if year == 1 else 0.0
        profit = saving - opex - paid - dep - cost + frp
        tax_value = tax * profit
        net_income += profit - tax_value
        operating = saving - opex - paid + frp - tax_value - reinvest
        # Остаточная стоимость — по линейному износу: техника стоит столько же, как бы её ни списывали.
        # Если баланс ниже (ускоренная амортизация), с разницы платится налог.
        value_left = max(0.0, dep_base - linear * age)
        # Сколько стоит своя техника на конец года: по износу, за вычетом налога с превышения над балансом.
        asset = value_left - tax * max(0.0, value_left - left)
        residual = asset if year == horizon else 0.0
        cash = operating + residual
        disc = (1 + rate) ** year
        if pbp is None and operating > 0 and cumulative + operating >= 0:
            pbp = year - 1 + (-cumulative) / operating
        if dpp is None and operating > 0 and discounted + operating / disc >= 0:
            dpp = year - 1 + (-discounted) / (operating / disc)
        cumulative += operating
        discounted += operating / disc
        npv += cash / disc
        inflow += cash
        flows.append(cash)
        rows.append({
            "year": year,
            "saving_rub": saving,
            "opex_rub": -opex,
            "growth_rub": -(opex - base_opex),
            "payouts_rub": -paid,
            "support_rub": frp,
            "depreciation_rub": dep,
            "net_income_rub": profit - tax_value,
            "tax_rub": -tax_value,
            "residual_rub": residual,
            "reinvest_rub": -reinvest,
            "cf_rub": cash,
            "asset_rub": asset,
            "cash_cumulative": cumulative,
            "cumulative": cumulative + residual,
            "discounted": discounted + residual / disc,
        })
    if capex <= 0:
        pbp = dpp = None
    return {
        "rows": rows,
        "npv": npv,
        "irr": _irr(flows),
        "pbp": pbp,
        "dpp": dpp,
        "roi": (inflow - capex) / capex * 100 if capex > 0 else None,
        "inflow": inflow,
        "net_income": net_income,
        "residual": rows[-1]["residual_rub"] if rows else 0.0,
        "asset_start": dep_base,
        "rate": rate,
        "payouts": payouts,
    }


def _irr(flows: list[float]) -> float | None:
    def npv(rate: float) -> float:
        return sum(value / (1 + rate) ** year for year, value in enumerate(flows))

    low, high = -0.99, 10.0
    if flows[0] >= 0 or npv(low) * npv(high) > 0:
        return None
    for _ in range(200):
        mid = (low + high) / 2
        if npv(low) * npv(mid) <= 0:
            high = mid
        else:
            low = mid
    return (low + high) / 2


def _requests(s: dict) -> list[dict]:
    """Чего не хватает расчёту: вопросы заказчику и вендору. Каждое допущение или пустое поле — отдельный вопрос."""
    out = []
    for row in s.get("release") or []:
        if row["request"]:
            out.append({**row["request"], "process_code": row["process_code"], "process_name": row["process_name"], "why": row["note"] or _release_how(row)})
    params = s["params"]
    if s["robots"] and params["robots_per_operator"]["source"] == "norm":
        out.append({"to": "vendor", "process_code": "", "process_name": "", "question": "Сколько машин ведёт один диспетчер в вашей системе управления парком?",
                    "why": f"Допущение {_t_plain(params['robots_per_operator']['value'])} машин на пост задаёт персонал эксплуатации — главную статью OPEX."})
    if s["robots"] and params["service_pct"]["source"] == "norm":
        out.append({"to": "vendor", "process_code": "", "process_name": "", "question": "Сколько стоит сервисный договор после гарантии, % цены в год?",
                    "why": "В карточках сервиса нет, взята медиана по 6 вендорам."})
    if s["robots"] and params["energy_tariff"]["source"] == "norm":
        out.append({"to": "customer", "process_code": "", "process_name": "", "question": "Какой тариф на электроэнергию по договору энергоснабжения?",
                    "why": "Тариф площадки не задан, взят средний коммерческий тариф."})
    return out


def _range(params: dict[str, dict], key: str) -> tuple[float, float, str, str]:
    """Диапазон параметра: из источника норматива, если значение стандартное, иначе по уровню достоверности."""
    item = params[key]
    value = item["value"]
    level = LEVELS.get(key, "C")
    if item["source"] == "site":
        level = "B"
    elif item["source"] == "project":
        level = "B"
    source = RANGES.get(key)
    if source and item["source"] == "norm" and source[0] <= value <= source[1]:
        return source[0], source[1], level, source[2]
    width = LEVEL_WIDTH[level]
    low, high = value * (1 - width), value * (1 + width)
    note = f"Уровень {level}: ±{_t_plain(width * 100)}%, в источнике диапазона нет."
    return max(item["min"], low), high, level, note


def _interval(report: dict) -> dict:
    """Интервал NPV и окупаемости: корень из суммы квадратов отклонений по торнадо, вниз и вверх отдельно."""
    base = _metric(report)
    rows = report.get("sensitivity") or []

    def spread(center, key_low, key_high):
        if center is None:
            return None, None
        down = up = 0.0
        for item in rows:
            values = [item[key_low], item[key_high]]
            if any(value is None for value in values):
                continue
            deltas = [value - center for value in values]
            down += min(0.0, *deltas) ** 2
            up += max(0.0, *deltas) ** 2
        return center - math.sqrt(down), center + math.sqrt(up)

    npv_low, npv_high = spread(base["npv"], "npv_low", "npv_high")
    pay_low, pay_high = spread(base["payback"], "payback_low", "payback_high")
    return {
        "npv": base["npv"], "npv_low": npv_low, "npv_high": npv_high,
        "payback": base["payback"], "payback_low": max(0.0, pay_low) if pay_low is not None else None, "payback_high": pay_high,
        "note": "Каждый параметр двигается в своём диапазоне из источника норматива или по уровню достоверности A–D; "
                "отклонения складываются как корень из суммы квадратов.",
    }


def _breakeven(
    rows: list[dict],
    site: dict,
    tasks: list[dict],
    params: dict[str, dict],
    report: dict,
    by_process: dict[str, dict[str, float]] | None = None,
    subsidies: frozenset[str] = frozenset(),
) -> list[dict]:
    """Точки безубыточности покупки: при каком значении параметра NPV = 0, и запас прочности до него."""
    if not report.get("robots"):
        return []
    base_npv = _metric(report)["npv"]
    fte = (report.get("release") or {}).get("fte") or 0
    out = []

    def npv_at(key: str, value: float) -> float:
        if key == "release":
            return _metric(_compute(rows, site, tasks, params, by_process, subsidies=subsidies, release_scale=value / fte))["npv"]
        changed = {k: dict(v) for k, v in params.items()}
        changed[key]["value"] = value
        return _metric(_compute(rows, site, tasks, changed, by_process, subsidies=subsidies))["npv"]

    for key, label, unit, lo, hi, integer in _BREAKEVEN:
        current = fte if key == "release" else params[key]["value"]
        if key == "release":
            if not fte:
                continue
            hi = fte * 5
        rising = npv_at(key, hi) > npv_at(key, lo)
        lo_npv, hi_npv = npv_at(key, lo), npv_at(key, hi)
        if (lo_npv >= 0) == (hi_npv >= 0):
            out.append({"key": key, "label": label, "unit": unit, "current": current, "value": None, "margin_pct": None,
                        "direction": "min" if rising else "max", "reachable": lo_npv >= 0})
            continue
        left, right = lo, hi
        for _ in range(40):
            mid = (left + right) / 2
            if integer and right - left <= 1:
                break
            if (npv_at(key, mid) >= 0) == rising:
                right = mid
            else:
                left = mid
            if not integer and right - left < 1e-3:
                break
        value = (math.ceil(right) if rising else math.floor(left)) if integer else (right if rising else left)
        margin = (value - current) / current * 100 if current else None
        out.append({"key": key, "label": label, "unit": unit, "current": current, "value": value, "margin_pct": margin,
                    "direction": "min" if rising else "max", "reachable": True, "npv": base_npv})
    return out


def _story(items: list[dict], p: dict) -> dict:
    """Объект одной строкой: сколько людей и ФОТ сейчас на роботизируемых операциях и сколько из этого уходит."""
    factor = p["salary_factor"] / 100
    groups: dict[str, dict] = {}
    for row in items:
        if not row["group"] or not row["staff"]:
            continue
        groups.setdefault(row["group"], {"staff": row["staff"] * row["split"], "rate": row["rate"] or 0})
    staff = sum(group["staff"] for group in groups.values())
    payroll = sum(group["staff"] * group["rate"] * factor for group in groups.values())
    released = sum(row["fte"] for row in items)
    saving = sum(row["fte"] * (row["rate"] or 0) * factor for row in items)
    return {"staff_now": staff, "payroll_now": payroll, "released": released, "saving": saving}


def _process_story(row: dict | None, item: dict, purchase: dict, factor: float, shared: list[str]) -> dict:
    """Процесс как история «было → стало»: люди и их стоимость сейчас, что уходит, сколько стоят роботы, что в итоге."""
    staff = row["staff"] if row else 0.0
    rate = (row["rate"] or 0) * factor if row else 0.0
    released = row["fte"] if row else 0.0
    payroll_now = staff * rate
    payroll_after = (staff - released) * rate
    robots_year = purchase["opex"]["value"] or 0
    dispatchers = next((line.get("count") for line in purchase["opex_lines"] if line["key"] == "operators"), None)
    flow = purchase.get("cashflow") or []
    return {
        "source": row["source"] if row else "",
        "role": row["role"] if row else "",
        "staff": staff,
        "wage_month": (row["wage_month"] * factor) if row and row["wage_month"] else None,
        "rate_year": rate,
        "payroll_now": payroll_now,
        "released": released,
        "remaining": max(0.0, staff - released),
        "payroll_after": payroll_after,
        "robots": item["count_used"] or 0,
        "capex": purchase["capex"]["value"] or 0,
        "robots_year": robots_year,
        "dispatchers": dispatchers,
        "cost_before": payroll_now,
        "cost_after": payroll_after + robots_year,
        "saving_year": payroll_now - payroll_after - robots_year,
        "payback": purchase["payback"]["value"],
        "npv": purchase["npv"]["value"],
        "total": flow[-1]["cumulative"] if flow else None,
        "shared_with": shared,
        "needs_staff": not (row and row["source"] and staff > 0),
        "by_cost": bool(row and row.get("by_cost")),
        "cost_month": row.get("cost_month") if row else None,
        "other_month": row.get("other_month") if row else None,
        "work": row.get("work") if row else None,
    }


# Границы реалистичного условия: дальше условие всё ещё показывается, но с пометкой «жёсткое».
_REALISTIC = {
    "price_factor": lambda item: item["from"] - item["to"] <= 30,
    "robots_per_operator": lambda item: item["to"] <= 20,
    "salary_factor": lambda item: item["to"] <= 130,
}


def _realistic(item: dict) -> bool:
    check = _REALISTIC.get(item["key"])
    return item["scope"] == "subsidy" or check is None or check(item)


def _condition(suggestions: list[dict]) -> dict | None:
    """Главное условие окупаемости. Любая подсказка делает процесс «окупится с условием»; первым показывается
    реалистичное изменение этого процесса или мера поддержки, потом — параметры площадки, и только если таких нет —
    жёсткое условие с пометкой."""
    ranked = [item for item in suggestions if item["scope"] != "site"] + [item for item in suggestions if item["scope"] == "site"]
    for item in ranked:
        if _realistic(item):
            return {**item, "hard": False}
    # Реалистичных нет: показываем самое мягкое из жёстких — с наименьшей скидкой, условия площадки последними.
    softest = sorted(ranked, key=lambda item: (item["scope"] == "site", item["from"] - item["to"] if item["key"] == "price_factor" else 1e9))
    return {**softest[0], "hard": True} if softest else None


def _completeness(report: dict, rows: list[dict], blockers: list[dict] | None) -> None:
    """Чего не хватает расчёту: причины от подбора, позиции парка вне расчёта и процессы без людей или затрат.
    Цифры не прячутся: посчитанное показывается, а недостающее — списком и подсказками у процессов."""
    out = list(blockers or [])
    out.extend({"process_code": item["process_code"], "code": "equipment_incomplete", "message": item["note"]}
               for item in report["fleet"] if not item["included"] and item["note"])
    # Количество не посчитано — в расчёте 1 робот: цифры есть, но это допущение, а не данные.
    out.extend({"process_code": item["process_code"], "code": "count_default", "message": NO_COUNT}
               for item in report["fleet"] if item["included"] and item.get("count_source") == "default")
    if not rows:
        out.append({"code": "empty_fleet", "message": "Нет подтверждённого парка для расчёта"})
    equipment = not out
    # Нет людей или затрат, или люди есть, а их стоимость неизвестна — экономии по процессу не посчитать.
    missing = [item["process_code"] for item in report.get("processes") or []
               if item["included"] and ((item.get("story") or {}).get("needs_staff") or (item.get("release") and item["release"].get("rate") is None))]
    if missing:
        out.append({"code": "labor_baseline_missing", "message": "Нет людей или затрат на части процессов", "processes": missing})
    report["blockers"] = out
    report["equipment_complete"] = equipment
    report["labor_baseline_complete"] = not missing
    report["complete"] = not out
    report["status"] = "complete" if not out else "incomplete"


def _annuity(rate: float, years: float) -> float:
    """Коэффициент аннуитета: какая доля суммы платится каждый год, чтобы за срок вернуть её со ставкой."""
    years = max(1.0, years)
    if abs(rate) < 1e-9:
        return 1 / years
    return rate / (1 - (1 + rate) ** -years)


def _profit_figs(s: dict, flow: dict, capex: float, capex_var: dict, owned: bool) -> tuple[dict, dict]:
    """Чистая прибыль за горизонт после возврата всех вложений и ROE: прибыль после налога на вложенный рубль в год."""
    horizon = s["horizon"]
    tax = s["p"]["profit_tax_pct"]
    net = flow["inflow"] - capex
    inflow_var = _var(r"\sum CF_t + V_T", "Деньги за горизонт после налога, с остаточной стоимостью техники", flow["inflow"], "₽", "calc", "Экономия ФОТ минус эксплуатация, выплаты при сокращении, повторная закупка парка и налог на прибыль.")
    net_profit = _fig(
        "net_profit", f"Чистая прибыль за {horizon} лет", net, "₽",
        r"\text{ЧП} = \sum_{t=1}^{T} CF_t + V_T - \text{CAPEX}",
        rf"{_t(flow['inflow'])} - {_t(capex)} = {_t(net)}\ \text{{₽}}",
        [inflow_var, capex_var, _t_var(s)],
        "Сколько денег остаётся у объекта за горизонт, когда все вложения уже вернулись: после налога на прибыль, выплат при сокращении и повторной закупки парка."
        if owned else "Для аренды вложения — только подготовка площадки; платёж аренды уже вычтен из потока каждого года.",
    )
    average = flow["net_income"] / horizon
    roe_value = average / capex * 100 if capex > 0 else None
    roe = _fig(
        "roe", "ROE в год", roe_value, "%",
        r"\text{ROE} = \dfrac{\overline{\text{ЧП}}_{\text{год}}}{\text{Капитал}} \times 100\%,\quad \text{ЧП}_t = (\Delta\text{ФОТ} - \text{OPEX} - \text{Выплаты}_t - \text{Аморт}_t) \times (1 - t_{\text{приб}})",
        rf"\dfrac{{{_t(average)}}}{{{_t(capex)}}} \times 100\% = {_t(roe_value, 1)}\%" if roe_value is not None else r"\text{вложений нет}",
        [
            _var(r"\overline{\text{ЧП}}_{\text{год}}", "Чистая прибыль в среднем за год", average, "₽/год", "calc", "После амортизации вложений и налога на прибыль."),
            _var(r"\text{Капитал}", "Собственный капитал = вложения (CAPEX)", capex, "₽", "calc"),
            _var(r"t_{\text{приб}}", "Налог на прибыль", tax, "%", "norm"),
        ],
        ("Финансирование — собственные средства, поэтому капитал равен CAPEX. CAPEX вычитается из прибыли долями через амортизацию, так что это доходность уже за вычетом вложений."
         if owned else "Капитал — вложения во внедрение на площадке; платёж аренды — в расходах каждого года.")
        if roe_value is not None else "Вложений нет: доходность на капитал не считается.",
    )
    return net_profit, roe


def _pi_fig(npv: float, capex: float, rate: float, owned: bool) -> dict:
    value = (npv + capex) / capex if owned and capex > 0 else None
    return _fig(
        "pi", "Индекс доходности", value, "",
        r"\text{PI} = \dfrac{\text{NPV} + \text{CAPEX}}{\text{CAPEX}} = \dfrac{\sum_t CF_t / (1 + r)^t}{\text{CAPEX}}",
        rf"\dfrac{{{_t(npv)} + {_t(capex)}}}{{{_t(capex)}}} = {_t(value, 2)}" if value is not None else "",
        [_var(r"\text{NPV}", "Чистая приведённая стоимость", npv, "₽", "calc"), _var(r"\text{CAPEX}", "Вложения", capex, "₽", "calc"),
         _var("r", "Реальная ставка дисконтирования", rate * 100, "%", "calc")],
        "Сколько приведённых рублей возвращает каждый вложенный рубль. Больше 1 — выгодно; по PI выбирают процессы, когда бюджет ограничен."
        if owned else "Для аренды не считается: своих вложений в технику нет.",
    )


def _eac_fig(s: dict, npv: float, rate: float) -> dict:
    """Годовая стоимость операций после налога: ручная работа минус выгода проекта, разложенная на горизонт."""
    p, horizon = s["p"], s["horizon"]
    tax = p["profit_tax_pct"] / 100
    payroll = s["payroll"]["total"]
    factor = _annuity(rate, horizon)
    base = payroll * (1 - tax)
    value = base - npv * factor
    return _fig(
        "eac", "Годовая стоимость с учётом вложений (EAC)", value, "₽/год",
        r"\text{EAC} = \text{ФОТ}_{\text{база}} \times (1 - t_{\text{приб}}) - \text{NPV} \times \dfrac{r}{1 - (1 + r)^{-T}}",
        rf"{_t(payroll)} \times (1 - {_t(tax, 2)}) - {_t(npv)} \times {_t(factor, 4)} = {_t(value)}\ \text{{₽}}",
        [
            _var(r"\text{ФОТ}_{\text{база}}", "ФОТ операций до роботизации", payroll, "₽/год", "calc"),
            _norm_var(s["params"], "profit_tax_pct"),
            _var(r"\text{NPV}", "Выгода сценария против ручной работы", npv, "₽", "calc"),
            _var("r", "Реальная ставка дисконтирования", rate * 100, "%", "calc"),
            _t_var(s),
        ],
        "Сколько в среднем стоит год этих операций после налога, если вложения разложить на горизонт с учётом стоимости денег. "
        "Ручная работа, покупка и аренда — на одной шкале: меньше — дешевле.",
    )


def _steady(scenario: dict) -> float | None:
    """Поток установившегося года: без уведомления, выплат при сокращении и остаточной стоимости."""
    rows = scenario.get("cashflow") or []
    if not rows:
        return None
    row = rows[min(1, len(rows) - 1)]
    return row["cf_rub"] - row["residual_rub"]


def _switch(buy: dict, rent: dict) -> dict | None:
    """Точка безразличия: через сколько месяцев использования покупка обгоняет аренду."""
    if not (buy.get("available") and rent.get("available")):
        return None
    flow_buy, flow_rent = _steady(buy), _steady(rent)
    if flow_buy is None or flow_rent is None:
        return None
    capex_buy, capex_rent = buy["capex"]["value"] or 0, rent["capex"]["value"] or 0
    gap = flow_buy - flow_rent
    months = (capex_buy - capex_rent) / gap * 12 if gap > 0 else None
    if months is not None and months < 0:
        months = 0.0
    subst = (rf"\dfrac{{{_t(capex_buy)} - {_t(capex_rent)}}}{{{_t(flow_buy)} - {_t(flow_rent)}}} \times 12 = {_t(months, 0)}\ \text{{мес.}}"
             if months is not None else r"CF_{\text{покуп}} \le CF_{\text{аренда}}:\ \text{покупка не обгоняет аренду}")
    fig = _fig(
        "switch", "Покупка выгоднее аренды через", months, "мес.",
        r"t^{*} = \dfrac{\text{CAPEX}_{\text{покуп}} - \text{CAPEX}_{\text{аренда}}}{CF_{\text{покуп}} - CF_{\text{аренда}}} \times 12",
        subst,
        [
            _var(r"\text{CAPEX}_{\text{покуп}}", "Вложения при покупке", capex_buy, "₽", "calc"),
            _var(r"\text{CAPEX}_{\text{аренда}}", "Вложения при аренде: внедрение на площадке", capex_rent, "₽", "calc"),
            _var(r"CF_{\text{покуп}}", "Поток года при покупке после налога", flow_buy, "₽/год", "calc"),
            _var(r"CF_{\text{аренда}}", "Поток года при аренде после налога", flow_rent, "₽/год", "calc"),
        ],
        "Если роботы нужны дольше — выгоднее купить, если меньше — арендовать. Поток полного года после налога, без дисконтирования."
        if months is not None else "Платёж аренды не дороже владения: при любом сроке аренда не проигрывает покупке.",
    )
    fig["symbol"] = "t^{*}"
    return fig


# Стресс-сценарии: сдвиг из источника, а не придуманный. Ключ, подпись, пояснение.
_STRESS = (
    ("volume", "Объём работ упал на 30%", "Людей на операциях на 30% меньше, а роботы уже куплены."),
    ("rate", "Дорогие деньги", "Ключевая ставка возвращается к максимуму 2024–2025 гг."),
    ("slow", "Внедрение на полгода дольше", "Экономия начинается на 6 месяцев позже, расходы на роботов — с первого года."),
    ("price", "Роботы на 20% дороже", "Курс или новая цена вендора: дороже и вложения, и сервис."),
    ("all", "Всё сразу", "Четыре неудачи одновременно — нижняя граница, которую стоит выдержать."),
)


def _stress(
    rows: list[dict],
    site: dict,
    tasks: list[dict],
    params: dict[str, dict],
    report: dict,
    by_process: dict[str, dict[str, float]] | None = None,
    subsidies: frozenset[str] = frozenset(),
) -> list[dict]:
    """Покупка в неудачных условиях: NPV и окупаемость, если пойдёт хуже, чем в центральной оценке."""
    if not report.get("robots"):
        return []
    base = _metric(report)
    rate_high = RANGES["market_rate_pct"][1]

    def shifted(key: str) -> tuple[dict[str, dict], float]:
        changed = {k: dict(v) for k, v in params.items()}
        keys = ("volume", "rate", "slow", "price") if key == "all" else (key,)
        scale = 1.0
        for one in keys:
            if one == "volume":
                scale = 0.7
            elif one == "rate":
                changed["market_rate_pct"]["value"] = max(changed["market_rate_pct"]["value"], rate_high)
            elif one == "slow":
                changed["notice_months"]["value"] = changed["notice_months"]["value"] + 6
            elif one == "price":
                changed["price_factor"]["value"] = changed["price_factor"]["value"] * 1.2
        return changed, scale

    out = []
    for key, label, note in _STRESS:
        changed, scale = shifted(key)
        value = _metric(_compute(rows, site, tasks, changed, by_process, subsidies=subsidies, release_scale=scale))
        if key == "rate":
            note = f"Ключевая ставка {_t_plain(rate_high)}% — максимум 2024–2025 гг., сейчас {_t_plain(params['market_rate_pct']['value'])}%."
        out.append({
            "key": key, "label": label, "note": note,
            "npv": value["npv"], "payback": value["payback"], "effect": value["effect"],
            "delta": value["npv"] - base["npv"] if value["npv"] is not None and base["npv"] is not None else None,
            "ok": value["npv"] is not None and value["npv"] >= 0,
        })
    return out


def _chance(report: dict, runs: int = 2000) -> dict | None:
    """Вероятность, что NPV покупки ≥ 0: случайные сочетания параметров в их диапазонах, отклик — по торнадо.
    Корреляций нет: каждый параметр двигается сам по себе."""
    base = _metric(report)["npv"]
    rows = [item for item in report.get("sensitivity") or [] if item.get("npv_low") is not None and item.get("npv_high") is not None]
    if base is None or not rows:
        return None
    rng = random.Random(20260101)
    positive = 0
    values = []
    for _ in range(runs):
        total = base
        for item in rows:
            lo, hi, mid = item["low_value"], item["high_value"], item["value"]
            x = rng.uniform(lo, hi)
            if x < mid and mid != lo:
                total += (item["npv_low"] - base) * (mid - x) / (mid - lo)
            elif x > mid and hi != mid:
                total += (item["npv_high"] - base) * (x - mid) / (hi - mid)
        values.append(total)
        positive += total >= 0
    values.sort()
    return {
        "npv_positive": positive / runs,
        "p10": values[int(runs * 0.1)],
        "p90": values[int(runs * 0.9) - 1],
        "runs": runs,
        "note": f"{runs} случайных сочетаний параметров, каждый — равномерно в своём диапазоне; "
                "NPV по каждому параметру — линейно между точками торнадо. Корреляций между параметрами нет.",
    }


def _plan(
    rows: list[dict],
    site: dict,
    tasks: list[dict],
    params: dict[str, dict],
    report: dict,
    by_process: dict[str, dict[str, float]] | None = None,
    subsidies: frozenset[str] = frozenset(),
    auto_off: frozenset[str] = frozenset(),
) -> dict | None:
    """Правки, которые платформа вносит сама: число роботов на процессе и состав процессов — набор с наибольшим
    NPV объекта в пределах бюджета. Каждый набор считается целиком: процессы одной роли делят людей, посты
    диспетчеров общие. Скидка вендора и господдержка сюда не входят: о них договариваются, а не решают расчётом."""
    views = [item for item in report.get("processes") or [] if item["included"]]
    if not views:
        return None
    by_process = by_process or {}
    budget = _num(site.get("budget_rub"))
    names = {item["process_code"]: item["process_name"] for item in views}
    tuning = {item["process_code"]: item["tuning"] for item in views if item.get("tuning")}
    tuned = {code: dict(values) for code, values in by_process.items()}
    for code, change in tuning.items():
        tuned.setdefault(code, {})["count"] = float(change["to"])

    def purchase_of(item: dict) -> dict:
        return next(sc for sc in item["scenarios"] if sc["key"] == "purchase")

    solo_npv = {item["process_code"]: tuning[item["process_code"]]["npv"] if item["process_code"] in tuning else purchase_of(item)["npv"]["value"]
                for item in views}
    capex_of = {item["process_code"]: tuning[item["process_code"]]["capex"] if item["process_code"] in tuning else (purchase_of(item)["capex"]["value"] or 0)
                for item in views}
    current = [item["process_code"] for item in views if not item["off"]]
    base = _metric(report)

    def run(codes: frozenset[str]) -> dict:
        own = {code: dict(values) for code, values in tuned.items()}
        for item in views:
            row = own.setdefault(item["process_code"], {})
            if item["process_code"] in manual:
                continue
            if item["process_code"] in codes:
                row.pop("off", None)
            else:
                row["off"] = 1
        scenario = next(sc for sc in _compute(rows, site, tasks, params, own, subsidies=subsidies)["scenarios"] if sc["key"] == "purchase")
        return {"npv": scenario["npv"]["value"], "capex": scenario["capex"]["value"] or 0, "payback": scenario["payback"]["value"]}

    # Процесс, который пользователь выключил сам, платформа не возвращает: это его решение.
    manual = {item["process_code"] for item in views if item["off"] and item["process_code"] not in auto_off}
    pool = sorted((item for item in views if item["process_code"] not in manual and item["status"] != "no_staff" and (solo_npv[item["process_code"]] or -1) >= 0),
                  key=lambda item: -(solo_npv[item["process_code"]] or 0))
    codes = [item["process_code"] for item in pool]
    fits = lambda chosen: not budget or sum(capex_of[code] for code in chosen) <= budget  # noqa: E731
    best: tuple[frozenset[str], dict] | None = None
    if len(codes) <= 7:
        for mask in range(1, 1 << len(codes)):
            chosen = frozenset(code for index, code in enumerate(codes) if mask >> index & 1)
            if not fits(chosen):
                continue
            result = run(chosen)
            if result["npv"] is not None and (best is None or result["npv"] > best[1]["npv"] + 1):
                best = (chosen, result)
    else:
        # Процессов много: жадно добавляем тот, что сильнее всего поднимает NPV, пока прирост есть.
        chosen = frozenset()
        while True:
            step = None
            for code in codes:
                if code not in chosen and fits(chosen | {code}):
                    result = run(chosen | {code})
                    if result["npv"] is not None and (step is None or result["npv"] > step[1]["npv"]):
                        step = (chosen | {code}, result)
            if step is None or (best is not None and step[1]["npv"] <= best[1]["npv"] + 1):
                break
            chosen, best = step[0], step
    if best is None:
        return {"budget": budget, "changes": [], "npv": None, "capex": 0, "payback": None, "current_npv": base["npv"], "gain": None,
                "note": "Ни один процесс не выгоден даже при подборе числа роботов: нужны данные о людях или условия вендора."}
    chosen, result = best
    # Нынешний состав сверх бюджета — не вариант, даже если его NPV больше.
    if base["npv"] is not None and fits(frozenset(current)) and result["npv"] <= base["npv"] + 1:
        return {"budget": budget, "changes": [], "npv": base["npv"], "capex": base.get("capex"), "payback": base["payback"],
                "current_npv": base["npv"], "gain": 0.0, "note": "Состав и число роботов уже лучшие из возможных."}
    changes = []
    for item in views:
        code = item["process_code"]
        if code in chosen and code in tuning:
            change = tuning[code]
            changes.append({"kind": "count", "code": code, "name": names[code], "from": change["from"], "to": change["to"],
                            "reason": f"При {change['to']} вместо {change['from']} процесс выгоден сам по себе: "
                                      f"NPV {'+' if change['npv'] >= 0 else ''}{_t_plain(change['npv'] / 1_000_000)} млн ₽. "
                                      "Больше людей, чем есть на процессе, лишние роботы не заменят."})
        if code in chosen and item["off"]:
            changes.append({"kind": "on", "code": code, "name": names[code], "reason": "Выгоден в составе объекта — возвращён в расчёт."})
        if code not in chosen and not item["off"]:
            changes.append({"kind": "off", "code": code, "name": names[code], "reason": _off_reason(item, solo_npv[code], chosen, names, budget)})
    return {
        "budget": budget,
        "changes": changes,
        "npv": result["npv"],
        "capex": result["capex"],
        "payback": result["payback"],
        "current_npv": base["npv"],
        "gain": result["npv"] - base["npv"] if base["npv"] is not None else None,
        "note": ("Наибольший NPV объекта в пределах бюджета площадки. " if budget else "Наибольший NPV объекта; бюджет площадки не задан. ")
                + "Каждый вариант посчитан целиком: процессы одной роли делят людей, посты диспетчеров общие.",
    }


def _off_reason(item: dict, npv: float | None, chosen: frozenset[str], names: dict[str, str], budget: float | None) -> str:
    """Почему платформа убрала процесс из итога — словами, которые можно проверить в строке процесса."""
    if item["status"] == "no_staff":
        return "Нет данных о людях на процессе: роботы пока только стоят денег. Укажите людей — платформа пересчитает."
    if npv is None or npv < 0:
        if item.get("condition"):
            return f"Невыгоден даже при подборе числа роботов. Окупится, если договориться: {_condition_words(item['condition'])}."
        return "Невыгоден даже при подборе числа роботов."
    shared = (item.get("story") or {}).get("shared_with") or []
    taken = [name for code, name in names.items() if code in chosen and name in shared]
    if taken:
        return f"Те же люди уже уходят с процесса «{taken[0]}»: этот процесс добавит только вложения и расходы."
    if budget:
        return "Выгоден сам по себе, но в бюджет площадки помещаются более выгодные процессы."
    return "Выгоден сам по себе, но без него итог объекта больше."


def _condition_words(condition: dict) -> str:
    if condition["scope"] == "subsidy" or condition["scope"] == "combo" and not condition.get("to"):
        return "господдержка"
    if condition["key"] == "price_factor":
        text = f"скидка вендора {_t_plain(round(condition['from'] - condition['to']))}%"
        return text + (" и господдержка" if condition["scope"] == "combo" else "")
    return f"{condition['label'].lower()} {_t_plain(condition['to'])} {condition['unit']}"


# Чем измеряется работа процесса, если у задачи нет своего потока: поля площадки и единица.
_UNIT_FLOW = {
    "pallet_transport": (("inbound_pallets_per_day", "outbound_pallets_per_day"), "паллета"),
    "rack_placement": (("inbound_pallets_per_day", "outbound_pallets_per_day"), "паллета"),
    "pallet_storage": (("inbound_pallets_per_day", "outbound_pallets_per_day"), "паллета"),
    "palletizing": (("outbound_pallets_per_day",), "паллета"),
    "order_picking": (("pick_lines_per_day",), "строка заказа"),
    "tote_delivery": (("pick_lines_per_day",), "строка заказа"),
}


def _unit_cost(s: dict, item: dict, story: dict) -> dict | None:
    """Стоимость одной операции процесса до и после: язык заказчика. Вложения — аннуитетом за срок службы."""
    if story["needs_staff"]:
        return None
    code = item["process_code"]
    site, p = s["site"], s["p"]
    days = _num(site.get("days_year"))
    per_day = sum(_num(task.get("flow_per_day")) or 0 for task in s.get("tasks") or [] if isinstance(task, dict) and task.get("process_code") == code)
    unit = "операция"
    if not per_day and code in _UNIT_FLOW:
        keys, unit = _UNIT_FLOW[code]
        per_day = sum(_num(site.get(key)) or 0 for key in keys)
    if not per_day or not days:
        return None
    volume = per_day * days
    rate = _real_rate(p)
    life = max(1.0, p["service_life_years"])
    capital = story["capex"] * _annuity(rate, life)
    return {
        "label": unit,
        "volume_year": volume,
        "before": story["payroll_now"] / volume,
        "after": (story["payroll_after"] + story["robots_year"] + capital) / volume,
        "capital_year": capital,
        "note": f"{_t_plain(per_day)} в сутки × {_t_plain(days)} дней. Вложения разложены на срок службы {_t_plain(life)} лет "
                f"под ставку {_t_plain(round(rate * 100, 1))}%, поэтому цена операции сравнима с ручной работой.",
    }
