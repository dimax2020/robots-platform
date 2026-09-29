<script setup lang="ts">
import { PhPrinter, PhFileXls, PhFileCsv, PhImage, PhWarning, PhArrowRight } from '@phosphor-icons/vue'
import { objectTypeImage, objectTypeLabel } from '~/data/projects'
import { downloadDataUrl, downloadText, toCsv, toExcelXml } from '~/utils/exportTables'
import { fetchErrorMessage } from '~/utils/errors'
import { useProjectReport } from '~/composables/useProjectReport'
import { figValue, millions, SOURCE_TONE } from '~/composables/usePlatformEconomy'
import { isAccent } from '~/utils/accent'
import { Simulation } from '~/sim/engine'
import { emptyLayout, placeProcess, placeShell, processReady } from '~/sim/templates'
import type PlanEditor from '~/components/PlanEditor.vue'
import type { WorkerResponse } from '~/sim/worker'
import type { Layout, ProcessStats, SimProcess, Visibility } from '~/sim/types'

const route = useRoute()
const id = computed(() => route.params.id as string)
const doc = useProjectReport(id)
const project = computed(() => doc.project.value)
useHead({ title: () => `Отчёт · ${project.value?.name ?? 'проект'}` })

const PALETTE = ['#1f7a5a', '#175fb0', '#b2582b', '#6b5bd6', '#c0417a', '#2f8f9d', '#8a6d1d', '#4f6b2a']
const editor = ref<InstanceType<typeof PlanEditor> | null>(null)
const shot = ref('')
const shotNote = ref('')
const vizCheck = ref<WorkerResponse | null>(null)
const vizChecking = ref(false)
const vizLayout = ref<Layout | null>(null)
const vizFloorId = ref('')
const vizKey = ref(0)
const emptyVisibility: Record<string, Visibility> = {}

const coverSrc = computed(() => project.value ? objectTypeImage[project.value.objectType] : objectTypeImage.warehouse)
const coverTitle = ref<HTMLElement | null>(null)

const printing = ref(false)
const fitCoverTitle = () => {
  if (printing.value) return
  const el = coverTitle.value
  if (!el) return
  el.style.fontSize = ''
  const max = 42
  const min = 16
  let size = max
  el.style.whiteSpace = 'nowrap'
  el.style.fontSize = `${size}px`
  while (size > min && el.scrollWidth > el.clientWidth + 1) {
    size -= 1
    el.style.fontSize = `${size}px`
  }
}

const print = () => {
  if (!import.meta.client) return
  const prev = document.title
  document.title = project.value?.name ?? 'Отчёт'
  printing.value = true
  if (coverTitle.value) {
    coverTitle.value.style.fontSize = ''
    coverTitle.value.style.whiteSpace = ''
  }
  const restore = () => {
    printing.value = false
    document.title = prev
    fitCoverTitle()
    window.removeEventListener('afterprint', restore)
  }
  window.addEventListener('afterprint', restore)
  window.print()
}

watch(() => [project.value?.name, doc.ready.value], () => nextTick(fitCoverTitle))

onMounted(() => {
  nextTick(fitCoverTitle)
  if (typeof ResizeObserver === 'undefined') return
  const box = coverTitle.value?.parentElement
  if (!box) return
  const ro = new ResizeObserver(() => fitCoverTitle())
  ro.observe(box)
  onBeforeUnmount(() => ro.disconnect())
})

const blocked = computed(() => !doc.ready.value)
const blockTitle = computed(() => {
  const step = doc.missing.value[0]
  return step ? `${step.text} Выгрузка пустого файла не стартует.` : 'Отчёт ещё не собран.'
})

const exportTables = (kind: 'xlsx' | 'csv') => {
  if (blocked.value || !project.value) return
  const sheets = [...doc.sheets.value]
  if (vizCheck.value) {
    const stats = vizCheck.value.stats.processes
    const keys = [...new Set(stats.flatMap((row) => Object.keys(row)))]
    sheets.push({
      name: 'Смена',
      rows: [
        ['Показатель', ...stats.map((row) => row.name)],
        ...keys.filter((key) => key !== 'code').map((key) => [STAT_LABEL[key] ?? key, ...stats.map((row) => formatStat(key, (row as unknown as Record<string, unknown>)[key], row.unit))]),
        ['Минимум по модели, шт.', ...stats.map((row) => vizCheck.value?.minimal[row.code] == null ? '—' : String(vizCheck.value?.minimal[row.code]))],
      ],
    })
  }
  if (!sheets.length) return
  const stem = doc.stem.value
  if (kind === 'csv') downloadText(`${stem}.csv`, 'text/csv;charset=utf-8', toCsv(sheets, doc.disclaimer.value))
  else downloadText(`${stem}.xls`, 'application/vnd.ms-excel', toExcelXml(sheets, doc.disclaimer.value))
}

const downloadPlan = () => {
  if (shot.value) {
    downloadDataUrl(`схема-${project.value?.name ?? 'план'}.png`, shot.value)
    return
  }
  void navigateTo(`/projects/${id.value}/plan`)
}

const drawn = (layout: Layout) => layout.floors.some((floor) => floor.stations.length || floor.zones.length || floor.blocks.length)

/** На кадре отчёта парк ужимается: иначе десятки процессов и сотни станций сливаются в одну простыню. */
const frameProcess = (proc: SimProcess): SimProcess => ({
  ...proc,
  requiredPerHour: Math.min(proc.requiredPerHour, 8),
  robot: { ...proc.robot, count: Math.min(Math.max(proc.robot.count, 1), 3) },
})

const plain = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T

const vizFrame = ref<SimProcess[]>([])

const assembleLayout = () => {
  const processes = doc.sceneProcesses.value.map(frameProcess)
  const saved = doc.savedLayout.value
  const site = { ...doc.site.value, clean_area_m2: 220 }
  const layout = saved && drawn(saved) ? plain(saved) : emptyLayout(doc.site.value)
  const auto = !(saved && drawn(saved))
  if (!drawn(layout)) placeShell(layout)
  const floorId = layout.floors[0]?.id ?? ''
  for (const proc of processes) {
    if (proc.kind === 'none' || !floorId) continue
    if (!processReady(layout, proc)) placeProcess(layout, floorId, proc, site)
  }
  vizFrame.value = processes
  vizLayout.value = layout
  vizFloorId.value = floorId
  vizKey.value += 1
  shot.value = ''
  shotNote.value = auto
    ? 'Кадр смены собран платформой автоматически: пол, стеллажи и станции расставлены по параметрам объекта, роботы выбранного парка поставлены на маршруты.'
    : 'Кадр смены снят со сохранённой схемы объекта. Роботы выбранного парка расставлены по станциям автоматически.'
}

watch(() => [doc.ready.value, doc.sceneProcesses.value.map((item) => item.code).join('|'), doc.savedLayout.value?.floors.length ?? 0], () => {
  if (!doc.ready.value) return
  assembleLayout()
}, { immediate: true })

const vizProcesses = computed(() => Object.fromEntries(vizFrame.value.map((item) => [item.code, item])) as Record<string, SimProcess>)
const vizColors = computed(() => Object.fromEntries(vizFrame.value.map((item, index) => [item.code, PALETTE[index % PALETTE.length]!])))
const legend = computed(() => doc.robots.value.map((robot, index) => ({
  key: robot.key,
  name: robot.name,
  process: robot.process,
  color: PALETTE[index % PALETTE.length]!,
})))

const onPlanReady = () => {
  nextTick(() => {
    const box = editor.value
    const layout = vizLayout.value
    if (!box || !layout) return
    box.fit()
    const active = vizFrame.value.filter((proc) => proc.kind !== 'none' && processReady(layout, proc))
    try {
      if (active.length) {
        const sim = new Simulation({
          layout: plain(layout),
          processes: plain(active),
          mode: 'normal',
          peak: 1,
          failureShare: 0,
          durationS: 8 * 3600,
          seed: 20260926,
        })
        sim.advance(12 * 60)
        box.drawRobots(sim.views())
      }
    } catch {
      shotNote.value = 'Схему площадки собрать удалось, роботы на кадр не встали: для части процессов нет проходимого маршрута.'
    }
    window.setTimeout(() => {
      box.fit()
      shot.value = box.exportPng() || shot.value
    }, 80)
    runShiftCheck(layout)
  })
}

let worker: Worker | null = null
const runShiftCheck = (layout: Layout) => {
  if (import.meta.server) return
  const processes = doc.sceneProcesses.value.filter((proc) => proc.kind !== 'none' && processReady(layout, proc))
  if (!processes.length) { vizCheck.value = null; return }
  const hours = Number(doc.site.value.shift_hours) || 8
  vizChecking.value = true
  worker ??= new Worker(new URL('../../../sim/worker.ts', import.meta.url), { type: 'module' })
  const id = Date.now()
  worker.onmessage = (event: MessageEvent<WorkerResponse>) => {
    if (event.data.id !== id) return
    vizCheck.value = event.data
    vizChecking.value = false
  }
  worker.onerror = () => { vizChecking.value = false }
  worker.postMessage({
    id,
    config: {
      layout: plain(layout),
      processes: plain(processes),
      mode: 'normal',
      peak: 1,
      failureShare: 0,
      durationS: hours * 3600,
      seed: 20260926,
    },
  })
}

const STAT_LABEL: Record<string, string> = {
  robots: 'Роботов в модели',
  active: 'В строю',
  offline: 'Не в строю',
  queued: 'В очереди',
  requiredPerHour: 'Нужно в час',
  donePerHour: 'Выполнено в час',
  done: 'Выполнено за смену',
  backlog: 'Не взято к концу смены',
  utilization: 'Загрузка',
  chargingShare: 'На зарядке',
  avgWaitS: 'Среднее ожидание',
  maxQueue: 'Максимальная очередь',
  avgCycleS: 'Средний цикл',
  confirmed: 'Подтверждает расчёт количества',
}
const STAT_SKIP = new Set(['code', 'name', 'unit', 'notes'])
const formatStat = (key: string, value: unknown, unit: string) => {
  if (typeof value === 'boolean') return value ? 'да' : 'нет'
  if (value == null || value === '') return '—'
  if (typeof value !== 'number') return String(value)
  if (key === 'utilization' || key === 'chargingShare') return `${Math.round(value * 100)}%`
  if (key === 'avgWaitS' || key === 'avgCycleS') return `${value.toLocaleString('ru-RU', { maximumFractionDigits: 0 })} с`
  if (key.endsWith('PerHour')) return `${value.toLocaleString('ru-RU', { maximumFractionDigits: value >= 10 ? 1 : 2 })} ${unit}`.trim()
  return value.toLocaleString('ru-RU', { maximumFractionDigits: 1 })
}
const statRows = (row: ProcessStats) => Object.entries(row)
  .filter(([key]) => !STAT_SKIP.has(key))
  .map(([key, value]) => ({ key, label: STAT_LABEL[key] ?? key, value: formatStat(key, value, row.unit) }))
const sourceText = (source: string) => ({ norm: 'стандарт', project: 'значение проекта', site: 'площадка', card: 'карточка', fleet: 'парк', calc: 'расчёт' } as Record<string, string>)[source] ?? source
/* Чувствительность как «торнадо»: полоса — куда уходит годовой эффект покупки при сдвиге допущения на ±20%,
   центр — текущий эффект. Шкала общая для всех строк, самые влиятельные допущения сверху. */
const paybackText = (value: number | null) => value == null ? 'не окупается' : figValue(value, 'лет')
const plainNum = (value: number) => value.toLocaleString('ru-RU', { maximumFractionDigits: Math.abs(value) < 10 ? 2 : 1 })
const signedMillions = (value: number) => `${value > 0 ? '+' : value < 0 ? '−' : ''}${millions(Math.abs(value))}`
const sensRows = computed(() => {
  const rows = doc.econ.value?.sensitivity ?? []
  const spread = Math.max(1, ...rows.flatMap((row) => [Math.abs(row.effect_low - row.effect), Math.abs(row.effect_high - row.effect)]))
  const segment = (value: number, base: number) => {
    const edge = 50 + ((value - base) / spread) * 50
    return { left: `${Math.min(edge, 50)}%`, width: `${Math.max(Math.abs(edge - 50), 0.6)}%`, good: value >= base }
  }
  return [...rows]
    .sort((a, b) => Math.abs(b.effect_high - b.effect_low) - Math.abs(a.effect_high - a.effect_low))
    .map((row) => {
      const low = paybackText(row.payback_low)
      const high = paybackText(row.payback_high)
      return {
        key: row.key,
        label: row.label,
        now: figValue(row.value, row.unit),
        range: `${plainNum(row.low_value)} … ${plainNum(row.high_value)}`,
        down: segment(row.effect_low, row.effect),
        up: segment(row.effect_high, row.effect),
        ends: [
          { key: 'down', text: `−20%: ${signedMillions(row.effect_low - row.effect)}`, value: row.effect_low },
          { key: 'up', text: `+20%: ${signedMillions(row.effect_high - row.effect)}`, value: row.effect_high },
        ].sort((a, b) => a.value - b.value),
        payback: low === high ? low : `${low} … ${high}`,
      }
    })
})
const sensBase = computed(() => {
  const row = doc.econ.value?.sensitivity[0]
  return row ? { effect: millions(row.effect), payback: paybackText(row.payback) } : null
})

const chartLabel = (value: number) => (value / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: 0 })
const robotGloss = computed(() => {
  const seen = new Set<string>()
  const rows: { label: string; note: string }[] = []
  for (const robot of doc.robots.value) {
    for (const item of robot.fig?.vars ?? []) {
      const note = item.note?.trim()
      if (!note) continue
      const key = `${item.label}\u0000${note}`
      if (seen.has(key)) continue
      seen.add(key)
      rows.push({ label: item.label, note })
    }
  }
  return rows
})
</script>

<template>
  <ProjectShell
    v-if="project"
    :project="project"
    current="report"
    title="Отчёт"
    lead="Три сценария экономики, парк с характеристиками и кадр работы роботов на объекте."
    dense
  >
    <template v-if="!doc.closed.value" #actions>
      <UiButton variant="secondary" class="no-print" :disabled="blocked" :title="blocked ? blockTitle : undefined" @click="print">
        <template #icon><PhPrinter :size="16" weight="bold" /></template>Печать в PDF
      </UiButton>
      <UiButton variant="secondary" class="no-print" :disabled="blocked" :title="blocked ? blockTitle : undefined" @click="exportTables('xlsx')">
        <template #icon><PhFileXls :size="16" weight="duotone" /></template>Excel
      </UiButton>
      <UiButton variant="secondary" class="no-print" :disabled="blocked" :title="blocked ? blockTitle : undefined" @click="exportTables('csv')">
        <template #icon><PhFileCsv :size="16" weight="duotone" /></template>CSV
      </UiButton>
      <UiButton variant="secondary" class="no-print" :disabled="!shot" @click="downloadPlan">
        <template #icon><PhImage :size="16" weight="duotone" /></template>Схема
      </UiButton>
    </template>

    <UiCallout v-if="doc.role.value === 'guest'" class="no-print" tone="info">Это демо-отчёт. Гость может открыть и распечатать его, сохранения собственного проекта у гостя нет.</UiCallout>
    <UiCallout v-if="doc.closed.value" class="no-print" tone="info" title="Урезанный путь">Экраны экономики, what-if, плана и отчёта для аэропорта и медучреждения в MVP не собираются. Доступны параметры, подбор и сравнение.</UiCallout>
    <UiCallout v-for="step in doc.missing.value" :key="step.id" class="no-print" tone="warn" :title="`Не пройден шаг «${step.label}»`">
      {{ step.text }} <NuxtLink :to="step.to" class="go">Перейти к шагу <PhArrowRight :size="14" weight="bold" /></NuxtLink>
    </UiCallout>

    <section v-if="doc.pending.value && !doc.ready.value && !doc.closed.value" class="waiting glass"><div class="h3">Собираем отчёт</div></section>
    <UiCallout v-else-if="!doc.ready.value && (doc.failure.value || doc.error.value)" class="no-print" tone="danger" title="Отчёт не собрался">{{ doc.failure.value || fetchErrorMessage(doc.error.value, 'Сервер не ответил.') }}</UiCallout>

    <article v-if="doc.ready.value" class="report" v-reveal>
      <section class="cover">
        <div class="cover-top">
          <Logo :size="34" mint wordmark on-graphite />
          <span class="cover-mark">Предварительная экспресс-оценка</span>
        </div>
        <div class="cover-title">
          <p class="cover-kicker">{{ objectTypeLabel[project.objectType] }} · {{ project.industry }}</p>
          <h2 ref="coverTitle" class="cover-h">{{ project.name }}</h2>
        </div>
        <figure class="cover-hero">
          <img :src="coverSrc" :alt="objectTypeLabel[project.objectType]">
        </figure>
        <footer class="cover-foot">
          <span>{{ doc.today.value }}</span>
          <span>каталог {{ project.catalogVersion }}</span>
          <span>модель {{ project.modelVersion }}</span>
        </footer>
      </section>

      <div class="r-in">
        <div class="disclaimer">
          <PhWarning :size="18" weight="fill" />
          <p><span class="strong">{{ doc.disclaimer.value }}</span> Числа, формулы и допущения взяты из расчёта экономики и what-if. Если в модели появится новое поле или изменится формула, отчёт покажет их так же, как экран расчёта.</p>
        </div>

        <section v-if="doc.advice.value" class="advice" :class="{ asis: doc.advice.value.rows.find((row) => row.winner)?.key === 'asis' }">
          <p class="advice-kicker">Что выгоднее</p>
          <h3>{{ doc.advice.value.headline }}</h3>
          <p>{{ doc.advice.value.detail }}</p>
          <table class="table advice-table">
            <thead>
              <tr><th>Сценарий</th><th class="num">TCO</th><th class="num">К лучшему</th><th class="num">Эффект</th><th class="num">Окупаемость</th></tr>
            </thead>
            <tbody>
              <tr v-for="row in doc.advice.value.rows" :key="row.key" :class="{ best: row.winner }">
                <td><b>{{ row.title }}</b></td>
                <td class="num">{{ row.tco }}</td>
                <td class="num">{{ row.gap }}</td>
                <td class="num">{{ row.effect }}</td>
                <td class="num">{{ row.payback }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section class="r-sec">
          <header class="sec-head">
            <span class="sec-n">01</span>
            <div>
              <h3 class="sec-title">Сводка сценариев</h3>
              <p class="sec-lead">Один парк в трёх режимах владения. Ниже — те же величины, что на экране экономики.</p>
            </div>
          </header>
          <p v-if="doc.payroll.value" class="base">{{ doc.payroll.value.label }}: <b>{{ doc.payroll.value.value }}</b> в год. От этой суммы считаются эффект и сравнение затрат.</p>
          <div class="scenes">
            <article v-for="s in doc.scenarios.value" :key="s.key" class="scene" :class="[s.key, { best: s.highlight }]">
              <div class="scene-top">
                <div>
                  <h4 class="scene-name">{{ s.title }}</h4>
                  <p class="scene-sub">{{ s.subtitle }}</p>
                </div>
                <span v-if="s.highlight" class="scene-band">ниже TCO</span>
              </div>
              <dl class="metrics">
                <div v-for="cell in s.metrics" :key="cell.label"><dt>{{ cell.label }}</dt><dd>{{ cell.value }}</dd></div>
              </dl>
              <p v-if="s.verdict" class="scene-verdict">{{ s.verdict }}</p>
              <p v-if="s.note" class="note">{{ s.note }}</p>
            </article>
          </div>
          <table class="table scenes-print">
            <thead>
              <tr>
                <th>Сценарий</th>
                <th class="num">CAPEX</th>
                <th class="num">Затраты в год</th>
                <th class="num">Эффект</th>
                <th class="num">Окуп.</th>
                <th class="num">TCO</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="s in doc.scenarios.value" :key="`p-${s.key}`" :class="{ best: s.highlight }">
                <td><b>{{ s.title }}</b><div class="caption">{{ s.subtitle }}</div></td>
                <td class="num">{{ s.capex }}</td>
                <td class="num">{{ s.opex }}</td>
                <td class="num">{{ s.effect }}</td>
                <td class="num">{{ s.metrics[3]?.value }}</td>
                <td class="num">{{ s.metrics[4]?.value }}</td>
              </tr>
            </tbody>
          </table>

          <div v-if="doc.chart.value.years.length" class="chart">
            <div class="label">Затраты нарастающим итогом</div>
            <p class="note">CAPEX + (OPEX + оставшийся ФОТ) × год, млн ₽. Без роботизации: ФОТ × год. Горизонт {{ doc.chart.value.horizon }} лет.</p>
            <div class="tco-rows">
              <div v-for="row in doc.chart.value.years" :key="row.year" class="tco-row">
                <span class="y">{{ row.year }} г.</span>
                <span class="tco-bars">
                  <span v-for="bar in row.bars" :key="bar.key" class="tb" :class="bar.key" :style="{ width: `${Math.max(2, (bar.value / doc.chart.value.max) * 100)}%` }"><i>{{ chartLabel(bar.value) }}</i></span>
                </span>
              </div>
            </div>
            <div class="legend">
              <span><i class="sw asis" /> Без роботизации</span>
              <span><i class="sw purchase" /> Покупка</span>
              <span><i class="sw raas" /> Аренда (RaaS)</span>
            </div>
          </div>
        </section>

        <section class="r-sec">
          <header class="sec-head">
            <span class="sec-n">02</span>
            <div>
              <h3 class="sec-title">Формулы и подстановка</h3>
              <p class="sec-lead">Каждая величина экономики: формула, числа и источник. Список строится по ответу расчёта, а не по фиксированному набору статей.</p>
            </div>
          </header>
          <article v-for="block in doc.formulas.value" :key="block.key" class="formula-block">
            <h4>{{ block.title }}</h4>
            <div class="formula-grid">
              <template v-for="(part, index) in block.parts" :key="`${block.key}-${part.title}-${index}`">
                <div v-if="part.total" class="formula-tile">
                  <div class="formula-line-h" :class="{ 'cost-accent': isAccent(part.total.key, part.total.label) }"><span>{{ part.total.label }}</span><b>{{ figValue(part.total.value, part.total.unit) }}</b></div>
                  <EconFormula dense :fig="part.total" />
                </div>
                <div v-for="line in part.lines" :key="line.key" class="formula-tile">
                  <div class="formula-line-h" :class="{ 'cost-accent': isAccent(line.key, line.label) }"><span>{{ line.label }}</span><b>{{ line.included ? figValue(line.value, line.unit) : 'не входит' }}</b></div>
                  <EconFormula dense :fig="line" />
                </div>
              </template>
            </div>
          </article>
        </section>

        <section class="r-sec">
          <header class="sec-head">
            <span class="sec-n">03</span>
            <div>
              <h3 class="sec-title">Роботы парка</h3>
              <p class="sec-lead">Один выбранный робот на процесс: фото, количество, числовые ТТХ и подстановка своей формулы. Общие пояснения к величинам — один раз над списком.</p>
            </div>
          </header>
          <ul v-if="robotGloss.length" class="robot-gloss">
            <li v-for="item in robotGloss" :key="`${item.label}-${item.note}`"><b>{{ item.label }}.</b> {{ item.note }}</li>
          </ul>
          <div v-if="doc.robots.value.length" class="robots">
            <article v-for="robot in doc.robots.value" :key="robot.key" class="robot">
              <img :src="robot.image" :alt="robot.name">
              <div class="robot-body">
                <p class="caption">{{ robot.process }}</p>
                <h4>{{ robot.name }}</h4>
                <p class="robot-meta">{{ robot.count }} · {{ robot.price }}<span v-if="robot.cost !== '—'"> · парк {{ robot.cost }}</span></p>
                <dl v-if="robot.specs.length" class="specs">
                  <div v-for="spec in robot.specs" :key="spec.label"><dt>{{ spec.label }}</dt><dd>{{ spec.value }}</dd></div>
                </dl>
                <p v-else class="note">В карточке нет числовых ТТХ.</p>
                <p v-if="robot.note" class="note">{{ robot.note }}</p>
                <EconFormula v-if="robot.fig" mini brief :fig="robot.fig" />
              </div>
            </article>
          </div>
          <p v-else class="note">В расчёт не вошёл ни один робот.</p>
        </section>

        <section class="r-sec">
          <header class="sec-head">
            <span class="sec-n">04</span>
            <div>
              <h3 class="sec-title">Визуализация</h3>
              <p class="sec-lead">{{ shotNote }} На кадре до трёх машин каждого процесса: так видны маршруты, а не вся численность парка.</p>
            </div>
          </header>
          <figure class="viz">
            <img v-if="shot" :src="shot" alt="Автоматически собранная схема работы роботов на объекте">
            <div v-else class="viz-wait">Собираем схему и расставляем роботов…</div>
          </figure>
          <ul v-if="legend.length" class="legend robots-legend">
            <li v-for="item in legend" :key="item.key"><i :style="{ background: item.color }" />{{ item.process }} · {{ item.name }}</li>
          </ul>
          <p v-if="vizChecking" class="note">Считаем смену целиком: те же показатели, что в мониторе визуализации.</p>
          <div v-if="vizCheck" class="shift">
            <article v-for="row in vizCheck.stats.processes" :key="row.code" class="shift-card">
              <header>
                <h4>{{ row.name }}</h4>
                <span class="shift-flag" :class="{ ok: row.confirmed }">{{ row.confirmed ? 'подтверждает расчёт' : 'не подтверждает расчёт' }}</span>
              </header>
              <p v-if="doc.sceneProcesses.value.find((proc) => proc.code === row.code)?.basis" class="note">{{ doc.sceneProcesses.value.find((proc) => proc.code === row.code)?.basis }}</p>
              <dl>
                <div v-for="cell in statRows(row)" :key="cell.key"><dt>{{ cell.label }}</dt><dd>{{ cell.value }}</dd></div>
                <div><dt>Минимум по модели</dt><dd>{{ vizCheck.minimal[row.code] == null ? 'не найден' : `${vizCheck.minimal[row.code]} шт.` }}</dd></div>
              </dl>
              <ul v-if="row.notes.length">
                <li v-for="note in row.notes" :key="note">{{ note }}</li>
              </ul>
            </article>
          </div>
        </section>

        <section v-if="doc.paramGroups.value.length" class="r-sec">
          <header class="sec-head">
            <span class="sec-n">05</span>
            <div>
              <h3 class="sec-title">Допущения what-if</h3>
              <p class="sec-lead">Все коэффициенты расчёта: значение, стандарт, источник и обоснование. Новая группа или поле из админки появятся здесь сами.</p>
            </div>
          </header>
          <div v-for="group in doc.paramGroups.value" :key="group.id" class="assume">
            <div class="label">{{ group.label }}</div>
            <article v-for="item in group.items" :key="item.key" class="assume-row">
              <div class="assume-h">
                <UiTex :tex="item.symbol" class="assume-sym" />
                <span class="strong" :class="{ 'cost-accent': isAccent(item.key, item.label) }">{{ item.label }}</span>
                <b>{{ item.value.toLocaleString('ru-RU') }} {{ item.unit }}</b>
                <UiBadge :tone="SOURCE_TONE[item.source]" size="sm">{{ sourceText(item.source) }}</UiBadge>
              </div>
              <dl>
                <div><dt>Стандарт</dt><dd>{{ item.standard.toLocaleString('ru-RU') }} {{ item.unit }}</dd></div>
                <div><dt>Диапазон</dt><dd>{{ item.min.toLocaleString('ru-RU') }} … {{ item.max.toLocaleString('ru-RU') }}</dd></div>
                <div v-if="item.overridden"><dt>Для проекта</dt><dd>значение заменено</dd></div>
              </dl>
              <p>{{ item.rationale }}</p>
              <p class="note">{{ item.origin }}</p>
            </article>
          </div>
        </section>

        <section v-if="doc.processes.value.length" class="r-sec">
          <header class="sec-head">
            <span class="sec-n">06</span>
            <div>
              <h3 class="sec-title">Экономика по процессам</h3>
              <p class="sec-lead">Те же коэффициенты, что в допущениях, но эффект и затраты разложены по процессам: у каждого своя доля ФОТ и свой робот. Если покупка не окупается, ниже — что нужно изменить.</p>
            </div>
          </header>
          <table class="table proc-table">
            <thead>
              <tr>
                <th>Процесс</th>
                <th class="num">Доля ФОТ</th>
                <th class="num">CAPEX</th>
                <th class="num">Эффект</th>
                <th class="num">Окуп.</th>
                <th class="num">TCO покупки</th>
                <th class="num">TCO аренды</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in doc.processes.value" :key="row.key" :class="{ best: row.profitable }">
                <td><b>{{ row.name }}</b><div class="caption">{{ row.robot }}{{ row.included ? '' : ' · не в расчёте' }}</div><div class="caption">{{ row.reason }}</div></td>
                <td class="num">{{ row.share }}</td>
                <td class="num">{{ row.capex }}</td>
                <td class="num">{{ row.effect }}</td>
                <td class="num">{{ row.payback }}</td>
                <td class="num">{{ row.tcoPurchase }}</td>
                <td class="num">{{ row.tcoRaas }}</td>
              </tr>
            </tbody>
          </table>
          <article v-for="row in doc.processes.value.filter((item) => item.suggestions.length)" :key="`${row.key}-fix`" class="proc-fix">
            <h4>{{ row.name }}: что меняет окупаемость</h4>
            <ul>
              <li v-for="hint in row.suggestions" :key="hint.key">{{ hint.label }}: {{ hint.change }}. Эффект {{ hint.effect }}, окупаемость {{ hint.payback }}.</li>
            </ul>
          </article>
        </section>

        <section v-if="doc.econ.value?.sensitivity.length" class="r-sec">
          <header class="sec-head">
            <span class="sec-n">07</span>
            <div>
              <h3 class="sec-title">Чувствительность</h3>
              <p class="sec-lead">Каждое допущение по очереди сдвигаем на 20% вниз и вверх, остальные оставляем как есть. Полоса показывает, как меняется годовой эффект покупки: вправо — растёт, влево — падает. Чем длиннее полоса, тем сильнее допущение влияет на результат. Самые влиятельные сверху.</p>
            </div>
          </header>
          <p v-if="sensBase" class="base">Сейчас эффект покупки <b>{{ sensBase.effect }}</b> в год, окупаемость: <b>{{ sensBase.payback }}</b>. Это центральная линия на полосах.</p>
          <table class="table sens-table">
            <thead>
              <tr>
                <th>Допущение</th>
                <th class="num">−20% … +20%</th>
                <th>Изменение эффекта в год</th>
                <th class="num">Окупаемость</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in sensRows" :key="row.key">
                <td><b :class="{ 'cost-accent': isAccent(row.key, row.label) }">{{ row.label }}</b><div class="caption">сейчас {{ row.now }}</div></td>
                <td class="num">{{ row.range }}</td>
                <td>
                  <span class="tornado" aria-hidden="true">
                    <i :class="row.down.good ? 'good' : 'bad'" :style="{ left: row.down.left, width: row.down.width }" />
                    <i :class="row.up.good ? 'good' : 'bad'" :style="{ left: row.up.left, width: row.up.width }" />
                    <em />
                  </span>
                  <span class="tornado-v"><span v-for="end in row.ends" :key="end.key">{{ end.text }}</span></span>
                </td>
                <td class="num">{{ row.payback }}</td>
              </tr>
            </tbody>
          </table>
          <div class="legend"><span><i class="sw good" /> эффект растёт</span><span><i class="sw bad" /> эффект падает</span><span><i class="sw mid" /> текущий эффект</span></div>
        </section>

        <section v-if="doc.params.value.length" class="r-sec">
          <header class="sec-head">
            <span class="sec-n">08</span>
            <div>
              <h3 class="sec-title">Параметры объекта</h3>
              <p class="sec-lead">Исходные данные площадки, на которых посчитана экономика.</p>
            </div>
          </header>
          <dl class="kv">
            <div v-for="item in doc.params.value" :key="item.label"><dt>{{ item.label }}</dt><dd>{{ item.value }}</dd></div>
          </dl>
        </section>

        <section v-if="doc.limits.value.length" class="r-sec">
          <header class="sec-head">
            <span class="sec-n">09</span>
            <div><h3 class="sec-title">Оговорки расчёта</h3></div>
          </header>
          <ol class="limits">
            <li v-for="(line, index) in doc.limits.value" :key="index"><span class="n">{{ index + 1 }}</span><span>{{ line }}</span></li>
          </ol>
        </section>

        <footer class="r-foot">
          <p class="strong">{{ doc.disclaimer.value }}</p>
          <p>Отчёт сформирован платформой подбора роботизированных решений. Кейс ФЦ БАС, хакатон «Лидеры цифровой трансформации», 2026. Версия каталога {{ project.catalogVersion }}, версия расчётной модели {{ project.modelVersion }}.</p>
        </footer>
      </div>
    </article>

    <div v-if="vizLayout" class="plan-off" aria-hidden="true">
      <ClientOnly>
        <PlanEditor
          :key="vizKey"
          ref="editor"
          :layout="vizLayout"
          :floor-id="vizFloorId"
          mode="view"
          tool="hand"
          process=""
          station-kind="load"
          station-item=""
          link-kind="elevator"
          pending-link=""
          :colors="vizColors"
          :processes="vizProcesses"
          :visibility="emptyVisibility"
          highlight=""
          :calibrate-meters="10"
          :selection="[]"
          :focus-robot="null"
          :snap="true"
          @ready="onPlanReady"
        />
      </ClientOnly>
    </div>
  </ProjectShell>
  <section v-else class="container gone">
    <UiCallout tone="danger" title="Проект не найден">Нет сохранённого расчёта с таким адресом.</UiCallout>
  </section>
</template>

<style scoped>
.waiting { padding: var(--space-8); }
.waiting > * { position: relative; z-index: 1; }
.gone { padding-top: var(--space-12); }
.go { display: inline-flex; align-items: center; gap: 4px; font-weight: 700; }

.report {
  width: 100%;
  overflow: hidden;
  background: #fff;
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
  border: 1px solid var(--border-hairline);
}

.cover {
  display: grid;
  grid-template-columns: minmax(280px, 0.92fr) minmax(360px, 1.15fr);
  grid-template-rows: auto auto auto;
  align-items: start;
  gap: 14px 28px;
  padding: 22px 26px;
  background:
    radial-gradient(90% 70% at 88% 0%, rgba(43, 209, 141, 0.18), transparent 55%),
    linear-gradient(180deg, #1c2421 0%, #121817 100%);
  color: var(--ink-on-graphite);
}
.cover-top { grid-column: 1; grid-row: 1; display: flex; justify-content: flex-start; align-items: center; gap: 14px; }
.cover-mark { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; color: var(--brand-300); }
.cover-title { grid-column: 1; grid-row: 2; display: grid; gap: 6px; min-width: 0; }
.cover-kicker { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-muted-graphite); }
.cover-h {
  margin: 0;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: clamp(28px, 2.6vw, 46px);
  line-height: 1.08;
  letter-spacing: -0.03em;
  width: 100%;
  min-width: 0;
  white-space: nowrap;
  overflow: hidden;
}
.cover-hero { grid-column: 2; grid-row: 1 / span 3; align-self: stretch; position: relative; margin: 0; min-height: 180px; border-radius: 16px; overflow: hidden; }
.cover-hero img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }
.cover-foot { grid-column: 1; grid-row: 3; display: flex; flex-wrap: wrap; gap: 6px 16px; font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.04em; color: var(--ink-muted-graphite); }

.r-in { padding: 18px 22px 22px; display: grid; gap: 16px; color: var(--ink-body); font-size: clamp(13px, 0.85vw, 15px); line-height: 1.4; }
.disclaimer { display: flex; gap: 10px; align-items: flex-start; padding: 12px 14px; border-radius: 12px; background: var(--state-warn-tint); color: #5c3700; font-size: 13.5px; line-height: 1.45; }
.disclaimer svg { flex: none; color: var(--state-warn); margin-top: 1px; }

.r-sec { display: grid; gap: 8px; }
.sec-head { display: flex; align-items: flex-start; gap: 10px; }
.sec-n { font-family: var(--font-mono); font-size: 12px; color: var(--brand-700); }
.sec-title { margin: 0; font-weight: 700; font-size: clamp(18px, 1.35vw, 24px); line-height: 1.2; letter-spacing: -0.015em; color: var(--ink-strong); }
.sec-lead { margin: 4px 0 0; color: var(--ink-muted); font-size: clamp(12.5px, 0.85vw, 15px); line-height: 1.35; }
.note { margin: 0; font-size: 12.5px; line-height: 1.4; color: var(--ink-muted); }
.base { margin: 0; font-size: 14px; color: var(--ink-body); }
.base b { font-family: var(--font-mono); font-weight: 600; color: var(--ink-strong); }

.advice {
  display: grid;
  gap: 6px;
  padding: 12px 14px;
  border-radius: 14px;
  background: var(--surface-brand-tint);
  border: 1px solid #b9e8d0;
}
.advice.asis { background: var(--surface-raised); border-color: var(--border-hairline); }
.advice-kicker { margin: 0; font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--brand-700); }
.advice h3 { margin: 0; font-size: clamp(16px, 1.3vw, 22px); letter-spacing: -0.02em; color: var(--ink-strong); }
.advice > p { margin: 0; }
.advice-table { width: 100%; background: #fff; border-radius: 10px; }
.advice-table tr.best td { background: #e8f7ef; }

.formula-block { display: grid; gap: 8px; }
.formula-block > h4 { margin: 8px 0 0; font-size: clamp(14px, 1vw, 16px); color: var(--ink-strong); }
.formula-part { display: grid; gap: 8px; }
.formula-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; align-items: stretch; }
.formula-tile { display: flex; flex-direction: column; gap: 4px; min-width: 0; height: 100%; padding: 8px 10px; border: 1px solid var(--border-hairline); border-radius: 12px; background: var(--surface-raised); }
.formula-tile :deep(.formula) { flex: 1; align-content: start; background: none; box-shadow: none; padding: 0; gap: 4px; }
.formula-tile :deep(.f-var) { display: flex; flex-wrap: wrap; align-items: baseline; gap: 2px 6px; padding: 2px 0; }
.formula-tile :deep(.f-what) { display: contents; }
.formula-tile :deep(.f-what .caption) { flex: 1 0 100%; }
.formula-tile :deep(.f-val) { margin-left: auto; white-space: nowrap; }
.formula-tile :deep(.body-sm) { font-size: clamp(11.5px, 0.75vw, 13px); line-height: 1.3; }
.formula-tile :deep(.caption),
.formula-tile :deep(.mono-sm) { font-size: clamp(11px, 0.7vw, 12px); }
.formula-tile :deep(.katex) { font-size: 0.82em; }
.formula-line-h { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; font-size: clamp(12.5px, 0.85vw, 14px); color: var(--ink-strong); }
.formula-line-h span { min-width: 0; }
.formula-line-h b { font-family: var(--font-mono); font-weight: 600; text-align: right; }
.formula-line-h.cost-accent,
.formula-line-h.cost-accent b { font-weight: 800; }

.proc-table { width: 100%; }
.proc-table td, .proc-table th { vertical-align: top; }
.proc-fix { display: grid; gap: 4px; }
.proc-fix h4 { margin: 0; font-size: 14px; color: var(--ink-strong); }
.proc-fix ul { margin: 0; padding-left: 18px; font-size: 13px; }
.assume { display: grid; gap: 0; }
.assume-row { display: grid; gap: 2px 12px; padding: 6px 0; border: 0; border-bottom: 1px solid var(--border-hairline); border-radius: 0; background: none; }
.assume-h { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px 10px; }
.assume-h b { margin-left: auto; font-family: var(--font-mono); font-weight: 600; font-size: 13px; }
.assume-sym { color: var(--ink-muted); }
.assume-row dl, .shift-card dl { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 2px 12px; margin: 0; }
.assume-row p { margin: 0; font-size: 12.5px; }
.assume-row dt, .shift-card dt { color: var(--ink-muted); font-size: 12px; }
.assume-row dd, .shift-card dd { margin: 0; font-family: var(--font-mono); font-size: 13px; color: var(--ink-strong); }

.sens-table { width: 100%; }
.sens-table td { vertical-align: middle; }
.sens-table th:first-child { width: 28%; }
.sens-table th:nth-child(3) { width: 40%; }
.tornado { position: relative; display: block; height: 12px; border-radius: 3px; background: rgba(15, 20, 19, 0.05); }
.tornado i { position: absolute; top: 2px; bottom: 2px; border-radius: 2px; }
.tornado i.good, .sw.good { background: var(--brand-600); }
.tornado i.bad, .sw.bad { background: var(--state-danger); }
.tornado em { position: absolute; left: 50%; top: -2px; bottom: -2px; width: 2px; margin-left: -1px; background: var(--ink-strong); }
.sw.mid { width: 2px; height: 12px; border-radius: 0; background: var(--ink-strong); vertical-align: -2px; }
.tornado-v { display: flex; justify-content: space-between; gap: 8px; margin-top: 3px; font-family: var(--font-mono); font-size: 11px; color: var(--ink-muted); white-space: nowrap; }
.shift { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.shift-card { display: grid; gap: 4px; padding: 8px 10px; border: 1px solid var(--border-hairline); border-radius: 10px; background: var(--surface-raised); }
.shift-card h4 { margin: 0; font-size: 15px; color: var(--ink-strong); }
.shift-card header { display: flex; justify-content: space-between; gap: 10px; align-items: center; }
.shift-flag { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.04em; text-transform: uppercase; color: #8a5a12; }
.shift-flag.ok { color: var(--brand-700); }
.shift-card ul { margin: 0; padding-left: 18px; color: var(--ink-muted); font-size: 12.5px; }
.robot-body :deep(.formula) { margin-top: 4px; }

.scenes { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
.scenes-print { display: none; }
.scene { padding: 14px 16px; border-radius: 14px; border: 1px solid var(--border-hairline); background: var(--surface-raised); display: grid; gap: 10px; align-content: start; }
.scene.best { background: var(--surface-brand-tint); border-color: #b9e8d0; }
.scene-top { display: flex; justify-content: space-between; gap: 10px; align-items: flex-start; }
.scene-name { margin: 0; font-size: clamp(15px, 1.05vw, 18px); font-weight: 700; color: var(--ink-strong); letter-spacing: -0.01em; }
.scene-sub { margin: 2px 0 0; color: var(--ink-muted); font-size: 12.5px; }
.scene-band { flex: none; font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.04em; text-transform: uppercase; padding: 4px 8px; border-radius: 999px; background: var(--brand-ink); color: #fff; }
.scene-verdict { margin: 0; font-size: 12.5px; line-height: 1.35; color: var(--ink-strong); }
.metrics { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 12px; margin: 0; }
.metrics > div { display: grid; gap: 1px; min-width: 0; }
.metrics dt { font-family: var(--font-mono); font-size: 10px; letter-spacing: 0.05em; text-transform: uppercase; color: var(--ink-muted); }
.metrics dd { margin: 0; font-family: var(--font-mono); font-size: clamp(13px, 0.95vw, 16px); font-weight: 600; color: var(--ink-strong); font-variant-numeric: tabular-nums; }

.chart { display: grid; gap: 8px; padding: 14px 16px; border-radius: 14px; border: 1px solid var(--border-hairline); background: var(--surface-raised); }
.tco-rows { display: grid; gap: 8px; }
.tco-row { display: grid; grid-template-columns: 42px 1fr; gap: 8px; align-items: center; }
.tco-bars { display: grid; gap: 2px; }
.tb { display: flex; align-items: center; justify-content: flex-end; height: 14px; border-radius: 3px; min-width: 28px; }
.tb i { font-style: normal; font-family: var(--font-mono); font-size: 9px; color: #fff; padding-right: 4px; line-height: 1; }
.tb.asis, .sw.asis { background: var(--border-strong); }
.tb.purchase, .sw.purchase { background: var(--brand-600); }
.tb.raas, .sw.raas { background: var(--state-warn); }
.legend { display: flex; gap: 14px; flex-wrap: wrap; margin: 0; padding: 0; list-style: none; font-size: 12.5px; color: var(--ink-muted); }
.sw, .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; vertical-align: -1px; margin-right: 4px; }
.y { font-family: var(--font-mono); font-size: 12px; color: var(--ink-muted); }

.books { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; align-items: start; }
.book { padding: 14px 16px; border-radius: 14px; border: 1px solid var(--border-hairline); background: #fff; display: grid; gap: 8px; }
.book.best { background: var(--surface-brand-tint); border-color: #b9e8d0; }
.book h4 { margin: 0; font-size: 15px; color: var(--ink-strong); }
.book ul { display: grid; gap: 4px; margin: 0; padding: 0 0 4px; list-style: none; }
.book li, .book-total { display: flex; justify-content: space-between; gap: 10px; align-items: baseline; font-size: 13px; }
.book li span { color: var(--ink-body); }
.book b { font-family: var(--font-mono); font-weight: 600; color: var(--ink-strong); font-variant-numeric: tabular-nums; white-space: nowrap; }
.book-total { margin: 0; padding-top: 6px; border-top: 1px solid var(--border-hairline); }
.book-total span { color: var(--ink-muted); font-size: 12px; }
.book-total.quiet { border-top: 0; padding-top: 0; }

.robot-gloss { display: grid; gap: 2px; margin: 0; padding: 0; list-style: none; color: var(--ink-muted); font-size: clamp(12px, 0.75vw, 13px); line-height: 1.35; }
.robot-gloss b { color: var(--ink-strong); font-weight: 700; }
.robots { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.robot { display: grid; grid-template-columns: 52px minmax(0, 1fr); gap: 8px; padding: 8px; border-radius: 12px; border: 1px solid var(--border-hairline); background: var(--surface-raised); align-items: start; }
.robot img { width: 52px; height: 44px; object-fit: contain; border-radius: 8px; background: #e9eeec; }
.robot-body { display: grid; gap: 2px; align-content: start; min-width: 0; }
.robot-body h4 { margin: 0; font-size: clamp(13px, 0.9vw, 15px); color: var(--ink-strong); }
.robot-meta { margin: 0; font-family: var(--font-mono); font-size: clamp(11px, 0.75vw, 12.5px); color: var(--ink-strong); }
.specs { display: flex; flex-wrap: wrap; gap: 2px 10px; margin: 2px 0 0; }
.specs div { display: inline-flex; gap: 4px; align-items: baseline; min-width: 0; }
.specs dt { font-size: clamp(11px, 0.7vw, 12px); color: var(--ink-muted); }
.specs dt::after { content: ':'; }
.specs dd { margin: 0; font-family: var(--font-mono); font-size: clamp(11px, 0.75vw, 12.5px); color: var(--ink-strong); }

.viz { margin: 0; border-radius: 14px; overflow: hidden; background: #e7ecea; border: 1px solid var(--border-hairline); min-height: 220px; }
.viz img { display: block; width: 100%; height: auto; }
.viz-wait { min-height: 220px; display: grid; place-items: center; color: var(--ink-muted); font-size: 14px; }
.robots-legend li { display: inline-flex; align-items: center; }

.kv { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px 20px; margin: 0; }
.kv > div { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
.kv dt { color: var(--ink-muted); font-size: 13px; }
.kv dd { margin: 0; text-align: right; color: var(--ink-strong); font-family: var(--font-mono); font-size: 12.5px; }

.limits { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
.limits li { display: grid; grid-template-columns: auto 1fr; gap: 10px; align-items: start; font-size: 14px; line-height: 1.45; }
.n { width: 22px; height: 22px; border-radius: 7px; background: var(--surface-graphite); color: var(--brand-300); display: inline-flex; align-items: center; justify-content: center; font-family: var(--font-mono); font-size: 11px; }
.r-foot { padding-top: 4px; border-top: 1px solid var(--border-hairline); display: grid; gap: 4px; font-size: 12.5px; line-height: 1.45; color: var(--ink-muted); }
.r-foot .strong { color: var(--ink-strong); }
.plan-off { position: fixed; left: -2400px; top: 0; width: 1200px; height: 720px; pointer-events: none; }

@media (min-width: 1500px) {
  .robots { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 1100px) {
  .scenes, .books, .formula-grid, .robots { grid-template-columns: 1fr 1fr; }
  .kv { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 800px) {
  .cover { grid-template-columns: 1fr; grid-template-rows: auto; padding: 20px; gap: 16px; }
  .cover-top, .cover-title, .cover-hero, .cover-foot { grid-column: auto; grid-row: auto; }
  .cover-hero { min-height: 180px; }
  .r-in { padding: 20px; gap: 22px; }
  .formula-grid, .scenes, .robots { grid-template-columns: 1fr; }
}

@media print {
  .report {
    max-width: none;
    overflow: visible;
    box-shadow: none;
    border: 0;
    border-radius: 0;
    background: #fff;
  }
  .cover {
    position: relative;
    display: flex;
    flex-direction: column;
    justify-content: flex-end;
    width: 100%;
    height: 297mm;
    max-height: 297mm;
    box-sizing: border-box;
    overflow: hidden;
    margin: 0;
    padding: 0;
    gap: 0;
    border-radius: 0;
    break-after: page;
    page-break-after: always;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }
  .cover-hero {
    position: absolute;
    inset: 0;
    width: auto;
    height: auto;
    min-height: 0;
    margin: 0;
    border-radius: 0;
    z-index: 0;
  }
  .cover-hero::after {
    content: "";
    position: absolute;
    inset: 0;
    background: linear-gradient(180deg, rgba(10, 14, 13, 0.78) 0%, rgba(10, 14, 13, 0.18) 42%, rgba(10, 14, 13, 0.82) 100%);
  }
  .cover-hero img { position: absolute; inset: 0; }
  .cover-top, .cover-title, .cover-foot { position: relative; z-index: 1; grid-column: auto; grid-row: auto; width: auto; max-width: none; }
  .cover-top { position: absolute; top: 0; left: 0; right: 0; padding: 14mm 16mm 0; }
  .cover-title { padding: 0 16mm 6mm; }
  .cover-foot { padding: 0 16mm 14mm; }
  .cover-h { font-size: 34px !important; line-height: 1.12; white-space: normal !important; overflow: visible !important; }
  /* Сетки и flex Chrome режет по страницам ненадёжно: плитки наезжают на следующий блок.
     В печати поток блочный, а плитки — строчные блоки: строка из двух плиток переносится целиком. */
  /* Лист без полей ради обложки в край; поля остальных страниц — отступы тела, повторённые на каждом фрагменте. */
  .r-in {
    display: block; padding: 12mm 14mm; font-size: 10.5px; line-height: 1.35; overflow: visible;
    -webkit-box-decoration-break: clone; box-decoration-break: clone;
  }
  .r-in > * + * { margin-top: 5mm; }
  .r-sec, .formula-block, .assume { display: block; }
  .r-sec > * + * { margin-top: 2.5mm; }
  .sec-head, .formula-block > h4, .assume > .label, .robot-gloss { break-after: avoid; page-break-after: avoid; }
  .sec-head { break-inside: avoid; page-break-inside: avoid; }
  .formula-block > h4 { margin: 4mm 0 2mm; font-size: 12px; }
  .disclaimer { padding: 6px 8px; font-size: 10px; break-inside: avoid; }
  .sec-title { font-size: 13px; }
  .sec-lead { font-size: 10px; }
  .advice { display: block; break-inside: avoid; page-break-inside: avoid; }
  .advice > * + * { margin-top: 2mm; }
  .advice h3 { font-size: 14px; }
  .scenes { display: none; }
  .scenes-print { display: table; }

  .r-in table { width: 100%; max-width: 100%; table-layout: fixed; border-collapse: collapse; }
  .r-in thead { display: table-header-group; }
  .r-in tr { break-inside: avoid; page-break-inside: avoid; }
  .r-in th, .r-in td { font-size: 9px; line-height: 1.3; padding: 3px 4px; vertical-align: top; overflow-wrap: anywhere; }
  .r-in td.num, .r-in th.num { white-space: nowrap; overflow-wrap: normal; }
  .r-in td .caption { font-size: 8.5px; line-height: 1.3; }
  .scenes-print th:first-child, .proc-table th:first-child { width: 30%; }
  .scenes-print tr.best td, .advice-table tr.best td, .proc-table tr.best td { background: #e8f7ef; }

  /* Плитки формул разной высоты: две колонки потока укладывают их плотно, без пустот под короткой плиткой. */
  .formula-grid { display: block; columns: 2; column-gap: 3mm; }
  .formula-grid:has(> .formula-tile:only-child) { columns: auto; }
  .formula-tile { display: block; height: auto; margin: 0 0 3mm; padding: 2mm; break-inside: avoid; page-break-inside: avoid; }
  .robots, .shift { display: block; margin-left: -1.5mm; margin-right: -1.5mm; }
  .robot, .shift-card {
    vertical-align: top; box-sizing: border-box;
    width: calc(50% - 3mm); height: auto; margin: 0 1.5mm 3mm;
    break-inside: avoid; page-break-inside: avoid;
  }
  .robot { display: inline-grid; grid-template-columns: 40px minmax(0, 1fr); padding: 2mm; }
  .robot img { width: 40px; height: 34px; }
  .shift-card { display: inline-grid; }

  .assume-row dl { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .sens-table th:first-child { width: 30%; }
  .sens-table th:nth-child(3) { width: 38%; }
  .base { font-size: 11px; }
  .tornado { height: 9px; }
  .tornado-v { font-size: 8px; }
  .shift-card dl { grid-template-columns: 1fr 1fr; }
  .assume-row, .proc-fix, .chart, .kv > div, .limits li { break-inside: avoid; page-break-inside: avoid; }
  .chart { display: block; }
  .chart > * + * { margin-top: 2mm; }
  .viz { break-inside: avoid; page-break-inside: avoid; overflow: visible; min-height: 0; }
  .viz img { max-width: 100%; height: auto; }
  .kv { grid-template-columns: 1fr 1fr 1fr; }
  .limits { gap: 2px; }
  .limits li { font-size: 10px; }
  .n { width: 14px; height: 14px; font-size: 8px; }
  .note, .r-foot, .legend { font-size: 9px; }
  .r-foot { break-inside: avoid; }
  .plan-off { display: none !important; }
  :deep(.callout) { display: none !important; }
  :deep(.katex-display),
  :deep(.tex.block) { overflow: visible; max-width: 100%; }
  :deep(.katex-html) { white-space: normal; }
}
</style>
