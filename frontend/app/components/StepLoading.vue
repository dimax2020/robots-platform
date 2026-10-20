<script setup lang="ts">
import { PhCheck } from '@phosphor-icons/vue'

/**
 * Загрузка шага: что именно считается — по этапам, сколько уже идёт, и заготовка страницы.
 * Этапы — ориентир для человека: сменяются по времени, точного прогресса сервер не отдаёт.
 */
const props = withDefaults(defineProps<{ label: string; title: string; stages?: string[]; hint?: string; timer?: boolean }>(), { stages: () => [], hint: '', timer: true })

/* Время идёт только в браузере: до того, как страница ожила, застывший «0,0 с» выглядел бы как зависание. */
let started = Date.now()
const now = ref(started)
const alive = ref(false)
let clock: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  started = Date.now()
  now.value = started
  alive.value = true
  clock = setInterval(() => { now.value = Date.now() }, 100)
})
onBeforeUnmount(() => { if (clock) clearInterval(clock) })

const seconds = computed(() => (now.value - started) / 1000)
const elapsed = computed(() => `${seconds.value.toLocaleString('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} с`)
/* Этап сменяется каждые 2,5 с; последний держится, пока расчёт не закончится. */
const current = computed(() => Math.min(props.stages.length - 1, Math.floor(seconds.value / 2.5)))
const slow = computed(() => seconds.value > 15)
</script>

<template>
  <section class="loading glass" role="status" aria-live="polite">
    <div class="l-in">
      <div class="l-head">
        <div class="l-copy">
          <span class="label">{{ label }}</span>
          <span class="h3">{{ title }}</span>
          <span v-if="hint" class="body-sm muted">{{ hint }}</span>
        </div>
        <div v-if="timer && alive" class="l-timer">
          <span class="display-3">{{ elapsed }}</span>
          <span class="caption">идёт расчёт</span>
        </div>
      </div>
      <ol v-if="stages.length" class="stages">
        <li v-for="(stage, index) in stages" :key="stage" :class="{ done: index < current, on: index === current }">
          <span class="dot"><PhCheck v-if="index < current" :size="11" weight="bold" /></span>
          <span class="body-sm">{{ stage }}</span>
        </li>
      </ol>
      <p v-if="slow" class="caption">Считаем дольше обычного: на больших объектах подбор и экономика занимают до минуты.</p>
      <div class="skeleton" aria-hidden="true">
        <span class="sk w60" />
        <span class="sk w90" />
        <span class="sk w75" />
      </div>
    </div>
  </section>
</template>

<style scoped>
.loading { border-radius: var(--radius-xl); }
.l-in { position: relative; z-index: 1; padding: var(--space-6); display: grid; gap: var(--space-5); }
.l-head { display: flex; justify-content: space-between; align-items: center; gap: var(--space-6); }
.l-copy { display: grid; gap: 6px; max-width: 56ch; }
.l-timer { display: grid; justify-items: end; gap: 4px; }
.l-timer .display-3 { font-variant-numeric: tabular-nums; }
.stages { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
.stages li { display: flex; align-items: center; gap: 10px; color: var(--ink-faint); transition: color var(--dur-fast) var(--ease); }
.stages li.done { color: var(--ink-muted); }
.stages li.on { color: var(--ink-strong); font-weight: 600; }
.dot { width: 18px; height: 18px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; flex: none; box-shadow: inset 0 0 0 1.5px rgba(15, 20, 19, 0.18); }
.done .dot { background: var(--brand-500); box-shadow: none; color: #fff; }
.on .dot { box-shadow: inset 0 0 0 2px var(--brand-500); animation: pulse 1.2s ease-in-out infinite; }
@keyframes pulse { 50% { box-shadow: inset 0 0 0 5px rgba(13, 132, 85, 0.25); } }
.skeleton { display: grid; gap: 10px; }
.sk { display: block; height: 14px; border-radius: 7px; background: linear-gradient(90deg, rgba(15, 20, 19, 0.06) 25%, rgba(15, 20, 19, 0.11) 50%, rgba(15, 20, 19, 0.06) 75%); background-size: 200% 100%; animation: shimmer 1.4s linear infinite; }
.w60 { width: 60%; }
.w90 { width: 90%; }
.w75 { width: 75%; }
@keyframes shimmer { from { background-position: 200% 0; } to { background-position: -200% 0; } }
@media (prefers-reduced-motion: reduce) { .sk, .on .dot { animation: none; } }
@media (max-width: 700px) { .l-head { display: grid; } .l-timer { justify-items: start; } }
</style>
