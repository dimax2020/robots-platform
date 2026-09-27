<script setup lang="ts">
import { PhArrowLeft } from '@phosphor-icons/vue'
import { type Project, objectTypeLabel, isFullPath } from '~/data/projects'
defineProps<{
  project: Project
  current: string
  title: string
  lead?: string
  dense?: boolean
  substages?: { id: string; label: string; to: string }[]
  currentSub?: string
}>()
</script>

<template>
  <section class="container shell" :class="{ dense }">
    <div class="shell-head no-print" v-reveal>
      <div class="crumbs">
        <NuxtLink :to="`/projects/${project.id}`" class="back body-sm"><PhArrowLeft :size="14" weight="bold" /> {{ project.name }}</NuxtLink>
        <span class="meta">
          <UiBadge tone="neutral">{{ objectTypeLabel[project.objectType] }}</UiBadge>
          <UiBadge :tone="isFullPath(project) ? 'ok' : 'info'">{{ isFullPath(project) ? 'Полный путь' : 'Урезанный путь' }}</UiBadge>
          <span class="mono-sm muted">каталог {{ project.catalogVersion }} · модель {{ project.modelVersion }}</span>
        </span>
      </div>
      <ProjectSteps :project="project" :current="current" :substages="substages" :current-sub="currentSub" />
    </div>
    <div class="shell-title no-print" v-reveal="1">
      <div>
        <h1 class="hero-2">{{ title }}</h1>
        <p v-if="lead" class="body-lg muted lead">{{ lead }}</p>
      </div>
      <div v-if="$slots.actions" class="actions"><slot name="actions" /></div>
    </div>
    <slot />
  </section>
</template>

<style scoped>
.shell { padding-top: var(--space-8); padding-bottom: var(--space-16); display: grid; gap: var(--space-8); }
.shell-head { display: grid; gap: var(--space-4); }
.crumbs { display: flex; justify-content: space-between; align-items: center; gap: var(--space-4); flex-wrap: wrap; }
.back { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-muted); font-weight: 600; }
.back:hover { color: var(--ink-strong); }
.meta { display: flex; align-items: center; gap: 8px; }
.shell-title { display: flex; justify-content: space-between; align-items: flex-end; gap: var(--space-8); }
.lead { max-width: 68ch; margin-top: 10px; }
.actions { display: flex; gap: 8px; flex: none; }
.dense { gap: var(--space-5); padding-bottom: var(--space-10); }
.dense .shell-title { align-items: center; }
.dense .lead { font-size: 16px; margin-top: 6px; max-width: 56ch; }
.dense :deep(.hero-2) { font-size: clamp(28px, 2vw, 40px); }
@media print {
  .shell { padding: 0; gap: 0; max-width: none; }
}
</style>
