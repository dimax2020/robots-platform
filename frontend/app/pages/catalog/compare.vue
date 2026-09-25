<script setup lang="ts">
import { PhX, PhPlus, PhWarning, PhDownloadSimple } from '@phosphor-icons/vue'
import { attrGroups, availabilityLabel, availabilityTone, formatRub, type AttrValue, type Product } from '~/data/catalog'

const { products, ensureCompareData } = useCatalog()
// Значения характеристик приходят массовой выдачей, её просит тот, кому она нужна
await ensureCompareData()

useHead({ title: 'Сравнение решений' })
const { ids, toggle } = useCompare()
const items = computed(() => ids.value.map((id) => products.value.find((p) => p.id === id)!).filter(Boolean))
const candidates = computed(() => products.value.filter((p) => !ids.value.includes(p.id)))
const adding = ref(false)

// Строки из одного справочника: объединение ключей всех выбранных продуктов по группам
const rows = computed(() => {
  const groups = attrGroups.filter((g) => g.code !== 'identification' && g.code !== 'data_quality')
  return groups.map((g) => {
    const keys = new Map<string, string>()
    items.value.forEach((p) => p.attrs.filter((a) => a.group === g.code).forEach((a) => keys.set(a.key, a.label)))
    return { group: g, keys: Array.from(keys.entries()) }
  }).filter((g) => g.keys.length)
})
const cell = (p: Product, key: string, group: AttrValue['group']): AttrValue =>
  p.attrs.find((a) => a.key === key) ?? { key, label: '', group, status: 'not_applicable' }
const manual = (p: Product) => !p.autoMatch
</script>

<template>
  <section class="container compare">
    <div class="between head" v-reveal>
      <div>
        <div class="label">Сравнение</div>
        <h1 class="hero-2">Рядом по одним и тем же полям</h1>
        <p class="body muted">Строки берутся из справочника характеристик, того же, что и карточка продукта. Пустые значения и «не применимо» показаны явно.</p>
      </div>
      <div class="row">
        <UiButton variant="secondary" @click="adding = !adding"><template #icon><PhPlus :size="16" weight="bold" /></template>Добавить продукт</UiButton>
        <UiButton variant="secondary"><template #icon><PhDownloadSimple :size="16" weight="bold" /></template>Выгрузить CSV</UiButton>
      </div>
    </div>

    <Transition name="fade">
      <div v-if="adding" class="picker glass">
        <div class="picker-head between">
          <span class="h4">Добавить в сравнение</span>
          <span class="caption">Можно вручную добавить продукт с УГТ ниже 5 или со статусом «разработка». Он не участвовал в автоподборе.</span>
        </div>
        <div class="picker-grid">
          <button v-for="p in candidates" :key="p.id" type="button" class="pick" @click="toggle(p.id)">
            <img :src="p.image" alt="">
            <span class="pick-text"><span class="body-sm strong">{{ p.name }}</span><span class="caption">{{ p.solutionType }} · УГТ {{ p.trl }}</span></span>
            <UiBadge v-if="manual(p)" tone="warn" size="sm">вне автоподбора</UiBadge>
          </button>
        </div>
      </div>
    </Transition>

    <div v-if="items.length" class="table-wrap glass glass-xl" v-reveal="1">
      <table class="cmp">
        <thead>
          <tr>
            <th class="param-h"><span class="label">Характеристика</span></th>
            <th v-for="p in items" :key="p.id" class="prod">
              <div class="prod-card">
                <button type="button" class="rm" :aria-label="`Убрать ${p.name}`" @click="toggle(p.id)"><PhX :size="12" weight="bold" /></button>
                <img :src="p.image" :alt="p.name">
                <NuxtLink :to="`/catalog/${p.slug}`" class="h4">{{ p.name }}</NuxtLink>
                <span class="caption">{{ p.manufacturer }}</span>
                <span class="prod-badges">
                  <UiBadge :tone="availabilityTone[p.availability]" size="sm">{{ availabilityLabel[p.availability] }}</UiBadge>
                  <UiBadge tone="neutral" mono size="sm">УГТ {{ p.trl }}</UiBadge>
                </span>
                <span v-if="manual(p)" class="manual"><PhWarning :size="12" weight="fill" /> Не входил в автоподбор</span>
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr class="sec"><td :colspan="items.length + 1"><span class="label">Цена</span></td></tr>
          <tr>
            <td class="param">Стоимость единицы</td>
            <td v-for="p in items" :key="p.id" class="val"><span class="mono-md strong">{{ formatRub(p.priceRub) }}</span><span v-if="p.priceNote" class="caption block">{{ p.priceNote }}</span></td>
          </tr>
          <template v-for="g in rows" :key="g.group.code">
            <tr class="sec"><td :colspan="items.length + 1"><span class="label">{{ g.group.label }}</span></td></tr>
            <tr v-for="[key, label] in g.keys" :key="key">
              <td class="param">{{ label }}</td>
              <td v-for="p in items" :key="p.id" class="val"><UiValueCell :attr="cell(p, key, g.group.code)" align="right" /></td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
    <div v-else class="empty glass">
      <div class="h3">В сравнении пока пусто</div>
      <p class="body muted">Отметьте модели в каталоге кнопкой «Сравнить» или добавьте продукт здесь.</p>
      <UiButton to="/catalog" variant="secondary">Открыть каталог</UiButton>
    </div>
  </section>
</template>

<style scoped>
.compare { padding-top: var(--space-12); padding-bottom: var(--space-16); display: grid; gap: var(--space-6); }
.head { align-items: flex-end; }
.head > div:first-child { display: grid; gap: 10px; max-width: 64ch; }
.picker { padding: var(--space-5); display: grid; gap: var(--space-4); }
.picker > * { position: relative; z-index: 1; }
.picker-head .caption { max-width: 60ch; text-align: right; }
.picker-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.pick { display: grid; grid-template-columns: 48px 1fr auto; gap: 12px; align-items: center; padding: 8px 10px; border-radius: 12px; background: rgba(255, 255, 255, 0.6); text-align: left; transition: background var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease); }
.pick:hover { background: #fff; box-shadow: inset 0 0 0 1px var(--border-hairline); }
.pick img { width: 48px; height: 48px; object-fit: cover; border-radius: 10px; }
.pick-text { display: grid; }
.table-wrap { padding: var(--space-3); overflow-x: auto; }
.cmp { position: relative; z-index: 1; min-width: 100%; }
.cmp th, .cmp td { padding: 12px 16px; vertical-align: top; }
.param-h { text-align: left; vertical-align: bottom; width: 240px; }
.prod { text-align: left; min-width: 220px; }
.prod-card { position: relative; display: grid; gap: 4px; padding: 12px; border-radius: 16px; background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.prod-card img { width: 100%; aspect-ratio: 4 / 3; object-fit: cover; border-radius: 12px; margin-bottom: 6px; }
.prod-card .h4 { color: var(--ink-strong); }
.prod-badges { display: flex; gap: 6px; margin-top: 4px; }
.rm { position: absolute; top: 18px; right: 18px; z-index: 2; width: 24px; height: 24px; border-radius: 50%; background: var(--surface-graphite); color: #fff; display: inline-flex; align-items: center; justify-content: center; }
.manual { display: inline-flex; align-items: center; gap: 4px; margin-top: 4px; font-size: 12px; font-weight: 600; color: var(--state-warn); }
.sec td { padding-top: 22px; padding-bottom: 6px; border-bottom: 1px solid rgba(15, 20, 19, 0.08); }
.param { font-size: 14px; color: var(--ink-body); border-bottom: 1px solid rgba(15, 20, 19, 0.05); }
.val { text-align: right; border-bottom: 1px solid rgba(15, 20, 19, 0.05); }
.val :deep(.cell) { justify-content: flex-end; width: 100%; }
.block { display: block; }
tbody tr:nth-child(odd):not(.sec) td { background: rgba(15, 20, 19, 0.018); }
.empty { padding: var(--space-12); text-align: center; display: grid; gap: var(--space-3); justify-items: center; }
.empty > * { position: relative; z-index: 1; }
.fade-enter-active, .fade-leave-active { transition: opacity var(--dur-mid) var(--ease), transform var(--dur-mid) var(--ease); }
.fade-enter-from, .fade-leave-to { opacity: 0; transform: translateY(-6px); }
</style>
