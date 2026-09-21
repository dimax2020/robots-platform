<script setup lang="ts">
import { PhPackage, PhTray, PhBookOpenText, PhCalculator, PhLinkSimple, PhUploadSimple, PhRocketLaunch, PhArrowRight, PhWarningCircle } from '@phosphor-icons/vue'
import { proposals, norms } from '~/data/projects'

definePageMeta({ layout: 'admin' })
useHead({ title: 'Админка · Обзор' })

const { products, sources, attributeDefs } = useCatalog()
const pending = proposals.filter((p) => p.status === 'pending').length
// Карточка, которую стоит проверить первой: меньше всех заполнена
const leastComplete = computed(() => [...products.value].sort((a, b) => a.completeness - b.completeness)[0])
const tiles = computed(() => [
  { to: '/admin/products', icon: PhPackage, title: 'Продукты', value: String(products.value.length), note: `${products.value.filter(p => p.autoMatch).length} готовы к автоподбору` },
  { to: '/admin/proposals', icon: PhTray, title: 'Очередь правок', value: String(pending), note: 'ждут решения', tone: 'brand' },
  { to: '/admin/refs', icon: PhBookOpenText, title: 'Справочники', value: String(attributeDefs.value.length), note: 'характеристик в справочнике' },
  { to: '/admin/norms', icon: PhCalculator, title: 'Нормативы', value: String(norms.length), note: 'все с обоснованием' },
  { to: '/admin/sources', icon: PhLinkSimple, title: 'Источники', value: String(sources.value.length), note: 'плановая проверка ещё не запускалась' },
  { to: '/admin/import', icon: PhUploadSimple, title: 'Импорт', value: '1', note: 'файл организатора загружен' },
  { to: '/admin/publish', icon: PhRocketLaunch, title: 'Публикация', value: 'v2026.09.3', note: '6 изменений к выпуску', mono: true },
])
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Обзор" title="Ручное управление каталогом" lead="Продукты, очередь правок, справочники, нормативы, источники, импорт и публикация версии. Парсер и импорт пишут в очередь, не в каталог напрямую." />

    <div class="signal glass" v-reveal>
      <PhWarningCircle :size="22" weight="fill" class="sig-ic" />
      <div class="sig-body">
        <div class="h4">Источник изменился: ronavi.example/h1500</div>
        <div class="body-sm muted">Страница производителя обновлена 18 сентября. Каталог сам не переписывается: проверьте карточку Ronavi H1500 и примите или отклоните изменения.</div>
      </div>
      <UiButton :to="`/admin/products/${leastComplete?.slug ?? ''}`" size="sm" variant="secondary">Проверить карточку <template #after><PhArrowRight :size="14" weight="bold" /></template></UiButton>
    </div>

    <div class="tiles">
      <NuxtLink v-for="(t, i) in tiles" :key="t.to" :to="t.to" class="tile" :class="[t.tone === 'brand' ? 'glass-graphite glass-graphite-solid' : 'glass', { first: i === 0 }]" v-reveal="Math.min(i, 5)">
        <div class="tile-in">
          <component :is="t.icon" :size="22" weight="duotone" class="t-ic" />
          <div class="t-val" :class="{ 'display-3': !t.mono, 'mono-lg': t.mono }">{{ t.value }}</div>
          <div class="h4">{{ t.title }}</div>
          <div class="caption" :class="{ warn: t.tone === 'warn' }">{{ t.note }}</div>
        </div>
      </NuxtLink>
    </div>
  </div>
</template>

<style scoped>
.signal { display: grid; grid-template-columns: auto 1fr auto; gap: 14px; align-items: center; padding: 16px 18px; }
.signal > * { position: relative; z-index: 1; }
.sig-ic { color: var(--state-warn); }
.tiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-4); }
.tile { border-radius: var(--radius-xl); transition: transform var(--dur-mid) var(--ease); }
.tile:hover { transform: translateY(-3px); }
.tile.first { grid-column: span 2; }
.tile-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: 6px; align-content: start; min-height: 170px; }
.t-ic { color: var(--brand-700); margin-bottom: auto; }
.glass-graphite .t-ic { color: var(--brand-300); }
.glass-graphite .display-3, .glass-graphite .h4 { color: var(--ink-on-graphite); }
.glass-graphite .caption { color: var(--ink-muted-graphite); }
.t-val { margin-top: 8px; }
.mono-lg { color: var(--ink-strong); }
.warn { color: var(--state-warn); }
@media (max-width: 1100px) { .tiles { grid-template-columns: 1fr 1fr; } }
</style>
