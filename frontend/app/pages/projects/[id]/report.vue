<script setup lang="ts">
import { PhFilePdf, PhFileXls } from '@phosphor-icons/vue'
import { objectTypeImage } from '~/data/projects'
import { photoFor } from '~/data/placeholders'
import { downloadText, toExcelXml } from '~/utils/exportTables'
import { fetchErrorMessage } from '~/utils/errors'
import { REPORT_NOTE, useReportData } from '~/composables/useReportData'

/**
 * Итоговый отчёт (ТЗ 3.7). Обложка с фото, краткая часть для руководителя и приложения для экономиста.
 * Документ свёрстан под A4: на экране он такой же, как в PDF, поэтому при печати ничего не съезжает.
 * Excel — те же разделы таблицами, чтобы экономист мог пересчитать.
 */
const route = useRoute()
const id = computed(() => route.params.id as string)
const doc = useReportData(id)
const project = computed(() => doc.project.value)
useHead({ title: () => `Отчёт · ${project.value?.name ?? 'проект'}` })

const mode = ref<'brief' | 'full'>('brief')
const cover = computed(() => project.value ? objectTypeImage[project.value.objectType] : objectTypeImage.warehouse)
/* Параметры объекта на обложке — самые узнаваемые, не больше восьми. */
const COVER_KEYS = ['Площадь', 'Смен в сутки', 'Длительность смены', 'Рабочих дней в году', 'Общая численность персонала склада', 'Бюджет на роботизацию', 'Объём приёмки', 'Объём отгрузки']
const coverParams = computed(() => {
  const picked = doc.siteRows.value.filter((row) => COVER_KEYS.includes(row.label))
  return (picked.length >= 4 ? picked : doc.siteRows.value).slice(0, 8)
})

const print = async (kind: 'brief' | 'full') => {
  if (!import.meta.client || !doc.ready.value) return
  mode.value = kind
  await nextTick()
  const prev = document.title
  document.title = `${project.value?.name ?? 'Отчёт'} — ${kind === 'brief' ? 'кратко' : 'полный отчёт'}`
  const restore = () => {
    document.title = prev
    window.removeEventListener('afterprint', restore)
  }
  window.addEventListener('afterprint', restore)
  window.print()
}
const exportExcel = () => {
  if (!doc.ready.value || !doc.sheets.value.length) return
  downloadText(`${doc.stem.value}_расчёт.xls`, 'application/vnd.ms-excel', toExcelXml(doc.sheets.value, REPORT_NOTE))
}
const capexRows = computed(() => {
  const labels = [...new Set([...doc.statement.value.buyCapex, ...doc.statement.value.rentCapex].map((line) => line.label))]
  return labels.map((label) => [label, doc.statement.value.buyCapex.find((line) => line.label === label)?.value ?? '—', doc.statement.value.rentCapex.find((line) => line.label === label)?.value ?? '—'])
})
const opexRows = computed(() => {
  const labels = [...new Set([...doc.statement.value.buyOpex, ...doc.statement.value.rentOpex].map((line) => line.label))]
  return labels.map((label) => [label, doc.statement.value.buyOpex.find((line) => line.label === label)?.value ?? '—', doc.statement.value.rentOpex.find((line) => line.label === label)?.value ?? '—'])
})
/* Фото робота не загрузилось — ставим заглушку процесса, чтобы в PDF не было битой картинки. */
const onImageError = (event: Event, process: string) => {
  const img = event.target as HTMLImageElement
  const fallback = photoFor(null, '', process)
  if (img.src !== fallback) img.src = fallback
}
const SCEN_ROWS = [
  { key: 'capex', label: 'Вложения (CAPEX)' },
  { key: 'cost', label: 'Затраты в год (OPEX и оставшийся ФОТ)' },
  { key: 'change', label: 'Изменение затрат к базе' },
  { key: 'effect', label: 'Годовой эффект' },
  { key: 'payback', label: 'Срок окупаемости' },
  { key: 'roi', label: 'ROI за горизонт' },
  { key: 'tco', label: 'TCO за горизонт' },
  { key: 'npv', label: 'NPV' },
] as const
</script>

<template>
  <ProjectShell
    v-if="project"
    :project="project"
    current="report"
    title="Отчёт"
    lead="Кратко — обложка и два листа для руководителя. Полностью — с приложениями: подбор, парк, статьи затрат, формулы, надёжность, схема и источники. Excel — расчётные таблицы."
    dense
  >
    <template v-if="!doc.closed.value" #actions>
      <div class="modes no-print" role="radiogroup" aria-label="Вид отчёта">
        <button type="button" role="radio" :aria-checked="mode === 'brief'" :class="{ on: mode === 'brief' }" @click="mode = 'brief'">Кратко</button>
        <button type="button" role="radio" :aria-checked="mode === 'full'" :class="{ on: mode === 'full' }" @click="mode = 'full'">Полностью</button>
      </div>
      <UiButton variant="secondary" class="no-print" :disabled="!doc.ready.value" @click="print('brief')"><template #icon><PhFilePdf :size="16" weight="duotone" /></template>PDF кратко</UiButton>
      <UiButton variant="secondary" class="no-print" :disabled="!doc.ready.value" @click="print('full')"><template #icon><PhFilePdf :size="16" weight="duotone" /></template>PDF полный</UiButton>
      <UiButton class="no-print" :disabled="!doc.ready.value" @click="exportExcel"><template #icon><PhFileXls :size="16" weight="duotone" /></template>Excel</UiButton>
    </template>

    <UiCallout v-if="doc.closed.value" tone="info" title="Отчёт для этого объекта не собирается">Полный путь с экономикой доступен для склада, аэропорта и больницы.</UiCallout>
    <StepLoading
      v-else-if="!doc.report.value && !doc.failure.value"
      label="Отчёт"
      title="Собираем отчёт"
      :stages="['Загружаем подбор и выбор роботов', 'Считаем экономику по процессам', 'Готовим выводы, таблицы и формулы']"
    />
    <UiCallout v-else-if="doc.failure.value" tone="danger" title="Отчёт не собрался">{{ fetchErrorMessage(doc.failure.value, 'Сервер не ответил.') }}</UiCallout>

    <article v-else class="doc">
      <!-- ОБЛОЖКА: фото объекта на весь верх листа, название, параметры, итог одной строкой. -->
      <section class="sheet cover">
        <figure class="c-hero"><img :src="cover" :alt="doc.objectLine.value"></figure>
        <div class="c-top"><Logo :size="30" mint wordmark on-graphite /><span class="c-mark">Отчёт о роботизации · предварительная оценка</span></div>
        <div class="c-body">
          <span class="c-kicker">{{ doc.objectLine.value }}</span>
          <h1 class="c-title">{{ project.name }}</h1>
          <div class="c-verdict" :class="doc.verdict.value.tone">
            <strong>{{ doc.verdict.value.title }}</strong>
            <span v-if="doc.kpis.value.length">{{ doc.kpis.value[0]!.label }} {{ doc.kpis.value[0]!.value }} · {{ doc.kpis.value[1]!.label.toLowerCase() }} {{ doc.kpis.value[1]!.value }} · {{ doc.kpis.value[3]!.label.toLowerCase() }} {{ doc.kpis.value[3]!.value }}</span>
          </div>
          <dl class="c-params">
            <div v-for="row in coverParams" :key="row.label"><dt>{{ row.label }}</dt><dd>{{ row.value }}</dd></div>
          </dl>
          <footer class="c-foot">
            <span>Дата расчёта: {{ doc.today }}</span>
            <span>Горизонт: {{ doc.horizon.value }} лет</span>
            <span>Процессов в расчёте: {{ doc.inTotal.value.length }}</span>
          </footer>
        </div>
      </section>

      <!-- ЛИСТ 1. Заключение, цифры, сравнение сценариев, что роботизировать. -->
      <section class="sheet">
        <header class="s-head"><span class="kicker">Краткий отчёт · 1</span><span class="muted small">{{ project.name }}</span></header>
        <h2>Заключение</h2>
        <div class="verdict" :class="doc.verdict.value.tone">
          <strong>{{ doc.verdict.value.title }}</strong>
          <span>{{ doc.verdict.value.why }}</span>
          <span v-if="doc.tzVerdict.value" class="small">Интерпретация по порогам ТЗ: {{ doc.tzVerdict.value }}</span>
        </div>
        <div class="kpis">
          <div v-for="item in doc.kpis.value" :key="item.label" class="kpi">
            <span class="k-label">{{ item.label }}</span>
            <span class="k-value">{{ item.value }}</span>
            <span class="k-note">{{ item.note }}</span>
          </div>
        </div>

        <h2>Сравнение сценариев</h2>
        <table class="tbl scen">
          <colgroup><col style="width: 34%"><col style="width: 22%"><col style="width: 22%"><col style="width: 22%"></colgroup>
          <thead><tr><th>Показатель</th><th v-for="col in doc.scenarioTable.value" :key="col.key" class="num" :class="{ best: col.best }">{{ col.title }}<span v-if="col.best" class="tag">выгоднее</span></th></tr></thead>
          <tbody>
            <tr v-for="row in SCEN_ROWS" :key="row.key">
              <th>{{ row.label }}</th>
              <td v-for="col in doc.scenarioTable.value" :key="col.key" class="num" :class="{ best: col.best }">{{ col[row.key] }}</td>
            </tr>
          </tbody>
        </table>
        <p class="small muted">Горизонт {{ doc.horizon.value }} лет. Окупаемость аренды — срок, за который вернутся её собственные вложения во внедрение на площадке: роботов при аренде покупать не нужно. {{ doc.rentLine.value }}</p>

        <h2>Что роботизировать</h2>
        <table class="tbl">
          <colgroup><col style="width: 30%"><col style="width: 30%"><col style="width: 13%"><col style="width: 14%"><col style="width: 13%"></colgroup>
          <thead><tr><th>Процесс</th><th>Робот</th><th class="num">Вложения</th><th class="num">Экономия в год</th><th class="num">Окупаемость</th></tr></thead>
          <tbody>
            <tr v-for="row in doc.plan.value" :key="row.code"><td>{{ row.name }}</td><td>{{ row.robot }}</td><td class="num">{{ row.capex }}</td><td class="num">{{ row.saving }}</td><td class="num">{{ row.payback }}</td></tr>
            <tr v-if="!doc.plan.value.length"><td colspan="5" class="muted">Ни один процесс не окупается при текущих данных.</td></tr>
          </tbody>
        </table>
        <p v-if="doc.outOfTotal.value.length" class="small muted">Не вошли в итог: {{ doc.outOfTotal.value.map((item) => item.process_name).join(', ') }}.</p>
      </section>

      <!-- ЛИСТ 2. Деньги, чувствительность, риски, что уточнить. -->
      <section class="sheet">
        <header class="s-head"><span class="kicker">Краткий отчёт · 2</span><span class="muted small">{{ project.name }}</span></header>
        <h2>Деньги по годам</h2>
        <div class="chart"><EconCashChart v-if="doc.buy.value" :scenarios="[doc.buy.value, ...(doc.rent.value ? [doc.rent.value] : [])]" picked="purchase" /></div>

        <h2>Чувствительность сценариев</h2>
        <table class="tbl">
          <colgroup><col style="width: 28%"><col style="width: 24%"><col style="width: 24%"><col style="width: 24%"></colgroup>
          <thead><tr><th>Параметр</th><th>Диапазон</th><th class="num">NPV покупки</th><th class="num">NPV аренды</th></tr></thead>
          <tbody><tr v-for="row in doc.sensitivityBoth.value" :key="row.label"><th>{{ row.label }}</th><td class="small">{{ row.range }}</td><td class="num">{{ row.buy }}</td><td class="num">{{ row.rent }}</td></tr></tbody>
        </table>

        <h2>Риски</h2>
        <div v-if="doc.risk.value" class="risk">
          <div><span class="k-label">Вероятность окупиться</span><span class="r-value">{{ doc.risk.value.chance }}</span></div>
          <div><span class="k-label">NPV, разброс</span><span class="r-value">{{ doc.risk.value.interval }}</span></div>
          <div><span class="k-label">Если всё пойдёт плохо сразу</span><span class="r-value">{{ doc.risk.value.worst }}</span></div>
          <div><span class="k-label">Запас по цене · по ставке</span><span class="r-value">{{ doc.risk.value.price }} · {{ doc.risk.value.rate }}</span></div>
        </div>

        <template v-if="doc.fixes.value.length">
          <h2>Что платформа поправила сама</h2>
          <ul class="list small"><li v-for="(item, index) in doc.fixes.value" :key="index">{{ item }}</li></ul>
        </template>
        <p class="note">{{ REPORT_NOTE }} Дата расчёта: {{ doc.today }}.</p>
      </section>

      <template v-if="mode === 'full'">
        <!-- А. Объект. -->
        <section class="sheet">
          <h2 class="ap"><span>А</span>Параметры объекта и процессы</h2>
          <div class="two">
            <table v-for="(half, index) in [doc.siteRows.value.slice(0, Math.ceil(doc.siteRows.value.length / 2)), doc.siteRows.value.slice(Math.ceil(doc.siteRows.value.length / 2))]" :key="index" class="tbl kv small-tbl">
              <colgroup><col style="width: 58%"><col style="width: 42%"></colgroup>
              <tbody><tr v-for="row in half" :key="row.label"><th>{{ row.label }}</th><td>{{ row.value }}</td></tr></tbody>
            </table>
          </div>
          <p class="small"><b>В работе:</b> {{ doc.processList.value.filter((item) => item.enabled).map((item) => item.name).join(', ') || '—' }}.</p>
          <p v-if="doc.processList.value.some((item) => !item.enabled)" class="small muted"><b>Не выбраны:</b> {{ doc.processList.value.filter((item) => !item.enabled).map((item) => item.name).join(', ') }}.</p>
        </section>

        <!-- Б. Подбор и состав парка. -->
        <section class="sheet">
          <h2 class="ap"><span>Б</span>Выбранные решения и состав парка</h2>
          <table class="tbl">
            <colgroup><col style="width: 26%"><col style="width: 28%"><col style="width: 10%"><col style="width: 24%"><col style="width: 12%"></colgroup>
            <thead><tr><th>Процесс</th><th>Робот</th><th class="num">Кол-во</th><th>Выбор</th><th class="num">Подходят</th></tr></thead>
            <tbody><tr v-for="row in doc.selection.value" :key="row.name" :class="{ dim: !!row.reason }"><td>{{ row.name }}</td><td>{{ row.robot }}</td><td class="num">{{ row.count }}</td><td>{{ row.how }}</td><td class="num">{{ row.candidates }}</td></tr></tbody>
          </table>
          <p v-for="reason in doc.selectionReasons.value" :key="reason" class="small muted">Робот не выбран: {{ reason.charAt(0).toLowerCase() + reason.slice(1) }}</p>
          <h3>Состав парка</h3>
          <div class="fleet">
            <article v-for="robot in doc.fleetCards.value" :key="robot.key" class="robot" :class="{ out: !robot.inTotal }">
              <img :src="robot.image" :alt="robot.name" @error="onImageError($event, robot.key.split(':')[0] ?? '')">
              <div class="r-body">
                <span class="small muted">{{ robot.process }}{{ robot.inTotal ? '' : ' · не в итоге' }}</span>
                <strong>{{ robot.name }}</strong>
                <span class="small mono">{{ robot.count }} · {{ robot.price }} · парк {{ robot.cost }}</span>
                <span v-if="robot.specs.length" class="small">{{ robot.specs.join(' · ') }}</span>
                <span v-for="note in robot.notes" :key="note" class="small muted">{{ note }}</span>
              </div>
            </article>
          </div>
        </section>

        <!-- В. Экономика по процессам. -->
        <section class="sheet">
          <h2 class="ap"><span>В</span>Экономика по процессам</h2>
          <p class="small muted">Каждый процесс — как если бы роботизировали только его. Люди уходят по доле операций, которую забирают роботы, целыми ставками в каждой смене.</p>
          <div class="cards">
            <div v-for="card in doc.processCards.value" :key="card.code" class="card" :class="card.tone">
              <div class="c-head"><strong>{{ card.name }}</strong><span class="badge">{{ card.status }}</span></div>
              <table class="tbl kv small-tbl">
                <colgroup><col style="width: 42%"><col style="width: 58%"></colgroup>
                <tbody><tr v-for="[label, value] in card.rows" :key="label"><th>{{ label }}</th><td>{{ value }}</td></tr></tbody>
              </table>
              <p v-if="card.note" class="small c-note">{{ card.note }}</p>
            </div>
          </div>
        </section>

        <!-- Г, Д. CAPEX и OPEX по статьям, деньги по годам и показатели. -->
        <section class="sheet">
          <h2 class="ap"><span>Г</span>CAPEX и OPEX по статьям</h2>
          <p class="small">ФОТ на роботизируемых операциях до роботизации — <b>{{ doc.statement.value.payroll }}</b> в год, после — <b>{{ doc.statement.value.payrollAfter }}</b>. Вложения и расходы — без НДС.</p>
          <table class="tbl">
            <colgroup><col style="width: 50%"><col style="width: 25%"><col style="width: 25%"></colgroup>
            <thead><tr><th>Статья</th><th class="num">Покупка</th><th class="num">Аренда</th></tr></thead>
            <tbody>
              <tr class="total"><th>CAPEX, один раз</th><td class="num">{{ doc.statement.value.buyCapexTotal }}</td><td class="num">{{ doc.statement.value.rentCapexTotal }}</td></tr>
              <tr v-for="row in capexRows" :key="`c-${row[0]}`"><td class="indent">{{ row[0] }}</td><td class="num">{{ row[1] }}</td><td class="num">{{ row[2] }}</td></tr>
              <tr class="total"><th>OPEX в год</th><td class="num">{{ doc.statement.value.buyOpexTotal }}</td><td class="num">{{ doc.statement.value.rentOpexTotal }}</td></tr>
              <tr v-for="row in opexRows" :key="`o-${row[0]}`"><td class="indent">{{ row[0] }}</td><td class="num">{{ row[1] }}</td><td class="num">{{ row[2] }}</td></tr>
            </tbody>
          </table>

          <h2 class="ap"><span>Д</span>Деньги по годам и показатели</h2>
          <table v-if="doc.cashTable.value" class="tbl cash">
            <thead><tr><th v-for="cell in doc.cashTable.value.head" :key="cell" :class="{ num: cell !== 'млн ₽' }">{{ cell }}</th></tr></thead>
            <tbody><tr v-for="row in doc.cashTable.value.body" :key="row[0]" :class="{ total: row[0] === 'Накоплено' || row[0] === 'Поток года' }"><th>{{ row[0] }}</th><td v-for="(cell, index) in row.slice(1)" :key="index" class="num">{{ cell }}</td></tr></tbody>
          </table>
          <table class="tbl">
            <colgroup><col style="width: 32%"><col style="width: 24%"><col style="width: 44%"></colgroup>
            <thead><tr><th>Показатель</th><th class="num">Значение</th><th>Что значит</th></tr></thead>
            <tbody><tr v-for="row in doc.metrics.value" :key="row[0]"><th>{{ row[0] }}</th><td class="num wrap">{{ row[1] }}</td><td class="small">{{ row[2] }}</td></tr></tbody>
          </table>
        </section>

        <!-- Е. Формулы и подстановка (ТЗ 3.5.8). -->
        <section class="sheet">
          <h2 class="ap"><span>Е</span>Формулы и подстановка</h2>
          <p class="small muted">Каждая величина — формула, числа и источник каждой переменной.</p>
          <template v-for="group in doc.formulas.value" :key="group.title">
            <h3>{{ group.title }}</h3>
            <div class="formulas">
              <div v-for="fig in group.figs" :key="`${group.title}-${fig.key}`" class="f-tile">
                <div class="f-head"><span>{{ fig.label }}</span></div>
                <EconFormula dense brief :fig="fig" />
              </div>
            </div>
          </template>
        </section>

        <!-- Ж. Надёжность. -->
        <section class="sheet">
          <h2 class="ap"><span>Ж</span>Надёжность расчёта</h2>
          <h3>Если пойдёт хуже</h3>
          <table class="tbl">
            <colgroup><col style="width: 26%"><col style="width: 16%"><col style="width: 18%"><col style="width: 40%"></colgroup>
            <thead><tr><th>Сценарий</th><th class="num">NPV</th><th class="num">Окупаемость</th><th>Что меняется</th></tr></thead>
            <tbody><tr v-for="row in doc.stress.value" :key="row[0]"><th>{{ row[0] }}</th><td class="num">{{ row[1] }}</td><td class="num">{{ row[2] }}</td><td class="small">{{ row[3] }}</td></tr></tbody>
          </table>
          <h3>Запас прочности — при каком значении NPV станет нулём</h3>
          <table class="tbl">
            <colgroup><col style="width: 34%"><col style="width: 22%"><col style="width: 30%"><col style="width: 14%"></colgroup>
            <thead><tr><th>Параметр</th><th class="num">Сейчас</th><th class="num">Безубыточность</th><th class="num">Запас</th></tr></thead>
            <tbody><tr v-for="row in doc.breakeven.value" :key="row[0]"><th>{{ row[0] }}</th><td class="num wrap">{{ row[1] }}</td><td class="num wrap">{{ row[2] }}</td><td class="num">{{ row[3] }}</td></tr></tbody>
          </table>
          <h3>Что сильнее всего двигает результат покупки</h3>
          <table class="tbl">
            <colgroup><col style="width: 30%"><col style="width: 26%"><col style="width: 30%"><col style="width: 14%"></colgroup>
            <thead><tr><th>Параметр</th><th>Диапазон</th><th class="num">NPV</th><th class="num">Доля</th></tr></thead>
            <tbody><tr v-for="row in doc.tornado.value" :key="row[0]"><th>{{ row[0] }}</th><td class="small">{{ row[1] }}</td><td class="num">{{ row[2] }}</td><td class="num">{{ row[3] }}</td></tr></tbody>
          </table>
          <p class="small muted">Диапазоны — из источников нормативов, а где их нет — по уровню достоверности: закон ±5%, данные ±10%, оценка ±20%, допущение ±35%.</p>
        </section>

        <!-- З. Схема объекта (ТЗ 3.7.4). -->
        <section v-if="doc.floors.value.length" class="sheet">
          <h2 class="ap"><span>З</span>Схема объекта</h2>
          <p class="small muted">Расстановка из шага «Визуализация»: рабочие зоны, точки погрузки и выгрузки, зарядка. Прогон смены с роботами — на шаге визуализации.</p>
          <template v-for="floor in doc.floors.value" :key="floor.id">
            <h3>{{ floor.name }}</h3>
            <PlanSketch :floor="floor" :colors="doc.colors.value" :names="doc.names.value" />
          </template>
        </section>

        <!-- И. Допущения и источники. -->
        <section class="sheet">
          <h2 class="ap"><span>И</span>Допущения и источники данных</h2>
          <p class="small">
            <template v-if="doc.changed.value.length">Изменены в проекте: {{ doc.changed.value.map((item) => item.label.toLowerCase()).join(', ') }}.</template>
            <template v-else>Своих значений в проекте нет: расчёт на условиях объекта и стандарте платформы.</template>
            {{ doc.subsidies.value.length ? ` Господдержка: ${doc.subsidies.value.join(', ')}.` : ' Без господдержки.' }}
          </p>
          <table class="tbl">
            <colgroup><col style="width: 34%"><col style="width: 26%"><col style="width: 20%"><col style="width: 20%"></colgroup>
            <thead><tr><th>Параметр</th><th class="num">Значение</th><th>Источник</th><th>Примечание</th></tr></thead>
            <tbody><tr v-for="row in doc.assumptions.value" :key="row[0]"><th>{{ row[0] }}</th><td class="num wrap">{{ row[1] }}</td><td class="small">{{ row[2] }}</td><td class="small">{{ row[3] }}</td></tr></tbody>
          </table>
          <h3>Источники данных</h3>
          <ol class="list small"><li v-for="(item, index) in doc.sources.value" :key="index">{{ item }}</li></ol>
        </section>

        <!-- К. Методика, аренда, ограничения. -->
        <section class="sheet">
          <h2 class="ap"><span>К</span>Методика, модель аренды и ограничения</h2>
          <h3>Как считали</h3>
          <ul class="list small">
            <li>Количество роботов — по формуле процесса: пиковая потребность в операциях на эффективную производительность робота с учётом готовности и резерва.</li>
            <li>Экономия — люди, чью работу забирают роботы: выработка робота за год против выработки человека, доля операций, целые ставки в каждой смене. Без данных о людях экономия по процессу не считается.</li>
            <li>CAPEX: оборудование, инфраструктура, ПО, интеграция, пусконаладка, обучение, резерв. OPEX: сервис, лицензии, электроэнергия, связь, расходные материалы, ремонт, персонал эксплуатации (диспетчеры).</li>
            <li>Сокращение — по ТК РФ: 2 месяца уведомления, выплаты до 2 средних заработков без страховых взносов.</li>
            <li>Налоги: НДС принимается к вычету, налог на прибыль 25%. Амортизация линейная на срок полезного использования; ускоренная — как мера господдержки. Если горизонт длиннее срока службы, парк покупается заново.</li>
            <li>Деньги во времени — в постоянных ценах; ставка дисконтирования — ключевая ставка Банка России за вычетом цели по инфляции. Финансирование — собственные средства.</li>
            <li>Состав процессов и число роботов платформа подбирает сама — набор с наибольшим NPV в пределах бюджета. Скидки вендора и господдержка сами в итог не включаются.</li>
          </ul>
          <h3>Модель аренды (RaaS)</h3>
          <ul class="list small">
            <li>Платёж — фиксированная ставка в процентах от цены робота в месяц; в неё входят сервис, ремонт, расходники и лицензии. Индексация платежа по договору учитывается сверх инфляции.</li>
            <li>CAPEX аренды — только подготовка площадки: инфраструктура, интеграция, пусконаладка, обучение. Оборудование и ПО — в платеже, то есть в OPEX.</li>
            <li>Срок договора равен горизонту расчёта, выкуп не предусмотрен. Окупаемость и ROI аренды — для вложений во внедрение; основное сравнение с покупкой — по NPV и годовой стоимости.</li>
          </ul>
          <template v-if="doc.limits.value.length">
            <h3>Ограничения расчёта</h3>
            <ul class="list small"><li v-for="(item, index) in doc.limits.value" :key="index">{{ item }}</li></ul>
          </template>
          <p class="note">{{ REPORT_NOTE }} Дата расчёта: {{ doc.today }}.</p>
        </section>
      </template>
      <p v-else class="more no-print">Приложения — объект, решения и парк, экономика процессов, статьи затрат, формулы, надёжность, схема, допущения и источники — в полном отчёте. <button type="button" class="link" @click="mode = 'full'">Показать полностью</button></p>
    </article>
  </ProjectShell>
  <section v-else class="container gone">
    <StepLoading label="Проект" title="Открываем проект" :timer="false" />
  </section>
</template>

<style scoped>
.gone { padding-top: var(--space-8); }
.modes { display: inline-flex; padding: 3px; border-radius: 999px; background: rgba(15, 20, 19, 0.06); }
.modes button { height: 36px; padding: 0 16px; border-radius: 999px; font-size: 14px; font-weight: 700; color: var(--ink-muted); }
.modes button.on { background: #fff; color: var(--brand-700); box-shadow: 0 1px 3px rgba(15, 20, 19, 0.15); }

/* Документ — ширина A4 и типографика в пунктах: на экране как на бумаге. */
.doc { width: 210mm; max-width: 100%; margin: 0 auto; display: grid; gap: 16px; font-size: 10pt; line-height: 1.42; color: #17201d; }
.sheet { box-sizing: border-box; width: 100%; min-height: 297mm; padding: 15mm 15mm 13mm; background: #fff; border-radius: 6px; box-shadow: 0 4px 24px rgba(15, 20, 19, 0.08), 0 0 0 1px rgba(15, 20, 19, 0.06); display: flex; flex-direction: column; gap: 8px; }

/* Обложка: фото на весь верх, тёмный блок с названием и параметрами внизу. */
.cover { position: relative; height: 297mm; padding: 0; overflow: hidden; background: #121817; color: #eef3f1; gap: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.c-hero { position: absolute; inset: 0 0 auto; height: 172mm; margin: 0; }
.c-hero img { width: 100%; height: 100%; object-fit: cover; display: block; }
.c-hero::after { content: ''; position: absolute; inset: 0; background: linear-gradient(180deg, rgba(18, 24, 23, 0.55) 0%, rgba(18, 24, 23, 0) 28%, rgba(18, 24, 23, 0) 62%, #121817 100%); }
.c-top { position: relative; z-index: 1; display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 11mm 13mm 0; }
.c-mark { font-family: var(--font-mono); font-size: 7.5pt; letter-spacing: 0.12em; text-transform: uppercase; color: #8ff0c4; }
.c-body { position: relative; z-index: 1; margin-top: auto; display: grid; gap: 10px; padding: 0 13mm 12mm; }
.c-kicker { font-family: var(--font-mono); font-size: 8pt; letter-spacing: 0.1em; text-transform: uppercase; color: #a9b6b1; }
.c-title { margin: 0; font-family: var(--font-display); font-weight: 700; font-size: 30pt; line-height: 1.05; letter-spacing: -0.02em; color: #fff; }
.c-verdict { display: grid; gap: 3px; padding: 10px 14px; border-radius: 10px; background: rgba(43, 209, 141, 0.14); border-left: 4px solid #2bd18d; }
.c-verdict strong { font-size: 15pt; color: #fff; }
.c-verdict span { font-size: 9.5pt; color: #cfe0d9; }
.c-verdict.warn { background: rgba(240, 177, 74, 0.16); border-color: #f0b14a; }
.c-verdict.bad { background: rgba(229, 88, 75, 0.16); border-color: #e5584b; }
.c-params { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 4px 22px; margin: 4px 0 0; }
.c-params > div { display: flex; justify-content: space-between; gap: 10px; padding: 3px 0; border-bottom: 1px solid rgba(255, 255, 255, 0.08); }
.c-params dt { color: #a9b6b1; font-size: 8.5pt; }
.c-params dd { margin: 0; text-align: right; font-family: var(--font-mono); font-size: 8.5pt; color: #eef3f1; }
.c-foot { display: flex; flex-wrap: wrap; gap: 4px 16px; padding-top: 6px; font-family: var(--font-mono); font-size: 7.5pt; color: #8a9893; }

.s-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; padding-bottom: 6px; border-bottom: 2px solid #0d8455; }
.kicker { font-size: 8pt; letter-spacing: 0.08em; text-transform: uppercase; color: #0d8455; font-weight: 700; }
h2 { margin: 10px 0 2px; font-size: 13pt; break-after: avoid; page-break-after: avoid; }
h3 { margin: 8px 0 2px; font-size: 10.5pt; break-after: avoid; page-break-after: avoid; }
p { margin: 0; }
.muted { color: #5b6763; }
.small { font-size: 8.5pt; }
.mono { font-family: var(--font-mono); }
.verdict { display: grid; gap: 4px; padding: 10px 14px; border-radius: 8px; border-left: 4px solid #0d8455; background: #ecf7f2; break-inside: avoid; }
.verdict strong { font-size: 14pt; line-height: 1.2; }
.verdict.warn { border-color: #d69a2d; background: #fdf4e3; }
.verdict.bad { border-color: #d0493c; background: #fdeceb; }
.kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; break-inside: avoid; }
.kpi { display: grid; gap: 2px; padding: 9px 11px; border-radius: 8px; border: 1px solid #dde5e1; }
.k-label { font-size: 8pt; color: #5b6763; font-weight: 600; }
.k-value { font-size: 13.5pt; font-weight: 800; font-variant-numeric: tabular-nums; white-space: nowrap; }
.k-note { font-size: 7.5pt; color: #7a8682; }
.tbl { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 9pt; }
.tbl th, .tbl td { padding: 4px 6px; border-bottom: 1px solid #e3e9e6; text-align: left; vertical-align: top; overflow-wrap: anywhere; }
.tbl thead th { font-size: 8pt; color: #5b6763; font-weight: 700; border-bottom: 1.5px solid #c9d3cf; }
.tbl tbody th { font-weight: 600; }
.tbl tr { break-inside: avoid; page-break-inside: avoid; }
.tbl .num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.tbl .num.wrap { white-space: normal; }
.tbl tr.total th, .tbl tr.total td { font-weight: 800; border-top: 1.5px solid #c9d3cf; }
.tbl tr.dim td { color: #8a9692; }
.tbl .indent { padding-left: 18px; color: #3d4845; }
.tbl.scen .best { background: #ecf7f2; }
.tbl.scen thead th.best { color: #0b6b45; }
.tag { display: block; font-size: 7pt; text-transform: uppercase; letter-spacing: 0.06em; color: #0d8455; }
.tbl.cash { font-size: 8pt; }
.small-tbl { font-size: 8pt; }
.chart { break-inside: avoid; }
.risk { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; break-inside: avoid; }
.risk > div { display: grid; gap: 2px; padding: 7px 10px; border-radius: 8px; border: 1px solid #dde5e1; }
.r-value { font-weight: 700; font-size: 9.5pt; }
.list { margin: 0; padding-left: 18px; display: grid; gap: 3px; }
.list li { break-inside: avoid; }
.note { margin-top: auto; padding-top: 10px; border-top: 1px solid #e3e9e6; font-size: 7.5pt; color: #7a8682; }
.ap { display: flex; align-items: baseline; gap: 8px; }
.ap span { display: inline-flex; align-items: center; justify-content: center; width: 22px; height: 22px; border-radius: 6px; background: #0d8455; color: #fff; font-size: 10pt; flex: none; }
.two { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; align-items: start; }
.fleet { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.robot { display: grid; grid-template-columns: 60px minmax(0, 1fr); gap: 10px; padding: 8px; border-radius: 8px; border: 1px solid #dde5e1; break-inside: avoid; page-break-inside: avoid; }
.robot.out { opacity: 0.6; }
.robot img { width: 60px; height: 50px; object-fit: contain; border-radius: 6px; background: #eef2f0; }
.r-body { display: grid; gap: 1px; min-width: 0; }
.cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.card { padding: 8px 10px; border-radius: 8px; border: 1px solid #dde5e1; border-left: 4px solid #0d8455; break-inside: avoid; page-break-inside: avoid; display: grid; gap: 4px; align-content: start; }
.card.warn { border-left-color: #d69a2d; }
.card.bad { border-left-color: #d0493c; }
.card.off { border-left-color: #b8c2be; }
.c-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.badge { font-size: 7.5pt; font-weight: 700; color: #3d4845; white-space: nowrap; }
.c-note { color: #8a5200; }
.formulas { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.f-tile { padding: 8px 10px; border-radius: 8px; border: 1px solid #dde5e1; break-inside: avoid; page-break-inside: avoid; display: grid; gap: 4px; align-content: start; min-width: 0; overflow: hidden; }
.f-head { font-weight: 700; font-size: 9pt; }
.f-tile :deep(.formula) { background: none; box-shadow: none; padding: 0; gap: 4px; }
.f-tile :deep(.katex) { font-size: 0.8em; }
.f-tile :deep(.body-sm), .f-tile :deep(.caption), .f-tile :deep(.mono-sm) { font-size: 8pt; }
/* В отчёте формула компактная: формула, подстановка, переменные с источником; длинные пояснения — на экране экономики. */
.f-tile :deep(.f-note) { display: none; }
.f-tile :deep(.f-vars) { gap: 0; }
.f-tile :deep(.f-var) { padding: 1px 0; }
.f-tile :deep(.badge) { font-size: 7pt; padding: 0 5px; }
.more { text-align: center; color: var(--ink-muted); }
.link { color: var(--link); font-weight: 700; }

/* Печать: листы — обычные блоки (Chrome не рвёт страницу между элементами сетки), каждый лист — с новой страницы. */
@media print {
  .doc { display: block; width: 210mm; }
  .sheet { display: block; min-height: 0; border-radius: 0; box-shadow: none; padding: 13mm 14mm 11mm; }
  .sheet > * + * { margin-top: 7px; }
  .sheet + .sheet { break-before: page; page-break-before: always; }
  .cover { display: flex; height: 297mm; padding: 0; }
  .cover > * + * { margin-top: 0; }
  .cover > .c-body { margin-top: auto; }
  .chart :deep(svg) { max-height: 58mm; }
  /* Сетки карточек на печати — колонками: Chrome переносит колонки между листами без пустых страниц. */
  .cards, .formulas, .fleet { display: block; column-count: 2; column-gap: 8px; }
  .cards > *, .formulas > *, .fleet > * { display: inline-grid; width: 100%; margin: 0 0 8px; box-sizing: border-box; }
  .note { margin-top: 12px; }
  .more { display: none; }
}
/* Только для экрана: лист A4 при печати уже 860 px, и без «screen» печать получала мобильную вёрстку. */
@media screen and (max-width: 860px) {
  .sheet:not(.cover) { min-height: 0; padding: 18px; }
  .kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .cards, .risk, .fleet, .formulas, .two { grid-template-columns: 1fr; }
}
</style>
