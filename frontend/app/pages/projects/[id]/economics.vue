<script setup lang="ts">
import { skippedAlerts } from '~/composables/usePlatformCompare'
import { PhArrowRight, PhCaretDown, PhProhibit, PhStorefront, PhUser } from '@phosphor-icons/vue'
import {
  millions,
  monthsText,
  PARAM_GROUPS,
  PRELIMINARY,
  rubles,
  signedMillions,
  SOURCE_TONE,
  subsidyKey,
  usePlatformEconomy,
  yearsText,
  conditionText,
  type EconFix,
  type EconFleet,
  type EconPlanChange,
  withPlan,
  type EconProcess,
  type EconScenario,
  type EconSuggestion,
} from '~/composables/usePlatformEconomy'
import { replaceQuery } from '~/composables/useQuerySync'
import { useStepPass } from '~/composables/useStepPass'
import { fetchErrorMessage } from '~/utils/errors'
import { isAccent } from '~/utils/accent'

const route = useRoute()
const id = computed(() => route.params.id as string)
/* Данные карточки робота правит только администратор каталога; пользователь видит лишь, что их нет. */
const { role } = useRole()
const { project, isDemo, readonly, report, loading, failure, pending, error, source, choices, skipped, load, saveOverrides, restoreProcess, setStaff, inactive } = usePlatformEconomy(id)
useHead({ title: () => `Экономика · ${project.value?.name ?? 'проект'}` })

/* В демо только просмотр: правки живут в предпросмотре и в проект не пишутся. */
const preview = ref<Record<string, number> | null>(null)
onMounted(() => { void load(preview.value) })
watch([() => JSON.stringify(source.value ?? null), () => JSON.stringify(choices.value)], () => { void load(preview.value) })

/* Сверху общая картина, ниже — вкладки, каждая отвечает на один вопрос пользователя. */
const TABS = [
  { id: 'processes', label: 'Что роботизировать', lead: 'Каждый процесс — как будто роботизируют только его. Нажмите на строку, чтобы открыть его страницу; переключатель убирает процесс из итога.' },
  { id: 'people', label: 'Откуда экономия', lead: 'Люди, чью работу забирают роботы, минус расходы на сами роботы. Сокращение по ТК РФ: 2 месяца уведомления и до 2 зарплат выплат.' },
  { id: 'money', label: 'Когда окупится', lead: 'Деньги по годам после налога на прибыль. В первом году — уведомление о сокращении и выплаты.' },
  { id: 'rent', label: 'Купить или арендовать', lead: 'Аренда почти не требует вложений, но платёж каждый месяц.' },
  { id: 'support', label: 'Господдержка', lead: 'Включите меру — общая картина пересчитается.' },
  { id: 'risk', label: 'Надёжность', lead: 'Разброс результата, неудачные сценарии, запас прочности и что уточнить.' },
] as const
type TabId = typeof TABS[number]['id']
const tab = ref<TabId>(TABS.some((item) => item.id === route.query.tab) ? route.query.tab as TabId : 'processes')
watch(tab, (current) => replaceQuery({ tab: current === 'processes' ? undefined : current }))
const activeTab = computed(() => TABS.find((item) => item.id === tab.value)!)
const tabsRef = ref<HTMLElement | null>(null)
const goto = (next: string) => {
  /* «Заполнить людей» ведёт на первый процесс без данных: там вопрос и задаётся. */
  if (next === 'processes') {
    const empty = processList.value.find((item) => !item.off && item.story?.needs_staff)
    if (empty) return navigateTo(stageTo(empty.process_code))
  }
  tab.value = next as TabId
  nextTick(() => tabsRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
}

/* Как прошлые шаги: сначала каждый процесс отдельным подшагом, последним — общая картина. */
const processList = computed(() => (report.value?.processes ?? []).filter((item) => item.included))
const stageTo = (code: string) => `/projects/${id.value}/economics?process=${code}`
/* Первый проход — по процессам; пройденный шаг открывается сразу с общей картины. */
const pass = useStepPass(id, 'economics')
const view = computed(() => {
  const asked = typeof route.query.process === 'string' ? route.query.process : ''
  if (asked === 'total' || processList.value.some((item) => item.process_code === asked)) return asked
  if (route.query.tab || pass.done.value) return 'total'
  return processList.value[0]?.process_code ?? 'total'
})
watch([view, () => processList.value.length], ([current, count]) => { if (current === 'total' && count) pass.markDone() }, { immediate: true })
const viewProcess = computed(() => view.value === 'total' ? null : processList.value.find((item) => item.process_code === view.value) ?? null)
const substages = computed(() => [
  ...processList.value.map((item) => ({ id: item.process_code, label: item.process_name, to: stageTo(item.process_code), tone: toneOf(item) })),
  { id: 'total', label: 'Общая картина', to: stageTo('total') },
])
const stageIndex = computed(() => substages.value.findIndex((stage) => stage.id === view.value))
const nextStage = computed(() => substages.value[stageIndex.value + 1] ?? null)
const forwardLabel = computed(() => !nextStage.value ? 'К what-if' : nextStage.value.id === 'total' ? 'Общая картина' : 'Следующий процесс')
const goForward = () => navigateTo(nextStage.value ? nextStage.value.to : `/projects/${id.value}/what-if`)
/* Что сейчас выставлено на процессе — одной строкой в заголовке свёрнутой настройки. */
const tuneSummary = computed(() => {
  const item = viewProcess.value
  if (!item) return ''
  const row = fleetOf(item.process_code)
  const count = row?.count_used ?? 0
  const word = count % 10 === 1 && count % 100 !== 11 ? 'робот' : [2, 3, 4].includes(count % 10) && ![12, 13, 14].includes(count % 100) ? 'робота' : 'роботов'
  const parts = [
    `${count.toLocaleString('ru-RU')} ${word}${row?.count_source === 'project' ? ' — своё число' : ''}`,
    `цена ${knobValue(item.process_code, 'price_factor').toLocaleString('ru-RU')}% карточки`,
    `сервис ${knobValue(item.process_code, 'service_pct').toLocaleString('ru-RU')}% в год`,
  ]
  if (item.suggestions.length) parts.push(`${item.suggestions.length} ${item.suggestions.length === 1 ? 'способ' : item.suggestions.length < 5 ? 'способа' : 'способов'} сделать выгодным`)
  return parts.join(' · ')
})
const fteHours = computed(() => report.value?.params.find((item) => item.key === 'fte_hours')?.value)

const scenarioOf = (key: EconScenario['key']) => report.value?.scenarios.find((item) => item.key === key) ?? null
const buy = computed(() => scenarioOf('purchase'))
const rent = computed(() => scenarioOf('raas'))
const dispatchers = computed(() => buy.value?.opex_lines.find((line) => line.key === 'operators')?.count ?? null)

/* Любая правка значений проекта: в демо — предпросмотр без сохранения, в своём проекте — сохраняем и пересчитываем. */
const busy = ref('')
const editError = ref('')
const applyOverrides = async (change: (next: Record<string, number>) => void, key: string) => {
  if (!report.value) return
  const next = { ...(preview.value ?? report.value.saved_overrides) }
  change(next)
  busy.value = key
  editError.value = ''
  try {
    if (readonly.value) preview.value = next
    else await saveOverrides(next)
    await load(preview.value)
  } catch (err: unknown) {
    editError.value = fetchErrorMessage(err, 'Не удалось пересчитать')
  } finally {
    busy.value = ''
  }
}
const setOff = (codes: string[], off: boolean) => applyOverrides((next) => {
  for (const code of codes) {
    if (off) next[`off:${code}`] = 1
    else delete next[`off:${code}`]
    delete next[`auto:off:${code}`]
  }
}, `off:${codes.join(',')}`)
const toggleSubsidy = (code: string) => applyOverrides((next) => {
  const key = subsidyKey(code)
  if (next[key]) delete next[key]
  else next[key] = 1
}, `subsidy:${code}`)
const setSubsidies = (codes: string[]) => applyOverrides((next) => { for (const code of codes) next[subsidyKey(code)] = 1 }, `subsidy:${codes.join(',')}`)

/* Процесс: количество роботов, цена и сервис только для него. */
const overrides = computed<Record<string, number>>(() => preview.value ?? report.value?.saved_overrides ?? {})
const fleetOf = (code: string) => report.value?.fleet.find((row) => row.process_code === code) ?? null
const setCount = (row: EconFleet, value: number | null) => applyOverrides((next) => {
  const key = `count:${row.process_code}`
  if (value == null) delete next[key]
  else next[key] = Math.min(10_000, Math.max(1, Math.round(value)))
  delete next[`auto:count:${row.process_code}`]
}, `count:${row.process_code}`)
const typeCount = (row: EconFleet, event: Event) => {
  const value = Number((event.target as HTMLInputElement).value)
  if (Number.isFinite(value) && value >= 1 && value !== row.count_used) void setCount(row, value)
}
const KNOBS = [
  { key: 'price_factor', label: 'Цена робота', unit: '% от цены карточки', step: 5, min: 50, max: 150, hint: 'меньше 100 — скидка вендора' },
  { key: 'service_pct', label: 'Сервис после гарантии', unit: '% цены в год', step: 0.5, min: 0, max: 20, hint: 'по договору с вендором' },
] as const
const knobKey = (code: string, key: string) => `process:${code}:${key}`
const knobOwn = (code: string, key: string) => overrides.value[knobKey(code, key)] != null
const knobValue = (code: string, key: string) => overrides.value[knobKey(code, key)] ?? report.value?.params.find((item) => item.key === key)?.value ?? 0
const setKnob = (code: string, key: string, value: number | null) => applyOverrides((next) => {
  if (value == null) delete next[knobKey(code, key)]
  else next[knobKey(code, key)] = value
}, `knob:${code}:${key}`)
const typeKnob = (code: string, knob: typeof KNOBS[number], event: Event) => {
  const value = Number((event.target as HTMLInputElement).value)
  if (Number.isFinite(value)) void setKnob(code, knob.key, Math.min(knob.max, Math.max(knob.min, value)))
}
const SCOPE_LABEL: Record<EconSuggestion['scope'], string> = { process: 'только этот процесс', site: 'вся площадка', subsidy: 'господдержка', combo: 'скидка + господдержка' }
const suggestionChange = (item: EconSuggestion) => item.scope === 'subsidy'
  ? (item.key.includes(',') ? `включить ${item.key.split(',').length} меры` : 'включить меру')
  : item.scope === 'combo'
    ? `цена ${item.from.toLocaleString('ru-RU')} → ${item.to.toLocaleString('ru-RU')}% и ${(item.with_labels ?? []).join(', ')}`
    : `${item.from.toLocaleString('ru-RU')} → ${item.to.toLocaleString('ru-RU')} ${item.unit}`
const applySuggestion = (code: string, item: EconSuggestion) => {
  if (item.scope === 'subsidy') return setSubsidies(item.key.split(','))
  if (item.scope === 'combo') {
    return applyOverrides((next) => {
      next[knobKey(code, item.key)] = item.to
      for (const sub of item.with ?? []) next[subsidyKey(sub)] = 1
    }, `combo:${code}`)
  }
  if (item.scope === 'process') return setKnob(code, item.key, item.to)
  return navigateTo(`/projects/${id.value}/what-if?${new URLSearchParams({ process: code, tune: item.key, value: String(item.to), scope: item.scope })}`)
}

/* Выработка робота, указанная в проекте: когда в карточке её нет или вендор назвал свою. */
const setRate = (code: string, value: number | null) => applyOverrides((next) => {
  if (value == null) delete next[`rate:${code}`]
  else next[`rate:${code}`] = value
}, `rate:${code}`)

/* Люди на процессе: ввод прямо в строке процесса. */
const saveStaff = async (item: EconProcess, people: number | null, wage: number | null, cost: number | null = null, other: number | null = null) => {
  busy.value = `staff:${item.process_code}`
  editError.value = ''
  try {
    await setStaff(item.process_code, item.process_name, people, wage, cost, other)
  } catch (err: unknown) {
    editError.value = fetchErrorMessage(err, 'Не удалось сохранить людей на процессе')
  } finally {
    busy.value = ''
  }
}

/* Процессы: сначала выгодные, потом невыгодные, без людей и исключённые; внутри — по NPV. */
const npvOf = (item: EconProcess) => item.scenarios.find((row) => row.key === 'purchase')?.npv?.value ?? null
const ORDER = { ok: 0, cond: 1, bad: 2, warn: 3, off: 4 } as const
const toneOf = (item: EconProcess) => item.off ? 'off' : item.profitable ? 'ok' : item.status === 'conditional' ? 'cond' : item.story?.needs_staff ? 'warn' : 'bad'
const processRows = computed(() => (report.value?.processes ?? []).filter((item) => item.included))
const cardRows = computed(() => [...processRows.value].sort((a, b) => ORDER[toneOf(a)] - ORDER[toneOf(b)] || (npvOf(b) ?? -Infinity) - (npvOf(a) ?? -Infinity)))
const active = computed(() => processRows.value.filter((item) => !item.off))
const good = computed(() => active.value.filter((item) => item.profitable).length)
const losers = computed(() => active.value.filter((item) => item.profitable === false && item.status !== 'conditional'))
const conditional = computed(() => active.value.filter((item) => item.status === 'conditional' && item.condition))
/* Применить условия всех процессов «с условием» разом: свои коэффициенты процессов и меры господдержки. */
/* Разом применяем только реалистичные условия процесса и меры поддержки; жёсткие и общие для площадки — вручную. */
const applicable = computed(() => conditional.value.filter((item) => item.condition!.scope !== 'site' && !item.condition!.hard))
const applyConditions = (items: EconProcess[]) => applyOverrides((next) => {
  for (const item of items) {
    const fix = item.condition
    if (!fix) continue
    if (fix.scope === 'process' || fix.scope === 'combo') next[knobKey(item.process_code, fix.key)] = fix.to
    if (fix.scope === 'combo') for (const code of fix.with ?? []) next[subsidyKey(code)] = 1
    if (fix.scope === 'subsidy') for (const code of fix.key.split(',')) next[subsidyKey(code)] = 1
    /* С условием процесс выгоден — возвращаем его в итог, даже если платформа его убирала. */
    delete next[`off:${item.process_code}`]
    delete next[`auto:off:${item.process_code}`]
  }
}, 'conditions')
/* План платформы: число роботов и состав процессов она меняет сама и помечает правки auto:*, чтобы их можно было вернуть. */
const applyPlan = (changes: EconPlanChange[]) => applyOverrides((next) => {
  const planned = withPlan(next, changes)
  for (const key of Object.keys(next)) if (!(key in planned)) delete next[key]
  Object.assign(next, planned)
}, 'plan')
/* Правки платформы вносятся сами при первом расчёте проекта. Демо, которое правит администратор, не трогаем: оно общее. */
const autoTried = ref(false)
watch(report, (current) => {
  if (!current || autoTried.value || busy.value) return
  autoTried.value = true
  if (isDemo.value && !readonly.value) return
  if (!overrides.value.auto && current.plan?.changes.length) void applyPlan(current.plan.changes)
}, { immediate: true })
/* Процесс, который платформа убрала сама, она же и возвращает, когда он стал выгоден: например, после ввода людей. */
let returned = ''
watch([report, busy], ([current, working]) => {
  if (!current || working || (isDemo.value && !readonly.value) || !overrides.value.auto) return
  const back = current.plan?.changes.filter((change) => change.kind === 'on') ?? []
  const key = back.map((change) => change.code).join(',')
  if (!back.length || key === returned) return
  returned = key
  void applyPlan(back)
})
const processOf = (code: string) => report.value?.processes?.find((item) => item.process_code === code) ?? null
const offReason = (code: string) => {
  const item = processOf(code)
  if (!item?.story || item.story.needs_staff) return 'Нет данных о людях на процессе: роботы пока только стоят денег. Укажите людей — платформа пересчитает.'
  if (!item.profitable) return item.condition ? `Невыгоден даже при подборе числа роботов. Окупится ${conditionText(item.condition)}, если договориться.` : 'Невыгоден даже при подборе числа роботов.'
  const taken = item.story.shared_with.find((name) => active.value.some((other) => other.process_name === name))
  if (taken) return `Те же люди уже уходят с процесса «${taken}»: этот процесс добавит только вложения и расходы.`
  return report.value?.plan?.budget ? 'Выгоден сам по себе, но в бюджет помещаются более выгодные процессы.' : 'Выгоден сам по себе, но без него итог объекта больше.'
}
const fixes = computed<EconFix[]>(() => Object.keys(overrides.value).flatMap((key): EconFix[] => {
  if (key.startsWith('auto:count:')) {
    const code = key.slice('auto:count:'.length)
    const item = processOf(code)
    return [{ key, kind: 'count', code, name: item?.process_name ?? code, change: `роботов ${overrides.value[key]} → ${overrides.value[`count:${code}`] ?? '—'}`,
      reason: `Больше людей, чем есть на процессе, лишние роботы не заменят.${item?.profitable ? ' С этим числом процесс выгоден.' : ''}` }]
  }
  if (key.startsWith('auto:off:')) {
    const code = key.slice('auto:off:'.length)
    return [{ key, kind: 'off', code, name: processOf(code)?.process_name ?? code, change: 'убран из итога', reason: offReason(code) }]
  }
  return []
}))
const undoKeys = (next: Record<string, number>, fix: EconFix) => {
  delete next[fix.key]
  if (fix.kind === 'off') delete next[`off:${fix.code}`]
  else {
    const from = overrides.value[fix.key]
    if (from == null || from === fleetOf(fix.code)?.count) delete next[`count:${fix.code}`]
    else next[`count:${fix.code}`] = from
  }
}
const undoFix = (fix: EconFix) => applyOverrides((next) => undoKeys(next, fix), `undo:${fix.key}`)
const undoAll = () => applyOverrides((next) => { for (const fix of fixes.value) undoKeys(next, fix) }, 'undo')
const setHorizon = (years: number) => applyOverrides((next) => { next.horizon_years = years }, 'horizon')
const worst = computed(() => report.value?.stress?.find((item) => item.key === 'all') ?? null)
const offCodes = computed(() => processRows.value.filter((item) => item.off).map((item) => item.process_code))
/* Без данных — в том числе процессы, которые платформа убрала из итога: данные по ним всё равно нужны. */
const noStaff = computed(() => processRows.value.filter((item) => item.story?.needs_staff).length)
const uncounted = computed(() => report.value?.fleet.filter((row) => row.included && !row.off && row.count_source === 'default').length ?? 0)
const openProcess = (code: string) => navigateTo(stageTo(code))
const unpriced = computed(() => report.value?.fleet.filter((row) => !row.included) ?? [])

/* Откуда экономия: статьи с формулами. */
const columns = computed(() => buy.value
  ? [
      { key: 'capex', title: 'Вложения', caption: 'один раз, без НДС', total: buy.value.capex, lines: buy.value.capex_lines },
      { key: 'opex', title: 'Роботы в год', caption: 'сервис, энергия, диспетчеры', total: buy.value.opex, lines: buy.value.opex_lines },
      { key: 'effect', title: 'Экономия в год', caption: 'меньше людей минус роботы', total: buy.value.effect, lines: [...buy.value.effect_lines, buy.value.payroll_after] },
    ]
  : [])
const open = ref<string | null>(null)
const toggle = (key: string) => { open.value = open.value === key ? null : key }
const openParam = ref<string | null>(null)

/* Покупка или аренда. */
const compareRows = computed(() => {
  const cols = [scenarioOf('asis'), buy.value, rent.value]
  const pay = (item: EconScenario | null) => !item || item.key === 'asis' ? '—' : item.key === 'raas' ? 'не нужна' : item.payback.value != null ? yearsText(item.payback.value) : 'нет'
  return {
    cols,
    rows: [
      { label: 'Вложения', values: cols.map((item) => item?.key === 'asis' ? '—' : millions(item?.capex.value)) },
      { label: 'Затраты в год', values: cols.map((item) => millions(item?.annual_cost)) },
      { label: 'Экономия в год', values: cols.map((item) => item?.key === 'asis' ? 'база' : millions(item?.effect.value)) },
      { label: 'Окупаемость', values: cols.map(pay) },
      { label: `Итог за ${report.value?.horizon_years ?? 5} лет`, values: cols.map((item) => item?.key === 'asis' ? '0' : signedMillions(item?.cashflow?.at(-1)?.cumulative ?? null)) },
      { label: 'Выгода с учётом стоимости денег (NPV)', values: cols.map((item) => item?.key === 'asis' ? '0' : signedMillions(item?.npv?.value)) },
      { label: 'Год работы с учётом вложений (EAC)', values: cols.map((item) => millions(item?.eac?.value)), expert: true },
    ],
  }
})
const switchOpen = ref(false)
const switchText = computed(() => {
  const fig = report.value?.switch
  if (!fig) return ''
  if (fig.value == null) return 'Аренда не проигрывает покупке при любом сроке: платёж не дороже владения.'
  if (fig.value < 1) return 'Покупка выгоднее аренды почти сразу.'
  return `Если роботы нужны дольше ${monthsText(fig.value)} — выгоднее купить, если меньше — арендовать.`
})
const rentBetter = computed(() => (rent.value?.npv?.value ?? -Infinity) > (buy.value?.npv?.value ?? -Infinity))
const rentVerdict = computed(() => {
  const r = rent.value?.npv?.value ?? null
  const b = buy.value?.npv?.value ?? null
  if (r != null && b != null && r < 0 && b < 0) return `Сейчас не окупается ни покупка, ни аренда. ${rentBetter.value ? 'Аренда' : 'Покупка'} теряет меньше.`
  return rentBetter.value ? 'Аренда выгоднее покупки: вложений почти нет, а выгода больше.' : 'Покупка выгоднее аренды: вложения окупаются, а платить каждый месяц не нужно.'
})

const enabledSubsidies = computed(() => new Set((report.value?.subsidies ?? []).filter((item) => item.enabled).map((item) => item.code)))
const groups = computed(() => PARAM_GROUPS.map((group) => ({
  ...group,
  items: (report.value?.params ?? []).filter((item) => item.group === group.id && (group.id !== 'subsidy'
    || (report.value?.subsidies ?? []).some((sub) => enabledSubsidies.value.has(sub.code) && sub.params.includes(item.key)))),
})).filter((group) => group.items.length))
const sourceText = (item: { source: string }) => ({ norm: 'стандарт', project: 'значение проекта', site: 'площадка' } as Record<string, string>)[item.source] ?? item.source
const requests = computed(() => {
  const all = report.value?.requests ?? []
  return { customer: all.filter((item) => item.to === 'customer'), vendor: all.filter((item) => item.to === 'vendor') }
})
const tabs = computed(() => TABS.map((item) => ({
  id: item.id,
  label: item.label,
  count: item.id === 'risk' ? (requests.value.customer.length + requests.value.vendor.length || undefined)
    : item.id === 'support' ? (enabledSubsidies.value.size || undefined)
      : item.id === 'processes' ? (processRows.value.length || undefined) : undefined,
})))

const restoring = ref('')
const restoreError = ref('')
const restore = async (code: string) => {
  restoring.value = code
  restoreError.value = ''
  try {
    await restoreProcess(code)
    await load(preview.value)
  } catch (err: unknown) {
    restoreError.value = fetchErrorMessage(err, 'Не удалось вернуть процесс')
  } finally {
    restoring.value = ''
  }
}
const inactiveOpen = ref(false)
</script>

<template>
  <ProjectShell
    v-if="project"
    :project="project"
    :alerts="skippedAlerts(skipped)"
    current="economics"
    :substages="report ? substages : undefined"
    :current-sub="view"
    title="Экономика"
    :subtitle="viewProcess ? `по процессу «${viewProcess.process_name}»` : report ? 'общая картина' : undefined"
  >
    <template #actions>
      <UiButton size="lg" @click="goForward">{{ forwardLabel }}<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
    </template>

    <UiCallout v-if="isDemo && !readonly" tone="info" title="Демо-объект">
      Вы правите демо как администратор: параметры и коэффициенты сохраняются в проект и после публикации станут видны всем.
    </UiCallout>

    <section v-if="(pending || loading) && !report" class="waiting glass"><div class="h3">Считаем экономику</div></section>
    <UiCallout v-else-if="failure || error" tone="danger" title="Экономика не посчиталась">{{ failure || fetchErrorMessage(error, 'Сервер не ответил.') }}</UiCallout>
    <template v-else-if="report && buy && viewProcess">
      <UiCallout v-if="editError" tone="danger">{{ editError }}</UiCallout>
      <EconProcessCard
        page
        :process="viewProcess"
        :busy="!!busy"
        :horizon="report.horizon_years"
        :fte-hours="fteHours"
        @off="(off) => setOff([viewProcess!.process_code], off)"
        :fixes="fixes.filter((fix) => fix.code === viewProcess!.process_code)"
        :rate-editable="role === 'admin'"
        :tune-summary="tuneSummary"
        :tune-hint="fleetOf(viewProcess.process_code)?.count_source === 'default' ? 'Число роботов не посчитано: формуле не хватает данных площадки, в расчёте 1 робот. Укажите своё число в настройке процесса.' : ''"
        @staff="(people, wage, cost, other) => saveStaff(viewProcess!, people, wage, cost, other)"
        @apply="applyConditions([viewProcess!])"
        @rate="(value) => setRate(viewProcess!.process_code, value)"
        @undo="undoFix"
      >
        <div class="tune">
          <div class="knobs">
            <div v-if="fleetOf(viewProcess!.process_code)?.included" class="knob">
              <span class="caption">Роботов</span>
              <span class="count">
                <button type="button" class="step" :disabled="!!busy || (fleetOf(viewProcess!.process_code)!.count_used ?? 1) <= 1" aria-label="Меньше" @click="setCount(fleetOf(viewProcess!.process_code)!, (fleetOf(viewProcess!.process_code)!.count_used ?? 1) - 1)">−</button>
                <input class="count-in mono-sm" type="number" min="1" max="10000" :value="fleetOf(viewProcess!.process_code)!.count_used ?? 1" :disabled="!!busy" aria-label="Роботов на процессе" @change="typeCount(fleetOf(viewProcess!.process_code)!, $event)" @keydown.enter="($event.target as HTMLInputElement).blur()">
                <button type="button" class="step" :disabled="!!busy" aria-label="Больше" @click="setCount(fleetOf(viewProcess!.process_code)!, (fleetOf(viewProcess!.process_code)!.count_used ?? 1) + 1)">+</button>
              </span>
              <span class="caption">
                <template v-if="fleetOf(viewProcess!.process_code)!.count_source === 'project'">вручную · <button type="button" class="reset" :disabled="!!busy" @click="setCount(fleetOf(viewProcess!.process_code)!, null)">{{ fleetOf(viewProcess!.process_code)!.count != null ? `по формуле ${fleetOf(viewProcess!.process_code)!.count!.toLocaleString('ru-RU')}` : 'сбросить' }}</button></template>
                <template v-else-if="fleetOf(viewProcess!.process_code)!.count_source === 'default'"><span class="warn-text">формула не посчитала — укажите своё число</span></template>
                <template v-else>по формуле подбора</template>
              </span>
            </div>
            <div v-for="knob in KNOBS" :key="knob.key" class="knob">
              <span class="caption">{{ knob.label }}</span>
              <span class="count">
                <button type="button" class="step" :disabled="!!busy || knobValue(viewProcess!.process_code, knob.key) <= knob.min" aria-label="Меньше" @click="setKnob(viewProcess!.process_code, knob.key, Math.max(knob.min, knobValue(viewProcess!.process_code, knob.key) - knob.step))">−</button>
                <input class="count-in mono-sm" type="number" :min="knob.min" :max="knob.max" :step="knob.step" :value="knobValue(viewProcess!.process_code, knob.key)" :disabled="!!busy" :aria-label="knob.label" @change="typeKnob(viewProcess!.process_code, knob, $event)" @keydown.enter="($event.target as HTMLInputElement).blur()">
                <button type="button" class="step" :disabled="!!busy || knobValue(viewProcess!.process_code, knob.key) >= knob.max" aria-label="Больше" @click="setKnob(viewProcess!.process_code, knob.key, Math.min(knob.max, knobValue(viewProcess!.process_code, knob.key) + knob.step))">+</button>
              </span>
              <span class="caption">{{ knob.unit }} · <button v-if="knobOwn(viewProcess!.process_code, knob.key)" type="button" class="reset" :disabled="!!busy" @click="setKnob(viewProcess!.process_code, knob.key, null)">сбросить</button><template v-else>{{ knob.hint }}</template></span>
            </div>
          </div>
          <div v-if="viewProcess!.suggestions.length" class="fixes">
            <span class="caption strong">Что сделает процесс выгодным</span>
            <div class="fix-list">
              <button v-for="fix in viewProcess!.suggestions" :key="`${fix.scope}:${fix.key}`" type="button" class="fix" :class="fix.scope" :disabled="!!busy" @click="applySuggestion(viewProcess!.process_code, fix)">
                <span class="fix-scope">{{ SCOPE_LABEL[fix.scope] }}</span>
                <span class="body-sm strong">{{ fix.label }}</span>
                <span class="mono-sm">{{ suggestionChange(fix) }}</span>
                <span class="caption">окупаемость {{ fix.payback != null ? yearsText(fix.payback) : '—' }}</span>
                <span class="fix-go">{{ fix.scope === 'site' ? 'Открыть в what-if →' : 'Применить' }}</span>
              </button>
            </div>
          </div>
        </div>
      </EconProcessCard>
      <div class="stage-foot">
        <span class="caption">Процесс {{ stageIndex + 1 }} из {{ processList.length }}. Общая картина сложит выбранные процессы и покажет итог объекта.</span>
        <UiButton @click="goForward">{{ forwardLabel }}<template #after><PhArrowRight :size="16" weight="bold" /></template></UiButton>
      </div>
      <p class="caption prelim">{{ report.disclaimer ?? PRELIMINARY }}</p>
    </template>
    <template v-else-if="report && buy">
      <EconOverview
        :buy="buy"
        :horizon="report.horizon_years"
        :staff-now="report.story?.staff_now ?? 0"
        :cost-now="report.story?.payroll_now ?? 0"
        :released="report.story?.released ?? 0"
        :dispatchers="dispatchers"
        :good="good"
        :total="active.length"
        :losers="losers.length"
        :conditional="conditional.length"
        :applicable="applicable.length"
        :no-staff="noStaff"
        :uncounted="uncounted"
        :chance="report.chance"
        :worst="worst"
        :plan="report.plan"
        :busy="!!busy"
        @keep-good="setOff(losers.map((item) => item.process_code), true)"
        @apply-conditions="applyConditions(applicable)"
        @apply-plan="report.plan && applyPlan(report.plan.changes)"
        @horizon="setHorizon"
        @goto="goto"
      >
        <template v-if="fixes.length" #fixes>
          <EconFixes :fixes="fixes" :busy="!!busy" @undo="undoFix" @undo-all="undoAll" />
        </template>
        <template #expert>
          <EconMetrics
            :buy="buy"
            :asis="scenarioOf('asis')"
            :discount="report.discount"
            :chance="report.chance"
            :interval="report.interval"
            :breakeven="report.breakeven ?? []"
            :sensitivity="report.sensitivity"
            :horizon="report.horizon_years"
          />
        </template>
      </EconOverview>
      <EconomicContext :report="report" />
      <UiCallout v-if="editError" tone="danger">{{ editError }}</UiCallout>

      <div ref="tabsRef" class="tabs-wrap"><UiTabs v-model="tab" :tabs="tabs" /></div>
      <p class="caption q-lead">{{ activeTab.lead }}</p>

      <!-- Какие процессы выгодны -->
      <template v-if="tab === 'processes'">
        <div v-if="losers.length || offCodes.length || applicable.length" class="p-actions">
          <span class="tally mono-md"><b>{{ good }}</b> из {{ active.length }} выгодны<template v-if="conditional.length"> · <b class="cond">{{ conditional.length }}</b> с условием</template></span>
          <UiButton v-if="applicable.length" size="sm" :disabled="!!busy" @click="applyConditions(applicable)">Применить условия · {{ applicable.length }}</UiButton>
          <UiButton v-if="losers.length" variant="danger" size="sm" :disabled="!!busy" @click="setOff(losers.map((item) => item.process_code), true)"><template #icon><PhProhibit :size="16" weight="bold" /></template>Убрать невыгодные · {{ losers.length }}</UiButton>
          <UiButton v-if="offCodes.length" variant="secondary" size="sm" :disabled="!!busy" @click="setOff(offCodes, false)">Вернуть все · {{ offCodes.length }}</UiButton>
        </div>
        <div class="cards">
          <EconProcessCard
            v-for="item in cardRows"
            :key="item.process_code"
            :process="item"
            :busy="!!busy"
            :horizon="report.horizon_years"
            :open="false"
            @toggle="openProcess(item.process_code)"
            @off="(off) => setOff([item.process_code], off)"
            @apply="applyConditions([item])"
          />
        </div>
        <p v-if="unpriced.length" class="caption">Нет цены робота, в расчёт не входят: {{ unpriced.map((row) => row.process_name).join(', ') }}.</p>
        <section v-if="inactive.length" class="inactive glass">
          <div class="c-in">
            <button type="button" class="c-head fleet-toggle" :aria-expanded="inactiveOpen" @click="inactiveOpen = !inactiveOpen">
              <div>
                <div class="h4">Выключены на шаге «Процессы» <span class="n-off mono-sm">{{ inactive.length }}</span></div>
                <div class="caption">Не входят ни в подбор, ни в экономику. Любой можно вернуть.</div>
              </div>
              <PhCaretDown :size="16" weight="bold" class="caret" :class="{ up: inactiveOpen }" />
            </button>
            <ul v-show="inactiveOpen" class="off-list">
              <li v-for="item in inactive" :key="item.code" class="off-item">
                <span class="body-sm">{{ item.name }}</span>
                <UiButton v-if="!readonly" variant="secondary" size="sm" :disabled="restoring === item.code" @click="restore(item.code)">{{ restoring === item.code ? 'Возвращаем' : 'Вернуть в проект' }}</UiButton>
              </li>
            </ul>
            <p v-if="restoreError" class="caption err">{{ restoreError }}</p>
          </div>
        </section>
      </template>

      <!-- Откуда экономия -->
      <template v-else-if="tab === 'people'">
        <section class="card glass">
          <div class="c-in">
            <EconPeople :items="report.release?.items ?? []" :dispatchers="dispatchers" :check="report.release?.check" :ask="() => goto('risk')" />
          </div>
        </section>
        <div class="cols">
          <section v-for="col in columns" :key="col.key" class="col glass">
            <div class="c-in">
              <button type="button" class="c-head c-btn" :aria-expanded="open === `total:${col.key}`" @click="toggle(`total:${col.key}`)">
                <span><span class="h4">{{ col.title }}</span><span class="caption block">{{ col.caption }}</span></span>
                <span class="c-total"><span class="mono-lg">{{ rubles(col.total.value) }}</span><UiExpandHint :open="open === `total:${col.key}`" label="" /></span>
              </button>
              <EconFormula v-if="open === `total:${col.key}`" :fig="col.total" />
              <ul class="lines">
                <li v-for="line in col.lines" :key="line.key">
                  <button type="button" class="line" :class="{ 'is-open': open === `${col.key}:${line.key}` }" :aria-expanded="open === `${col.key}:${line.key}`" @click="toggle(`${col.key}:${line.key}`)">
                    <span class="body-sm" :class="{ 'cost-accent': isAccent(line.key, line.label) }">{{ line.label }}</span>
                    <span class="mono-md" :class="{ dim: !line.included }">{{ line.included ? rubles(line.value) : 'не входит' }}</span>
                    <PhCaretDown :size="12" weight="bold" class="caret" :class="{ up: open === `${col.key}:${line.key}` }" />
                  </button>
                  <EconFormula v-if="open === `${col.key}:${line.key}`" :fig="line" />
                </li>
              </ul>
            </div>
          </section>
        </div>
      </template>

      <!-- Когда вернутся деньги -->
      <template v-else-if="tab === 'money'">
        <section class="card glass">
          <div class="c-in">
            <div class="h4">Накоплено с начала: старт в минусе на вложения, пересечение нуля — окупаемость</div>
            <EconCashChart :scenarios="[buy]" picked="purchase" />
          </div>
        </section>
        <section v-if="buy.cashflow?.length" class="card glass">
          <div class="c-in">
            <div class="h4">Что приходит и уходит каждый год</div>
            <EconCashflow :scenario="buy" />
          </div>
        </section>
      </template>

      <!-- Купить или арендовать -->
      <template v-else-if="tab === 'rent'">
        <section class="card glass">
          <div class="c-in">
            <p class="verdict body-lg"><b>{{ rentVerdict }}</b></p>
            <div v-if="report.switch" class="switch-row">
              <p class="body-sm">{{ switchText }}</p>
              <button type="button" class="reset" @click="switchOpen = !switchOpen">{{ switchOpen ? 'скрыть расчёт' : 'как посчитано' }}</button>
            </div>
            <EconFormula v-if="switchOpen && report.switch" :fig="report.switch" />
            <table class="cmp">
              <thead><tr><th /><th v-for="col in compareRows.cols" :key="col?.key">{{ col?.title }}</th></tr></thead>
              <tbody>
                <tr v-for="row in compareRows.rows" :key="row.label" :class="{ expert: row.expert }">
                  <th>{{ row.label }}</th>
                  <td v-for="(value, index) in row.values" :key="index" :class="{ on: compareRows.cols[index]?.key === (rentBetter ? 'raas' : 'purchase') }">{{ value }}</td>
                </tr>
              </tbody>
            </table>
            <p v-if="rent?.note" class="caption">{{ rent.note }}</p>
          </div>
        </section>
        <section class="card glass">
          <div class="c-in">
            <div class="h4">Накоплено с начала: покупка и аренда</div>
            <EconCashChart :scenarios="[buy, ...(rent ? [rent] : [])]" picked="purchase" />
          </div>
        </section>
      </template>

      <!-- Господдержка -->
      <template v-else-if="tab === 'support'">
        <EconSubsidies v-if="report.subsidies?.length" :items="report.subsidies" :horizon="report.horizon_years" :busy="busy.replace('subsidy:', '')" :to="`/projects/${project.id}/what-if`" @toggle="toggleSubsidy" />
        <p class="caption">Льготный лизинг и субсидия Москвы на лизинг относятся к схеме «Лизинг» и в покупку не входят, иначе скидка считалась бы без договора лизинга.</p>
      </template>

      <!-- Надёжность расчёта -->
      <template v-else-if="tab === 'risk'">
        <section class="card glass">
          <div class="c-in">
            <EconRisk :interval="report.interval" :breakeven="report.breakeven ?? []" :sensitivity="report.sensitivity" :stress="report.stress ?? []" :chance="report.chance" :horizon="report.horizon_years" />
          </div>
        </section>
        <section v-if="requests.customer.length || requests.vendor.length" class="card glass">
          <div class="c-in">
            <div class="h4">Что уточнить, чтобы расчёт стал точнее</div>
            <div class="asks">
              <div v-for="side in (['customer', 'vendor'] as const)" :key="side" class="ask-col">
                <div class="ask-head"><component :is="side === 'customer' ? PhUser : PhStorefront" :size="18" weight="duotone" /><span class="h4">{{ side === 'customer' ? 'Заказчику' : 'Вендору' }}</span><span class="mono-sm muted">{{ requests[side].length }}</span></div>
                <ol class="ask-list">
                  <li v-for="(item, index) in requests[side]" :key="index">
                    <span class="body-sm strong">{{ item.question }}</span>
                    <span class="caption">{{ item.process_name ? `${item.process_name}. ` : '' }}{{ item.why }}</span>
                  </li>
                  <li v-if="!requests[side].length" class="caption">Вопросов нет.</li>
                </ol>
              </div>
            </div>
          </div>
        </section>
        <section class="card glass">
          <div class="c-in">
            <div class="c-head">
              <div><div class="h4">Предпосылки расчёта</div><div class="caption">Стандарт задаётся в админке, значение проекта — на шаге what-if. Источник у каждого числа.</div></div>
              <UiButton :to="`/projects/${project.id}/what-if`" variant="secondary" size="sm">Изменить</UiButton>
            </div>
            <div v-for="group in groups" :key="group.id" class="coef-group">
              <div class="label">{{ group.label }}</div>
              <div class="coef-list">
                <div v-for="item in group.items" :key="item.key" class="coef" :class="{ open: openParam === item.key }">
                  <button type="button" class="coef-btn" @click="openParam = openParam === item.key ? null : item.key">
                    <UiTex :tex="item.symbol" class="sym" />
                    <span class="body-sm strong">{{ item.label }}</span>
                    <span class="mono-md">{{ item.value.toLocaleString('ru-RU') }} <span class="muted">{{ item.unit }}</span></span>
                    <UiBadge :tone="SOURCE_TONE[item.source]" size="sm">{{ sourceText(item) }}</UiBadge>
                    <PhCaretDown :size="14" weight="bold" class="caret" />
                  </button>
                  <div v-if="openParam === item.key" class="coef-body">
                    <div><span class="caption">Обоснование</span><p class="body-sm">{{ item.rationale }}</p></div>
                    <div><span class="caption">Источник стандарта</span><p class="body-sm">{{ item.origin }}</p></div>
                    <div><span class="caption">Стандарт</span><p class="body-sm">{{ item.standard.toLocaleString('ru-RU') }} {{ item.unit }}</p></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </template>

      <p class="caption prelim">{{ report.disclaimer ?? PRELIMINARY }}<template v-if="readonly"> В демо изменения действуют до перезагрузки страницы.</template></p>
    </template>
  </ProjectShell>
  <section v-else class="container gone">
    <UiCallout tone="danger" title="Проект не найден">Нет сохранённого расчёта с таким адресом.</UiCallout>
  </section>
</template>

<style scoped>
.waiting { padding: var(--space-10); }
.waiting > * { position: relative; z-index: 1; }
.gone { padding-top: var(--space-12); }
.c-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: var(--space-4); }
.c-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.c-btn { width: 100%; text-align: left; }
.c-btn:hover .h4 { color: var(--link); }
.c-total { display: inline-flex; align-items: center; gap: 8px; flex: none; }
.c-total .mono-lg { font-size: 18px; color: var(--ink-strong); white-space: nowrap; }
.fleet-toggle { width: 100%; text-align: left; align-items: center; }
.block { display: block; }
.caret { color: var(--ink-faint); transition: transform var(--dur-fast) var(--ease); flex: none; }
.caret.up { transform: rotate(180deg); }
.card { border-radius: var(--radius-xl); }
.h4 { margin: 0; }
.prelim { margin: 0; }

.tabs-wrap { overflow-x: auto; margin: var(--space-4) -2px 0; padding: 2px; scroll-margin-top: 90px; }
.tabs-wrap :deep(.tabs) { min-width: 940px; }
.q-lead { margin: calc(var(--space-2) * -1) 0 calc(var(--space-2) * -1); max-width: 100ch; }

.stage-foot { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; }
.p-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.tally { white-space: nowrap; color: var(--ink-muted); margin-right: 6px; }
.tally b { color: var(--brand-600); }
.tally b.cond { color: #b7791f; }
.cards { display: grid; gap: 8px; }
.tune { display: grid; gap: var(--space-4); padding-top: var(--space-4); border-top: 1px solid rgba(15, 20, 19, 0.08); }
.knobs { display: flex; flex-wrap: wrap; gap: var(--space-6); }
.knob { display: grid; gap: 6px; justify-items: start; }
.count { display: grid; grid-template-columns: 30px 64px 30px; column-gap: 4px; align-items: center; }
.step { width: 30px; height: 30px; border-radius: 9px; font-size: 18px; font-weight: 700; line-height: 1; color: var(--ink-strong); background: #fff; box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.12); }
.step:not(:disabled):hover { box-shadow: inset 0 0 0 1.5px var(--brand-500); color: var(--brand-700); }
.step:disabled { opacity: 0.4; }
.count-in { width: 64px; height: 30px; border-radius: 9px; text-align: center; background: #fff; box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.12); border: 0; -moz-appearance: textfield; }
.count-in::-webkit-outer-spin-button, .count-in::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
.reset { color: var(--link); font-weight: 600; text-decoration: underline; text-underline-offset: 2px; }
.warn-text { display: inline-block; padding: 2px 8px; border-radius: 6px; background: #fff3cf; color: #5c3700; font-weight: 700; }
.fixes { display: grid; gap: 8px; }
.fix-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 10px; }
.fix { display: grid; gap: 4px; align-content: start; text-align: left; padding: 12px 14px; border-radius: 14px; background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.08); transition: box-shadow var(--dur-fast) var(--ease); }
.fix:not(:disabled):hover { box-shadow: inset 0 0 0 1.5px var(--brand-500); }
.fix .mono-sm { color: var(--brand-700); }
.fix-scope { justify-self: start; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 999px; background: rgba(15, 20, 19, 0.06); color: var(--ink-muted); }
.fix.subsidy .fix-scope { background: var(--state-ok-tint); color: var(--state-ok); }
.fix-go { margin-top: 4px; font-size: 13px; font-weight: 700; color: var(--link); }
.n-off { display: inline-flex; align-items: center; justify-content: center; min-width: 24px; height: 22px; padding: 0 6px; margin-left: 6px; border-radius: 999px; background: rgba(15, 20, 19, 0.07); color: var(--ink-muted); vertical-align: 2px; }
.off-list { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
.off-item { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 10px 14px; border-radius: 12px; background: rgba(255, 255, 255, 0.5); }
.err { color: var(--state-danger); margin: 0; }

.cols { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4); align-items: start; }
.col { border-radius: var(--radius-xl); }
.lines { display: grid; margin: 0; padding: 0; list-style: none; }
.lines li { display: grid; gap: 8px; padding: 8px 0; border-top: 1px solid rgba(15, 20, 19, 0.06); }
.lines li:first-child { border-top: 0; }
.line { width: calc(100% + 16px); margin: -4px -8px; padding: 4px 8px; border-radius: 8px; display: grid; grid-template-columns: minmax(0, 1fr) auto 12px; gap: 10px; align-items: center; text-align: left; }
.line:hover, .line.is-open { background: var(--surface-brand-tint); }
.line .mono-md { color: var(--ink-strong); white-space: nowrap; }
.dim { color: var(--ink-muted) !important; }

.verdict { margin: 0; }
.cmp { width: 100%; border-collapse: collapse; }
.cmp th, .cmp td { padding: 10px 8px; border-bottom: 1px solid rgba(15, 20, 19, 0.06); text-align: right; white-space: nowrap; }
.cmp thead th { font-size: 13px; font-weight: 700; color: var(--ink-muted); }
.cmp tbody th { text-align: left; font-weight: 600; font-size: 13px; color: var(--ink-body); white-space: normal; }
.cmp td { font-family: var(--font-mono); font-size: 13px; color: var(--ink-strong); font-variant-numeric: tabular-nums; }
.cmp tr.expert th, .cmp tr.expert td { color: var(--ink-muted); }
.switch-row { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 12px; }
.switch-row p { margin: 0; }
.switch-row .reset { font-size: 13px; }
.cmp .on { background: var(--surface-brand-tint); color: var(--brand-ink); font-weight: 700; }

.asks { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.ask-col { display: grid; gap: 10px; align-content: start; padding: 16px; border-radius: 16px; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.ask-head { display: flex; align-items: center; gap: 8px; color: var(--brand-700); }
.ask-list { margin: 0; padding-left: 20px; display: grid; gap: 10px; }
.ask-list li { display: grid; gap: 2px; }

.coef-group { display: grid; gap: 6px; }
.coef-list { display: grid; gap: 6px; }
.coef { border-radius: 12px; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.coef-btn { width: 100%; display: grid; grid-template-columns: 90px 1fr auto auto 14px; gap: 14px; align-items: center; padding: 10px 14px; text-align: left; }
.sym { color: var(--ink-muted); }
.open .caret { transform: rotate(180deg); }
.coef-body { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 16px; padding: 4px 14px 14px 118px; }
.coef-body .caption { display: block; margin-bottom: 2px; }
.coef-body p { margin: 0; }

@media (max-width: 1100px) {
  .cols, .asks { grid-template-columns: 1fr; }
  .coef-btn { grid-template-columns: 70px 1fr auto 14px; }
  .coef-btn :deep(.badge) { display: none; }
  .coef-body { padding-left: 14px; grid-template-columns: 1fr; }
}
</style>
