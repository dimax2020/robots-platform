<script setup lang="ts">
import { PhCaretDown, PhArrowRight, PhEnvelopeSimple, PhScales, PhFunction } from '@phosphor-icons/vue'
import { projectById, matchFit, matchCheck, matchExcluded, isFullPath, type MatchRow } from '~/data/projects'
import { demoProducts as products } from '~/data/demo'

const route = useRoute()
const project = computed(() => projectById(route.params.id as string))
useHead({ title: () => `Подбор · ${project.value.name}` })
const { toggle, has } = useCompare()

const p = (id: string) => products.find((x) => x.id === id)!
const open = ref<string | null>('p-01')
const tab = ref<'fit' | 'check' | 'excluded'>('fit')
const tabs = computed(() => [
  { id: 'fit', label: 'Подходит', count: matchFit.length },
  { id: 'check', label: 'Требует проверки', count: matchCheck.length },
  { id: 'excluded', label: 'Исключён', count: matchExcluded.length },
])
const list = computed<MatchRow[]>(() => tab.value === 'fit' ? matchFit : tab.value === 'check' ? matchCheck : matchExcluded)
const notInAuto = computed(() => products.filter((x) => !x.autoMatch))
</script>

<template>
  <ProjectShell :project="project" current="match" title="Подбор и объяснение" lead="Три списка. Пустое поле не равно отказу: такие решения лежат отдельно, с перечнем недостающих данных и запросом вендору.">
    <template #actions>
      <UiButton v-if="isFullPath(project)" :to="`/projects/${project.id}/scenarios`" size="lg">К сценариям<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
      <UiButton v-else to="/catalog/compare" size="lg" variant="secondary"><template #icon><PhScales :size="16" weight="bold" /></template>Открыть сравнение</UiButton>
    </template>

    <div class="summary" v-reveal>
      <div class="sum glass ok"><span class="display-3">{{ matchFit.length }}</span><span><span class="h4">Подходит</span><span class="caption block">все жёсткие проверки пройдены</span></span></div>
      <div class="sum glass warn"><span class="display-3">{{ matchCheck.length }}</span><span><span class="h4">Требует проверки</span><span class="caption block">нет отказа, но часть полей пустая</span></span></div>
      <div class="sum glass danger"><span class="display-3">{{ matchExcluded.length }}</span><span><span class="h4">Исключён</span><span class="caption block">хотя бы одна проверка не пройдена</span></span></div>
      <div class="sum glass neutral"><span class="display-3">{{ notInAuto.length }}</span><span><span class="h4">Вне автоподбора</span><span class="caption block">УГТ ниже 7 или разработка</span></span></div>
    </div>

    <div class="tabs-row" v-reveal="1">
      <UiTabs v-model="tab" :tabs="tabs" />
    </div>

    <TransitionGroup name="rows" tag="div" class="rows" v-reveal="2">
      <article v-for="r in list" :key="r.productId" class="mrow glass" :class="[tab, { open: open === r.productId }]">
        <div class="mrow-main">
          <img :src="p(r.productId).image" alt="" class="thumb">
          <div class="who">
            <NuxtLink :to="`/catalog/${p(r.productId).slug}`" class="h4">{{ p(r.productId).name }}</NuxtLink>
            <div class="caption">{{ p(r.productId).solutionType }} · {{ p(r.productId).manufacturer }}</div>
          </div>

          <div v-if="tab === 'fit'" class="metric">
            <span class="caption">Оценка</span>
            <span class="score"><span class="bar"><span :style="{ width: `${(r.score ?? 0) * 100}%` }" /></span><span class="mono-md">{{ Math.round((r.score ?? 0) * 100) }}</span></span>
          </div>
          <div v-if="tab === 'fit'" class="metric">
            <span class="caption">Расчётное количество</span>
            <span class="display-4">{{ r.count }} <span class="unit">шт.</span></span>
          </div>

          <div v-if="tab === 'check'" class="metric wide">
            <span class="caption">Не хватает данных</span>
            <span class="missing"><span v-for="m in r.missing" :key="m" class="miss">{{ m }}</span></span>
          </div>
          <div v-if="tab === 'check'" class="metric">
            <UiButton variant="secondary" size="sm"><template #icon><PhEnvelopeSimple :size="14" weight="bold" /></template>Запрос вендору</UiButton>
          </div>

          <div v-if="tab === 'excluded'" class="metric wide">
            <span class="caption">Причина отказа</span>
            <span class="body-sm reason">{{ r.reason }}</span>
          </div>

          <button type="button" class="expand" :aria-expanded="open === r.productId" @click="open = open === r.productId ? null : r.productId">
            <PhFunction :size="16" weight="bold" /> Объяснение <PhCaretDown :size="14" weight="bold" class="caret" />
          </button>
        </div>

        <Transition name="exp">
          <div v-if="open === r.productId" class="explain">
            <div v-for="e in r.explanation" :key="e.title" class="ex">
              <div class="ex-title h4">{{ e.title }}</div>
              <code class="formula">{{ e.formula }}</code>
              <p class="body-sm human">{{ e.human }}</p>
              <div class="ex-src"><UiSourceTag v-if="e.sourceId" :source-id="e.sourceId" /><span v-else class="caption">без источника: правило платформы</span></div>
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
      Продукты в разработке и с УГТ ниже 7 в автоподбор не попадают: {{ notInAuto.map(x => x.name).join(', ') }}. Их можно добавить в сравнение вручную, с предупреждением.
    </UiCallout>
  </ProjectShell>
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
.check .mrow-main { grid-template-columns: 64px minmax(200px, 1.2fr) 2fr auto auto; }
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
.expand { display: inline-flex; align-items: center; gap: 6px; height: 36px; padding: 0 12px; border-radius: 10px; font-size: 13px; font-weight: 700; color: var(--ink-strong); background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); transition: all var(--dur-fast) var(--ease); white-space: nowrap; }
.expand:hover { background: #fff; }
.caret { transition: transform var(--dur-fast) var(--ease); }
.open .caret { transform: rotate(180deg); }
.explain { position: relative; z-index: 1; display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; padding: 4px 16px 16px; }
.ex { display: grid; gap: 8px; padding: 14px; border-radius: 14px; background: rgba(255, 255, 255, 0.65); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); align-content: start; }
.formula { display: block; padding: 10px 12px; border-radius: 10px; background: var(--surface-graphite); color: var(--brand-300); font-family: var(--font-mono); font-size: 12.5px; line-height: 1.5; white-space: pre-wrap; }
.human { color: var(--ink-body); }
.ex-foot { grid-column: 1 / -1; display: flex; justify-content: space-between; align-items: center; gap: 12px; padding-top: 4px; }
.rows-enter-active, .rows-leave-active { transition: opacity var(--dur-mid) var(--ease), transform var(--dur-mid) var(--ease); }
.rows-enter-from, .rows-leave-to { opacity: 0; transform: translateY(8px); }
.rows-leave-active { position: absolute; width: 100%; }
.exp-enter-active, .exp-leave-active { transition: opacity var(--dur-mid) var(--ease), transform var(--dur-mid) var(--ease); }
.exp-enter-from, .exp-leave-to { opacity: 0; transform: translateY(-6px); }
</style>
