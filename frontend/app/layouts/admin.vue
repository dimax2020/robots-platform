<script setup lang="ts">
import { PhSquaresFour, PhPackage, PhTray, PhBookOpenText, PhCalculator, PhLinkSimple, PhUploadSimple, PhRocketLaunch, PhSlidersHorizontal } from '@phosphor-icons/vue'
import { proposals } from '~/data/projects'

const route = useRoute()
const pending = proposals.filter((p) => p.status === 'pending').length
const items = [
  { to: '/admin', label: 'Обзор', icon: PhSquaresFour, exact: true },
  { to: '/admin/products', label: 'Продукты', icon: PhPackage },
  { to: '/admin/proposals', label: 'Очередь правок', icon: PhTray, count: pending },
  { to: '/admin/refs', label: 'Справочники', icon: PhBookOpenText },
  { to: '/admin/norms', label: 'Нормативы', icon: PhCalculator },
  { to: '/admin/sources', label: 'Источники', icon: PhLinkSimple, count: 1, tone: 'warn' },
  { to: '/admin/platform', label: 'Импорт таблиц', icon: PhUploadSimple },
  { to: '/admin/processes', label: 'Процессы', icon: PhSlidersHorizontal },
  { to: '/admin/parsers', label: 'Парсеры', icon: PhRocketLaunch },
  { to: '/admin/import', label: 'Импорт', icon: PhUploadSimple },
  { to: '/admin/publish', label: 'Публикация', icon: PhRocketLaunch },
]
const isOn = (i: typeof items[number]) => (i.exact ? route.path === i.to : route.path.startsWith(i.to))
</script>

<template>
  <div class="layout">
    <AppNavbar />
    <div class="container admin">
      <aside class="side">
        <nav class="menu glass" aria-label="Разделы админки">
          <div class="menu-head"><span class="label">Админка</span><span class="caption">каталог v2026.09.3</span></div>
          <NuxtLink v-for="i in items" :key="i.to" :to="i.to" class="mi" :class="{ on: isOn(i) }">
            <component :is="i.icon" :size="18" weight="duotone" />
            <span>{{ i.label }}</span>
            <span v-if="i.count" class="cnt" :class="i.tone">{{ i.count }}</span>
          </NuxtLink>
        </nav>
      </aside>
      <main class="main">
        <slot />
      </main>
    </div>
    <AppFooter />
  </div>
</template>

<style scoped>
.layout { min-height: 100dvh; display: flex; flex-direction: column; }
.admin { flex: 1; display: grid; grid-template-columns: clamp(240px, 15vw, 280px) minmax(0, 1fr); gap: var(--space-6); align-items: start; padding-top: var(--space-8); padding-bottom: var(--space-16); }
.side { position: sticky; top: 96px; }
.menu { padding: 8px; display: grid; gap: 2px; }
.menu > * { position: relative; z-index: 1; }
.menu-head { display: grid; gap: 2px; padding: 10px 12px 12px; }
.mi { display: grid; grid-template-columns: auto 1fr auto; gap: 10px; align-items: center; min-height: 40px; padding: 0 12px; border-radius: 10px; font-size: 14px; font-weight: 600; color: var(--ink-body); transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease); }
.mi:hover { background: rgba(15, 20, 19, 0.05); color: var(--ink-strong); }
.mi.on { background: var(--surface-graphite); color: var(--ink-on-graphite); }
.mi.on svg { color: var(--brand-300); }
.cnt { font-family: var(--font-mono); font-size: 11px; padding: 2px 7px; border-radius: 6px; background: var(--surface-brand-tint); color: var(--brand-ink); }
.cnt.warn { background: var(--state-warn-tint); color: var(--state-warn); }
.mi.on .cnt { background: var(--brand-400); color: var(--brand-900); }
.main { min-width: 0; }
.main :deep(.admin-page) { display: grid; gap: var(--space-6); }
</style>
