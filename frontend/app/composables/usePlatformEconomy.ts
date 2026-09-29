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
  tco: EconFig
  years: { year: number; cost_rub: number; net_rub: number }[]
  verdict: string
}

export interface EconParam {
  key: string
  group: 'capex' | 'opex' | 'staff' | 'raas' | 'horizon' | 'whatif' | 'subsidy'
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
  scope: 'process' | 'site' | 'subsidy'
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
  note: string
  share: number
  share_note: string
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
  scenarios: EconScenario[]
  processes?: EconProcess[]
  subsidies?: EconSubsidy[]
  params: EconParam[]
  sensitivity: EconSensitivity[]
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

export const millions = (value: number | null | undefined) =>
  value == null ? '—' : `${(value / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} млн ₽`

export const figValue = (value: number | null | undefined, unit: string) => {
  if (value == null) return '—'
  if (unit.startsWith('₽')) return `${Math.round(value).toLocaleString('ru-RU')} ${unit}`
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

  const source = computed(() => {
    if (!project.value) return null
    return { site: live.site.value, tasks: live.tasks.value }
  })

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
    inactive,
  }
}
