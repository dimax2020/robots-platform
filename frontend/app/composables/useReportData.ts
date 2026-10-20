import type { Ref } from 'vue'
import { siteFieldMeta } from '~/data/siteFields'
import { isFullPath, objectTypeLabel } from '~/data/projects'
import { fileStem, type TableSheet } from '~/utils/exportTables'
import { usePlatformCompare } from '~/composables/usePlatformCompare'
import { platformGet } from '~/composables/usePlatform'
import { photoFor } from '~/data/placeholders'
import type { Layout } from '~/sim/types'
import {
  conditionText,
  millions,
  PRELIMINARY,
  rentPaybackText,
  signedMillions,
  usePlatformEconomy,
  withPlan,
  yearsText,
  type EconFig,
  type EconProcess,
  type EconScenario,
} from '~/composables/usePlatformEconomy'

/**
 * Данные итогового отчёта: тот же расчёт, что на шагах подбора и экономики, с правками платформы.
 * Синтетические данные демо в отчёт не попадают — ни значения, ни пометки о них.
 */
export const REPORT_NOTE = `${PRELIMINARY} Расчёт в постоянных ценах, без НДС, после налога на прибыль.`

const fmt = (value: number | null | undefined, digits = 1) => value == null ? '—' : value.toLocaleString('ru-RU', { maximumFractionDigits: digits })
const plural = (n: number, one: string, few: string, many: string) => {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few
  return many
}
/* Причины от подбора про демонстрационные и синтетические данные — не для отчёта руководителю. */
const isSynthetic = (item: { code?: string; message?: string }) => /demo|synthetic/i.test(item.code ?? '') || /синтет|демонстрац/i.test(item.message ?? '')

export function useReportData(id: Ref<string>) {
  const economy = usePlatformEconomy(id)
  const compare = usePlatformCompare(id)
  const report = economy.report
  const project = economy.project

  /* Как на странице проекта: правки платформы ещё не внесены — показываем итог с ними, как на шаге «Экономика». */
  let planned = false
  watch(report, (value) => {
    if (!value || planned || value.saved_overrides.auto || !value.plan?.changes.length) return
    planned = true
    void economy.load(withPlan(value.saved_overrides, value.plan.changes))
  })
  watch(economy.source, (value) => { if (value && !planned) void economy.load() }, { immediate: true })

  /* План объекта для схемы в отчёте (ТЗ 3.7.4). */
  const layout = ref<Layout | null>(null)
  watch(() => economy.live.record.value?.id, async (key) => {
    if (!key) return
    try {
      layout.value = ((await platformGet<{ layout: Layout | null }>(`/projects/${key}/layout`)).layout) ?? null
    } catch {
      layout.value = null
    }
  }, { immediate: true })
  const PALETTE = ['#0d8455', '#c4512b', '#c23a8a', '#8a6d1a', '#1f6fb5', '#6b4fc7', '#0f8c96', '#b8860b']
  const colors = computed(() => Object.fromEntries(economy.groups.value.map((group, index) => [group.process_code, PALETTE[index % PALETTE.length]!])))
  const names = computed(() => Object.fromEntries(economy.groups.value.map((group) => [group.process_code, group.process_name])))
  const floors = computed(() => (layout.value?.floors ?? []).filter((floor) => floor.stations.length || floor.zones.length || floor.blocks.length))

  const closed = computed(() => Boolean(project.value && !isFullPath(project.value)))
  const ready = computed(() => Boolean(report.value && !closed.value))
  const today = new Date().toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
  const stem = computed(() => fileStem(project.value?.name ?? 'otchet'))

  const scenario = (key: EconScenario['key']) => report.value?.scenarios.find((item) => item.key === key) ?? null
  const buy = computed(() => scenario('purchase'))
  const rent = computed(() => scenario('raas'))
  const asis = computed(() => scenario('asis'))
  const horizon = computed(() => report.value?.horizon_years ?? 5)
  const netOf = (item: EconScenario | null) => item?.cashflow?.at(-1)?.cumulative ?? null

  const processes = computed(() => (report.value?.processes ?? []).filter((item) => item.included))
  const inTotal = computed(() => processes.value.filter((item) => !item.off))
  const outOfTotal = computed(() => processes.value.filter((item) => item.off))
  const noData = computed(() => processes.value.filter((item) => item.story?.needs_staff))

  /* Вывод одной строкой и почему. */
  const verdict = computed(() => {
    const b = buy.value
    if (!b || !inTotal.value.length) return { tone: 'bad' as const, title: 'Нет процессов, которые окупаются', why: 'Ни один процесс не даёт экономии при текущих данных.' }
    const payback = b.payback.value
    const npv = b.npv?.value ?? null
    if (payback != null && payback <= horizon.value && (npv ?? 0) >= 0) {
      return { tone: 'ok' as const, title: `Роботизация окупится за ${yearsText(payback)}`, why: `Вложив ${millions(b.capex.value)} один раз, объект будет тратить на ${millions(b.effect.value)} в год меньше. Итог за ${horizon.value} лет — ${signedMillions(netOf(b))}.` }
    }
    if (payback != null) return { tone: 'warn' as const, title: `Окупится только за ${yearsText(payback)}`, why: 'С учётом стоимости денег вложения возвращаются слишком поздно.' }
    return { tone: 'bad' as const, title: `Роботизация не окупится за ${yearsText(horizon.value)}`, why: 'Роботы и их обслуживание обходятся дороже, чем люди, которых они заменяют.' }
  })

  const kpis = computed(() => {
    const b = buy.value
    if (!b) return []
    return [
      { label: 'Вложения', value: millions(b.capex.value), note: 'один раз, без НДС' },
      { label: 'Экономия в год', value: millions(b.effect.value), note: 'люди минус расходы на роботов' },
      { label: 'Окупаемость', value: b.payback.value != null ? yearsText(b.payback.value) : 'нет', note: `горизонт ${horizon.value} лет` },
      { label: `Итог за ${horizon.value} лет`, value: signedMillions(netOf(b)), note: `NPV ${signedMillions(b.npv?.value ?? null)}` },
    ]
  })

  const purchaseOf = (item: EconProcess) => item.scenarios.find((row) => row.key === 'purchase') ?? null
  /* Что роботизировать: процессы в итоге с роботом, вложениями, экономией и окупаемостью. */
  const plan = computed(() => inTotal.value.map((item) => ({
    code: item.process_code,
    name: item.process_name,
    robot: `${item.robot_name}${item.count ? ` × ${fmt(item.count, 0)}` : ''}`,
    capex: millions(item.story?.capex ?? purchaseOf(item)?.capex.value),
    saving: millions(item.story?.saving_year),
    payback: item.story?.payback != null ? yearsText(item.story.payback) : 'не окупается',
  })))

  const rentLine = computed(() => {
    const b = buy.value?.npv?.value ?? null
    const r = rent.value?.npv?.value ?? null
    if (b == null || r == null) return ''
    const better = r > b ? 'Аренда' : 'Покупка'
    const sw = report.value?.switch?.value
    const when = sw != null ? ` Если роботы нужны дольше ${fmt(sw / 12, 1)} ${plural(Math.round(sw / 12), 'года', 'лет', 'лет')}, выгоднее купить.` : ''
    return `${better} выгоднее: NPV покупки ${signedMillions(b)}, аренды ${signedMillions(r)}.${when}`
  })

  const risk = computed(() => {
    const r = report.value
    if (!r) return null
    const worst = r.stress?.find((item) => item.key === 'all') ?? null
    const price = r.breakeven?.find((item) => item.key === 'price_factor') ?? null
    const rate = r.breakeven?.find((item) => item.key === 'market_rate_pct') ?? null
    return {
      chance: r.chance ? `${Math.round(r.chance.npv_positive * 100)}%` : '—',
      interval: r.interval?.npv_low != null ? `${signedMillions(r.interval.npv_low)} … ${signedMillions(r.interval.npv_high)}` : '—',
      worst: worst ? `${signedMillions(worst.npv)}${worst.payback != null ? `, окупится за ${yearsText(worst.payback)}` : ', не окупается'}` : '—',
      price: price?.value != null ? (price.value >= 100 ? `парк может подорожать на ${fmt(price.value - 100, 0)}%` : `нужна скидка ${fmt(100 - price.value, 0)}%`) : '—',
      rate: rate?.value != null ? `выдержит ключевую ставку до ${fmt(rate.value)}%` : '—',
    }
  })

  /* Итоговая таблица сценариев по единым показателям (ТЗ 3.5.5, 3.7.1; «Дополнения», п. 2.4). */
  const scenarioTable = computed(() => {
    const rows = [asis.value, buy.value, rent.value].filter(Boolean) as EconScenario[]
    const base = asis.value?.annual_cost ?? null
    const pct = (v: number | null | undefined) => v == null ? '—' : `${fmt(v, 0)}%`
    const delta = (v: number | null | undefined) => v == null || base == null ? '—' : signedMillions(v - base)
    return rows.map((item) => ({
      key: item.key,
      title: item.key === 'asis' ? 'Без роботизации' : item.key === 'purchase' ? 'Покупка' : 'Аренда (RaaS)',
      capex: item.key === 'asis' ? '—' : millions(item.capex.value),
      cost: millions(item.annual_cost),
      change: item.key === 'asis' ? 'база' : delta(item.annual_cost),
      effect: item.key === 'asis' ? 'база' : millions(item.effect.value),
      payback: item.key === 'asis' ? '—' : item.key === 'raas' ? rentPaybackText(item) : item.payback.value != null ? yearsText(item.payback.value) : 'нет',
      roi: item.key === 'asis' ? '—' : item.key === 'raas' ? pct(item.implementation_roi) : pct(item.roi.value),
      tco: millions(item.tco.value),
      npv: item.key === 'asis' ? '0' : signedMillions(item.npv?.value ?? null),
      best: item.key !== 'asis' && (item.npv?.value ?? -Infinity) === Math.max(buy.value?.npv?.value ?? -Infinity, rent.value?.npv?.value ?? -Infinity),
    }))
  })
  const tzVerdict = computed(() => buy.value?.verdict ?? '')

  /* Чувствительность: покупка и аренда на тех же границах главных параметров (ТЗ 3.5.6 — для каждого сценария, не меньше трёх). */
  const sensitivityBoth = computed(() => (report.value?.sensitivity ?? []).filter((item) => item.npv_low != null && item.npv_high != null).slice(0, 5).map((item) => ({
    label: item.label,
    range: `${fmt(item.low_value, 2)} … ${fmt(item.high_value, 2)} ${item.unit}`,
    buy: `${signedMillions(Math.min(item.npv_low!, item.npv_high!))} … ${signedMillions(Math.max(item.npv_low!, item.npv_high!))}`,
    rent: item.rent_npv_low != null && item.rent_npv_high != null ? `${signedMillions(Math.min(item.rent_npv_low, item.rent_npv_high))} … ${signedMillions(Math.max(item.rent_npv_low, item.rent_npv_high))}` : '—',
  })))

  /* CAPEX и OPEX по статьям для покупки и аренды (ТЗ 3.5.2). */
  const lines = (figs: EconFig[] | undefined) => (figs ?? []).map((fig) => ({ label: fig.label, value: fig.included ? millions(fig.value) : 'не входит' }))
  const statement = computed(() => ({
    buyCapex: lines(buy.value?.capex_lines), buyOpex: lines(buy.value?.opex_lines),
    rentCapex: lines(rent.value?.capex_lines), rentOpex: lines(rent.value?.opex_lines),
    buyCapexTotal: millions(buy.value?.capex.value), buyOpexTotal: millions(buy.value?.opex.value),
    rentCapexTotal: millions(rent.value?.capex.value), rentOpexTotal: millions(rent.value?.opex.value),
    payroll: millions(report.value?.payroll?.value), payrollAfter: millions(buy.value?.payroll_after.value),
  }))

  /* Формулы с подстановкой (ТЗ 3.5.8): итоговые величины покупки и статьи. */
  const formulas = computed(() => {
    const b = buy.value
    if (!b) return []
    const main = [b.capex, b.opex, b.effect, b.payback, b.roi, b.tco, b.npv, b.irr, b.dpp, b.pi, b.eac, report.value?.discount].filter((fig): fig is EconFig => Boolean(fig && fig.tex))
    return [
      { title: 'Итоговые показатели покупки', figs: main },
      { title: 'Статьи CAPEX', figs: b.capex_lines.filter((fig) => fig.tex) },
      { title: 'Статьи OPEX', figs: b.opex_lines.filter((fig) => fig.tex) },
      { title: 'Аренда', figs: [rent.value?.capex, rent.value?.opex, rent.value?.opex_lines.find((fig) => fig.key === 'raas_payment'), rent.value?.npv].filter((fig): fig is EconFig => Boolean(fig && fig.tex)) },
    ].filter((group) => group.figs.length)
  })

  /* Состав парка (ТЗ 3.7.2): фото, количество, цена, ТТХ и причины подбора (ТЗ 3.4.2). */
  const fleetCards = computed(() => (report.value?.fleet ?? []).map((row) => {
    const group = economy.groups.value.find((item) => item.process_code === row.process_code)
    const hit = group?.hits.find((item) => item.product_id === row.product_id)
    const view = processes.value.find((item) => item.process_code === row.process_code)
    return {
      key: `${row.process_code}:${row.product_id}`,
      process: row.process_name,
      name: row.name,
      image: photoFor(row.image_url, row.name, row.process_code),
      count: row.count_used != null ? `${fmt(row.count_used, 0)} шт.${row.count_source === 'default' ? ' (количество не посчитано)' : row.count_source === 'project' ? ' (задано в проекте)' : ''}` : '—',
      price: row.price_rub != null ? `${fmt(row.price_rub / 1e6, 2)} млн ₽ за шт.` : 'нет цены',
      cost: row.cost_rub != null ? millions(row.cost_rub) : '—',
      inTotal: row.included && !view?.off,
      specs: (hit?.specs ?? []).filter((spec) => spec.key !== 'price_rub' && !/цена/i.test(spec.label)).slice(0, 6).map((spec) => `${spec.label}: ${fmt(spec.value, 2)}${spec.unit ? ` ${spec.unit}` : ''}`),
      notes: (hit?.notes ?? []).filter((note) => !isSynthetic({ message: note })).slice(0, 3),
      fig: row.fig,
    }
  }))

  /* Источники данных (ТЗ 3.7.2). */
  const sources = computed(() => {
    const origins = new Set<string>()
    for (const item of report.value?.params ?? []) if (item.origin && item.origin !== 'demo_synthetic') origins.add(item.origin)
    return [
      'Параметры объекта и численность на процессах — данные заказчика (шаг «Параметры» и экономика по процессам).',
      'Роботы, цены и характеристики — каталог роботизированных решений платформы (карточки производителей).',
      'Количество роботов — формулы процессов по параметрам площадки и характеристикам робота.',
      ...[...origins].sort().map((origin) => `Нормативы: ${origin}.`),
    ]
  })

  /* Объект и параметры. */
  const site = computed(() => economy.live.site.value)
  const siteRows = computed(() => siteFieldMeta.flatMap((meta) => {
    const raw = site.value[meta.key]
    if (raw == null || raw === '' || typeof raw === 'object') return []
    const value = typeof raw === 'number' ? raw.toLocaleString('ru-RU') : typeof raw === 'boolean' ? (raw ? 'да' : 'нет') : String(raw)
    return [{ label: meta.plain ?? meta.label, value: `${value}${meta.unit ? ` ${meta.unit}` : ''}` }]
  }))
  const processList = computed(() => economy.live.record.value?.processes ?? [])

  /* Подбор: что выбрано на каждом процессе. */
  const selection = computed(() => economy.groups.value.map((group) => {
    const hit = compare.remainingHit(group)
    const pass = group.hits.filter((row) => row.verdict === 'pass').length
    return {
      name: group.process_name,
      robot: hit ? hit.name : '—',
      count: hit?.count != null ? fmt(hit.count, 0) : '—',
      how: hit ? (group.best_product_id && hit.product_id !== group.best_product_id ? 'свой выбор' : 'рекомендован платформой') : 'робот не выбран',
      reason: hit ? '' : compare.skipReason(group),
      candidates: `${pass} из ${group.hits.length}`,
    }
  }))

  /* Причины, почему у процессов нет робота, — по одному разу под таблицей. */
  const selectionReasons = computed(() => [...new Set(selection.value.map((row) => row.reason).filter(Boolean))])

  /* Экономика каждого процесса — карточкой. */
  const fteHours = computed(() => report.value?.params.find((item) => item.key === 'fte_hours')?.value ?? 1810)
  const STATUS: Record<string, string> = { ok: 'Выгоден', conditional: 'Окупится с условием', bad: 'Невыгоден', no_staff: 'Нет данных о людях', none: '—' }
  const processCards = computed(() => processes.value.map((item) => {
    const s = item.story
    const w = s?.work
    const unit = w?.unit[2] ?? ''
    const rows: [string, string][] = []
    if (s && !s.needs_staff) {
      rows.push(['Сейчас вручную', s.by_cost ? `${millions((s.cost_month ?? 0) * 12)} в год — затраты суммой` : `${fmt(s.staff, 0)} чел. × ${fmt(s.wage_month, 0)} ₽ = ${millions(s.payroll_now)} в год`])
      if (s.other_month) rows.push(['Техника и прочее', `${fmt(s.other_month, 0)} ₽ в месяц`])
    }
    if (w?.volume_year) rows.push(['Объём работы', `${fmt(w.per_day, 0)} ${unit} в сутки · ${fmt(w.volume_year / 1000, 0)} тыс. в год`])
    if (w?.robot_year && w.person_rate) rows.push(['Человек / робот за год', `${fmt(w.person_rate * fteHours.value / 1000, 1)} / ${fmt(w.robot_year / 1000, 1)} тыс. ${unit} · робот ≈ ${fmt(w.replaces)} чел.`])
    if (w?.coverage != null) rows.push(['Роботы закрывают', `${fmt(w.coverage * 100, 0)}% операций`])
    if (s) {
      rows.push(['Роботы', `${item.robot_name} × ${fmt(s.robots, 0)}, вложения ${millions(s.capex)}`])
      if (!s.needs_staff) rows.push([s.by_cost ? 'Уходит затрат' : 'Уходят людей', s.by_cost ? `${fmt(s.released * 100, 0)}%` : `${fmt(s.released)} чел.`])
      rows.push(['Затраты в год', `${millions(s.cost_before)} → ${millions(s.cost_after)}`])
      rows.push(['Экономия в год', millions(s.saving_year)])
      rows.push(['Окупаемость · NPV', `${s.payback != null ? yearsText(s.payback) : 'не окупается'} · ${signedMillions(s.npv)}`])
      if (s.unit) rows.push([s.unit.label === 'операция' ? 'Цена одной операции' : `Цена за ${s.unit.label === 'паллета' ? 'паллету' : s.unit.label === 'строка заказа' ? 'строку заказа' : s.unit.label}`, `${fmt(s.unit.before)} ₽ → ${fmt(s.unit.after)} ₽`])
    }
    return {
      code: item.process_code,
      name: item.process_name,
      status: item.off ? 'Не в итоге' : STATUS[item.status ?? 'none'] ?? '—',
      tone: item.off ? 'off' : item.status === 'ok' ? 'ok' : item.status === 'conditional' ? 'warn' : 'bad',
      note: item.off ? item.reason : item.condition ? `Окупится ${conditionText(item.condition)}.` : '',
      rows,
    }
  }))

  /* Правки платформы: что она поменяла сама. */
  const overrides = computed(() => report.value?.effective_overrides ?? report.value?.saved_overrides ?? {})
  const fixes = computed(() => Object.keys(overrides.value).flatMap((key) => {
    const name = (code: string) => processes.value.find((item) => item.process_code === code)?.process_name ?? code
    if (key.startsWith('auto:count:')) {
      const code = key.slice('auto:count:'.length)
      return [`${name(code)}: роботов ${overrides.value[key]} → ${overrides.value[`count:${code}`] ?? '—'} — больше людей, чем есть на процессе, лишние роботы не заменят`]
    }
    if (key.startsWith('auto:off:')) {
      const code = key.slice('auto:off:'.length)
      const item = processes.value.find((row) => row.process_code === code)
      return [`${name(code)}: убран из итога — ${item?.story?.needs_staff ? 'нет данных о людях на процессе' : 'невыгоден или те же люди уже уходят с другого процесса'}`]
    }
    return []
  }))

  /* Деньги по годам — таблица. */
  const cashTable = computed(() => {
    const b = buy.value
    if (!b?.cashflow?.length) return null
    const rows = b.cashflow
    const head = ['млн ₽', 'Старт', ...rows.map((row) => `${row.year} год`)]
    /* Ноль со знаком «−0» тоже ноль: иначе пустая статья попадает в таблицу. */
    const mln = (value: number) => Math.abs(value) < 50_000 ? '0' : fmt(value / 1e6)
    const line = (label: string, start: number, pick: (row: (typeof rows)[number]) => number) => [label, mln(start), ...rows.map((row) => mln(pick(row)))]
    return {
      head,
      body: [
        line('Вложения', -(b.capex.value ?? 0), () => 0),
        line('Экономия на людях', 0, (row) => row.saving_rub),
        line('Расходы на роботов', 0, (row) => row.opex_rub),
        line('Выплаты при сокращении', 0, (row) => row.payouts_rub),
        line('Налог на прибыль', 0, (row) => row.tax_rub),
        line('Повторная закупка', 0, (row) => row.reinvest_rub ?? 0),
        line('Остаточная стоимость', 0, (row) => row.residual_rub),
        line('Поток года', -(b.capex.value ?? 0), (row) => row.cf_rub),
        line('Накоплено', -(b.capex.value ?? 0), (row) => row.cumulative),
      ].filter((row) => row.slice(1).some((cell) => cell !== '0')),
    }
  })

  /* Показатели для экономиста. */
  const metrics = computed(() => {
    const b = buy.value
    const r = report.value
    if (!b || !r) return []
    const pct = (v: number | null | undefined) => v == null ? '—' : `${fmt(v)}%`
    return [
      ['NPV', signedMillions(b.npv?.value ?? null), 'Сколько проект приносит сверх вложений с учётом стоимости денег'],
      ['IRR', pct(b.irr?.value), `Доходность вложений; ставка дисконтирования ${pct(r.discount?.value)}`],
      ['PI', fmt(b.pi?.value, 2), 'Приведённый рубль на рубль вложений'],
      ['Окупаемость простая / дисконтированная', `${b.payback.value != null ? yearsText(b.payback.value) : '—'} / ${b.dpp?.value != null ? yearsText(b.dpp.value) : '—'}`, 'Без остаточной стоимости техники'],
      ['Чистый ROI', pct(b.roi.value), `За ${horizon.value} лет после возврата вложений`],
      ['EAC покупки / вручную', `${millions(b.eac?.value)} / ${millions(asis.value?.eac?.value)}`, 'Годовая стоимость операций после налога с учётом вложений'],
      ['TCO покупки / вручную', `${millions(b.tco.value)} / ${millions(asis.value?.tco.value)}`, `Сумма затрат за ${horizon.value} лет без налогов и дисконта`],
      ['Ставка дисконтирования', pct(r.discount?.value), 'Ключевая ставка ЦБ за вычетом цели по инфляции'],
    ] as [string, string, string][]
  })

  const stress = computed(() => (report.value?.stress ?? []).map((item) => [item.label, signedMillions(item.npv), item.payback != null ? yearsText(item.payback) : 'не окупается', item.note] as [string, string, string, string]))
  const breakeven = computed(() => (report.value?.breakeven ?? []).map((item) => [
    item.label,
    `${fmt(item.current)} ${item.unit}`,
    item.value != null ? `${fmt(item.value)} ${item.unit}` : item.reachable ? 'окупается во всём диапазоне' : 'не окупается',
    item.margin_pct != null ? `${fmt(Math.abs(item.margin_pct), 0)}%` : '—',
  ] as [string, string, string, string]))
  const tornado = computed(() => (report.value?.sensitivity ?? []).filter((item) => (item.share ?? 0) >= 0.005 && item.npv_low != null && item.npv_high != null).slice(0, 10).map((item) => [
    item.label,
    `${fmt(item.low_value, 2)} … ${fmt(item.high_value, 2)} ${item.unit}`,
    `${signedMillions(Math.min(item.npv_low!, item.npv_high!))} … ${signedMillions(Math.max(item.npv_low!, item.npv_high!))}`,
    `${Math.round((item.share ?? 0) * 100)}%`,
  ] as [string, string, string, string]))

  /* Допущения: что изменено в проекте и главные нормативы. */
  const SOURCE: Record<string, string> = { norm: 'стандарт платформы', project: 'значение проекта', site: 'данные площадки' }
  /* Допущения, которые задал объект (в демо — заготовленные для него), — «условия объекта», а не правки пользователя. */
  const ownBy = (item: { source: string; origin: string }) => item.source === 'project' && item.origin === 'demo_synthetic' ? 'условия объекта' : SOURCE[item.source] ?? item.source
  const assumptions = computed(() => (report.value?.params ?? []).filter((item) => item.group !== 'subsidy' || item.source === 'project').map((item) => [
    item.label,
    `${fmt(item.value, 2)} ${item.unit}`,
    ownBy(item),
    item.source === 'project' && item.value !== item.standard ? `стандарт ${fmt(item.standard, 2)}` : '',
  ] as [string, string, string, string]))
  const changed = computed(() => (report.value?.params ?? []).filter((item) => item.source === 'project' && item.origin !== 'demo_synthetic'))
  const subsidies = computed(() => (report.value?.subsidies ?? []).filter((item) => item.enabled).map((item) => item.label))

  const limits = computed(() => (report.value?.blockers ?? []).filter((item) => !isSynthetic(item)).map((item) => {
    const name = processes.value.find((row) => row.process_code === item.process_code)?.process_name
    return `${name ? `${name}: ` : ''}${item.message}`
  }))

  const objectLine = computed(() => project.value ? `${objectTypeLabel[project.value.objectType]}${project.value.industry ? ` · ${project.value.industry}` : ''}` : '')

  /* Excel для экономиста: те же разделы таблицами. */
  const sheets = computed<TableSheet[]>(() => {
    if (!report.value) return []
    const out: TableSheet[] = [
      { name: 'Итог', rows: [['Проект', project.value?.name ?? ''], ['Объект', objectLine.value], ['Дата', today], ['Вывод', verdict.value.title], ['Почему', verdict.value.why], ...kpis.value.map((k) => [k.label, `${k.value} (${k.note})`]), ['Купить или арендовать', rentLine.value]] },
      { name: 'Сценарии', headed: true, rows: [['Сценарий', 'CAPEX', 'Затраты в год', 'Изменение к базе', 'Годовой эффект', 'Окупаемость', 'ROI', `TCO за ${horizon.value} лет`, 'NPV'], ...scenarioTable.value.map((row) => [row.title, row.capex, row.cost, row.change, row.effect, row.payback, row.roi, row.tco, row.npv])] },
      { name: 'CAPEX и OPEX', headed: true, rows: [['Статья', 'Покупка', 'Аренда'],
        ['CAPEX', statement.value.buyCapexTotal, statement.value.rentCapexTotal],
        ...[...new Set([...statement.value.buyCapex, ...statement.value.rentCapex].map((line) => line.label))].map((label) => [`  ${label}`, statement.value.buyCapex.find((line) => line.label === label)?.value ?? '—', statement.value.rentCapex.find((line) => line.label === label)?.value ?? '—']),
        ['OPEX в год', statement.value.buyOpexTotal, statement.value.rentOpexTotal],
        ...[...new Set([...statement.value.buyOpex, ...statement.value.rentOpex].map((line) => line.label))].map((label) => [`  ${label}`, statement.value.buyOpex.find((line) => line.label === label)?.value ?? '—', statement.value.rentOpex.find((line) => line.label === label)?.value ?? '—'])] },
      { name: 'Состав парка', headed: true, rows: [['Процесс', 'Робот', 'Количество', 'Цена', 'Стоимость', 'В итоге'], ...fleetCards.value.map((row) => [row.process, row.name, row.count, row.price, row.cost, row.inTotal ? 'да' : 'нет'])] },
      { name: 'Чувствительность сценариев', headed: true, rows: [['Параметр', 'Диапазон', 'NPV покупки', 'NPV аренды'], ...sensitivityBoth.value.map((row) => [row.label, row.range, row.buy, row.rent])] },
      { name: 'Источники', rows: sources.value.map((row, index) => [String(index + 1), row]) },
      { name: 'Что роботизировать', headed: true, rows: [['Процесс', 'Робот', 'Вложения', 'Экономия в год', 'Окупаемость'], ...plan.value.map((row) => [row.name, row.robot, row.capex, row.saving, row.payback])] },
      { name: 'Процессы', headed: true, rows: [['Процесс', 'Статус', 'Показатель', 'Значение'], ...processCards.value.flatMap((card) => card.rows.map(([label, value], index) => [index ? '' : card.name, index ? '' : card.status, label, value]))] },
      { name: 'Подбор', headed: true, rows: [['Процесс', 'Робот', 'Количество', 'Выбор', 'Подходят'], ...selection.value.map((row) => [row.name, row.robot, row.count, row.how, row.candidates])] },
    ]
    if (cashTable.value) out.push({ name: 'Деньги по годам', headed: true, rows: [cashTable.value.head, ...cashTable.value.body] })
    out.push({ name: 'Показатели', headed: true, rows: [['Показатель', 'Значение', 'Что значит'], ...metrics.value] })
    out.push({ name: 'Если пойдёт хуже', headed: true, rows: [['Сценарий', 'NPV', 'Окупаемость', 'Условие'], ...stress.value] })
    out.push({ name: 'Запас прочности', headed: true, rows: [['Параметр', 'Сейчас', 'Безубыточность', 'Запас'], ...breakeven.value] })
    out.push({ name: 'Чувствительность', headed: true, rows: [['Параметр', 'Диапазон', 'NPV', 'Доля разброса'], ...tornado.value] })
    out.push({ name: 'Допущения', headed: true, rows: [['Параметр', 'Значение', 'Источник', 'Примечание'], ...assumptions.value] })
    out.push({ name: 'Объект', rows: siteRows.value.map((row) => [row.label, row.value]) })
    return out
  })

  return {
    project, report, ready, closed, today, stem, loading: economy.loading, failure: economy.failure, pending: economy.pending,
    buy, rent, horizon, verdict, kpis, plan, inTotal, outOfTotal, noData, rentLine, risk,
    siteRows, processList, selection, selectionReasons, processCards, scenarioTable, tzVerdict, sensitivityBoth, statement, formulas, fleetCards, sources,
    layout, floors, colors, names, fixes, cashTable, metrics, stress, breakeven, tornado,
    assumptions, changed, subsidies, limits, objectLine, sheets,
  }
}
