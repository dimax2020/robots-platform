import type { Ref } from 'vue'
import { objectTypeLabel, isFullPath } from '~/data/projects'
import { siteFieldMeta } from '~/data/siteFields'
import { photoFor } from '~/data/placeholders'
import { fetchErrorMessage } from '~/utils/errors'
import { fileStem, type TableSheet } from '~/utils/exportTables'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { useLiveProject } from '~/composables/useLiveProject'
import { usePlatformCompare, type MatchGroup, type MatchHit } from '~/composables/usePlatformCompare'
import {
  PARAM_GROUPS,
  PRELIMINARY,
  figValue,
  millions,
  rubles,
  usePlatformEconomy,
  type EconFig,
  type EconParam,
  type EconScenario,
  type EconSensitivity,
} from '~/composables/usePlatformEconomy'
import { buildProcess, normalizeLayout } from '~/sim/templates'
import type { Layout, LayoutItem, SimProcess } from '~/sim/types'

export interface MissingStep {
  id: string
  label: string
  to: string
  text: string
}

export interface MetricCell { label: string; value: string }
export interface CostLine { label: string; value: string }

export interface ScenarioCard {
  key: EconScenario['key']
  title: string
  subtitle: string
  note: string
  verdict: string
  highlight: boolean
  metrics: MetricCell[]
  capex: string
  opex: string
  effect: string
  payrollAfter: string
  capexLines: CostLine[]
  opexLines: CostLine[]
}

export interface ChartBar { key: string; value: number; label: string }
export interface ChartYear { year: number; bars: ChartBar[] }

export interface RobotCard {
  key: string
  process: string
  name: string
  image: string
  count: string
  price: string
  cost: string
  note: string
  specs: { label: string; value: string }[]
  fig: EconFig | null
}

export interface FormulaPart {
  title: string
  total: EconFig | null
  lines: EconFig[]
}

export interface AdviceRow {
  key: string
  title: string
  tco: string
  gap: string
  effect: string
  payback: string
  winner: boolean
}

export interface Advice {
  title: string
  headline: string
  detail: string
  rows: AdviceRow[]
}

export interface ParamRow { label: string; value: string }

interface ReportGroup extends MatchGroup {
  layout_items?: LayoutItem[]
}

const ORDER: EconScenario['key'][] = ['asis', 'purchase', 'raas']
const TITLES: Record<EconScenario['key'], string> = {
  asis: 'Без роботизации',
  purchase: 'Покупка',
  raas: 'Аренда (RaaS)',
}

const filled = (value: unknown) => value !== null && value !== undefined && value !== ''

const formatValue = (value: unknown, unit = '') => {
  if (typeof value === 'boolean') return value ? 'да' : 'нет'
  if (typeof value === 'number' && Number.isFinite(value)) {
    const text = value.toLocaleString('ru-RU', { maximumFractionDigits: Math.abs(value) < 10 ? 3 : 1 })
    return unit ? `${text} ${unit}` : text
  }
  const text = String(value)
  return unit && text ? `${text} ${unit}` : text
}

const formatSpec = (value: number, unit: string) => {
  const digits = unit === '₽' || unit === 'шт' || unit === 'мм' || unit === 'кг' ? 0 : 1
  const text = value.toLocaleString('ru-RU', { maximumFractionDigits: digits })
  return unit ? `${text} ${unit}` : text
}

const money = (fig?: EconFig | null) => (fig?.unit.startsWith('₽') ? millions(fig.value) : figValue(fig?.value, fig?.unit ?? ''))

const linesOf = (figs: EconFig[]) => figs
  .filter((item) => item.included && item.value != null)
  .map((item) => ({ label: item.label, value: rubles(item.value) }))

const paybackText = (item: EconScenario) => {
  if (item.key === 'asis') return '—'
  return item.payback.value != null ? figValue(item.payback.value, 'лет') : 'нет'
}

const isFig = (value: unknown): value is EconFig => {
  if (!value || typeof value !== 'object') return false
  const row = value as Partial<EconFig>
  return typeof row.label === 'string' && typeof row.tex === 'string' && Array.isArray(row.vars)
}

const FIG_ORDER = ['capex', 'opex', 'effect', 'payroll_after', 'payback', 'roi', 'tco']

/** Любая величина с формулой и любой список статей. Новое поле в ответе экономики попадает в отчёт без правки вёрстки. */
export function formulaParts(source: Record<string, unknown>): FormulaPart[] {
  const parts: FormulaPart[] = []
  const used = new Set<string>()
  for (const [key, value] of Object.entries(source)) {
    if (!Array.isArray(value) || !value.some(isFig)) continue
    const totalKey = key.endsWith('_lines') ? key.slice(0, -'_lines'.length) : ''
    const total = totalKey && isFig(source[totalKey]) ? source[totalKey] : null
    if (totalKey) used.add(totalKey)
    used.add(key)
    parts.push({ title: total?.label || key, total, lines: value.filter(isFig) })
  }
  const rest = Object.entries(source).filter(([key, value]) => isFig(value) && !used.has(key))
  rest.sort((left, right) => (FIG_ORDER.indexOf(left[0]) + 1 || 99) - (FIG_ORDER.indexOf(right[0]) + 1 || 99))
  for (const [key, value] of rest) {
    if (!isFig(value)) continue
    parts.push({ title: value.label || key, total: value, lines: [] })
  }
  const rank = (part: FormulaPart) => {
    const index = FIG_ORDER.findIndex((key) => part.total?.key === key || part.total?.key?.startsWith(key))
    return index === -1 ? 99 : index
  }
  return parts.sort((left, right) => rank(left) - rank(right))
}

const looseFig = (key: string, label: string, unit: string, raw: unknown): EconFig | null => {
  if (!raw || typeof raw !== 'object') return null
  const row = raw as Partial<EconFig>
  if (typeof row.tex !== 'string' || !row.tex) return null
  return {
    key,
    label: row.label || label,
    value: row.value ?? null,
    unit: row.unit || unit,
    tex: row.tex,
    subst: row.subst ?? '',
    vars: Array.isArray(row.vars) ? row.vars : [],
    note: row.note ?? '',
    included: row.value != null,
    symbol: row.symbol ?? '',
  }
}

const sensitivityRows = (rows: readonly EconSensitivity[]) => {
  const payback = (value: number | null) => value == null ? 'не окупается' : figValue(value, 'лет')
  return [
    ['Допущение', 'Единица', 'Сейчас', 'При −20%', 'При +20%', 'Эффект в год сейчас', 'Эффект при −20%', 'Эффект при +20%', 'Окупаемость сейчас', 'Окупаемость при −20%', 'Окупаемость при +20%'],
    ...[...rows]
      .sort((a, b) => Math.abs(b.effect_high - b.effect_low) - Math.abs(a.effect_high - a.effect_low))
      .map((item) => [
        item.label, item.unit, figValue(item.value, ''), figValue(item.low_value, ''), figValue(item.high_value, ''),
        millions(item.effect), millions(item.effect_low), millions(item.effect_high),
        payback(item.payback), payback(item.payback_low), payback(item.payback_high),
      ]),
  ]
}

export function useProjectReport(id: Ref<string>) {
  const live = useLiveProject(id)
  const compare = usePlatformCompare(id)
  const economy = usePlatformEconomy(id)
  const { role } = useRole()

  const groups = ref<ReportGroup[]>([])
  const layout = ref<Layout | null>(null)
  const fieldLabels = ref<Record<string, { label: string; unit: string }>>({})
  const loading = ref(false)
  const failure = ref('')
  let token = 0

  const project = computed(() => live.shell.value)
  const isDemo = computed(() => live.isDemo.value)
  const closed = computed(() => Boolean(project.value && !isFullPath(project.value)))
  const today = computed(() => new Date().toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' }))
  const site = computed(() => live.site.value)

  const hasParams = computed(() => {
    const processes = live.record.value?.processes.filter((item) => item.enabled) ?? []
    return Object.values(site.value).some(filled) || processes.length > 0
  })

  const missing = computed<MissingStep[]>(() => {
    if (!project.value || isDemo.value || closed.value) return []
    if (!hasParams.value) {
      return [{ id: 'params', label: 'Параметры', to: `/projects/${id.value}/params`, text: 'Нет сохранённых параметров объекта и включённых процессов.' }]
    }
    if (!groups.value.length) {
      return [{ id: 'match', label: 'Подбор', to: `/projects/${id.value}/match`, text: 'Подбор ещё не посчитан: нет вердиктов по включённым процессам.' }]
    }
    if (!economy.report.value) {
      return [{ id: 'economics', label: 'Экономика', to: `/projects/${id.value}/economics`, text: 'Экономика ещё не посчитана: нет трёх сценариев для выгрузки.' }]
    }
    return []
  })

  const ready = computed(() => {
    if (!project.value || closed.value) return false
    if (isDemo.value) return Boolean(economy.report.value)
    return missing.value.length === 0 && Boolean(economy.report.value)
  })

  const disclaimer = computed(() => economy.report.value?.disclaimer || PRELIMINARY)

  const params = computed<ParamRow[]>(() => Object.entries(site.value).flatMap(([key, value]) => {
    if (!filled(value)) return []
    const meta = fieldLabels.value[key] ?? siteFieldMeta.find((item) => item.key === key)
    return [{ label: meta?.label ?? key, value: formatValue(value, meta?.unit ?? '') }]
  }))

  const ordered = computed(() => {
    const report = economy.report.value
    if (!report) return []
    return ORDER.flatMap((key) => {
      const item = report.scenarios.find((row) => row.key === key)
      return item ? [item] : []
    })
  })

  const winnerKey = computed(() => {
    const rows = ordered.value.filter((item) => item.tco.value != null)
    if (!rows.length) return ''
    return rows.reduce((left, right) => (left.tco.value! <= right.tco.value! ? left : right)).key
  })

  const advice = computed<Advice | null>(() => {
    const report = economy.report.value
    const ranked = [...ordered.value].filter((item) => item.tco.value != null).sort((left, right) => left.tco.value! - right.tco.value!)
    const winner = ranked[0]
    const next = ranked[1]
    if (!report || !winner) return null
    const gap = next?.tco.value != null ? next.tco.value - winner.tco.value! : null
    const payback = winner.key === 'asis' ? '' : winner.payback.value != null ? `Окупаемость ${figValue(winner.payback.value, 'лет')}, эффект в год ${millions(winner.effect.value)}.` : 'Срок окупаемости не считается: эффект не покрывает вложения.'
    const versus = next && gap != null
      ? `TCO за ${report.horizon_years} лет — ${millions(winner.tco.value)}, на ${millions(gap)} меньше, чем у «${next.title}» (${millions(next.tco.value)}).`
      : `TCO за ${report.horizon_years} лет — ${millions(winner.tco.value)}.`
    const why = winner.key === 'asis'
      ? 'Покупка и аренда при этих допущениях не снижают совокупные затраты относительно текущих операций.'
      : payback
    return {
      title: winner.title,
      headline: `Выгоднее «${winner.title}»`,
      detail: `${versus} ${why}`.trim(),
      rows: ordered.value.map((item) => ({
        key: item.key,
        title: item.title,
        tco: millions(item.tco.value),
        gap: item.key === winner.key || winner.tco.value == null || item.tco.value == null ? (item.key === winner.key ? 'минимум' : '—') : `+${millions(item.tco.value - winner.tco.value)}`,
        effect: item.key === 'asis' ? 'база' : millions(item.effect.value),
        payback: paybackText(item),
        winner: item.key === winner.key,
      })),
    }
  })

  const scenarios = computed<ScenarioCard[]>(() => ordered.value.map((item) => ({
    key: item.key,
    title: item.title || TITLES[item.key],
    subtitle: item.subtitle,
    note: item.note,
    verdict: item.key === 'asis' ? 'Точка сравнения' : item.verdict,
    highlight: item.key === winnerKey.value,
    metrics: [
      { label: 'CAPEX', value: money(item.capex) },
      { label: 'Затраты в год', value: millions(item.annual_cost) },
      { label: 'Эффект в год', value: item.key === 'asis' ? 'база' : money(item.effect) },
      { label: 'Окупаемость', value: paybackText(item) },
      { label: 'TCO', value: money(item.tco) },
    ],
    capex: money(item.capex),
    opex: millions(item.annual_cost),
    effect: item.key === 'asis' ? 'база' : money(item.effect),
    payrollAfter: item.key === 'asis' ? money(economy.report.value?.payroll) : money(item.payroll_after),
    capexLines: item.key === 'asis' ? [] : linesOf(item.capex_lines),
    opexLines: item.key === 'asis' ? [{ label: 'ФОТ до роботизации', value: rubles(economy.report.value?.payroll.value) }] : linesOf(item.opex_lines),
  })))

  const chart = computed(() => {
    const report = economy.report.value
    const base = report?.scenarios.find((item) => item.key === 'asis')?.years ?? report?.scenarios[0]?.years ?? []
    const years: ChartYear[] = base.map((row) => ({
      year: row.year,
      bars: ORDER.map((key) => {
        const item = report?.scenarios.find((scenario) => scenario.key === key)
        return { key, label: item?.title || TITLES[key], value: item?.years.find((year) => year.year === row.year)?.cost_rub ?? 0 }
      }),
    }))
    return {
      horizon: report?.horizon_years ?? years.length,
      max: Math.max(1, ...years.flatMap((row) => row.bars.map((bar) => bar.value))),
      years,
    }
  })

  const payroll = computed(() => economy.report.value ? { label: economy.report.value.payroll.label, value: millions(economy.report.value.payroll.value) } : null)

  const hitOf = (process: string, productId: string): MatchHit | null => {
    const group = groups.value.find((item) => item.process_code === process)
    if (!group) return null
    return group.hits.find((hit) => hit.product_id === productId) ?? compare.remainingHit(group)
  }

  const robots = computed<RobotCard[]>(() => {
    const fleet = economy.report.value?.fleet ?? []
    const rows = fleet.filter((row) => row.included)
    const source = rows.length ? rows : fleet
    return source.map((row) => {
      const hit = hitOf(row.process_code, row.product_id)
      const specs = (hit?.specs ?? [])
        .filter((spec) => spec.key !== 'price_rub')
        .map((spec) => ({ label: spec.label, value: formatSpec(spec.value, spec.unit) }))
      return {
        key: row.process_code,
        process: row.process_name,
        name: row.name,
        image: photoFor(row.image_url, row.name, row.process_code),
        count: row.count_used != null ? `${row.count_used.toLocaleString('ru-RU')} шт.` : 'количество не задано',
        price: row.price_rub != null ? rubles(row.price_rub) : 'цены нет',
        cost: row.cost_rub != null ? rubles(row.cost_rub) : '—',
        note: row.note,
        specs,
        fig: row.fig,
      }
    })
  })

  const paramGroups = computed(() => {
    const rows = economy.report.value?.params ?? []
    const known = new Map(PARAM_GROUPS.map((group) => [group.id, group.label]))
    const ids = [...new Set(rows.map((item) => item.group))]
    const orderedIds = [...PARAM_GROUPS.map((group) => group.id).filter((id) => ids.includes(id)), ...ids.filter((id) => !known.has(id))]
    return orderedIds.map((id) => ({
      id,
      label: known.get(id as EconParam['group']) ?? id,
      items: rows.filter((item) => item.group === id),
    }))
  })

  const formulas = computed(() => {
    const report = economy.report.value as (typeof economy.report.value & { hours?: unknown; operator?: unknown }) | null
    if (!report) return []
    const bases = [
      looseFig('hours', 'Фонд рабочих часов', 'ч', report.hours),
      looseFig('operator', 'Стоимость одного оператора', '₽/год', report.operator),
    ].filter((fig): fig is EconFig => Boolean(fig))
    const support = (report.subsidies ?? []).map((item) => {
      const state = item.enabled ? 'Мера включена в расчёт.' : 'Мера выключена: сумма показана как доступная, в сценарии не входит.'
      const total = item.total == null ? '' : ` За горизонт ${report.horizon_years} лет: ${millions(item.total)}.`
      return {
        ...item.fig,
        note: `${state}${total} ${item.subtitle} ${item.fig.note}`.trim(),
      }
    })
    return [
      ...bases.map((fig) => ({ key: fig.key, title: fig.label, parts: formulaParts({ [fig.key]: fig }) })),
      { key: 'payroll', title: report.payroll.label, parts: formulaParts({ payroll: report.payroll }) },
      ...ordered.value.map((item) => ({ key: item.key, title: item.title, parts: formulaParts(item as unknown as Record<string, unknown>) })),
      ...(support.length ? [{ key: 'subsidy', title: 'Господдержка', parts: formulaParts(Object.fromEntries(support.map((fig) => [fig.key, fig]))) }] : []),
    ]
  })

  const processes = computed(() => {
    const report = economy.report.value
    if (!report?.processes?.length) return []
    return report.processes.map((item) => {
      const purchase = item.scenarios.find((row) => row.key === 'purchase')
      const raas = item.scenarios.find((row) => row.key === 'raas')
      return {
        key: item.process_code,
        name: item.process_name,
        robot: item.robot_name,
        included: item.included,
        share: item.included ? `${(item.share * 100).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} %` : '—',
        reason: item.reason,
        profitable: item.profitable,
        capex: purchase ? money(purchase.capex) : '—',
        effect: purchase ? money(purchase.effect) : '—',
        payback: purchase ? paybackText(purchase) : '—',
        tcoPurchase: purchase ? money(purchase.tco) : '—',
        tcoRaas: raas ? money(raas.tco) : '—',
        suggestions: item.suggestions.map((hint) => ({
          key: `${hint.scope}:${hint.key}`,
          label: hint.label,
          change: hint.scope === 'subsidy' ? 'включить меру' : `${hint.from.toLocaleString('ru-RU')} → ${hint.to.toLocaleString('ru-RU')} ${hint.unit}`.trim(),
          effect: millions(hint.effect),
          payback: hint.payback == null ? 'нет' : figValue(hint.payback, 'лет'),
        })),
      }
    })
  })

  const sceneProcesses = computed<SimProcess[]>(() => groups.value.map((group) => {
    const hit = compare.remainingHit(group)
    const robot = hit ? { name: hit.name, count: hit.count ?? null, specs: (hit.specs ?? []).map((spec) => ({ key: spec.key, value: spec.value })) } : null
    return buildProcess(group.process_code, group.process_name, robot, site.value, group.layout_items ?? [])
  }))

  const limits = computed(() => {
    const report = economy.report.value
    if (!report) return []
    return [
      ...report.fleet.filter((row) => row.note).map((row) => `${row.name}: ${row.note}`),
      ...report.scenarios.filter((row) => row.note).map((row) => `${row.title}: ${row.note}`),
    ]
  })

  const sheets = computed<TableSheet[]>(() => {
    if (!project.value) return []
    return [
      {
        name: 'Паспорт проекта',
        rows: [
          ['Имя проекта', project.value.name],
          ['Тип объекта', objectTypeLabel[project.value.objectType]],
          ['Отрасль', project.value.industry],
          ['Дата', today.value],
          ['Версия каталога', project.value.catalogVersion],
          ['Версия модели', project.value.modelVersion],
          ['Оговорка', disclaimer.value],
          ['ФОТ до роботизации', payroll.value?.value ?? '—'],
        ],
      },
      {
        name: 'Параметры объекта',
        rows: [['Параметр', 'Значение'], ...params.value.map((item) => [item.label, item.value])],
      },
      {
        name: 'Сценарии',
        rows: [
          ['Сценарий', 'CAPEX', 'Затраты в год', 'Эффект в год', 'Окупаемость', 'TCO', 'Полоса'],
          ...scenarios.value.map((item) => [item.title, item.capex, item.opex, item.effect, item.metrics[3]?.value ?? '—', item.metrics[4]?.value ?? '—', item.verdict]),
        ],
      },
      {
        name: 'Вывод',
        rows: [
          ['Выгоднее', advice.value?.title ?? '—'],
          ['Пояснение', advice.value?.detail ?? '—'],
          ['Сценарий', 'TCO', 'К минимуму', 'Эффект', 'Окупаемость'],
          ...(advice.value?.rows.map((item) => [item.title, item.tco, item.gap, item.effect, item.payback]) ?? []),
        ],
      },
      {
        name: 'Формулы',
        rows: [
          ['Блок', 'Статья', 'Значение', 'Входит', 'Формула', 'Подстановка', 'Примечание'],
          ...formulas.value.flatMap((block) => block.parts.flatMap((part) => {
            const figs = [part.total, ...part.lines].filter((fig): fig is EconFig => Boolean(fig))
            return figs.map((fig) => [block.title, fig.label, fig.value == null ? '—' : String(fig.value), fig.included ? 'да' : 'нет', fig.tex, fig.subst, fig.note])
          })),
        ],
      },
      {
        name: 'Подстановка',
        rows: [
          ['Блок', 'Статья', 'Символ', 'Величина', 'Значение', 'Единица', 'Источник', 'Пояснение'],
          ...formulas.value.flatMap((block) => block.parts.flatMap((part) => {
            const figs = [part.total, ...part.lines].filter((fig): fig is EconFig => Boolean(fig))
            return figs.flatMap((fig) => fig.vars.map((item) => [block.title, fig.label, item.symbol, item.label, item.value == null ? '—' : String(item.value), item.unit, item.source_label, item.note]))
          })),
        ],
      },
      {
        name: 'Допущения',
        rows: [
          ['Группа', 'Параметр', 'Символ', 'Значение', 'Единица', 'Стандарт', 'Источник', 'Обоснование', 'Происхождение'],
          ...paramGroups.value.flatMap((group) => group.items.map((item) => [group.label, item.label, item.symbol, String(item.value), item.unit, String(item.standard), item.source, item.rationale, item.origin])),
        ],
      },
      {
        name: 'Процессы',
        rows: [
          ['Процесс', 'Робот', 'В расчёте', 'Доля ФОТ', 'CAPEX покупки', 'Эффект', 'Окупаемость', 'TCO покупки', 'TCO аренды', 'Вывод'],
          ...processes.value.map((item) => [item.name, item.robot, item.included ? 'да' : 'нет', item.share, item.capex, item.effect, item.payback, item.tcoPurchase, item.tcoRaas, item.reason]),
        ],
      },
      {
        name: 'Чувствительность',
        rows: sensitivityRows(economy.report.value?.sensitivity ?? []),
      },
      {
        name: 'Роботы',
        rows: [
          ['Процесс', 'Робот', 'Количество', 'Цена', 'Стоимость парка', 'ТТХ'],
          ...robots.value.map((item) => [item.process, item.name, item.count, item.price, item.cost, item.specs.map((spec) => `${spec.label}: ${spec.value}`).join('; ') || '—']),
        ],
      },
    ]
  })

  const stem = computed(() => fileStem(project.value?.name ?? 'otchet'))

  const load = async () => {
    if (import.meta.server || !project.value) return
    const mine = ++token
    loading.value = true
    failure.value = ''
    try {
      const code = live.objectCode.value
      if (code) {
        try {
          const form = await platformGet<{ fields: { key: string; label: string; unit: string }[] }>(`/catalog/objects/${code}/fields`)
          if (mine === token) {
            fieldLabels.value = Object.fromEntries(form.fields.map((item) => [item.key, { label: item.label, unit: item.unit }]))
          }
        } catch {
          fieldLabels.value = {}
        }
      }
      if (closed.value) return
      if (!hasParams.value) return
      const currentSite = site.value
      const match = isDemo.value
        ? await platformSend<{ groups: ReportGroup[] }>('/catalog/preview/match', 'POST', { object_code: code, site: currentSite })
        : await platformSend<{ groups: ReportGroup[] }>(`/projects/${id.value}/match`, 'POST', { site: currentSite })
      if (mine !== token) return
      groups.value = match.groups
      if (!isDemo.value) {
        try {
          const stored = await platformGet<{ layout: Partial<Layout> }>(`/projects/${id.value}/layout`)
          if (mine === token) {
            layout.value = stored.layout?.floors?.length ? normalizeLayout(stored.layout as Partial<Layout> & Record<string, unknown>) : null
          }
        } catch {
          if (mine === token) layout.value = null
        }
      }
      await economy.load()
    } catch (err: unknown) {
      if (mine === token) failure.value = fetchErrorMessage(err, 'Не удалось собрать отчёт')
    } finally {
      if (mine === token) loading.value = false
    }
  }

  watch([() => project.value?.id, () => JSON.stringify(site.value), () => JSON.stringify(compare.choices.value), () => live.pending.value], () => {
    if (live.pending.value) return
    void load()
  }, { immediate: true })

  return {
    project,
    role,
    isDemo,
    closed,
    pending: computed(() => live.pending.value || loading.value),
    error: computed(() => (isDemo.value ? null : live.error.value)),
    failure: computed(() => failure.value || economy.failure.value),
    ready,
    missing,
    disclaimer,
    today,
    advice,
    scenarios,
    chart,
    payroll,
    robots,
    formulas,
    processes,
    paramGroups,
    econ: economy.report,
    params,
    limits,
    site,
    sceneProcesses,
    savedLayout: layout,
    sheets,
    stem,
    load,
  }
}
