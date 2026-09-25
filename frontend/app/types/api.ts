// Контракт бэкенда как есть: snake_case, числовые id источников.
// Преобразование в модель представления живёт в composables/useCatalog.ts.

export type ApiAvailability = 'operation' | 'piloting' | 'rnd'
export type ApiSourceKind = 'vendor' | 'dealer' | 'media' | 'catalog' | 'analogue' | 'assumption'
export type ApiValueStatus = 'known' | 'unknown' | 'not_applicable'
export type ApiAttrGroup = 'identification' | 'technical' | 'infrastructure' | 'economics' | 'applicability' | 'data_quality'

export interface ApiRef {
  code: string
  name: string
}

export interface ApiAttrValue {
  status: ApiValueStatus
  /** Число, текст, флаг или диапазон `[min, max]` из engine.models.AttrValue. */
  value?: string | number | boolean | number[] | null
  unit?: string | null
  source_id?: number | null
  quote?: string | null
  note?: string | null
  extracted_by?: string | null
}

export interface ApiAttributeDef {
  key: string
  group_code: ApiAttrGroup
  label: string
  unit?: string | null
  datatype: 'number' | 'text' | 'bool' | 'enum' | 'range'
  enum_values?: string[] | null
  required_for?: string[] | null
  sort?: number | null
}

export interface ApiSource {
  id: number
  kind: ApiSourceKind
  reliability: 'A' | 'B' | 'C' | 'D'
  url?: string | null
  publisher?: string | null
  title?: string | null
  captured_at: string
  rationale?: string | null
  last_checked_at?: string | null
  usage_count: number
}

export interface ApiCase {
  id: number
  summary?: string | null
  customer?: string | null
  process?: ApiRef | null
  source_id?: number | null
}

export interface ApiProductCard {
  id: string
  slug: string
  name: string
  manufacturer: string
  legal_entity?: string | null
  country?: string | null
  region?: string | null
  availability: ApiAvailability
  trl?: number | null
  market_potential?: number | null
  auto_match: boolean
  solution_type: ApiRef
  family: string
  processes: ApiRef[]
  object_types: ApiRef[]
  industries: ApiRef[]
  price_rub?: number | null
  price_note?: string | null
  completeness_filled: number
  completeness_total: number
}

export interface ApiProductDetail extends ApiProductCard {
  summary?: string | null
  attrs: Record<string, ApiAttrValue>
  cases: ApiCase[]
  sources: ApiSource[]
}

export interface ApiProductList {
  catalog_version_id: number
  total: number
  products: ApiProductCard[]
}

export interface ApiTreeNode {
  key: string
  label: string
  level: 'industry' | 'object_type' | 'process' | 'solution_type'
  children: ApiTreeNode[]
  product_ids: string[]
}

export interface ApiCatalogTree {
  catalog_version_id: number
  nodes: ApiTreeNode[]
}

/** Массовая выдача ТТХ: GET /catalog/attrs (E4 §2). */
export interface ApiCatalogAttrs {
  catalog_version_id: number
  attrs: Record<string, Record<string, ApiAttrValue>>
}

export type ApiCompareGroup = 'technical' | 'operational' | 'economic'
export type ApiCompareOrigin = 'attr' | 'engine' | 'derived'
export type ApiCompareBetter = 'max' | 'min' | 'none'

/** Запись спеки сравнения: GET /catalog/compare-spec отдаёт массив таких объектов (E4 §3). */
export interface ApiCompareParam {
  key: string
  label: string
  unit?: string | null
  group: ApiCompareGroup
  origin: ApiCompareOrigin
  better: ApiCompareBetter
  rationale: string
}

// ---------------------------------------------------------------------------
// Проекты и расчёт (§7, CalcResponse)
// ---------------------------------------------------------------------------

export type ApiVerdict = 'pass' | 'fail' | 'unknown'
export type ApiScenarioCode = 'baseline' | 'per_task' | 'optimal'
export type ApiTraceStepName = 'prepare' | 'match' | 'size' | 'rank' | 'cost' | 'layout' | 'sim'

export interface ApiSiteProfile {
  object_type_code: string
  area_m2?: number | null
  free_m2?: number | null
  aisle_width_m?: number | null
  temp_min_c?: number | null
  temp_max_c?: number | null
  shifts_per_day?: number | null
  shift_hours?: number | null
  days_year?: number | null
  staff_salary_year_rub?: number | null
  energy_tariff_rub_kwh?: number | null
  budget_rub?: number | null
  clean_area_m2?: number | null
  pallet_places?: number | null
  storage_height_m?: number | null
  floor_load_kg_m2?: number | null
  floor_flatness_mm?: number | null
  peak_factor?: number | null
  power_kw?: number | null
  noise_limit_dba?: number | null
  has_wms?: boolean | null
  floors_count?: number | null
  main_aisle_width_m?: number | null
  floor_type?: string | null
  inbound_pallets_per_day?: number | null
  outbound_pallets_per_day?: number | null
  pick_lines_per_day?: number | null
  pick_units_per_day?: number | null
  piece_pick_share_pct?: number | null
  sku_count?: number | null
  sku_a_share_pct?: number | null
  staff_total?: number | null
  pickers_count?: number | null
  forklift_operators?: number | null
  pack_operators?: number | null
  picker_salary_month_rub?: number | null
  forklift_salary_month_rub?: number | null
  payroll_burden?: number | null
  picker_lines_per_hour?: number | null
  time_loss_pct?: number | null
  picker_route_m?: number | null
  conveyor_length_m?: number | null
  rack_type?: string | null
  pallet_mass_kg?: number | null
  unit_mass_kg?: number | null
  pallet_dims_mm?: string | null
  unit_dims_mm?: string | null
  oversized_share_pct?: number | null
  erp_name?: string | null
  payback_years?: number | null
}

export interface ApiTask {
  process_code: string
  name?: string | null
  flow_per_hour?: number | null
  flow_per_day?: number | null
  peak_factor?: number | null
  route_len_m?: number | null
  max_load_kg?: number | null
  t_load_s?: number | null
  t_unload_s?: number | null
  container_types?: string[]
  staff_fte_now?: number | null
}

export interface ApiProject {
  id: string
  owner_id: string
  name: string
  object_type_code: string
  site: ApiSiteProfile
  tasks: ApiTask[]
  overrides: Record<string, number>
  created_at?: string | null
  updated_at?: string | null
}

export interface ApiProjectCreate {
  name: string
  object_type_code: string
  industry_code?: string | null
  use_demo?: boolean
}

export interface ApiProjectPatch {
  name?: string | null
  site?: ApiSiteProfile | null
  tasks?: ApiTask[] | null
  overrides?: Record<string, number> | null
}

export interface ApiSiteProfileRef {
  object_type_code: string
  name?: string | null
  site: ApiSiteProfile
  tasks: ApiTask[]
  field_sources?: Record<string, string> | null
}

export interface ApiCandidate {
  product_id: string
  process_code: string
  verdict: ApiVerdict
  failed: string[]
  unknown: string[]
  score?: number | null
}

export interface ApiSizedOption {
  product_id: string
  process_code: string
  count: number
  formula: string
  family: string
}

export interface ApiEconomics {
  capex_rub: number
  opex_year_rub: number
  effect_year_rub: number
  payback_years?: number | null
  roi_pct?: number | null
  tco_rub: number
  horizon_years: number
  breakdown: Record<string, number>
}

export interface ApiScenario {
  code: ApiScenarioCode
  name: string
  options: ApiSizedOption[]
  economics?: ApiEconomics | null
  raas_available: boolean
}

export interface ApiVendorQuery {
  product_id: string
  product_name: string
  manufacturer: string
  field: string
  source_url?: string | null
}

export interface ApiTraceStep {
  step: ApiTraceStepName | string
  product_id?: string | null
  verdict?: ApiVerdict | null
  formula?: string | null
  value?: number | null
  unit?: string | null
  source?: string | null
  message: string
}

export interface ApiCalcResponse {
  engine_version: string
  catalog_version_id: number
  candidates: ApiCandidate[]
  options: ApiSizedOption[]
  scenarios: ApiScenario[]
  vendor_queries: ApiVendorQuery[]
  plan?: unknown | null
  sim?: unknown | null
  trace: ApiTraceStep[]
  run_id: string
}
