<script setup lang="ts">
import { PhArrowLeft } from '@phosphor-icons/vue'
import { type Project, objectTypeLabel } from '~/data/projects'
import type { RailItem } from '~/components/ProcessRail.vue'
const props = defineProps<{
  project: Project
  current: string
  title: string
  /** Строка под заголовком мельче него: например, текущий процесс. */
  subtitle?: string
  lead?: string
  dense?: boolean
  substages?: { id: string; label: string; to: string; tone?: string }[]
  currentSub?: string
  alerts?: Record<string, { title: string; items: string[]; note: string }>
  /** Процессы шага слева: итог и все процессы. Когда задано, заголовок и содержимое встают справа от списка. */
  rail?: { summary: RailItem; items: RailItem[] } | null
}>()
const placeLabel = computed(() => {
  const object = objectTypeLabel[props.project.objectType] || props.project.objectType
  const industry = props.project.industry
  return industry && industry !== object ? `${industry} — ${object}` : object
})
</script>

<template>
  <section class="container shell" :class="{ dense }">
    <div class="shell-head no-print" v-reveal>
      <div class="crumbs">
        <NuxtLink :to="`/projects/${project.id}`" class="back body-sm"><PhArrowLeft :size="14" weight="bold" /> {{ project.name }}</NuxtLink>
        <span class="meta">
          <UiBadge tone="neutral">{{ placeLabel }}</UiBadge>
          <UiBadge v-if="project.isDemo && project.readonly" tone="info">Демо · только просмотр</UiBadge>
          <UiBadge v-else-if="project.isDemo" :tone="project.published ? 'ok' : 'warn'">{{ project.published ? 'Демо · опубликовано' : 'Демо · не опубликовано' }}</UiBadge>
        </span>
      </div>
      <DemoBanner v-if="project.isDemo && project.readonly" :project-key="project.id" />
      <slot name="banner" />
      <ProjectSteps :project="project" :current="current" :substages="substages" :current-sub="currentSub" :alerts="alerts" />
    </div>
    <div :class="{ 'with-rail': rail }">
      <ProcessRail v-if="rail" class="no-print" :summary="rail.summary" :items="rail.items" :current="currentSub" />
      <div class="shell-body">
        <div class="shell-title no-print" v-reveal="1">
          <div>
            <h1 class="hero-2">{{ title }}</h1>
            <div v-if="subtitle" class="h3 subtitle">{{ subtitle }}</div>
            <p v-if="lead" class="body-lg muted lead">{{ lead }}</p>
          </div>
          <div v-if="$slots.actions" class="actions"><slot name="actions" /></div>
        </div>
        <slot />
      </div>
    </div>
  </section>
</template>

<style scoped>
.shell { padding-top: var(--space-8); padding-bottom: var(--space-16); display: grid; gap: var(--space-8); }
.shell-head { display: grid; gap: var(--space-4); }
.crumbs { display: flex; justify-content: space-between; align-items: center; gap: var(--space-4); flex-wrap: wrap; }
.back { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-muted); font-weight: 600; }
.back:hover { color: var(--ink-strong); }
.meta { display: flex; align-items: center; gap: 8px; }
.shell-body { display: grid; gap: var(--space-8); min-width: 0; align-content: start; }
.with-rail { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: var(--space-6); align-items: start; }
.dense .shell-body { gap: var(--space-5); }
@media (max-width: 1100px) { .with-rail { grid-template-columns: minmax(0, 1fr); } }
.shell-title { display: flex; justify-content: space-between; align-items: flex-end; gap: var(--space-8); }
.subtitle { margin-top: 6px; color: var(--ink-body); }
.lead { max-width: 68ch; margin-top: 10px; }
.actions { display: flex; gap: 8px; flex: none; }
.dense { gap: var(--space-5); padding-bottom: var(--space-10); }
.dense .shell-title { align-items: center; }
.dense .lead { font-size: 16px; margin-top: 6px; max-width: 56ch; }
.dense :deep(.hero-2) { font-size: clamp(28px, 2vw, 40px); }
/* Узкий экран: кнопка «дальше» под заголовком во всю ширину, а не обрезана справа. */
@media (max-width: 700px) {
  .shell-title { flex-direction: column; align-items: stretch; gap: var(--space-4); }
  .actions { flex-wrap: wrap; }
  .actions > :deep(*) { flex: 1; justify-content: center; }
}
@media print {
  .shell { padding: 0; gap: 0; max-width: none; }
}
</style>
