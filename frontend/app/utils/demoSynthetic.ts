export interface DemoSyntheticValue {
  key: string
  label: string
  value: string | number | boolean | string[]
  unit: string
  origin: 'demo_synthetic'
  explanation: string
  vendor_confirmed: false
  requires_vendor_confirmation: boolean
  references?: { url?: string; title: string; basis?: string; source_id?: number }[]
  category?: 'site' | 'finance'
}

export interface DemoSyntheticGroup {
  process_code: string
  process_name: string
  product_id: string
  name: string
  fields: DemoSyntheticValue[]
  included_in_economy: boolean
}

export const formatDemoValue = (value: DemoSyntheticValue['value']): string => {
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'boolean') return value ? 'да' : 'нет'
  return typeof value === 'number' ? value.toLocaleString('ru-RU') : value
}

export const formatOrigin = (origin: string): string => {
  if (origin === 'demo_synthetic') return 'Синтетика'
  if (origin === 'project_input') return 'Данные вендора'
  return origin
}
