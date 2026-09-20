<script setup lang="ts">
import { PhMagnifyingGlass, PhSlidersHorizontal, PhFunnelSimple, PhCheckSquare, PhSquare } from '@phosphor-icons/vue'
import { products, catalogTree, availabilityLabel, type Availability } from '~/data/catalog'

useHead({ title: 'Каталог решений' })

const q = ref('')
const sort = ref<'relevance' | 'price' | 'trl' | 'name'>('relevance')
const selectedNode = ref<string>('')
const nodeIds = ref<string[] | null>(null)
const avail = ref<Availability[]>([])
const onlyAuto = ref(false)
const minTrl = ref(1)

const onSelect = (label: string, ids: string[]) => {
  if (selectedNode.value === label) { selectedNode.value = ''; nodeIds.value = null; return }
  selectedNode.value = label
  nodeIds.value = ids
}
const toggleAvail = (a: Availability) => {
  avail.value = avail.value.includes(a) ? avail.value.filter((x) => x !== a) : [...avail.value, a]
}
const reset = () => { q.value = ''; selectedNode.value = ''; nodeIds.value = null; avail.value = []; onlyAuto.value = false; minTrl.value = 1 }

const filtered = computed(() => {
  let list = products.slice()
  if (nodeIds.value) list = list.filter((p) => nodeIds.value!.includes(p.id))
  if (avail.value.length) list = list.filter((p) => avail.value.includes(p.availability))
  if (onlyAuto.value) list = list.filter((p) => p.autoMatch)
  if (minTrl.value > 1) list = list.filter((p) => p.trl >= minTrl.value)
  if (q.value.trim()) {
    const s = q.value.trim().toLowerCase()
    list = list.filter((p) => [p.name, p.manufacturer, p.solutionType, ...p.processes].join(' ').toLowerCase().includes(s))
  }
  if (sort.value === 'price') list.sort((a, b) => (a.priceRub ?? 1e12) - (b.priceRub ?? 1e12))
  if (sort.value === 'trl') list.sort((a, b) => b.trl - a.trl)
  if (sort.value === 'name') list.sort((a, b) => a.name.localeCompare(b.name, 'ru'))
  return list
})

const activeChips = computed(() => {
  const chips: { key: string; label: string; clear: () => void }[] = []
  if (selectedNode.value) chips.push({ key: 'node', label: selectedNode.value, clear: () => { selectedNode.value = ''; nodeIds.value = null } })
  avail.value.forEach((a) => chips.push({ key: `a-${a}`, label: availabilityLabel[a], clear: () => toggleAvail(a) }))
  if (onlyAuto.value) chips.push({ key: 'auto', label: 'Готов к автоподбору', clear: () => { onlyAuto.value = false } })
  if (minTrl.value > 1) chips.push({ key: 'trl', label: `УГТ от ${minTrl.value}`, clear: () => { minTrl.value = 1 } })
  if (q.value.trim()) chips.push({ key: 'q', label: `«${q.value.trim()}»`, clear: () => { q.value = '' } })
  return chips
})

const countOf = (a: Availability) => products.filter((p) => p.availability === a).length
const plural = (n: number) => (n % 10 === 1 && n % 100 !== 11 ? 'модель' : n % 10 >= 2 && n % 10 <= 4 && (n % 100 < 10 || n % 100 >= 20) ? 'модели' : 'моделей')
const emptyHint = computed(() => {
  if (avail.value.length && avail.value.length < 3) return `Снимите фильтр по статусу «${availabilityLabel[avail.value[0]!]}»`
  if (minTrl.value > 7) return 'Опустите порог УГТ: большинство решений имеют УГТ 7–9'
  if (selectedNode.value) return `Выйдите из ветки «${selectedNode.value}»`
  return 'Измените запрос: поиск идёт по названию, производителю и процессу'
})
</script>

<template>
  <section class="container catalog">
    <div class="top" v-reveal>
      <div>
        <div class="label">Каталог</div>
        <h1 class="hero-2">Дерево решений</h1>
        <p class="body muted">Отрасль → тип объекта → процесс → тип решения → продукт. Дерево собирается из справочников, продукт может быть в нескольких ветках.</p>
      </div>
      <div class="search glass glass-strong">
        <PhMagnifyingGlass :size="18" weight="bold" class="s-ic" />
        <input v-model="q" class="s-in" placeholder="Ronavi, Автомакон, комплектация…" aria-label="Поиск по каталогу">
        <span class="caption s-hint">по названию, производителю и процессу</span>
      </div>
    </div>

    <div class="body-grid">
      <aside class="side">
        <div class="side-inner glass">
          <div class="side-block">
            <div class="side-head"><PhFunnelSimple :size="16" weight="bold" /> <span class="label">Дерево</span></div>
            <CatalogTree :nodes="catalogTree" :selected="selectedNode" @select="onSelect" />
          </div>
          <div class="hairline" />
          <div class="side-block">
            <div class="side-head"><PhSlidersHorizontal :size="16" weight="bold" /> <span class="label">Фильтры</span></div>
            <div class="f-group">
              <div class="f-title">Статус</div>
              <button v-for="a in (['operation', 'piloting', 'rnd'] as Availability[])" :key="a" type="button" class="check" :class="{ on: avail.includes(a) }" @click="toggleAvail(a)">
                <PhCheckSquare v-if="avail.includes(a)" :size="18" weight="fill" /><PhSquare v-else :size="18" />
                <span>{{ availabilityLabel[a] }}</span><span class="mono-sm muted">{{ countOf(a) }}</span>
              </button>
            </div>
            <div class="f-group">
              <div class="f-title between">УГТ не ниже <span class="mono-md">{{ minTrl }}</span></div>
              <input v-model.number="minTrl" type="range" min="1" max="9" step="1" class="range" :style="{ '--pct': `${((minTrl - 1) / 8) * 100}%` }" aria-label="Минимальный уровень готовности технологии">
              <div class="range-ticks mono-sm muted"><span>1</span><span>5</span><span>9</span></div>
            </div>
            <div class="f-group">
              <button type="button" class="check" :class="{ on: onlyAuto }" @click="onlyAuto = !onlyAuto">
                <PhCheckSquare v-if="onlyAuto" :size="18" weight="fill" /><PhSquare v-else :size="18" />
                <span>Готов к автоподбору</span>
              </button>
              <div class="caption">УГТ ≥ 7 и статус не «разработка»</div>
            </div>
          </div>
        </div>
      </aside>

      <div class="results">
        <div class="results-head">
          <div class="chips">
            <span class="count h4">Найдено {{ filtered.length }} {{ plural(filtered.length) }}</span>
            <UiChip v-for="c in activeChips" :key="c.key" removable @remove="c.clear" @click="c.clear">{{ c.label }}</UiChip>
            <button v-if="activeChips.length" type="button" class="link body-sm" @click="reset">Сбросить всё</button>
          </div>
          <label class="sort">
            <span class="caption">Сортировка</span>
            <select v-model="sort" class="select">
              <option value="relevance">По релевантности</option>
              <option value="price">По цене</option>
              <option value="trl">По УГТ</option>
              <option value="name">По названию</option>
            </select>
          </label>
        </div>

        <TransitionGroup v-if="filtered.length" name="cards" tag="div" class="grid grid-cards cards">
          <RobotCard v-for="p in filtered" :key="p.id" :product="p" />
        </TransitionGroup>
        <div v-else class="empty glass">
          <div class="h3">По этим условиям ничего нет</div>
          <p class="body muted">{{ emptyHint }}</p>
          <UiButton variant="secondary" @click="reset">Сбросить фильтры</UiButton>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.catalog { padding-top: var(--space-12); padding-bottom: var(--space-16); }
.top { display: grid; grid-template-columns: 1fr minmax(320px, 440px); gap: var(--space-8); align-items: end; margin-bottom: var(--space-8); }
.top > div:first-child { display: grid; gap: 10px; max-width: 64ch; }
.search { display: grid; grid-template-columns: auto 1fr; gap: 0 10px; align-items: center; padding: 10px 16px; border-radius: 16px; }
.s-ic { color: var(--ink-muted); position: relative; z-index: 1; grid-row: 1; }
.s-in { position: relative; z-index: 1; background: none; border: 0; outline: none; font-size: 16px; font-weight: 600; color: var(--ink-strong); min-height: 32px; }
.s-in::placeholder { color: var(--ink-faint); font-weight: 500; }
.s-hint { grid-column: 2; position: relative; z-index: 1; }

.body-grid { display: grid; grid-template-columns: clamp(280px, 18vw, 320px) minmax(0, 1fr); gap: var(--space-6); align-items: start; }
.side { position: sticky; top: 96px; }
.side-inner { display: grid; gap: var(--space-4); padding: var(--space-4); }
.side-inner > * { position: relative; z-index: 1; }
.side-block { display: grid; gap: 10px; }
.side-head { display: flex; align-items: center; gap: 8px; padding: 4px 8px; color: var(--ink-muted); }
.f-group { display: grid; gap: 6px; padding: 4px 8px; }
.f-title { font-size: 13px; font-weight: 700; color: var(--ink-strong); margin-bottom: 2px; }
.check { display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 10px; min-height: 34px; padding: 0 6px; border-radius: 8px; font-size: 14px; font-weight: 500; color: var(--ink-body); text-align: left; transition: background var(--dur-fast) var(--ease); }
.check:hover { background: rgba(15, 20, 19, 0.05); }
.check svg { color: var(--ink-faint); }
.check.on svg { color: var(--brand-600); }
.range-ticks { display: flex; justify-content: space-between; }

.results { display: grid; gap: var(--space-5); min-width: 0; }
.results-head { display: flex; justify-content: space-between; align-items: center; gap: var(--space-4); flex-wrap: wrap; }
.chips { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.count { margin-right: 8px; }
.sort { display: flex; align-items: center; gap: 10px; }
.sort .select { width: 190px; min-height: 40px; }
.cards { position: relative; }
.cards-enter-active, .cards-leave-active { transition: opacity var(--dur-mid) var(--ease), transform var(--dur-mid) var(--ease); }
.cards-enter-from, .cards-leave-to { opacity: 0; transform: scale(0.98); }
.cards-leave-active { position: absolute; }
.cards-move { transition: transform var(--dur-slow) var(--ease); }
.empty { padding: var(--space-12); text-align: center; display: grid; gap: var(--space-3); justify-items: center; }
.empty > * { position: relative; z-index: 1; }
@media (max-width: 1100px) { .body-grid { grid-template-columns: 1fr; } .side { position: static; } .top { grid-template-columns: 1fr; } }
</style>
