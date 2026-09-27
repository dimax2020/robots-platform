<script setup lang="ts">
import { activeAdminPath, adminNav, adminOverview } from '~/data/adminNav'

const route = useRoute()
const active = computed(() => activeAdminPath(route.path))
</script>

<template>
  <div class="layout">
    <AppNavbar />
    <div class="container admin">
      <aside class="side">
        <nav class="menu glass" aria-label="Разделы админки">
          <div class="menu-head"><span class="label">Админка</span><span class="caption">каталог и модель подбора</span></div>
          <NuxtLink :to="adminOverview.to" class="mi" :class="{ on: active === adminOverview.to }">
            <component :is="adminOverview.icon" :size="18" weight="duotone" />
            <span>{{ adminOverview.label }}</span>
          </NuxtLink>
          <template v-for="group in adminNav" :key="group.label">
            <div class="grp caption">{{ group.label }}</div>
            <NuxtLink v-for="item in group.items" :key="item.to" :to="item.to" class="mi" :class="{ on: active === item.to }">
              <component :is="item.icon" :size="18" weight="duotone" />
              <span>{{ item.label }}</span>
            </NuxtLink>
          </template>
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
.grp { padding: 14px 12px 4px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; font-size: 11.5px; }
.mi { display: grid; grid-template-columns: auto 1fr; gap: 10px; align-items: center; min-height: 38px; padding: 0 12px; border-radius: 10px; font-size: 14px; font-weight: 600; color: var(--ink-body); transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease); }
.mi:hover { background: rgba(15, 20, 19, 0.05); color: var(--ink-strong); }
.mi.on { background: var(--surface-graphite); color: var(--ink-on-graphite); }
.mi.on svg { color: var(--brand-300); }
.main { min-width: 0; }
.main :deep(.admin-page) { display: grid; gap: var(--space-6); }
.main :deep(.a-panel) { padding: var(--space-5); display: grid; gap: var(--space-4); align-content: start; }
.main :deep(.a-panel > *) { position: relative; z-index: 1; }
.main :deep(.a-head) { display: flex; gap: 12px; align-items: flex-start; justify-content: space-between; flex-wrap: wrap; }
.main :deep(.a-row) { display: flex; gap: 12px; align-items: end; flex-wrap: wrap; }
.main :deep(.a-fld) { display: grid; gap: 6px; flex: 1; min-width: 180px; align-content: start; }
.main :deep(.a-fld.narrow) { flex: 0 0 170px; min-width: 120px; }
.main :deep(.a-fld .input), .main :deep(.a-fld .select), .main :deep(.a-fld .textarea) { width: 100%; }
.main :deep(.a-split) { display: grid; grid-template-columns: 300px minmax(0, 1fr); gap: var(--space-5); align-items: start; }
.main :deep(.a-list) { padding: 8px; display: grid; gap: 6px; max-height: 78vh; overflow: auto; position: sticky; top: 96px; }
.main :deep(.a-list > *) { position: relative; z-index: 1; }
.main :deep(.a-item) { display: grid; gap: 2px; text-align: left; padding: 10px 12px; border-radius: 14px; background: rgba(255, 255, 255, 0.55); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.main :deep(.a-item.on) { background: #fff; box-shadow: inset 0 0 0 1px var(--brand-400); }
.main :deep(.a-item .body-sm) { color: var(--ink-strong); }
.main :deep(.a-sub) { padding: 10px 4px 2px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; font-size: 11.5px; color: var(--ink-muted); }
.main :deep(.a-block) { display: grid; gap: 10px; padding-top: 14px; border-top: 1px solid var(--border-hairline); }
.main :deep(.a-tbl) { overflow: auto; }
.main :deep(.a-chips) { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.main :deep(.a-pill) { display: inline-flex; align-items: center; gap: 6px; padding: 3px 9px; border-radius: 999px; font-size: 12.5px; font-weight: 600; background: rgba(15, 20, 19, 0.06); color: var(--ink-body); }
.main :deep(.a-pill.warn) { background: var(--state-warn-tint); color: var(--state-warn); }
.main :deep(.a-pill.ok) { background: var(--surface-brand-tint); color: var(--brand-ink); }
.main :deep(.a-pill.danger) { background: var(--state-danger-tint); color: var(--state-danger); }
.main :deep(.a-x) { width: 30px; height: 30px; border-radius: 8px; display: inline-grid; place-items: center; color: var(--ink-muted); flex: none; }
.main :deep(.a-x:hover) { background: var(--state-danger-tint); color: var(--state-danger); }
.main :deep(.a-letter) { width: 22px; height: 22px; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center; font-family: var(--font-mono); font-weight: 700; font-size: 11px; flex: none; }
.main :deep(.a-letter.c-A) { background: var(--surface-graphite); color: var(--brand-300); }
.main :deep(.a-letter.c-B) { background: var(--surface-brand-tint); color: var(--brand-ink); }
.main :deep(.a-letter.c-C) { background: var(--state-warn-tint); color: var(--state-warn); }
.main :deep(.a-letter.c-D) { background: rgba(15, 20, 19, 0.08); color: var(--ink-muted); }
.main :deep(.num) { text-align: right; }
@media (max-width: 1100px) {
  .main :deep(.a-split) { grid-template-columns: 1fr; }
  .main :deep(.a-list) { position: static; max-height: none; }
}
@media (max-width: 1100px) {
  .admin { grid-template-columns: 1fr; }
  .side { position: static; }
}
</style>
