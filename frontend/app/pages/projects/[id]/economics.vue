<script setup lang="ts">
import { PhArrowRight, PhCaretDown } from '@phosphor-icons/vue'
import { photoFor } from '~/data/placeholders'
import {
  figValue,
  millions,
  PARAM_GROUPS,
  PRELIMINARY,
  rubles,
  SOURCE_TONE,
  subsidyKey,
  usePlatformEconomy,
  type EconFig,
  type EconScenario,
  type EconSuggestion,
} from '~/composables/usePlatformEconomy'
import { replaceQuery } from '~/composables/useQuerySync'
import { fetchErrorMessage } from '~/utils/errors'
import { isAccent } from '~/utils/accent'

const route = useRoute()
const id = computed(() => route.params.id as string)
const { project, isDemo, readonly, report, loading, failure, pending, error, source, choices, skipped, load, saveOverrides, disableProcess, restoreProcess, inactive } = usePlatformEconomy(id)
useHead({ title: () => `Экономика · ${project.value?.name ?? 'проект'}` })

/* В демо только просмотр: включённые меры живут в предпросмотре и в проект не пишутся. */
const preview = ref<Record<string, number> | null>(null)
onMounted(() => { void load(preview.value) })
watch([() => JSON.stringify(source.value ?? null), () => JSON.stringify(choices.value)], () => { void load(preview.value) })

const processCode = ref(typeof route.query.process === 'string' ? route.query.process : '')
watch(processCode, (value) => replaceQuery({ process: value || undefined }))
const activeProcess = computed(() => report.value?.processes?.find((item) => item.process_code === processCode.value) ?? null)
const scenarios = computed(() => activeProcess.value?.scenarios?.length ? activeProcess.value.scenarios : processCode.value ? [] : (report.value?.scenarios ?? []))
const payrollFig = computed(() => activeProcess.value?.payroll ?? report.value?.payroll ?? null)
const fleetPurchase = computed(() => report.value?.scenarios.find((item) => item.key === 'purchase') ?? null)
const activePurchase = computed(() => activeProcess.value?.scenarios.find((item) => item.key === 'purchase') ?? null)
const activeRobot = computed(() => report.value?.fleet.find((row) => row.process_code === processCode.value) ?? null)
const picked = ref<EconScenario['key']>('purchase')
const scenario = computed(() => scenarios.value.find((item) => item.key === picked.value) ?? null)
const cancelOpen = ref(false)
const disabling = ref(false)
const cancelError = ref('')
watch(processCode, () => { cancelOpen.value = false; cancelError.value = '' })

const subsidyBusy = ref('')
const subsidyError = ref('')
const setSubsidies = async (codes: string[], on: boolean | null) => {
  if (!report.value) return
  const next = { ...(preview.value ?? report.value.saved_overrides) }
  for (const code of codes) {
    const key = subsidyKey(code)
    if (on ?? !next[key]) next[key] = 1
    else delete next[key]
  }
  subsidyBusy.value = codes.join(',')
  subsidyError.value = ''
  try {
    if (readonly.value) {
      preview.value = next
    } else {
      await saveOverrides(next)
    }
    await load(preview.value)
  } catch (err: unknown) {
    subsidyError.value = fetchErrorMessage(err, 'Не удалось изменить меру поддержки')
  } finally {
    subsidyBusy.value = ''
  }
}
const toggleSubsidy = (code: string) => setSubsidies([code], null)

const SCOPE_LABEL: Record<EconSuggestion['scope'], string> = { process: 'только этот процесс', site: 'вся площадка', subsidy: 'господдержка' }
const suggestionChange = (item: EconSuggestion) => item.scope === 'subsidy'
  ? (item.key.includes(',') ? `включить ${item.key.split(',').length} меры` : 'включить меру')
  : `${item.from.toLocaleString('ru-RU')} → ${item.to.toLocaleString('ru-RU')} ${item.unit}`
const tuneTo = (item: EconSuggestion) => {
  const params = new URLSearchParams({
    process: activeProcess.value?.process_code ?? '',
    tune: item.key,
    value: String(item.to),
    scope: item.scope,
  })
  return `/projects/${id.value}/what-if?${params}`
}
const confirmCancel = async () => {
  const item = activeProcess.value
  if (!item) return
  disabling.value = true
  cancelError.value = ''
  const reason = `${item.reason} Выключен на шаге экономики ${new Date().toLocaleDateString('ru-RU')}.`
  try {
    await disableProcess(item.process_code, reason)
    processCode.value = ''
    cancelOpen.value = false
    await load(preview.value)
  } catch (err: unknown) {
    cancelError.value = fetchErrorMessage(err, 'Не удалось выключить процесс')
  } finally {
    disabling.value = false
  }
}
const restoring = ref('')
const restoreError = ref('')
const restore = async (code: string) => {
  restoring.value = code
  restoreError.value = ''
  try {
    await restoreProcess(code)
    await load(preview.value)
    processCode.value = code
  } catch (err: unknown) {
    restoreError.value = fetchErrorMessage(err, 'Не удалось вернуть процесс')
  } finally {
    restoring.value = ''
  }
}
const inactiveOpen = ref(true)
const open = ref<string | null>(null)
const toggle = (key: string) => { open.value = open.value === key ? null : key }
const openParam = ref<string | null>(null)

const kpis = computed<EconFig[]>(() => scenario.value ? [scenario.value.roi, scenario.value.tco, scenario.value.effect] : [])
const columns = computed(() => scenario.value
  ? [
      { key: 'capex', title: 'CAPEX', caption: 'единовременно', total: scenario.value.capex, lines: scenario.value.capex_lines },
      { key: 'opex', title: 'OPEX за год', caption: 'эксплуатация парка', total: scenario.value.opex, lines: scenario.value.opex_lines },
      { key: 'effect', title: 'Эффект за год', caption: 'экономия ФОТ минус OPEX', total: scenario.value.effect, lines: [...scenario.value.effect_lines, scenario.value.payroll_after] },
    ]
  : [])

const chartMax = computed(() => Math.max(1, ...scenarios.value.flatMap((item) => item.years.map((row) => row.cost_rub))))
const chartYears = computed(() => {
  const base = scenarios.value[0]?.years ?? []
  return base.map((row) => ({
    year: row.year,
    bars: scenarios.value.map((item) => ({ key: item.key, value: item.years.find((y) => y.year === row.year)?.cost_rub ?? 0 })),
  }))
})
const enabledSubsidies = computed(() => new Set((report.value?.subsidies ?? []).filter((item) => item.enabled).map((item) => item.code)))
const groups = computed(() => PARAM_GROUPS.map((group) => ({
  ...group,
  items: (report.value?.params ?? []).filter((item) => item.group === group.id && (group.id !== 'subsidy'
    || (report.value?.subsidies ?? []).some((sub) => enabledSubsidies.value.has(sub.code) && sub.params.includes(item.key)))),
})).filter((group) => group.items.length))
const sourceText = (item: { source: string }) => ({ norm: 'стандарт', project: 'значение проекта', site: 'площадка' } as Record<string, string>)[item.source] ?? item.source
const withoutPrice = computed(() => report.value?.fleet.filter((row) => !row.included).length ?? 0)
const fleetOpen = ref(false)
</script>

<template>
  <ProjectShell
    v-if="project"
    :project="project"
    current="economics"
    title="Экономика: три сценария"
    lead="Без роботизации, покупка и аренда. Выберите процесс, чтобы посмотреть его окупаемость отдельно. Если покупка не окупается, подберите допущения или меру господдержки — или выключите процесс."
  >
    <template #actions>
      <UiButton :to="`/projects/${project.id}/compare`" variant="secondary">К сравнению</UiButton>
      <UiButton :to="`/projects/${project.id}/what-if`" size="lg">К what-if<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
    </template>

    <UiCallout tone="warn" title="Предварительная оценка">{{ report?.disclaimer ?? PRELIMINARY }}</UiCallout>
    <SkippedProcesses :rows="skipped" />

    <UiCallout v-if="readonly" tone="info" title="Демо-объект · только просмотр">
      Параметры площадки и коэффициенты задал администратор, расчёт идёт тем же движком, что и в ваших проектах. Чтобы менять допущения, скопируйте демо в свои проекты.
    </UiCallout>
    <UiCallout v-else-if="isDemo" tone="info" title="Демо-объект">
      Вы правите демо как администратор: параметры и коэффициенты сохраняются в проект и после публикации станут видны всем.
    </UiCallout>

    <section v-if="(pending || loading) && !report" class="waiting glass"><div class="h3">Считаем экономику</div></section>
    <UiCallout v-else-if="failure || error" tone="danger" title="Экономика не посчиталась">{{ failure || fetchErrorMessage(error, 'Сервер не ответил.') }}</UiCallout>
    <template v-else-if="report">
      <EconProcessGrid
        v-if="report.processes?.length"
        v-model="processCode"
        :processes="report.processes"
        :fleet="fleetPurchase"
        :robots="report.robots"
        :horizon="report.horizon_years"
      />

      <section v-if="inactive.length" class="inactive glass">
        <div class="c-in">
          <button type="button" class="c-head fleet-toggle" :aria-expanded="inactiveOpen" @click="inactiveOpen = !inactiveOpen">
            <div>
              <div class="h3">Неактивные процессы <span class="count mono-sm">{{ inactive.length }}</span></div>
              <div class="caption">Не входят в подбор и экономику. Любой можно вернуть — расчёт пересчитается.</div>
            </div>
            <PhCaretDown :size="16" weight="bold" class="caret" :class="{ up: inactiveOpen }" />
          </button>
          <ul v-show="inactiveOpen" class="off-list">
            <li v-for="item in inactive" :key="item.code" class="off" :class="{ loss: item.disabled_reason }">
              <span class="off-copy">
                <span class="off-title">
                  <span class="body-sm strong">{{ item.name }}</span>
                  <span class="off-tag" :class="{ loss: item.disabled_reason }">{{ item.disabled_reason ? 'невыгоден' : 'выключен в параметрах' }}</span>
                </span>
                <span class="caption">{{ item.disabled_reason || 'Процесс сняли с подбора на шаге параметров.' }}</span>
              </span>
              <UiButton v-if="!readonly" variant="secondary" size="sm" :disabled="restoring === item.code" @click="restore(item.code)">{{ restoring === item.code ? 'Возвращаем' : 'Вернуть в проект' }}</UiButton>
            </li>
          </ul>
          <p v-if="restoreError" class="caption d-err-light">{{ restoreError }}</p>
        </div>
      </section>

      <section v-if="activeProcess" class="detail glass-graphite glass-graphite-solid">
        <div class="d-in">
          <div class="d-main">
            <img class="d-photo" :src="photoFor(activeProcess.image_url, activeProcess.robot_name, activeProcess.process_code)" :alt="activeProcess.robot_name">
            <div class="d-copy">
              <span class="label">{{ activeProcess.process_name }}</span>
              <span class="h3">{{ activeProcess.robot_name }}</span>
              <span class="caption">{{ activeProcess.count ? `${activeProcess.count.toLocaleString('ru-RU')} шт. · ` : '' }}{{ rubles(activeProcess.cost_rub) }} оборудование · доля ФОТ {{ Math.round(activeProcess.share * 100) }}%</span>
            </div>
            <div class="d-kpi">
              <span class="caption">Окупаемость покупки</span>
              <span class="d-pay" :class="{ bad: activeProcess.profitable === false }">{{ activePurchase?.payback.value != null ? figValue(activePurchase.payback.value, 'лет') : 'нет' }}</span>
              <span class="caption">горизонт {{ report.horizon_years }} лет</span>
            </div>
          </div>
          <p class="d-reason body-sm" :class="{ bad: activeProcess.profitable === false }">{{ activeProcess.reason }}</p>
          <p v-if="activeProcess.share_note" class="caption d-note">{{ activeProcess.share_note }}</p>
          <div class="d-actions">
            <UiButton :to="`/projects/${project.id}/what-if?process=${activeProcess.process_code}`" variant="onGraphite" size="sm">Настроить в what-if</UiButton>
            <UiButton v-if="activeRobot?.fig" variant="glass" size="sm" @click="toggle(`fleet:${activeProcess.process_code}`)">Как посчитано оборудование</UiButton>
            <UiButton v-if="activeProcess.included && activeProcess.profitable === false && !cancelOpen" variant="danger" size="sm" @click="cancelOpen = true">Выключить процесс</UiButton>
          </div>
          <EconFormula v-if="activeRobot?.fig && open === `fleet:${activeProcess.process_code}`" :fig="activeRobot.fig" dark />

          <div v-if="cancelOpen" class="rescue">
            <div>
              <div class="h4">Прежде чем выключать — вот что сделает процесс прибыльным</div>
              <p class="caption">Ближайшие изменения, при которых покупка окупается за {{ report.horizon_years }} лет. Меру господдержки можно включить сразу, остальное откроется в what-if с подставленным значением.</p>
            </div>
            <div v-if="activeProcess.suggestions.length" class="rescue-grid">
              <div v-for="item in activeProcess.suggestions" :key="`${item.scope}:${item.key}`" class="fix" :class="item.scope">
                <span class="fix-scope">{{ SCOPE_LABEL[item.scope] }}</span>
                <span class="body-sm strong">{{ item.label }}</span>
                <span class="mono-md">{{ suggestionChange(item) }}</span>
                <span class="caption">окупаемость {{ item.payback != null ? figValue(item.payback, 'лет') : '—' }} · эффект {{ millions(item.effect) }}</span>
                <UiButton v-if="item.scope === 'subsidy'" size="sm" :disabled="subsidyBusy === item.key" @click="setSubsidies(item.key.split(','), true)">{{ item.key.includes(',') ? 'Включить меры' : 'Включить меру' }}</UiButton>
                <UiButton v-else :to="tuneTo(item)" size="sm">Открыть в what-if</UiButton>
              </div>
            </div>
            <p v-else class="body-sm">В допустимых границах коэффициентов и мер поддержки процесс не становится прибыльным.</p>
            <div class="d-actions">
              <UiButton variant="onGraphite" size="sm" @click="cancelOpen = false">Оставить процесс</UiButton>
              <UiButton variant="danger" size="sm" :disabled="readonly || disabling" @click="confirmCancel">{{ disabling ? 'Выключаем' : 'Всё равно выключить' }}</UiButton>
            </div>
            <p class="caption">Выключенный процесс попадёт в список неактивных с пометкой «невыгоден» — его можно вернуть в любой момент.</p>
            <p v-if="readonly" class="caption">В этом демо процесс не выключается. Допущения в what-if можно двигать, но они не сохранятся.</p>
            <p v-if="cancelError" class="caption d-err">{{ cancelError }}</p>
          </div>
        </div>
      </section>

      <EconSubsidies
        v-if="report.subsidies?.length"
        :items="report.subsidies"
        :horizon="report.horizon_years"
        :busy="subsidyBusy"
        :to="`/projects/${project.id}/what-if`"
        @toggle="toggleSubsidy"
      />
      <UiCallout v-if="subsidyError" tone="danger">{{ subsidyError }}</UiCallout>

      <section v-if="!processCode" class="fleet glass">
        <div class="c-in">
          <button type="button" class="c-head fleet-toggle" :aria-expanded="fleetOpen" @click="fleetOpen = !fleetOpen">
            <div>
              <div class="h3">Один робот на процесс</div>
              <div class="caption">{{ report.fleet.length }} процессов, {{ report.robots.toLocaleString('ru-RU') }} роботов в расчёте{{ withoutPrice ? `, ${withoutPrice} без цены не входят` : '' }}.</div>
            </div>
            <PhCaretDown :size="16" weight="bold" class="caret" :class="{ up: fleetOpen }" />
          </button>
          <ul v-show="fleetOpen" class="fleet-list">
            <li v-for="row in report.fleet" :key="row.process_code">
              <button type="button" class="fleet-row" :disabled="!row.fig" @click="row.fig && toggle(`fleet:${row.process_code}`)">
                <img :src="photoFor(row.image_url, row.name, row.process_code)" :alt="row.name">
                <span class="fleet-name">
                  <span class="caption">{{ row.process_name }}</span>
                  <span class="body-sm strong">{{ row.name }}</span>
                  <span v-if="row.note" class="caption">{{ row.note }}</span>
                </span>
                <span class="mono-sm">{{ row.included ? `${row.count_used?.toLocaleString('ru-RU')} шт.` : '—' }}</span>
                <span class="mono-sm">{{ rubles(row.cost_rub) }}</span>
                <PhCaretDown v-if="row.fig" :size="14" weight="bold" class="caret" :class="{ up: open === `fleet:${row.process_code}` }" />
              </button>
              <EconFormula v-if="row.fig && open === `fleet:${row.process_code}`" :fig="row.fig" />
            </li>
          </ul>
        </div>
      </section>

      <div v-if="scenarios.length" class="scen">
        <button
          v-for="item in scenarios"
          :key="item.key"
          type="button"
          class="sc"
          :class="picked === item.key ? 'glass-graphite glass-graphite-solid on' : 'glass'"
          @click="picked = item.key"
        >
          <span class="sc-in">
            <span class="sc-title"><span class="h3">{{ item.title }}</span><span class="caption">{{ item.subtitle }}</span></span>
            <span class="sc-nums">
              <span><span class="caption">CAPEX</span><span class="mono-md">{{ millions(item.capex.value) }}</span></span>
              <span><span class="caption">Затраты в год</span><span class="mono-md">{{ millions(item.annual_cost) }}</span></span>
              <span><span class="caption">Эффект в год</span><span class="mono-md">{{ item.key === 'asis' ? 'база' : millions(item.effect.value) }}</span></span>
              <span><span class="caption">Окупаемость</span><span class="mono-md">{{ item.key === 'asis' ? '—' : item.payback.value != null ? figValue(item.payback.value, 'лет') : 'нет' }}</span></span>
              <span><span class="caption">TCO за {{ report.horizon_years }} лет</span><span class="mono-md">{{ millions(item.tco.value) }}</span></span>
            </span>
            <span v-if="item.note" class="caption sc-note">{{ item.note }}</span>
            <span class="caption sc-note">Предварительная оценка</span>
          </span>
        </button>
      </div>

      <template v-if="scenario">
        <div class="top">
          <div class="result glass-graphite glass-graphite-solid">
            <div class="label">{{ scenario.title }} · окупаемость</div>
            <button type="button" class="payback" @click="toggle('payback')">
              <span class="payback-n">{{ scenario.key === 'asis' ? '—' : scenario.payback.value != null ? scenario.payback.value.toLocaleString('ru-RU', { maximumFractionDigits: 1, minimumFractionDigits: 1 }) : 'нет' }}</span>
              <span class="caption">{{ scenario.payback.value != null ? 'лет' : scenario.key === 'asis' ? 'точка сравнения' : 'эффект не покрывает вложения' }}</span>
              <PhCaretDown :size="14" weight="bold" class="caret" :class="{ up: open === 'payback' }" />
            </button>
            <p v-if="scenario.verdict" class="body-sm verdict">{{ scenario.verdict }}</p>
            <p class="caption prelim">{{ report.disclaimer }}</p>
            <EconFormula v-if="open === 'payback'" :fig="scenario.payback" dark />
            <div class="kpis">
              <button v-for="fig in kpis" :key="fig.key" type="button" class="kpi" :class="{ on: open === `kpi:${fig.key}` }" @click="toggle(`kpi:${fig.key}`)">
                <span class="caption">{{ fig.label }}</span>
                <span class="mono-lg">{{ fig.value == null ? '—' : fig.unit === '%' ? figValue(fig.value, '%') : millions(fig.value) }}</span>
              </button>
            </div>
            <template v-for="fig in kpis" :key="`f-${fig.key}`">
              <EconFormula v-if="open === `kpi:${fig.key}`" :fig="fig" dark />
            </template>
          </div>
          <div v-if="payrollFig" class="side glass">
            <div class="u-in">
              <div class="label">{{ activeProcess ? 'Доля процесса' : 'База сравнения' }}</div>
              <div class="h3">{{ payrollFig.label }}</div>
              <div class="mono-lg">{{ rubles(payrollFig.value) }}</div>
              <EconFormula :fig="payrollFig" />
            </div>
          </div>
        </div>

        <div class="cols">
          <section v-for="col in columns" :key="col.key" class="col glass">
            <div class="c-in">
              <button type="button" class="c-head c-btn" @click="toggle(`total:${col.key}`)">
                <span><span class="h3">{{ col.title }}</span><span class="caption block">{{ col.caption }}</span></span>
                <span class="mono-lg">{{ rubles(col.total.value) }}</span>
              </button>
              <EconFormula v-if="open === `total:${col.key}`" :fig="col.total" />
              <ul class="lines">
                <li v-for="line in col.lines" :key="line.key">
                  <button type="button" class="line" @click="toggle(`${col.key}:${line.key}`)">
                    <span class="body-sm" :class="{ 'cost-accent': isAccent(line.key, line.label) }">{{ line.label }}</span>
                    <span class="mono-md" :class="{ dim: !line.included, 'cost-accent': isAccent(line.key, line.label) }">{{ line.included ? rubles(line.value) : 'не входит' }}</span>
                    <PhCaretDown :size="12" weight="bold" class="caret" :class="{ up: open === `${col.key}:${line.key}` }" />
                  </button>
                  <EconFormula v-if="open === `${col.key}:${line.key}`" :fig="line" />
                </li>
                <li v-if="!col.lines.length" class="caption">Статей нет.</li>
              </ul>
            </div>
          </section>
        </div>
      </template>

      <section v-if="scenarios.length" class="chart glass">
        <div class="c-in">
          <div class="c-head">
            <div>
              <div class="h3">Затраты нарастающим итогом</div>
              <div class="caption">CAPEX + (OPEX + оставшийся ФОТ) × год, млн ₽. Без роботизации: ФОТ × год. Предварительная оценка.</div>
            </div>
          </div>
          <div class="tco-rows">
            <div v-for="row in chartYears" :key="row.year" class="tco-row">
              <span class="mono-sm y">{{ row.year }} г.</span>
              <span class="tco-bars">
                <span v-for="bar in row.bars" :key="bar.key" class="tb" :class="bar.key" :style="{ width: `${Math.max(2, (bar.value / chartMax) * 100)}%` }"><i>{{ (bar.value / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: 0 }) }}</i></span>
              </span>
            </div>
          </div>
          <div class="legend caption"><span><i class="sw asis" /> без роботизации</span><span><i class="sw purchase" /> покупка</span><span><i class="sw raas" /> аренда</span></div>
        </div>
      </section>

      <section class="coefs glass">
        <div class="c-in">
          <div class="c-head">
            <div><div class="h3">Предпосылки расчёта</div><div class="caption">{{ activeProcess ? 'Общие коэффициенты парка. Свои для выбранного процесса задаются на шаге what-if.' : 'Стандарт задаётся в админке, значение проекта — на шаге what-if' }}</div></div>
            <UiButton :to="`/projects/${project.id}/what-if`" variant="secondary" size="sm">Изменить</UiButton>
          </div>
          <div v-for="group in groups" :key="group.id" class="coef-group">
            <div class="label">{{ group.label }}</div>
            <div class="coef-list">
              <div v-for="item in group.items" :key="item.key" class="coef" :class="{ open: openParam === item.key }">
                <button type="button" class="coef-btn" @click="openParam = openParam === item.key ? null : item.key">
                  <UiTex :tex="item.symbol" class="sym" />
                  <span class="body-sm strong" :class="{ 'cost-accent': isAccent(item.key, item.label) }">{{ item.label }}</span>
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
.fleet-toggle { width: 100%; text-align: left; align-items: center; }
.c-head .mono-lg { color: var(--ink-strong); white-space: nowrap; flex: none; font-size: 20px; }
.c-btn { width: 100%; text-align: left; }
.block { display: block; }
.caret { color: var(--ink-faint); transition: transform var(--dur-fast) var(--ease); flex: none; }
.caret.up { transform: rotate(180deg); }

.fleet-list { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.fleet-list li { display: grid; gap: 8px; }
.fleet-row { width: 100%; display: grid; grid-template-columns: 64px minmax(0, 1fr) auto auto 14px; gap: 12px; align-items: center; text-align: left; padding: 4px; border-radius: 12px; }
.fleet-row:not(:disabled):hover { background: rgba(255, 255, 255, 0.55); }
.fleet-row img { width: 64px; height: 50px; object-fit: contain; border-radius: 10px; background: #e9eeec; }
.fleet-name { display: grid; gap: 2px; min-width: 0; }
.fleet-name .body-sm { color: var(--ink-strong); }

.inactive .count { display: inline-flex; align-items: center; justify-content: center; min-width: 24px; height: 22px; padding: 0 6px; margin-left: 6px; border-radius: 999px; background: rgba(15, 20, 19, 0.07); color: var(--ink-muted); vertical-align: 3px; }
.off-list { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
.off { display: flex; justify-content: space-between; align-items: center; gap: 16px; padding: 12px 14px; border-radius: 14px; background: rgba(255, 255, 255, 0.5); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.off.loss { box-shadow: inset 3px 0 0 rgba(179, 42, 38, 0.6), inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.off-copy { display: grid; gap: 4px; min-width: 0; }
.off-title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.off-title .body-sm { color: var(--ink-muted); text-decoration: line-through; text-decoration-color: rgba(15, 20, 19, 0.3); }
.off-tag { font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 999px; background: rgba(15, 20, 19, 0.06); color: var(--ink-muted); white-space: nowrap; }
.off-tag.loss { background: var(--state-danger-tint); color: var(--state-danger); }
.d-err-light { color: var(--state-danger); margin: 0; }
.detail { border-radius: var(--radius-xl); }
.d-in { position: relative; z-index: 1; padding: var(--space-6); display: grid; gap: var(--space-4); }
.d-main { display: grid; grid-template-columns: 96px minmax(0, 1fr) auto; gap: var(--space-5); align-items: center; }
.d-photo { width: 96px; height: 76px; object-fit: contain; border-radius: 14px; background: rgba(255, 255, 255, 0.92); }
.d-copy { display: grid; gap: 4px; min-width: 0; }
.d-copy .h3 { color: var(--ink-on-graphite); }
.d-copy .caption, .d-kpi .caption, .d-note { color: var(--ink-muted-graphite); }
.d-kpi { display: grid; justify-items: end; gap: 2px; }
.d-pay { font-family: var(--font-mono); font-size: 44px; line-height: 1; letter-spacing: -0.04em; color: var(--brand-300); }
.d-pay.bad { color: #ff8a80; }
.d-reason { margin: 0; padding: 10px 14px; border-radius: 12px; background: rgba(98, 232, 174, 0.1); color: var(--brand-300); }
.d-reason.bad { background: rgba(255, 138, 128, 0.12); color: #ffb4ab; }
.d-note { margin: 0; }
.d-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.d-err { color: #ffb4ab; margin: 0; }
.rescue { display: grid; gap: var(--space-4); padding-top: var(--space-4); border-top: 1px solid rgba(255, 255, 255, 0.1); }
.rescue .h4 { margin: 0; color: var(--ink-on-graphite); }
.rescue p { margin: 4px 0 0; color: var(--ink-muted-graphite); }
.rescue-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; }
.fix { display: grid; gap: 6px; align-content: start; padding: 14px; border-radius: var(--radius-lg); background: rgba(255, 255, 255, 0.06); box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08); }
.fix .body-sm { color: var(--ink-on-graphite); }
.fix .mono-md { color: var(--brand-300); }
.fix .caption { color: var(--ink-muted-graphite); }
.fix :deep(.btn) { justify-self: start; margin-top: 4px; }
.fix-scope { justify-self: start; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 999px; background: rgba(255, 255, 255, 0.1); color: var(--ink-muted-graphite); }
.fix.subsidy { box-shadow: inset 0 0 0 1px rgba(98, 232, 174, 0.35); }
.fix.subsidy .fix-scope { background: rgba(98, 232, 174, 0.16); color: var(--brand-300); }

.scen { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4); }
.sc { border-radius: var(--radius-xl); text-align: left; transition: transform var(--dur-mid) var(--ease); }
.sc:hover { transform: translateY(-2px); }
.sc-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: var(--space-4); }
.sc-title { display: grid; gap: 4px; }
.sc-nums { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 14px; padding-top: 12px; border-top: 1px solid rgba(15, 20, 19, 0.08); }
.sc-nums > span { display: grid; gap: 2px; }
.sc-nums .mono-md { color: var(--ink-strong); }
.on .sc-nums { border-top-color: rgba(255, 255, 255, 0.12); }
.on .sc-nums .mono-md, .on .h3 { color: var(--ink-on-graphite); }
.on .caption { color: var(--ink-muted-graphite); }
.sc-note { display: block; }

.top { display: grid; grid-template-columns: minmax(0, 7fr) minmax(0, 5fr); gap: var(--space-4); align-items: start; }
.result { padding: var(--space-6); display: grid; gap: var(--space-4); }
.payback { display: flex; align-items: baseline; gap: 10px; text-align: left; }
.payback-n { font-family: var(--font-mono); font-size: 64px; line-height: 0.9; letter-spacing: -0.04em; color: #fff; }
.payback .caption { color: var(--ink-muted-graphite); }
.verdict { color: var(--brand-300); margin: 0; }
.prelim { color: #f0ad45; margin: 0; }
.kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-3); padding-top: var(--space-4); border-top: 1px solid rgba(255, 255, 255, 0.1); }
.kpi { display: grid; gap: 4px; text-align: left; padding: 8px 10px; border-radius: 12px; }
.kpi:hover, .kpi.on { background: rgba(255, 255, 255, 0.06); }
.kpi .caption { color: var(--ink-muted-graphite); }
.kpi .mono-lg { color: var(--brand-300); font-size: 22px; line-height: 1.15; overflow-wrap: anywhere; }
.side .u-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: 10px; }
.side .mono-lg { color: var(--ink-strong); font-size: 22px; }

.cols { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4); align-items: start; }
.lines { display: grid; margin: 0; padding: 0; list-style: none; }
.lines li { display: grid; gap: 8px; padding: 8px 0; border-top: 1px solid rgba(15, 20, 19, 0.06); }
.lines li:first-child { border-top: 0; }
.line { width: 100%; display: grid; grid-template-columns: minmax(0, 1fr) auto 12px; gap: 10px; align-items: center; text-align: left; }
.line .mono-md { color: var(--ink-strong); white-space: nowrap; }
.dim { color: var(--ink-muted) !important; }

.tco-rows { display: grid; gap: 8px; }
.tco-row { display: grid; grid-template-columns: 40px 1fr; gap: 8px; align-items: center; }
.tco-bars { display: grid; gap: 2px; }
.tb { display: flex; align-items: center; justify-content: flex-end; height: 12px; border-radius: 3px; min-width: 28px; transition: width var(--dur-mid) var(--ease); }
.tb i { font-style: normal; font-family: var(--font-mono); font-size: 9px; color: #fff; padding-right: 4px; line-height: 1; }
.tb.asis, .sw.asis { background: var(--border-strong); }
.tb.purchase, .sw.purchase { background: var(--brand-600); }
.tb.raas, .sw.raas { background: var(--state-warn); }
.legend { display: flex; gap: 14px; flex-wrap: wrap; }
.sw { display: inline-block; width: 10px; height: 10px; border-radius: 3px; vertical-align: -1px; margin-right: 4px; }
.y { color: var(--ink-muted); }

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
  .top, .cols, .scen { grid-template-columns: 1fr; }
  .coef-btn { grid-template-columns: 70px 1fr auto 14px; }
  .coef-btn :deep(.badge) { display: none; }
  .coef-body { padding-left: 14px; grid-template-columns: 1fr; }
}
@media (max-width: 720px) {
  .fleet-row { grid-template-columns: 64px minmax(0, 1fr) 14px; }
  .fleet-row .mono-sm { grid-column: 2; }
  .kpis { grid-template-columns: 1fr; }
  .payback-n { font-size: 48px; }
  .d-main { grid-template-columns: 72px minmax(0, 1fr); }
  .d-photo { width: 72px; height: 58px; }
  .d-kpi { grid-column: 1 / -1; justify-items: start; }
}
</style>
