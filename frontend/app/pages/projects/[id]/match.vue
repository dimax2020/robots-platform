<script setup lang="ts">
import { PhCaretDown, PhScales, PhFunction, PhPlay, PhArrowSquareOut } from '@phosphor-icons/vue'
import { projects } from '~/data/projects'
import { labelProcess } from '~/data/siteFields'
import { fetchErrorMessage, type CalcCandidate, type CalcTrace } from '~/composables/useCalc'

const route = useRoute()
const id = computed(() => route.params.id as string)
const { products, defs, pending: catalogPending } = useCatalog()
const { project, detail, run, pending, error, refresh, calculate } = useCalc(id)
const demoProject = computed(() => projects.find((p) => p.id === id.value))
const shell = computed(() => project.value ?? demoProject.value)
useHead({ title: () => `Подбор · ${shell.value?.name ?? 'проект'}` })
const { toggle, has } = useCompare()

const tab = ref<'fit' | 'check' | 'excluded'>('fit')
const open = ref<string | null>(null)
const calculating = ref(false)
const calcError = ref('')

const productOf = (productId: string) => products.value.find((p) => p.id === productId)
const attrLabel = (key: string) => defs.value.get(key)?.label ?? key
const processName = (code: string) => {
  const task = detail.value?.tasks.find((t) => t.process_code === code)
  return labelProcess(code, task?.name)
}

// все посчитанные количества, а не только вошедшие в парк: свой расчёт
// показывается и тому кандидату, что проиграл по счёту
const optionOf = (c: CalcCandidate) =>
  (run.value?.options ?? []).find((o) => o.productId === c.productId && o.processCode === c.processCode)
const countOf = (c: CalcCandidate) => optionOf(c)?.count
const formulaOf = (c: CalcCandidate) => optionOf(c)?.formula

const fit = computed(() => (run.value?.candidates ?? []).filter((c) => c.verdict === 'pass'))
const check = computed(() => (run.value?.candidates ?? []).filter((c) => c.verdict === 'unknown'))
const excluded = computed(() => (run.value?.candidates ?? []).filter((c) => c.verdict === 'fail'))
const notInAuto = computed(() => products.value.filter((x) => !x.autoMatch))

const tabs = computed(() => [
  { id: 'fit', label: 'Подходит', count: fit.value.length },
  { id: 'check', label: 'Требует проверки', count: check.value.length },
  { id: 'excluded', label: 'Исключён', count: excluded.value.length },
])
const list = computed(() => (tab.value === 'fit' ? fit.value : tab.value === 'check' ? check.value : excluded.value))

const rowKey = (c: CalcCandidate) => `${c.productId}:${c.processCode}`
const tracesOf = (productId: string) => (run.value?.trace ?? []).filter((t) => t.productId === productId)
const STEP_TITLE: Record<string, string> = {
  prepare: 'Подготовка входа',
  match: 'Жёсткие проверки',
  size: 'Расчёт количества',
  rank: 'Скоринг',
}
const STEP_ORDER = ['prepare', 'match', 'size', 'rank']
const groupedTrace = (productId: string) => {
  const items = tracesOf(productId)
  const seen = new Set<string>()
  const steps = [
    ...STEP_ORDER.filter((s) => items.some((t) => t.step === s)),
    ...items.map((t) => t.step).filter((s) => !STEP_ORDER.includes(s)),
  ]
  return steps
    .filter((s) => {
      if (seen.has(s)) return false
      seen.add(s)
      return true
    })
    .map((step) => ({
      step,
      title: STEP_TITLE[step] ?? step,
      items: items.filter((t) => t.step === step),
    }))
}
const globalTrace = computed(() => (run.value?.trace ?? []).filter((t) => !t.productId))
const queriesOf = (productId: string) => (run.value?.vendorQueries ?? []).filter((q) => q.productId === productId)

const emptyWhy = computed(() => {
  if (!run.value) return ''
  if (run.value.candidates.length) return ''
  const msgs = globalTrace.value.map((t) => t.message).filter(Boolean)
  if (!(detail.value?.tasks.length)) return 'В проекте нет задач: нечего сопоставлять с каталогом. Добавьте процессы на шаге параметров.'
  if (msgs.length) return msgs.join(' ')
  return 'Кандидатов нет: ни один продукт не прошёл отбор по процессам проекта. Проверьте тип объекта и список задач.'
})

watch(fit, (rows) => {
  if (!open.value && rows[0]) open.value = rowKey(rows[0])
}, { immediate: true })

const runCalc = async () => {
  if (calculating.value || !project.value) return
  calculating.value = true
  calcError.value = ''
  try {
    await calculate()
    await refresh()
    tab.value = 'fit'
  } catch (e: unknown) {
    calcError.value = fetchErrorMessage(e, 'Не удалось запустить расчёт')
  } finally {
    calculating.value = false
  }
}

const sourceRest = (source?: string) => {
  if (!source) return ''
  return source.replace(/^\[[A-D]\]\s*/i, '')
}

const verdictTone = (v?: CalcTrace['verdict']) => {
  if (v === 'pass') return 'ok'
  if (v === 'fail') return 'danger'
  if (v === 'unknown') return 'warn'
  return 'neutral'
}
const verdictLabel = (v?: CalcTrace['verdict']) => {
  if (v === 'pass') return 'пройдено'
  if (v === 'fail') return 'отказ'
  if (v === 'unknown') return 'нет данных'
  return ''
}

const live = computed(() => Boolean(project.value))
const noRun = computed(() => live.value && !pending.value && !error.value && !run.value)
const loading = computed(() => pending.value || catalogPending.value)
</script>

<template>
  <ProjectShell
    v-if="shell"
    :project="shell"
    current="match"
    title="Подбор и объяснение"
    lead="Три списка. Пустое поле не равно отказу: такие решения лежат отдельно, с перечнем недостающих данных и запросом вендору."
  >
    <template #actions>
      <UiButton v-if="live && (noRun || run)" :disabled="calculating" size="lg" @click="runCalc">
        <template #icon><PhPlay :size="16" weight="bold" /></template>
        {{ calculating ? 'Считаем…' : run ? 'Пересчитать' : 'Запустить подбор' }}
      </UiButton>
      <UiButton v-if="live && run" :to="`/projects/${shell.id}/compare`" size="lg" variant="secondary">
        <template #icon><PhScales :size="16" weight="bold" /></template>Открыть сравнение
      </UiButton>
    </template>

    <UiCallout v-if="!live" tone="warn" title="Это демонстрационный макет">
      Живой подбор работает с проектом, сохранённым на сервере. Создайте проект — площадка и задачи предзаполнятся из профиля объекта.
      <div class="call-actions">
        <UiButton to="/projects/new" size="sm">Создать проект</UiButton>
      </div>
    </UiCallout>

    <UiCallout v-else-if="error" tone="danger" title="Не удалось загрузить расчёт">
      {{ fetchErrorMessage(error, 'Сервер не ответил. Проверьте, что API запущен.') }}
    </UiCallout>

    <div v-else-if="loading" class="summary" v-reveal>
      <div v-for="i in 4" :key="i" class="sum glass"><UiSkeleton h="56px" /></div>
    </div>

    <template v-else-if="noRun">
      <UiCallout tone="info" title="Расчёт ещё не запускался">
        Параметры площадки сохранены, но конвейер подбора не запускали. Запуск запишет прогон: корзины, количество и трассировку каждого числа.
        <div class="call-actions">
          <UiButton :disabled="calculating" @click="runCalc">
            <template #icon><PhPlay :size="16" weight="bold" /></template>
            {{ calculating ? 'Считаем…' : 'Запустить подбор' }}
          </UiButton>
        </div>
      </UiCallout>
    </template>

    <template v-else-if="run">
      <UiCallout v-if="calcError" tone="danger" title="Расчёт не прошёл">{{ calcError }}</UiCallout>

      <div class="summary" v-reveal>
        <div class="sum glass ok"><span class="display-3">{{ fit.length }}</span><span><span class="h4">Подходит</span><span class="caption block">все жёсткие проверки пройдены</span></span></div>
        <div class="sum glass warn"><span class="display-3">{{ check.length }}</span><span><span class="h4">Требует проверки</span><span class="caption block">нет отказа, но часть полей пустая</span></span></div>
        <div class="sum glass danger"><span class="display-3">{{ excluded.length }}</span><span><span class="h4">Исключён</span><span class="caption block">хотя бы одна проверка не пройдена</span></span></div>
        <div class="sum glass neutral"><span class="display-3">{{ notInAuto.length }}</span><span><span class="h4">Вне автоподбора</span><span class="caption block">УГТ ниже 7 или разработка</span></span></div>
      </div>

      <div v-if="globalTrace.length" class="prep glass" v-reveal>
        <div class="h4">Как подготовлен вход</div>
        <div class="caption">Преобразования площадки и потока, общие для всех кандидатов. Каждое число — из трассировки.</div>
        <div v-for="(t, i) in globalTrace" :key="`${t.step}-${i}`" class="prep-item">
          <UiBadge :tone="verdictTone(t.verdict)" size="sm">{{ STEP_TITLE[t.step] ?? t.step }}</UiBadge>
          <div>
            <p class="body-sm">{{ t.message }}</p>
            <code v-if="t.formula" class="formula">{{ t.formula }}</code>
            <div v-if="t.value != null" class="caption">{{ t.value.toLocaleString('ru-RU') }}<template v-if="t.unit"> {{ t.unit }}</template></div>
            <div v-if="t.source" class="ex-src"><UiSourceTag :text="t.source" /><span class="caption">{{ sourceRest(t.source) }}</span></div>
          </div>
        </div>
      </div>

      <div class="tabs-row" v-reveal="1">
        <UiTabs v-model="tab" :tabs="tabs" />
      </div>

      <div v-if="!list.length" class="empty glass" v-reveal="2">
        <div class="h3">{{ tab === 'fit' ? 'Пока никто не прошёл' : tab === 'check' ? 'Пустых полей нет' : 'Отказов нет' }}</div>
        <p class="body muted">{{ emptyWhy || (tab === 'fit' ? 'Либо кандидаты в других корзинах, либо подбор не нашёл подходящих решений.' : 'Переключите вкладку — состав корзин собран из вердиктов расчёта.') }}</p>
      </div>

      <TransitionGroup v-else name="rows" tag="div" class="rows" v-reveal="2">
        <article v-for="r in list" :key="rowKey(r)" class="mrow glass" :class="[tab, { open: open === rowKey(r) }]">
          <div class="mrow-main">
            <img :src="productOf(r.productId)?.image ?? '/img/robot-amr-pallet.png'" alt="" class="thumb">
            <div class="who">
              <NuxtLink v-if="productOf(r.productId)" :to="`/catalog/${productOf(r.productId)!.slug}`" class="h4">{{ productOf(r.productId)!.name }}</NuxtLink>
              <span v-else class="h4">{{ queriesOf(r.productId)[0]?.productName ?? 'Продукт не в текущем каталоге' }}</span>
              <div class="caption">{{ productOf(r.productId)?.solutionType ?? queriesOf(r.productId)[0]?.manufacturer }} · {{ processName(r.processCode) }}</div>
            </div>

            <div v-if="tab === 'fit'" class="metric">
              <span class="caption">Оценка</span>
              <span class="score"><span class="bar"><span :style="{ width: `${(r.score ?? 0) * 100}%` }" /></span><span class="mono-md">{{ Math.round((r.score ?? 0) * 100) }}</span></span>
            </div>
            <div v-if="tab === 'fit'" class="metric">
              <span class="caption">Расчётное количество</span>
              <span class="display-4">{{ countOf(r) ?? '—' }} <span class="unit">шт.</span></span>
            </div>

            <div v-if="tab === 'check'" class="metric wide">
              <span class="caption">Не хватает данных</span>
              <span class="missing"><span v-for="m in r.unknown" :key="m" class="miss">{{ attrLabel(m) }}</span></span>
            </div>
            <div v-if="tab === 'check'" class="metric vendor">
              <span class="caption">Запрос вендору</span>
              <span class="body-sm">{{ queriesOf(r.productId).map((q) => attrLabel(q.field)).join(', ') || 'поля не сформированы' }}</span>
              <a
                v-if="queriesOf(r.productId).find((q) => q.sourceUrl)"
                class="src-link caption"
                :href="queriesOf(r.productId).find((q) => q.sourceUrl)!.sourceUrl"
                target="_blank"
                rel="noreferrer"
              >Источник <PhArrowSquareOut :size="12" /></a>
            </div>

            <div v-if="tab === 'excluded'" class="metric wide">
              <span class="caption">Причина отказа</span>
              <span class="body-sm reason">{{ r.failed.map(attrLabel).join(', ') || 'жёсткое правило не пройдено' }}</span>
            </div>

            <button type="button" class="expand" :aria-expanded="open === rowKey(r)" @click="open = open === rowKey(r) ? null : rowKey(r)">
              <PhFunction :size="16" weight="bold" /> Объяснение <PhCaretDown :size="14" weight="bold" class="caret" />
            </button>
          </div>

          <Transition name="exp">
            <div v-if="open === rowKey(r)" class="explain">
              <div v-if="formulaOf(r)" class="ex">
                <div class="ex-title h4">Итоговая формула количества</div>
                <code class="formula">{{ formulaOf(r) }}</code>
                <p class="body-sm human">Число на карточке взято из этой записи трассировки, не из скрытого коэффициента.</p>
              </div>
              <div v-for="g in groupedTrace(r.productId)" :key="g.step" class="ex">
                <div class="ex-title h4">{{ g.title }}</div>
                <div v-for="(e, i) in g.items" :key="`${g.step}-${i}`" class="ex-item">
                  <div class="ex-head">
                    <UiBadge v-if="e.verdict" :tone="verdictTone(e.verdict)" size="sm">{{ verdictLabel(e.verdict) }}</UiBadge>
                    <p class="body-sm human">{{ e.message }}</p>
                  </div>
                  <code v-if="e.formula" class="formula">{{ e.formula }}</code>
                  <div v-if="e.value != null" class="caption val">{{ e.value.toLocaleString('ru-RU') }}<template v-if="e.unit"> {{ e.unit }}</template></div>
                  <div class="ex-src">
                    <UiSourceTag v-if="e.source" :text="e.source" />
                    <span v-if="e.source" class="caption">{{ sourceRest(e.source) }}</span>
                    <span v-else class="caption">без источника: правило платформы</span>
                  </div>
                </div>
              </div>
              <div v-if="!groupedTrace(r.productId).length && !formulaOf(r)" class="ex">
                <p class="body-sm human">Для этой строки трассировка пуста — числу в интерфейсе не на что опереться.</p>
              </div>
              <div class="ex-foot">
                <span class="caption">Это текст для заказчика, не технический лог. Формула с подставленными числами и единицами.</span>
                <button type="button" class="link body-sm" @click="toggle(r.productId)">{{ has(r.productId) ? 'Убрать из сравнения' : 'Добавить в сравнение' }}</button>
              </div>
            </div>
          </Transition>
        </article>
      </TransitionGroup>

      <UiCallout tone="warn" title="Вне автоподбора">
        Продукты в разработке и с УГТ ниже 7 в автоподбор не попадают<template v-if="notInAuto.length">: {{ notInAuto.map((x) => x.name).join(', ') }}</template>. Их можно добавить в сравнение вручную, с предупреждением.
      </UiCallout>
    </template>
  </ProjectShell>

  <section v-else class="container missing">
    <UiCallout tone="danger" title="Проект не найден">Нет ни сохранённого расчёта, ни демо-макета с таким адресом.</UiCallout>
    <UiButton to="/projects">К списку проектов</UiButton>
  </section>
</template>

<style scoped>
.summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-4); }
.sum { display: grid; grid-template-columns: auto 1fr; gap: 14px; align-items: center; padding: 16px 18px; }
.sum > * { position: relative; z-index: 1; }
.sum .display-3 { min-width: 44px; }
.ok .display-3 { color: var(--state-ok); }
.warn .display-3 { color: var(--state-warn); }
.danger .display-3 { color: var(--state-danger); }
.neutral .display-3 { color: var(--ink-muted); }
.block { display: block; }
.tabs-row { max-width: 560px; }
.rows { display: grid; gap: 10px; }
.mrow { overflow: hidden; }
.mrow-main { position: relative; z-index: 1; display: grid; grid-template-columns: 64px minmax(200px, 1.4fr) 1fr 1fr auto; gap: var(--space-5); align-items: center; padding: 14px 16px; }
.check .mrow-main { grid-template-columns: 64px minmax(200px, 1.2fr) 2fr 1fr auto; }
.excluded .mrow-main { grid-template-columns: 64px minmax(200px, 1.2fr) 2fr auto; }
.thumb { width: 64px; height: 64px; object-fit: cover; border-radius: 14px; }
.who .h4 { color: var(--ink-strong); }
.metric { display: grid; gap: 4px; }
.score { display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: center; min-width: 140px; }
.bar { height: 6px; border-radius: 3px; background: rgba(15, 20, 19, 0.08); overflow: hidden; }
.bar span { display: block; height: 100%; background: linear-gradient(90deg, var(--brand-400), var(--brand-600)); border-radius: 3px; }
.unit { font-family: var(--font-sans); font-size: 14px; font-weight: 600; color: var(--ink-muted); }
.missing { display: flex; gap: 6px; flex-wrap: wrap; }
.miss { font-size: 12px; font-weight: 600; padding: 4px 8px; border-radius: 6px; background: var(--state-warn-tint); color: var(--state-warn); }
.reason { color: var(--state-danger); font-weight: 600; }
.vendor .src-link { display: inline-flex; align-items: center; gap: 4px; color: var(--link); font-weight: 600; }
.expand { display: inline-flex; align-items: center; gap: 6px; height: 36px; padding: 0 12px; border-radius: 10px; font-size: 13px; font-weight: 700; color: var(--ink-strong); background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); transition: all var(--dur-fast) var(--ease); white-space: nowrap; }
.expand:hover { background: #fff; }
.caret { transition: transform var(--dur-fast) var(--ease); }
.open .caret { transform: rotate(180deg); }
.explain { position: relative; z-index: 1; display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; padding: 4px 16px 16px; }
.ex { display: grid; gap: 10px; padding: 14px; border-radius: 14px; background: rgba(255, 255, 255, 0.65); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); align-content: start; }
.ex-item { display: grid; gap: 8px; padding-top: 8px; border-top: 1px solid rgba(15, 20, 19, 0.06); }
.ex-item:first-of-type { padding-top: 0; border-top: 0; }
.ex-head { display: grid; gap: 6px; }
.formula { display: block; padding: 10px 12px; border-radius: 10px; background: var(--surface-graphite); color: var(--brand-300); font-family: var(--font-mono); font-size: 12.5px; line-height: 1.5; white-space: pre-wrap; }
.human { color: var(--ink-body); }
.ex-src { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ex-foot { grid-column: 1 / -1; display: flex; justify-content: space-between; align-items: center; gap: 12px; padding-top: 4px; }
.prep { padding: 16px 18px; display: grid; gap: 12px; }
.prep > * { position: relative; z-index: 1; }
.prep-item { display: grid; grid-template-columns: auto 1fr; gap: 12px; align-items: start; }
.prep-item .formula { margin-top: 8px; }
.empty { padding: var(--space-10); text-align: center; display: grid; gap: 8px; justify-items: center; }
.empty > * { position: relative; z-index: 1; }
.call-actions { margin-top: 10px; }
.missing { padding-top: var(--space-12); display: grid; gap: var(--space-4); justify-items: start; }
.rows-enter-active, .rows-leave-active { transition: opacity var(--dur-mid) var(--ease), transform var(--dur-mid) var(--ease); }
.rows-enter-from, .rows-leave-to { opacity: 0; transform: translateY(8px); }
.rows-leave-active { position: absolute; width: 100%; }
.exp-enter-active, .exp-leave-active { transition: opacity var(--dur-mid) var(--ease), transform var(--dur-mid) var(--ease); }
.exp-enter-from, .exp-leave-to { opacity: 0; transform: translateY(-6px); }
@media (max-width: 1100px) { .summary { grid-template-columns: 1fr 1fr; } .mrow-main, .check .mrow-main, .excluded .mrow-main { grid-template-columns: 64px 1fr; } }
</style>
