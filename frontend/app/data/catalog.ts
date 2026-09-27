// Модель представления каталога, подписи и форматтеры.
// Сами данные приходят из API — см. composables/useCatalog.ts.
// Мок-массивы остались только под страницы проекта (demoProducts, demoSources): они зависят
// от конвейера расчёта, а он пока заглушка.

import type { ApiAttrGroup, ApiAvailability, ApiSourceKind, ApiValueStatus } from '~/types/api'

export type Availability = ApiAvailability
export type SourceKind = ApiSourceKind
export type Confidence = 'A' | 'B' | 'C' | 'D'
export type ValueStatus = ApiValueStatus
export type AttrGroup = ApiAttrGroup

export interface Source {
  id: string
  kind: SourceKind
  publisher: string
  url: string
  fetchedAt: string
  checkedAt: string
  quote?: string
  usageCount?: number
}

export interface AttrValue {
  key: string
  label: string
  unit?: string
  group: AttrGroup
  status: ValueStatus
  value?: string | number
  range?: [number, number]
  sourceId?: string
  quote?: string
  note?: string
}

export interface ProductCase {
  id: string
  summary: string
  customer?: string
  process?: string
  sourceId?: string
}

export interface Product {
  id: string
  slug: string
  name: string
  manufacturer: string
  legalEntity: string
  country: string
  city: string
  availability: Availability
  trl: number
  marketPotential: number
  autoMatch: boolean
  solutionType: string
  solutionTypeCode: string
  family: string
  processes: string[]
  objects: string[]
  industries: string[]
  image: string
  summary: string
  priceRub?: number
  priceNote?: string
  highlights: { label: string; value: string }[]
  attrs: AttrValue[]
  cases: ProductCase[]
  completeness: number
}

export const sourceKindLabel: Record<SourceKind, string> = {
  vendor: 'Производитель',
  dealer: 'Дилер',
  media: 'СМИ',
  catalog: 'Каталог организатора',
  analogue: 'Оценка по аналогу',
  assumption: 'Допущение команды',
}

// Достоверность выводится из типа источника, а не хранится рядом со значением (§6.3)
export const confidenceByKind: Record<SourceKind, Confidence> = {
  vendor: 'A',
  dealer: 'B',
  catalog: 'B',
  media: 'C',
  analogue: 'C',
  assumption: 'D',
}

export const availabilityLabel: Record<Availability, string> = {
  operation: 'В эксплуатации',
  piloting: 'Пилот',
  rnd: 'Разработка',
}

export const availabilityTone: Record<Availability, 'ok' | 'warn' | 'neutral'> = {
  operation: 'ok',
  piloting: 'warn',
  rnd: 'neutral',
}

export const attrGroups: { code: AttrGroup; label: string; hint: string }[] = [
  { code: 'identification', label: 'Идентификация', hint: 'Название, производитель, юрлицо, страна, статус, УГТ, рыночный потенциал' },
  { code: 'technical', label: 'Технические характеристики', hint: 'Нагрузка, скорость, автономность, точность, производительность' },
  { code: 'infrastructure', label: 'Инфраструктура', hint: 'Связь, пол, питание, температурный режим' },
  { code: 'economics', label: 'Экономика', hint: 'Стоимость единицы, ПО, внедрение, сервис' },
  { code: 'applicability', label: 'Применимость', hint: 'Объекты, процессы, кейсы, риски' },
  { code: 'data_quality', label: 'Качество данных', hint: 'Источники, даты, выведенная достоверность, готовность к автоподбору' },
]

export interface TreeNode {
  label: string
  count?: number
  token?: string
  children?: TreeNode[]
  productIds?: string[]
}

// Число уникальных продуктов в поддереве
export const countNode = (n: TreeNode): number => {
  if (!n.productIds?.length) {
    if (n.children?.length) return n.children.reduce((sum, child) => sum + countNode(child), 0)
    return n.count ?? 0
  }
  const ids = new Set<string>()
  const walk = (x: TreeNode) => { x.productIds?.forEach((id) => ids.add(id)); x.children?.forEach(walk) }
  walk(n)
  return ids.size
}

export const formatRub = (n?: number) => {
  if (n == null) return 'нет данных'
  if (n >= 1_000_000) return `${(n / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} млн ₽`
  return `${n.toLocaleString('ru-RU')} ₽`
}

export const formatNum = (n: number, digits = 0) => n.toLocaleString('ru-RU', { maximumFractionDigits: digits, minimumFractionDigits: digits })

// ---------------------------------------------------------------------------
// Презентация: API картинок и подборки highlights не отдаёт
// ---------------------------------------------------------------------------

// Картинка выводится из семейства и кода типа решения: 187 позиций своих фото не имеют
const IMAGE_BY_FAMILY: Record<string, string> = {
  flow_cycle: '/img/robot-amr-pallet.png',
  area_window: '/img/robot-uv.png',
  station_robots: '/img/robot-arm.png',
  count_window: '/img/robot-drone.png',
  perimeter_rounds: '/img/robot-patrol.png',
}

const IMAGE_BY_SOLUTION: Record<string, string> = {
  amr: '/img/robot-amr-pallet.png',
  fmr: '/img/robot-forklift.png',
  fmr_vehicle: '/img/robot-forklift.png',
  autonomous_forklift: '/img/robot-forklift.png',
  mobile_picker: '/img/robot-g2p.png',
  robotic_cart: '/img/robot-g2p.png',
  shuttle: '/img/robot-cube.png',
  smart_storage: '/img/robot-cube.png',
  stacker_crane: '/img/robot-cube.png',
  cobot: '/img/robot-cobot.png',
  manipulator: '/img/robot-arm.png',
  robot_manipulator: '/img/robot-arm.png',
  welding_robot: '/img/robot-arm.png',
  palletizing_robot: '/img/robot-arm.png',
  cleaning_robot: '/img/robot-uv.png',
  security_robot: '/img/robot-patrol.png',
  bas_generic: '/img/robot-drone.png',
  bas_multirotor: '/img/robot-drone.png',
  bas_unspecified: '/img/robot-drone.png',
  uav_vtol: '/img/robot-drone.png',
  uav_multirotor: '/img/robot-drone.png',
  uav_fixed_wing: '/img/robot-drone.png',
  inventory_robot: '/img/robot-drone.png',
  autonomous_tug: '/img/site-airport.png',
  autonomous_truck: '/img/site-airport.png',
}

export const imageFor = (solutionTypeCode: string, family: string) =>
  IMAGE_BY_SOLUTION[solutionTypeCode] ?? IMAGE_BY_FAMILY[family] ?? '/img/robot-amr-pallet.png'

const TRL_LABEL = 'УГТ'

/**
 * Пока ТТХ не заполнены, в карточке показываются те четыре факта, которые в каталоге есть:
 * статус, УГТ, цена и регион. По мере появления ТТХ они вытесняют их слева.
 */
export const highlightsFor = (p: {
  attrs: AttrValue[]
  availability: Availability
  trl: number
  priceRub?: number
  city: string
}): { label: string; value: string }[] => {
  const PREFERRED = ['payload_kg', 'speed_loaded_ms', 'work_time_h', 'throughput', 'navigation', 'reach_mm', 'lift_height_mm']
  const fromAttrs = PREFERRED
    .map((key) => p.attrs.find((a) => a.key === key && a.status === 'known'))
    .filter((a): a is AttrValue => Boolean(a))
    .map((a) => ({
      label: a.label,
      value: typeof a.value === 'number' ? `${formatNum(a.value, a.value % 1 ? 1 : 0)}${a.unit ? ` ${a.unit}` : ''}` : String(a.value),
    }))

  const fallback = [
    { label: 'Статус', value: availabilityLabel[p.availability] },
    { label: TRL_LABEL, value: p.trl ? String(p.trl) : 'нет данных' },
    { label: 'Цена', value: formatRub(p.priceRub) },
    { label: 'Регион', value: p.city || 'нет данных' },
  ]

  return [...fromAttrs, ...fallback].slice(0, 4)
}
