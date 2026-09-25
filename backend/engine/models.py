"""Единственная точка связи между данными, движком, API и фронтом (§5, §13.1).

Из этих моделей генерируется /api/v1/openapi.json → web/types/api.ts.
Менять без объявления команде нельзя.
"""

from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Step = Literal["prepare", "match", "size", "cost", "rank", "layout", "sim"]
Verdict = Literal["pass", "fail", "unknown"]
Reliability = Literal["A", "B", "C", "D"]
SourceKind = Literal["vendor", "dealer", "media", "catalog", "analogue", "assumption"]
AttrStatus = Literal["known", "unknown", "not_applicable"]
Availability = Literal["operation", "piloting", "rnd"]
ScenarioCode = Literal["baseline", "per_task", "optimal"]


# ---------------------------------------------------------------------------
# Трассировка (§4.1)
# ---------------------------------------------------------------------------


class TraceStep(BaseModel):
    step: Step
    product_id: UUID | None = None
    verdict: Verdict | None = None
    formula: str | None = None  # "ceil(120 / (3600/48 * 0.82))" — с подставленными числами
    value: float | None = None
    unit: str | None = None
    source: str | None = None  # "[A] ronavi-robotics.ru/catalogue/h1500"
    message: str  # человеческая формулировка для интерфейса


# ---------------------------------------------------------------------------
# Каталог (§6.2–6.4)
# ---------------------------------------------------------------------------


class AttrValue(BaseModel):
    status: AttrStatus = "known"
    value: float | str | bool | list[float] | None = None  # list = диапазон [min, max]
    unit: str | None = None
    source_id: int | None = None  # достоверность и дата берутся отсюда
    quote: str | None = None  # цитата из источника, подтверждающая значение
    note: str | None = None
    extracted_by: str | None = None  # модель и версия, если значение извлечено автоматически


class Source(BaseModel):
    id: int
    kind: SourceKind
    url: str | None = None
    publisher: str | None = None
    title: str | None = None
    captured_at: date
    rationale: str | None = None
    ref_product_id: UUID | None = None


class AttributeDef(BaseModel):
    key: str
    group_code: Literal[
        "identification", "technical", "infrastructure", "economics", "applicability", "data_quality"
    ]
    label: str
    unit: str | None = None
    datatype: Literal["number", "range", "text", "enum", "bool"]
    enum_values: list[str] | None = None
    required_for: list[str] | None = None
    sort: int | None = None


class Product(BaseModel):
    id: UUID
    solution_type_code: str
    name: str
    manufacturer: str
    legal_entity: str | None = None
    country: str | None = None
    availability: Availability
    trl: int | None = None
    market_potential: int | None = None
    summary: str | None = None
    attrs: dict[str, AttrValue] = Field(default_factory=dict)
    case_process_codes: list[str] = Field(default_factory=list)  # коды процессов из product_case, для has_case


class CalcNorm(BaseModel):
    key: str
    value: float
    unit: str | None = None
    solution_type_code: str | None = None  # None = общий норматив
    source_id: int
    editable: bool = True


class SolutionType(BaseModel):
    code: str
    name: str
    family: Literal["flow_cycle", "area_window", "station_robots", "count_window", "perimeter_rounds"]
    rule_spec: dict  # RuleSpec, валидируется в engine.rules


class Catalog(BaseModel):
    """Снимок каталога, загружаемый один раз в lifespan (§11.1)."""

    version_id: int
    solution_types: list[SolutionType] = Field(default_factory=list)
    products: list[Product] = Field(default_factory=list)
    attribute_defs: list[AttributeDef] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    norms: list[CalcNorm] = Field(default_factory=list)
    process_solutions: dict[str, list[str]] = Field(default_factory=dict)  # процесс → типы решений


# ---------------------------------------------------------------------------
# Вход расчёта (§4, §6.6)
# ---------------------------------------------------------------------------


class SiteProfile(BaseModel):
    object_type_code: str  # warehouse | airport | hospital
    area_m2: float | None = None
    free_m2: float | None = None
    aisle_width_m: float | None = None
    temp_min_c: float | None = None
    temp_max_c: float | None = None
    shifts_per_day: int = 1
    shift_hours: float = 8
    days_year: int = 250
    staff_salary_year_rub: float | None = None
    energy_tariff_rub_kwh: float | None = None
    budget_rub: float | None = None
    clean_area_m2: float | None = None  # м² убираемой / активной зоны
    pallet_places: int | None = None  # шт
    storage_height_m: float | None = None  # м, высота зоны хранения
    floor_load_kg_m2: float | None = None  # кг/м², несущая способность пола
    floor_flatness_mm: float | None = None  # мм/2м
    peak_factor: float = 1.0  # доля, пик к среднечасовой
    power_kw: float | None = None  # кВт
    noise_limit_dba: float | None = None  # дБА
    has_wms: bool | None = None
    # Лист «Склад» датасета. На аэропорте и больнице остаются пустыми.
    floors_count: int | None = None
    main_aisle_width_m: float | None = None
    floor_type: str | None = None
    inbound_pallets_per_day: float | None = None
    outbound_pallets_per_day: float | None = None
    pick_lines_per_day: float | None = None
    pick_units_per_day: float | None = None
    piece_pick_share_pct: float | None = None
    sku_count: int | None = None
    sku_a_share_pct: float | None = None
    staff_total: int | None = None
    pickers_count: int | None = None
    forklift_operators: int | None = None
    pack_operators: int | None = None
    picker_salary_month_rub: float | None = None
    forklift_salary_month_rub: float | None = None
    payroll_burden: float | None = None
    picker_lines_per_hour: float | None = None
    time_loss_pct: float | None = None
    picker_route_m: float | None = None
    conveyor_length_m: float | None = None
    rack_type: str | None = None
    pallet_mass_kg: float | None = None
    unit_mass_kg: float | None = None
    pallet_dims_mm: str | None = None
    unit_dims_mm: str | None = None
    oversized_share_pct: float | None = None
    erp_name: str | None = None
    payback_years: float | None = None


class Task(BaseModel):
    process_code: str
    name: str | None = None  # человеческое название для интерфейса
    flow_per_hour: float | None = None
    flow_per_day: float | None = None  # операций в сутки; в часовой переводит §6.1
    peak_factor: float | None = None  # переопределение пика площадки
    route_len_m: float | None = None
    max_load_kg: float | None = None
    t_load_s: float = 0
    t_unload_s: float = 0
    container_types: list[str] = Field(default_factory=list)
    staff_fte_now: float | None = None


class CalcRequest(BaseModel):
    site: SiteProfile
    tasks: list[Task]
    overrides: dict[str, float] = Field(default_factory=dict)  # ключ calc_norm → значение (ТЗ 3.5.3)
    horizon_years: int = Field(default=5, ge=1, le=15)
    manual_product_ids: list[UUID] = Field(default_factory=list)  # ручное добавление (ТЗ 3.4.4)


# ---------------------------------------------------------------------------
# Выход по шагам (§4)
# ---------------------------------------------------------------------------


class Candidate(BaseModel):
    product_id: UUID
    process_code: str
    verdict: Verdict
    failed: list[str] = Field(default_factory=list)  # ключи полей, давших fail
    unknown: list[str] = Field(default_factory=list)  # ключи полей, давших unknown
    score: float | None = None


class SizedOption(BaseModel):
    product_id: UUID
    process_code: str
    count: int
    formula: str
    family: str


class Economics(BaseModel):
    capex_rub: float
    opex_year_rub: float
    effect_year_rub: float
    payback_years: float | None = None
    roi_pct: float | None = None
    tco_rub: float
    horizon_years: int
    breakdown: dict[str, float] = Field(default_factory=dict)  # статьи CAPEX/OPEX/эффекта


class Scenario(BaseModel):
    code: ScenarioCode
    name: str
    options: list[SizedOption] = Field(default_factory=list)
    economics: Economics | None = None
    raas_available: bool = False


class VendorQuery(BaseModel):
    """Блок «требует уточнения у вендора» (§7.1)."""

    product_id: UUID
    product_name: str
    manufacturer: str
    field: str
    source_url: str | None = None


class Zone(BaseModel):
    id: str
    kind: Literal["storage", "receiving", "shipping", "charging", "picking", "other"]
    x: float
    y: float
    w: float
    h: float
    label: str


class Route(BaseModel):
    id: str
    from_zone: str
    to_zone: str
    points: list[tuple[float, float]]
    length_m: float


class Plan(BaseModel):
    width_m: float
    height_m: float
    zones: list[Zone] = Field(default_factory=list)
    routes: list[Route] = Field(default_factory=list)
    charging_points: list[tuple[float, float]] = Field(default_factory=list)


class SimEvent(BaseModel):
    t: float
    robot_id: str
    x: float
    y: float
    state: Literal["idle", "moving", "loading", "unloading", "charging", "waiting"]


class ShiftRun(BaseModel):
    tick_s: float
    duration_s: float
    fleet_size: int
    utilization: float  # 0..1
    charge_queue_max: int
    completed_ops: int
    events: list[SimEvent] = Field(default_factory=list)


class Interval(BaseModel):
    p10: float
    p50: float
    p90: float
    drivers: dict[str, float] = Field(default_factory=dict)  # вклад входа в дисперсию, 0..1


class CalcResponse(BaseModel):
    engine_version: str
    catalog_version_id: int
    candidates: list[Candidate] = Field(default_factory=list)
    # все посчитанные количества, а не только вошедшие в сценарий:
    # строке кандидата нужно своё число, даже если в парк он не попал
    options: list[SizedOption] = Field(default_factory=list)
    scenarios: list[Scenario] = Field(default_factory=list)
    vendor_queries: list[VendorQuery] = Field(default_factory=list)
    plan: Plan | None = None
    sim: ShiftRun | None = None
    trace: list[TraceStep] = Field(default_factory=list)


class SensitivityResponse(BaseModel):
    engine_version: str
    catalog_version_id: int
    runs: int
    payback_years: Interval
    trace: list[TraceStep] = Field(default_factory=list)
