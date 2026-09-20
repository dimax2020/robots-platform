<script setup lang="ts">
import { PhCheck, PhLock } from '@phosphor-icons/vue'
import { steps, type Project, isFullPath } from '~/data/projects'

const props = defineProps<{ project: Project; current?: string }>()
const full = computed(() => isFullPath(props.project))
const available = computed(() => (full.value ? steps.length : 2))
</script>

<template>
  <nav class="steps" aria-label="Шаги расчёта">
    <ol>
      <li v-for="(s, i) in steps" :key="s.code" :class="{ done: i + 1 < project.step && i < available, cur: s.path === current, locked: i >= available, next: i + 1 === project.step }">
        <NuxtLink v-if="i < available" :to="`/projects/${project.id}/${s.path}`">
          <span class="dot"><PhCheck v-if="i + 1 < project.step" :size="12" weight="bold" /><span v-else class="n">{{ i + 1 }}</span></span>
          <span class="t">{{ s.label }}</span>
        </NuxtLink>
        <span v-else class="lk" :title="'Для этого типа объекта шаг в MVP не открывается'">
          <span class="dot"><PhLock :size="11" weight="bold" /></span>
          <span class="t">{{ s.label }}</span>
        </span>
      </li>
    </ol>
  </nav>
</template>

<style scoped>
.steps ol { display: flex; align-items: center; gap: 4px; padding: 4px; border-radius: 14px; background: rgba(15, 20, 19, 0.05); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.04); overflow-x: auto; }
li { flex: 1; min-width: 0; }
li a, .lk { display: flex; align-items: center; gap: 8px; height: 40px; padding: 0 12px 0 8px; border-radius: 10px; font-size: 14px; font-weight: 600; color: var(--ink-muted); white-space: nowrap; transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease); }
li a:hover { background: rgba(255, 255, 255, 0.7); color: var(--ink-strong); }
.dot { display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 8px; background: rgba(15, 20, 19, 0.06); font-family: var(--font-mono); font-size: 11px; flex: none; }
.done .dot { background: var(--surface-brand-tint); color: var(--brand-700); }
.done a { color: var(--ink-body); }
.cur a { background: var(--surface-graphite); color: var(--ink-on-graphite); box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1); }
.cur .dot { background: var(--brand-400); color: var(--brand-900); }
.next:not(.cur) a { color: var(--ink-strong); }
.next:not(.cur) .dot { background: #fff; box-shadow: inset 0 0 0 1.5px var(--brand-500); color: var(--brand-700); }
.locked .lk { opacity: 0.55; cursor: not-allowed; }
</style>
