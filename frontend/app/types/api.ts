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
  value?: string | number | boolean | null
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
