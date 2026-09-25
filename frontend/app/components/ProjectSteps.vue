<script setup lang="ts">
import { PhCheck, PhLock } from '@phosphor-icons/vue'
import { steps, type Project, isFullPath } from '~/data/projects'

const props = defineProps<{
  project: Project
  current?: string
  substages?: { id: string; label: string; to: string }[]
  currentSub?: string
}>()
const full = computed(() => isFullPath(props.project))
// подбор и сравнение живут на process_solutions — открыты всем трём типам
const available = computed(() => (full.value ? steps.length : 3))

const shown = computed(() => {
  const all = props.substages ?? []
  if (!all.length) return { items: [] as { id: string; label: string; to: string }[], rest: 0 }
  if (all.length <= 3) return { items: all, rest: 0 }
  const index = Math.max(0, all.findIndex((item) => item.id === props.currentSub))
  const start = Math.min(index, all.length - 3)
  const items = all.slice(start, start + 3)
  return { items, rest: all.length - (start + items.length) }
})
</script>

<template>
  <nav class="steps" aria-label="Шаги расчёта">
    <ol>
      <!-- номер в UI = i+2 (шаги ТЗ 2–8); project.step из mapProject — индекс рельса с 1, поэтому done/next сравниваем с i+1 -->
      <li v-for="(s, i) in steps" :key="s.code" :class="{ done: i + 1 < project.step && i < available, cur: s.path === current, locked: i >= available, next: i + 1 === project.step, open: s.path === current && shown.items.length }">
        <NuxtLink v-if="i < available" :to="`/projects/${project.id}/${s.path}`">
          <span class="dot"><PhCheck v-if="i + 1 < project.step" :size="12" weight="bold" /><span v-else class="n">{{ i + 2 }}</span></span>
          <span class="t">{{ s.label }}</span>
        </NuxtLink>
        <span v-else class="lk" :title="'Для этого типа объекта шаг в MVP не открывается'">
          <span class="dot"><PhLock :size="11" weight="bold" /></span>
          <span class="t">{{ s.label }}</span>
        </span>
        <div v-if="s.path === current && shown.items.length" class="subrow">
          <NuxtLink v-for="sub in shown.items" :key="sub.id" :to="sub.to" class="sub" :class="{ on: sub.id === currentSub }" :aria-current="sub.id === currentSub ? 'step' : undefined">
            <span class="sdot" />
            <span>{{ sub.label }}</span>
          </NuxtLink>
          <span v-if="shown.rest" class="caption more">ещё {{ shown.rest }}</span>
        </div>
      </li>
    </ol>
  </nav>
</template>

<style scoped>
.steps ol { display: flex; align-items: flex-start; gap: 4px; padding: 4px; border-radius: 14px; background: rgba(15, 20, 19, 0.05); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.04); overflow-x: auto; }
li { flex: 1; min-width: 0; }
li.open { flex: 1.8; min-width: 220px; }
li > a, .lk { display: flex; align-items: center; gap: 8px; height: 40px; padding: 0 12px 0 8px; border-radius: 10px; font-size: 14px; font-weight: 600; color: var(--ink-muted); white-space: nowrap; transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease); }
li > a:hover { background: rgba(255, 255, 255, 0.7); color: var(--ink-strong); }
.dot { display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 8px; background: rgba(15, 20, 19, 0.06); font-family: var(--font-mono); font-size: 11px; flex: none; }
.done .dot { background: var(--surface-brand-tint); color: var(--brand-700); }
.done > a { color: var(--ink-body); }
.cur > a { background: var(--surface-graphite); color: var(--ink-on-graphite); box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1); }
.cur > a .dot { background: var(--brand-400); color: var(--brand-900); }
.next:not(.cur) > a { color: var(--ink-strong); }
.next:not(.cur) > a .dot { background: #fff; box-shadow: inset 0 0 0 1.5px var(--brand-500); color: var(--brand-700); }
.locked .lk { opacity: 0.55; cursor: not-allowed; }
.subrow { display: grid; gap: 4px; padding: 6px 4px 4px; }
.sub { display: flex; align-items: flex-start; gap: 8px; min-height: 32px; padding: 6px 8px; border-radius: 8px; font-size: 13px; font-weight: 600; line-height: 1.3; color: var(--ink-muted); white-space: normal; }
.sub:hover { background: rgba(255, 255, 255, 0.7); color: var(--ink-strong); }
.sub.on { background: #fff; color: var(--ink-strong); box-shadow: inset 0 0 0 1px var(--brand-400); }
.sdot { width: 8px; height: 8px; margin-top: 5px; border-radius: 99px; background: rgba(15, 20, 19, 0.16); flex: none; }
.sub.on .sdot { background: var(--brand-500); }
.more { padding: 2px 8px 4px; }
</style>
