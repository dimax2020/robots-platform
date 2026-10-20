import type { Ref } from 'vue'
import { fetchErrorMessage } from '~/utils/errors'
import { platformSend } from '~/composables/usePlatform'
import { useLiveProject } from '~/composables/useLiveProject'
import { usePlatformCompare, type MatchGroup } from '~/composables/usePlatformCompare'

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
  annual_cost: number
  effect: EconFig
  effect_lines: EconFig[]
  payback: EconFig
  roi: EconFig
  npv?: EconFig
  irr?: EconFig
  dpp?: EconFig
  /** Индекс доходности: приведённый поток на рубль вложений. */
  pi?: EconFig
  /** Годовая стоимость операций после налога с учётом вложений: сравнивает сценарии на одной шкале. */
  eac?: EconFig
  tco: EconFig
  cashflow?: EconCashRow[]
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
  /** Цена одной операции до и после: ₽ на паллету или строку заказа. */
  unit?: EconUnitCost | null
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

/** Оптимальный состав: набор процессов с наибольшим NPV объекта в пределах бюджета. */
export interface EconBestSet {
  budget: number | null
  codes: string[]
  names: string[]
  npv: number | null
  capex: number
  payback: number | null
  current_npv: number | null
  current_capex?: number
  same: boolean
  gain: number | null
  dropped: string[]
  added: string[]
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
}

export interface EconReport {
  project_id: string
  disclaimer: string
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
  best_set?: EconBestSet | null
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
  const project = live.shell
  const isDemo = live.isDemo
  const readonly = live.readonly
  const objectCode = live.objectCode

  /* Люди на процессе, введённые на шаге экономики. В демо живут только здесь, в своём проекте сохраняются в задачи площадки. */
  const staffPatch = ref<Record<string, { name: string; staff_fte_now: number | null; staff_salary_month_rub: number | null }>>({})
  const withStaff = (tasks: unknown[]) => {
    const rows = (tasks as Record<string, unknown>[]).map((task) => ({ ...task }))
    for (const [code, patch] of Object.entries(staffPatch.value)) {
      const row = rows.find((task) => task.process_code === code)
      if (row) Object.assign(row, { staff_fte_now: patch.staff_fte_now, staff_salary_month_rub: patch.staff_salary_month_rub })
      else rows.push({ process_code: code, name: patch.name, staff_fte_now: patch.staff_fte_now, staff_salary_month_rub: patch.staff_salary_month_rub })
    }
    return rows
  }
  const source = computed(() => {
    if (!project.value) return null
    return { site: live.site.value, tasks: withStaff(live.tasks.value) }
  })
  const setStaff = async (code: string, name: string, fte: number | null, wageMonth: number | null) => {
    staffPatch.value = { ...staffPatch.value, [code]: { name, staff_fte_now: fte, staff_salary_month_rub: wageMonth } }
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

  const ensureProject = async () => id.value

  /* Демо считается тем же движком через те же ручки проекта: опубликованное демо сервер отдаёт без входа. */
  const request = async (preview: Record<string, number> | null = null) => {
    if (!source.value || !objectCode.value) throw new Error('Нет параметров площадки')
    const match = await platformSend<{ groups: MatchGroup[] }>(`/projects/${id.value}/match`, 'POST', { site: source.value.site, tasks: source.value.tasks })
    skipped.value = skippedOf(match.groups)
    const body: Record<string, unknown> = {
      site: source.value.site,
      tasks: source.value.tasks,
      choices: choices.value,
      picks: picksFor(match.groups),
    }
    if (preview) body.preview = preview
    return await platformSend<EconReport>(`/projects/${id.value}/economy`, 'POST', body)
  }

  const load = async (preview: Record<string, number> | null = null) => {
    asked = preview
    if (import.meta.server || !source.value || !objectCode.value) return
    const mine = ++token
    loading.value = true
    failure.value = ''
    try {
      const result = await request(preview)
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
