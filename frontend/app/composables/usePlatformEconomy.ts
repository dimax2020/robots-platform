import type { Ref } from 'vue'
import { projects } from '~/data/projects'
import { fetchErrorMessage } from '~/composables/useCalc'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { usePlatformCompare } from '~/composables/usePlatformCompare'

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
  group: 'capex' | 'opex' | 'staff' | 'raas' | 'horizon' | 'whatif'
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

export interface EconReport {
  project_id: string
  fleet: EconFleet[]
  horizon_years: number
  robots: number
  payroll: EconFig
  scenarios: EconScenario[]
  params: EconParam[]
  sensitivity: EconSensitivity[]
  saved_overrides: Record<string, number>
}

export const PARAM_GROUPS: { id: EconParam['group']; label: string }[] = [
  { id: 'whatif', label: 'What-if' },
  { id: 'staff', label: 'Персонал' },
  { id: 'capex', label: 'CAPEX' },
  { id: 'opex', label: 'OPEX' },
  { id: 'raas', label: 'Аренда' },
  { id: 'horizon', label: 'Горизонт' },
]

export const SOURCE_TONE: Record<EconSource, 'ok' | 'warn' | 'info' | 'neutral' | 'brand'> = {
  card: 'ok',
  fleet: 'ok',
  site: 'info',
  norm: 'neutral',
  project: 'brand',
  calc: 'neutral',
}

interface PlatformProject { id: string; object_code: string }

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
  const { project: liveProject, detail, pending: livePending, error: liveError } = useCalc(id)
  const demoProject = computed(() => projects.find((item) => item.id === id.value))
  const project = computed(() => liveProject.value ?? demoProject.value)
  const isDemo = computed(() => !liveProject.value && Boolean(demoProject.value))
  const objectCode = computed(() => liveProject.value?.objectType ?? demoProject.value?.objectType ?? '')
  const { profile, pending: profilePending } = useSiteProfile(computed(() => (isDemo.value ? objectCode.value : '')))
  const { choices } = usePlatformCompare(id)

  const source = computed(() => {
    if (liveProject.value && detail.value) return { site: detail.value.site ?? {}, tasks: detail.value.tasks ?? [] }
    if (isDemo.value && profile.value) return { site: profile.value.site ?? {}, tasks: profile.value.tasks ?? [] }
    return null
  })

  const report = ref<EconReport | null>(null)
  const loading = ref(false)
  const failure = ref('')
  const platformId = ref<string | null>(null)
  let token = 0

  const ensureProject = async () => {
    if (platformId.value) return platformId.value
    const key = `platform-project:${id.value}`
    const saved = localStorage.getItem(key)
    if (saved) {
      try {
        const current = await platformGet<PlatformProject>(`/projects/${saved}`)
        if (current.object_code === objectCode.value) {
          platformId.value = current.id
          return current.id
        }
      } catch {
        localStorage.removeItem(key)
      }
    }
    const created = await platformSend<PlatformProject>('/projects', 'POST', { name: project.value?.name ?? objectCode.value, object_code: objectCode.value, site: {} })
    localStorage.setItem(key, created.id)
    platformId.value = created.id
    return created.id
  }

  const request = async (preview: Record<string, number> | null = null) => {
    if (!source.value) throw new Error('Нет параметров площадки')
    const projectId = await ensureProject()
    return await platformSend<EconReport>(`/projects/${projectId}/economy`, 'POST', {
      site: source.value.site,
      tasks: source.value.tasks,
      choices: choices.value,
      preview,
    })
  }

  const load = async (preview: Record<string, number> | null = null) => {
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

  const saveOverrides = async (values: Record<string, number>) => {
    const projectId = await ensureProject()
    await platformSend(`/projects/${projectId}/economy/overrides`, 'PUT', { values })
  }

  return {
    project,
    isDemo,
    report,
    loading,
    failure,
    pending: computed(() => livePending.value || profilePending.value),
    error: liveError,
    source,
    choices,
    load,
    request,
    saveOverrides,
  }
}
