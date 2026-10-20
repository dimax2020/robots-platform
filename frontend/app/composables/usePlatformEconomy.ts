import type { Ref } from 'vue'
import type { DemoSyntheticGroup } from '~/utils/demoSynthetic'
import { fetchErrorMessage } from '~/utils/errors'
import { platformSend } from '~/composables/usePlatform'
import { useLiveProject } from '~/composables/useLiveProject'
import { usePlatformCompare, type MatchGroup, type SelectionAssumption } from '~/composables/usePlatformCompare'

export type EconSource = 'card' | 'fleet' | 'site' | 'norm' | 'project' | 'calc'

export interface EconVar {
  symbol: string
  label: string
  value: number | null
  unit: string
  source: EconSource
  source_label: string
  note: string
}

export interface EconFig {
  key: string
  label: string
  value: number | null
  unit: string
  tex: string
  subst: string
  vars: EconVar[]
  note: string
  included: boolean
  symbol: string
  /** Персонал эксплуатации: сколько человек на постах диспетчера. */
  count?: number
}

export interface EconFleet {
  applicability?: string
  assumptions?: SelectionAssumption[]
  uses_demo_synthetic?: boolean
  sizing?: { model?: string; working_count?: number; reserve_count?: number; inputs?: Record<string, number>;
    input_provenance?: Record<string, { label?: string; unit?: string; origin?: string; source_id?: number | null }>; [key: string]: unknown }
  process_code: string
  process_name: string
  product_id: string
  name: string
  slug: string
  image_url: string | null
  price_rub: number | null
  count: number | null
  count_used: number | null
  /** formula — формула процесса, project — задано пользователем, default — формула не посчитала, взят 1. */
  count_source?: 'formula' | 'project' | 'default'
  /** Пользователь исключил процесс из расчёта объекта. */
  off?: boolean
  included: boolean
  note: string
  cost_rub: number | null
  raas_available: boolean
  fig: EconFig | null
  price_used?: number | null
}

export interface EconScenario {
  key: 'asis' | 'purchase' | 'raas'
  title: string
  subtitle: string
  available: boolean
  note: string
  capex: EconFig
  capex_lines: EconFig[]
  opex: EconFig
  opex_lines: EconFig[]
  payroll_after: EconFig
  annual_cost: number | null
  effect: EconFig
  effect_lines: EconFig[]
  payback: EconFig
  roi: EconFig
  /** Чистая прибыль за горизонт после налога и возврата всех вложений. */
  net_profit?: EconFig
  /** ROE в год: прибыль после амортизации и налога на капитал, равный CAPEX. */
  roe?: EconFig
  npv?: EconFig
  irr?: EconFig
  dpp?: EconFig
  /** Индекс доходности: приведённый поток на рубль вложений. */
  pi?: EconFig
  /** Годовая стоимость операций после налога с учётом вложений: сравнивает сценарии на одной шкале. */
  eac?: EconFig
  tco: EconFig
  cashflow?: EconCashRow[]
  /** Аренда: окупаемость и ROI вложений во внедрение на площадке — для сравнения сценариев по единым показателям. */
  implementation_payback?: number | null
  implementation_roi?: number | null
  /** Стоимость своей техники и внедрения сразу после покупки — база износа. */
  asset_start?: number
  years: { year: number; cost_rub: number; net_rub: number }[]
  verdict: string
}

/** Год денежного потока после налога. Расходы и налог — отрицательные. */
export interface EconCashRow {
  year: number
  saving_rub: number
  opex_rub: number
  payouts_rub: number
  /** Повторная закупка, когда горизонт длиннее срока службы. */
  reinvest_rub?: number
  support_rub: number
  depreciation_rub: number
  tax_rub: number
  residual_rub: number
  cf_rub: number
  cumulative: number
  discounted: number
  /** Стоимость своей техники на конец года, по износу. */
  asset_rub?: number
  /** Накоплено деньгами, без стоимости техники. */
  cash_cumulative?: number
}

/** Высвобождение процесса: откуда численность, какую долю берут роботы, сколько людей уходит. */
export interface EconRelease {
  process_code?: string
  process_name?: string
  source: '' | 'task' | 'role'
  role: string
  staff: number
  split: number
  auto: number
  auto_note?: string
  capped: boolean
  cap?: number | null
  fte: number
  /** Годовая стоимость сотрудника с начислениями и его зарплата в месяц. */
  rate?: number | null
  wage_month?: number | null
  group?: string
  by_cost?: boolean
  cost_month?: number | null
  /** Техника, топливо, аренда на ручной работе, ₽ в месяц: уходят вместе с людьми. */
  other_month?: number | null
  work?: EconWork | null
  note: string
}

/** Процесс историей «было → стало»: люди сейчас, кто уходит, сколько стоят роботы, что в итоге. */
export interface EconStory {
  source: '' | 'task' | 'role'
  role: string
  staff: number
  wage_month: number | null
  rate_year: number
  payroll_now: number
  released: number
  remaining: number
  payroll_after: number
  robots: number
  capex: number
  robots_year: number
  dispatchers: number | null
  cost_before: number
  cost_after: number
  saving_year: number
  payback: number | null
  npv: number | null
  total: number | null
  shared_with: string[]
  needs_staff: boolean
  /** Затраты введены суммой: людей не знаем, экономия — по доле операций. */
  by_cost?: boolean
  cost_month?: number | null
  /** Техника, топливо, аренда на ручной работе, ₽ в месяц: уходят вместе с людьми. */
  other_month?: number | null
  work?: EconWork | null
  /** Цена одной операции до и после: ₽ на паллету или строку заказа. */
  unit?: EconUnitCost | null
}

/** Работа процесса в операциях: объём, выработка человека и робота, сколько операций берут роботы. */
export interface EconWork {
  /** Единица: одна, две, пять — «паллета», «паллеты», «паллет». */
  unit: [string, string, string]
  per_day: number | null
  volume_year: number | null
  volume_source: string
  /** Операций в час на одного робота с учётом готовности. */
  robot_rate: number | null
  robot_rate_how: string
  /** Выработку робота указал пользователь, а не карточка. */
  robot_rate_own?: boolean
  /** Выработка до поправки на готовность: то, что пользователь вводит. */
  robot_rate_raw?: number | null
  robot_year: number | null
  robots: number
  capacity_year: number
  /** Сколько роботов нужно, чтобы забрать всю автоматизируемую работу. */
  robots_full: number | null
  auto: number
  coverage: number | null
  taken_year: number | null
  /** Операций в час на одного человека: объём / (люди × часы в год). */
  person_rate: number | null
  /** Скольких людей заменяет один робот. */
  replaces: number | null
}

export interface EconUnitCost {
  label: string
  volume_year: number
  before: number
  after: number
  capital_year: number
  note: string
}

/** Покупка в неудачных условиях. */
export interface EconStress {
  key: 'volume' | 'rate' | 'slow' | 'price' | 'all'
  label: string
  note: string
  npv: number | null
  payback: number | null
  effect: number | null
  delta: number | null
  ok: boolean
}

/** Вероятность, что NPV покупки не меньше нуля, по случайным сочетаниям параметров. */
export interface EconChance {
  npv_positive: number
  p10: number
  p90: number
  runs: number
  note: string
}

/** Правка, которую платформа вносит сама: число роботов на процессе или его место в итоге объекта. */
export interface EconPlanChange {
  kind: 'count' | 'off' | 'on'
  code: string
  name: string
  from?: number
  to?: number
  reason: string
}

/** Правка платформы, уже внесённая в проект: показывается с причиной и кнопкой «Вернуть». */
export interface EconFix { key: string; kind: 'count' | 'off'; code: string; name: string; change: string; reason: string }

/** План платформы: лучший состав и число роботов в пределах бюджета. Скидки и господдержка сюда не входят. */
export interface EconPlan {
  budget: number | null
  changes: EconPlanChange[]
  npv: number | null
  capex: number | null
  payback: number | null
  current_npv: number | null
  gain: number | null
  note: string
}

export interface EconRequest {
  to: 'customer' | 'vendor'
  process_code: string
  process_name: string
  question: string
  why: string
}

export interface EconParam {
  key: string
  group: 'capex' | 'opex' | 'staff' | 'raas' | 'horizon' | 'whatif' | 'finance' | 'subsidy'
  label: string
  symbol: string
  unit: string
  value: number
  standard: number
  source: EconSource
  overridden: boolean
  rationale: string
  origin: string
  min: number
  max: number
  step: number
}

export interface EconSensitivity {
  key: string
  label: string
  unit: string
  value: number
  low_value: number
  high_value: number
  payback: number | null
  payback_low: number | null
  payback_high: number | null
  effect: number
  effect_low: number
  effect_high: number
  swing: number | null
  npv?: number | null
  npv_low?: number | null
  npv_high?: number | null
  /** NPV аренды на тех же границах параметра: чувствительность для каждого сценария. */
  rent_npv?: number | null
  rent_npv_low?: number | null
  rent_npv_high?: number | null
  level?: 'A' | 'B' | 'C' | 'D'
  range_note?: string
  /** Доля в разбросе NPV: квадрат размаха к сумме квадратов. */
  share?: number
}

export interface EconInterval {
  npv: number | null
  npv_low: number | null
  npv_high: number | null
  payback: number | null
  payback_low: number | null
  payback_high: number | null
  note: string
}

export interface EconBreakeven {
  key: string
  label: string
  unit: string
  current: number
  value: number | null
  margin_pct: number | null
  direction: 'min' | 'max'
  /** Без точки: true — окупается во всём диапазоне, false — не окупается нигде. */
  reachable: boolean
}

export const PRELIMINARY = 'Результат является предварительной оценкой и требует верификации при обследовании объекта.'

export interface EconSubsidy {
  code: string
  label: string
  subtitle: string
  kind: 'once' | 'year'
  enabled: boolean
  value: number | null
  total: number | null
  params: string[]
  fig: EconFig
}

export interface EconSuggestion {
  key: string
  label: string
  unit: string
  scope: 'process' | 'site' | 'subsidy' | 'combo'
  /** Для combo: какие меры господдержки включаются вместе со скидкой. */
  with?: string[]
  with_labels?: string[]
  from: number
  to: number
  effect: number
  payback: number | null
}

export interface EconProcess {
  process_code: string
  process_name: string
  robot_name: string
  image_url: string | null
  count: number | null
  cost_rub: number | null
  included: boolean
  off?: boolean
  note: string
  share: number
  share_note: string
  release?: EconRelease | null
  story?: EconStory | null
  /** Вывод: выгоден, окупится с условием, невыгоден, нет данных о людях. */
  status?: 'ok' | 'conditional' | 'bad' | 'no_staff' | 'none'
  /** Ближайшее изменение, при котором процесс окупается. hard — условие за пределами реалистичного (скидка больше 30% и т. п.). */
  condition?: (EconSuggestion & { hard?: boolean }) | null
  profitable: boolean | null
  reason: string
  payroll: EconFig | null
  scenarios: EconScenario[]
  suggestions: EconSuggestion[]
  /** Число роботов, при котором процесс выгоден сам по себе: его платформа ставит сама. */
  tuning?: { from: number; to: number; npv: number; payback: number | null; capex: number; enough: number } | null
}

export interface EconReport {
  assumptions?: { process_code: string; product_id: string; name: string; fields: SelectionAssumption[] }[]
  uses_demo_synthetic?: boolean
  demo_synthetic?: DemoSyntheticGroup[]
  project_id: string
  disclaimer: string
  status?: 'complete' | 'incomplete' | 'demo_estimate'
  scope?: 'project' | 'automation_program'
  effective_overrides?: Record<string, number>
  active_overrides?: Record<string, number>
  manual_processes?: { process_code: string; process_name: string; mode: string }[]
  complete?: boolean
  blockers?: { code: string; message: string; process_code?: string }[]
  coverage?: { requested_processes: number; included_processes: number }
  fleet: EconFleet[]
  horizon_years: number
  robots: number
  payroll: EconFig
  release?: { fte: number; base_fte: number; share: number | null; check: string; items: EconRelease[] }
  story?: { staff_now: number; payroll_now: number; released: number; saving: number }
  discount?: EconFig
  requests?: EconRequest[]
  scenarios: EconScenario[]
  processes?: EconProcess[]
  subsidies?: EconSubsidy[]
  params: EconParam[]
  sensitivity: EconSensitivity[]
  interval?: EconInterval
  breakeven?: EconBreakeven[]
  stress?: EconStress[]
  chance?: EconChance | null
  plan?: EconPlan | null
  /** Через сколько месяцев покупка обгоняет аренду. */
  switch?: EconFig | null
  saved_overrides: Record<string, number>
}

/** Коэффициенты, которые what-if умеет задать одному процессу. Остальные остаются на всю площадку. */
export const PROCESS_PARAM_KEYS = [
  'price_factor',
  'infra_pct', 'software_pct', 'integration_pct', 'commissioning_pct', 'training_pct', 'reserve_pct',
  'service_pct', 'license_pct', 'comms_pct', 'consumables_pct', 'repair_pct', 'energy_kwh',
  'raas_rate_pct',
  'replacement_pct', 'robots_per_operator',
] as const

export const PARAM_GROUPS: { id: EconParam['group']; label: string }[] = [
  { id: 'whatif', label: 'What-if' },
  { id: 'staff', label: 'Персонал' },
  { id: 'capex', label: 'CAPEX' },
  { id: 'opex', label: 'OPEX' },
  { id: 'raas', label: 'Аренда' },
  { id: 'horizon', label: 'Горизонт' },
  { id: 'finance', label: 'Налоги и деньги' },
  { id: 'subsidy', label: 'Господдержка' },
]

export const subsidyKey = (code: string) => `subsidy:${code}`

export const SOURCE_TONE: Record<EconSource, 'ok' | 'warn' | 'info' | 'neutral' | 'brand'> = {
  card: 'ok',
  fleet: 'ok',
  site: 'info',
  norm: 'neutral',
  project: 'brand',
  calc: 'neutral',
}

export const rubles = (value: number | null | undefined) => value == null ? '—' : `${Math.round(value).toLocaleString('ru-RU')} ₽`

/** Миллионы со знаком: для NPV и потоков, где важно, плюс или минус. */
export const signedMillions = (value: number | null | undefined, digits = 1) => {
  if (value == null) return '—'
  const text = Math.abs(value / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: digits })
  return `${value < 0 ? '−' : value > 0 ? '+' : ''}${text} млн ₽`
}

/** Условие окупаемости словами: «при скидке вендора 15%», «с субсидией Минпромторга». */
export const conditionText = (item: EconSuggestion) => {
  const n = (value: number) => value.toLocaleString('ru-RU', { maximumFractionDigits: 1 })
  if (item.scope === 'subsidy') return item.key.includes(',') ? `с ${item.key.split(',').length} мерами господдержки` : `с мерой «${item.label}»`
  if (item.scope === 'combo') return `при скидке вендора ${n(item.from - item.to)}% и мерах господдержки`
  if (item.key === 'price_factor') return item.to < item.from ? `при скидке вендора ${n(item.from - item.to)}%` : `даже если цена вырастет на ${n(item.to - item.from)}%`
  if (item.key === 'service_pct') return `при сервисе ${n(item.to)}% цены в год вместо ${n(item.from)}%`
  if (item.key === 'salary_factor') return `если зарплаты на ${n(item.to - item.from)}% выше`
  if (item.key === 'robots_per_operator') return `если диспетчер ведёт ${n(item.to)} машин вместо ${n(item.from)}`
  if (item.key === 'energy_tariff') return `при тарифе ${n(item.to)} ₽/кВт·ч`
  return `${item.label.toLowerCase()}: ${n(item.from)} → ${n(item.to)} ${item.unit}`.trim()
}

/** «2,3 года», «5 лет»: окупаемость словами. */
export const yearsText = (value: number | null | undefined) => {
  if (value == null) return '—'
  const rounded = Math.round(value * 10) / 10
  const text = rounded.toLocaleString('ru-RU', { maximumFractionDigits: 1 })
  if (!Number.isInteger(rounded)) return `${text} года`
  const mod10 = rounded % 10
  const mod100 = rounded % 100
  if (mod10 === 1 && mod100 !== 11) return `${text} год`
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${text} года`
  return `${text} лет`
}

export const millions = (value: number | null | undefined) =>
  value == null ? '—' : `${(value / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} млн ₽`

/* Почему робот выбран, откуда его количество и как он попадает в деньги — тремя короткими фразами для человека. */
const RANK_LABEL: Record<string, string> = { payload_kg: 'грузоподъёмность', proizvoditelnost: 'производительность', speed_loaded_ms: 'скорость с грузом', throughput: 'пропускная способность' }
const robotsWord = (n: number) => n % 10 === 1 && n % 100 !== 11 ? 'робот' : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? 'робота' : 'роботов'
export interface RobotChoice { why: string; count: string; money: string; rent: string }
export function robotChoice(group: (MatchGroup & { rank_key?: string; rank_order?: string }) | undefined, fleet: EconFleet | undefined, processCapex?: number | null, autoFrom?: number | null, off = false): RobotChoice | null {
  if (!fleet) return null
  const hits = group?.hits ?? []
  const fits = hits.filter((hit) => hit.verdict === 'pass')
  const ready = fits.filter((hit) => hit.economic_ready || hit.demo_economic_ready)
  const best = group?.demo_best_product_id ?? group?.best_product_id
  const label = group?.rank_key ? RANK_LABEL[group.rank_key] ?? 'ключевая характеристика процесса' : ''
  const ruleText = label ? `${group?.rank_order === 'asc' ? 'наименьшая' : 'наибольшая'} ${label}` : 'самая низкая цена'
  let why: string
  if (best && fleet.product_id !== best) why = `Выбран вручную в сравнении. Платформа по умолчанию предложила бы другого робота — с лучшим показателем «${label || 'цена'}».`
  else if (!hits.length) why = 'Выбран на шаге подбора.'
  else if (ready.length <= 1) why = `Из ${hits.length} ${robotsWord(hits.length)} каталога для этого процесса под условия площадки подходят ${fits.length}, и только у этого известны цена и производительность — его и считаем.`
  else why = `Из ${hits.length} ${robotsWord(hits.length)} каталога под условия площадки подходят ${fits.length}, у ${ready.length} известны цена и производительность. Среди них у этого ${ruleText} — поэтому он.`
  const n = fleet.count_used ?? fleet.count ?? 1
  const sizing = fleet.sizing
  const working = typeof sizing?.working_count === 'number' ? sizing.working_count : null
  const reserve = typeof sizing?.reserve_count === 'number' ? sizing.reserve_count : 0
  const count = autoFrom != null ? `${n} шт. — платформа уменьшила с ${autoFrom}: людей на процессе меньше, лишние роботы никого не заменят.`
    : fleet.count_source === 'project' ? `${n} шт. — задано вручную.`
    : fleet.count_source === 'default' ? 'Формуле не хватило данных площадки — в расчёте 1 робот. Уточните число на процессе.'
    : working != null && n === working + reserve ? `${n} шт.: ${working} в работе${reserve ? ` + ${reserve} в резерве` : ''} — по суточному потоку и выработке одного робота с учётом зарядки и простоев.`
    : `${n} шт. — по формуле процесса из потока и параметров площадки.`
  const unit = fleet.price_rub
  const money = !fleet.included || fleet.off || off ? 'Процесс не входит в итог, поэтому в CAPEX робот не заложен.'
    : unit == null ? 'Цены нет в карточке робота, поэтому в CAPEX он не заложен.'
    : `Покупается сразу, до запуска: ${n} × ${rubles(unit)} с НДС = ${millions(fleet.cost_rub)} без НДС — строка «Оборудование» в CAPEX.${processCapex ? ` Вместе с инфраструктурой, интеграцией и запуском процесс стоит ${millions(processCapex)}.` : ''}`
  const rent = fleet.raas_available ? 'При аренде робот не покупается: он в ежемесячном платеже, а в CAPEX остаётся только подготовка площадки.' : ''
  return { why, count, money, rent }
}

export const figValue = (value: number | null | undefined, unit: string) => {
  if (value == null) return '—'
  /* Сумма в рублях округляется. Тариф вроде 7,2 ₽/кВт·ч оставляем дробным, иначе в тексте и в формуле разные числа. */
  if (unit === '₽') return `${Math.round(value).toLocaleString('ru-RU')} ${unit}`
  if (unit.startsWith('₽')) {
    const text = value.toLocaleString('ru-RU', { maximumFractionDigits: Number.isInteger(value) ? 0 : 2 })
    return `${text} ${unit}`
  }
  if (unit === '%') return `${Math.round(value).toLocaleString('ru-RU')}%`
  if (unit === 'лет') return `${value.toLocaleString('ru-RU', { maximumFractionDigits: 1, minimumFractionDigits: 1 })} лет`
  const text = value.toLocaleString('ru-RU', { maximumFractionDigits: Math.abs(value) < 10 ? 3 : 1 })
  return unit ? `${text} ${unit}` : text
}

export function usePlatformEconomy(id: Ref<string>) {
  const live = useLiveProject(id)
  const { choices, picksFor, skippedOf } = usePlatformCompare(id)
  const skipped = ref<{ code: string; name: string; reason: string }[]>([])
  /* Результат подбора, на котором посчитана экономика: странице проекта он нужен для сводки по шагам. */
  const groups = ref<MatchGroup[]>([])
  const project = live.shell
  const isDemo = live.isDemo
  const readonly = live.readonly
  const objectCode = live.objectCode

  /* Люди на процессе, введённые на шаге экономики. В демо живут только здесь, в своём проекте сохраняются в задачи площадки. */
  type StaffPatch = { name: string; staff_fte_now: number | null; staff_salary_month_rub: number | null; staff_cost_month_rub: number | null; other_cost_month_rub: number | null }
  const staffPatch = ref<Record<string, StaffPatch>>({})
  const withStaff = (tasks: unknown[]) => {
    const rows = (tasks as Record<string, unknown>[]).map((task) => ({ ...task }))
    for (const [code, patch] of Object.entries(staffPatch.value)) {
      const row = rows.find((task) => task.process_code === code)
      const values = { staff_fte_now: patch.staff_fte_now, staff_salary_month_rub: patch.staff_salary_month_rub, staff_cost_month_rub: patch.staff_cost_month_rub, other_cost_month_rub: patch.other_cost_month_rub }
      if (row) Object.assign(row, values)
      else rows.push({ process_code: code, name: patch.name, ...values })
    }
    return rows
  }
  const source = computed(() => {
    if (!project.value) return null
    return { site: live.site.value, tasks: withStaff(live.tasks.value) }
  })
  /* Люди и зарплата — или затраты на процесс суммой в месяц, если людей не считали. Одно исключает другое. */
  const setStaff = async (code: string, name: string, fte: number | null, wageMonth: number | null, costMonth: number | null = null, otherMonth: number | null = null) => {
    staffPatch.value = { ...staffPatch.value, [code]: { name, staff_fte_now: costMonth ? null : fte, staff_salary_month_rub: costMonth ? null : wageMonth, staff_cost_month_rub: costMonth, other_cost_month_rub: costMonth ? null : otherMonth } }
    const rec = live.record.value
    if (!rec || readonly.value) return
    const enabled: Record<string, boolean> = {}
    for (const item of rec.processes) enabled[item.code] = item.enabled
    await live.save({ ...rec.site }, withStaff(rec.tasks), enabled)
  }

  const report = ref<EconReport | null>(null)
  const loading = ref(false)
  const failure = ref('')
  let token = 0
  let asked: Record<string, number> | null | undefined
  // Локальный What-if живёт при переходах по маршруту и не записывается в исходный проект.
  const previews = useState<Record<string, Record<string, number>>>('economy-previews', () => ({}))

  const ensureProject = async () => id.value

  /* Демо считается тем же движком через те же ручки проекта: опубликованное демо сервер отдаёт без входа. */
  const request = async (preview: Record<string, number> | null = null) => {
    if (!source.value || !objectCode.value) throw new Error('Нет параметров площадки')
    const match = await platformSend<{ groups: MatchGroup[] }>(`/projects/${id.value}/match`, 'POST', { site: source.value.site, tasks: source.value.tasks })
    skipped.value = skippedOf(match.groups)
    groups.value = match.groups
    const body: Record<string, unknown> = {
      site: source.value.site,
      tasks: source.value.tasks,
      choices: choices.value,
      picks: picksFor(match.groups),
    }
    if (preview) body.preview = preview
    const result = await platformSend<EconReport>(`/projects/${id.value}/economy`, 'POST', body)
    if (result.scope === 'automation_program') skipped.value = skipped.value.filter(row => !result.manual_processes?.some(p => p.process_code === row.code))
    return result
  }

  const load = async (preview: Record<string, number> | null | undefined = undefined) => {
    const effective = preview === undefined ? previews.value[id.value] ?? null : preview
    if (preview !== undefined) {
      if (preview === null) delete previews.value[id.value]
      else previews.value[id.value] = { ...preview }
    }
    asked = effective
    if (import.meta.server || !source.value || !objectCode.value) return
    const mine = ++token
    loading.value = true
    failure.value = ''
    try {
      const result = await request(effective)
      if (mine === token) report.value = result
    } catch (err: unknown) {
      if (mine === token) failure.value = fetchErrorMessage(err, 'Не удалось посчитать экономику')
    } finally {
      if (mine === token) loading.value = false
    }
  }

  /* Отчёт зовёт расчёт сразу, а площадка демо подгружается следом. Без повтора экран остаётся пустым, а кнопки выгрузки — неактивными. */
  watch([source, objectCode], () => {
    if (asked === undefined || !source.value || !objectCode.value) return
    void load(asked)
  })

  /* Только просмотр: коэффициенты меняются в what-if локально, но в проект не пишутся. */
  const saveOverrides = async (values: Record<string, number>) => {
    if (readonly.value) return
    await platformSend(`/projects/${id.value}/economy/overrides`, 'PUT', { values })
  }

  const setProcess = async (code: string, on: boolean, reason?: string) => {
    const rec = live.record.value
    if (!rec || readonly.value) return
    const enabled: Record<string, boolean> = {}
    for (const item of rec.processes) enabled[item.code] = item.code === code ? on : item.enabled
    await live.save({ ...rec.site }, rec.tasks, enabled, reason ? { [code]: reason } : undefined)
  }
  const disableProcess = (code: string, reason: string) => setProcess(code, false, reason)
  const restoreProcess = (code: string) => setProcess(code, true)
  const inactive = computed(() => (live.record.value?.processes ?? []).filter((item) => !item.enabled))

  return {
    project,
    isDemo,
    readonly,
    report,
    loading,
    failure,
    pending: live.pending,
    error: live.error,
    source,
    choices,
    skipped,
    groups,
    live,
    objectCode,
    ensureProject,
    load,
    request,
    saveOverrides,
    disableProcess,
    restoreProcess,
    setStaff,
    inactive,
  }
}

/** Месяцы словами: «8 мес.», «2 года 4 мес.». */
export const monthsText = (value: number | null | undefined) => {
  if (value == null) return '—'
  const total = Math.round(value)
  const years = Math.floor(total / 12)
  const months = total % 12
  if (!years) return `${months} мес.`
  return months ? `${yearsText(years)} ${months} мес.` : yearsText(years)
}

/** Значения проекта с правками платформы: число роботов и состав процессов, с метками auto:*, чтобы их можно было вернуть. */
export const withPlan = (overrides: Record<string, number>, changes: EconPlanChange[]) => {
  const next = { ...overrides }
  for (const change of changes) {
    if (change.kind === 'count') {
      next[`auto:count:${change.code}`] = next[`auto:count:${change.code}`] ?? change.from ?? 1
      next[`count:${change.code}`] = change.to ?? 1
    } else if (change.kind === 'off') {
      next[`off:${change.code}`] = 1
      next[`auto:off:${change.code}`] = 1
    } else {
      delete next[`off:${change.code}`]
      delete next[`auto:off:${change.code}`]
    }
  }
  next.auto = 1
  return next
}

/** Срок окупаемости аренды: своих вложений — только внедрение на площадке, окупаемость считается для них. */
export const rentPaybackText = (item: EconScenario) => {
  if ((item.capex.value ?? 0) <= 0) return 'сразу: вложений нет'
  return item.implementation_payback != null ? yearsText(item.implementation_payback) : 'не окупается'
}
