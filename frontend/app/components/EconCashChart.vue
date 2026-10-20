<script setup lang="ts">
import { signedMillions, yearsText, type EconScenario } from '~/composables/usePlatformEconomy'

/** Накопленный денежный поток после налога: старт с минуса на вложения, ноль — момент окупаемости. */
const props = defineProps<{ scenarios: EconScenario[]; picked: string }>()

/* Рисуем в реальную ширину контейнера: так подписи не растягиваются вместе с графиком. */
const box = ref<HTMLElement | null>(null)
const W = ref(760)
const H = 280
let observer: ResizeObserver | undefined
onMounted(() => {
  if (!box.value) return
  observer = new ResizeObserver(([entry]) => { if (entry) W.value = Math.max(320, Math.round(entry.contentRect.width)) })
  observer.observe(box.value)
})
onBeforeUnmount(() => observer?.disconnect())
const PAD = { left: 64, right: 96, top: 18, bottom: 34 }

const COLORS: Record<string, string> = { purchase: 'var(--brand-600)', raas: '#c98a1c' }
const series = computed(() => props.scenarios
  .filter((item) => item.key !== 'asis' && item.cashflow?.length)
  .map((item) => ({
    key: item.key,
    title: item.title,
    color: COLORS[item.key] ?? 'var(--ink-muted)',
    points: [{ x: 0, y: -(item.capex.value ?? 0) }, ...item.cashflow!.map((row) => ({ x: row.year, y: row.cumulative }))],
    payback: item.key === 'purchase' ? item.payback.value : null,
    end: item.cashflow![item.cashflow!.length - 1]!.cumulative,
  })))

const years = computed(() => Math.max(1, ...series.value.map((item) => item.points.length - 1)))
const range = computed(() => {
  const values = series.value.flatMap((item) => item.points.map((point) => point.y))
  const min = Math.min(0, ...values)
  const max = Math.max(0, ...values)
  const pad = (max - min || 1) * 0.08
  return { min: min - pad, max: max + pad }
})
const x = (year: number) => PAD.left + (year / years.value) * (W.value - PAD.left - PAD.right)
const y = (value: number) => PAD.top + (1 - (value - range.value.min) / (range.value.max - range.value.min)) * (H - PAD.top - PAD.bottom)
const path = (points: { x: number; y: number }[]) => points.map((point, index) => `${index ? 'L' : 'M'} ${x(point.x).toFixed(1)} ${y(point.y).toFixed(1)}`).join(' ')
const area = (points: { x: number; y: number }[]) => `${path(points)} L ${x(points[points.length - 1]!.x).toFixed(1)} ${y(0).toFixed(1)} L ${x(0).toFixed(1)} ${y(0).toFixed(1)} Z`

/* Подписи оси: 4–5 круглых значений в миллионах. */
const ticks = computed(() => {
  const span = range.value.max - range.value.min
  const raw = span / 4
  const power = 10 ** Math.floor(Math.log10(raw || 1))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((m) => m >= raw) ?? raw
  const out: number[] = []
  for (let v = Math.ceil(range.value.min / step) * step; v <= range.value.max; v += step) out.push(v)
  return out
})
const tickText = (value: number) => `${(value / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: 1 })}`
</script>

<template>
  <figure ref="box" class="chart">
    <svg :viewBox="`0 0 ${W} ${H}`" role="img" aria-label="Накопленный денежный поток по годам">
      <g class="grid">
        <line v-for="t in ticks" :key="t" :x1="PAD.left" :x2="W - PAD.right" :y1="y(t)" :y2="y(t)" :class="{ zero: Math.abs(t) < 1 }" />
        <text v-for="t in ticks" :key="`l${t}`" :x="PAD.left - 10" :y="y(t) + 4" text-anchor="end">{{ tickText(t) }}</text>
        <text v-for="n in years + 1" :key="`y${n}`" :x="x(n - 1)" :y="H - 10" text-anchor="middle">{{ n - 1 === 0 ? 'старт' : `${n - 1} год` }}</text>
      </g>
      <line :x1="PAD.left" :x2="W - PAD.right" :y1="y(0)" :y2="y(0)" class="zero-line" />
      <g v-for="s in series" :key="s.key" :class="['s', { dim: picked !== s.key }]">
        <path :d="area(s.points)" :fill="s.color" class="area" />
        <path :d="path(s.points)" :stroke="s.color" class="line" />
        <circle v-for="point in s.points" :key="point.x" :cx="x(point.x)" :cy="y(point.y)" r="4" :fill="s.color" />
        <text :x="x(s.points[s.points.length - 1]!.x) + 10" :y="y(s.end) + 4" class="end" :fill="s.color">{{ signedMillions(s.end, 0) }}</text>
      </g>
      <g v-for="s in series.filter((item) => item.payback != null && item.payback <= years)" :key="`p${s.key}`" class="pay">
        <line :x1="x(s.payback!)" :x2="x(s.payback!)" :y1="PAD.top" :y2="H - PAD.bottom" />
        <circle :cx="x(s.payback!)" :cy="y(0)" r="6" />
        <text :x="x(s.payback!) + 8" :y="PAD.top + 12">окупаемость {{ yearsText(s.payback) }}</text>
      </g>
    </svg>
    <figcaption class="legend caption">
      <span v-for="s in series" :key="s.key"><i :style="{ background: s.color }" />{{ s.title }}</span>
      <span>млн ₽, после налога; в последний год — с остаточной стоимостью техники</span>
    </figcaption>
  </figure>
</template>

<style scoped>
.chart { margin: 0; display: grid; gap: 8px; }
svg { width: 100%; height: auto; display: block; overflow: visible; }
.grid line { stroke: rgba(15, 20, 19, 0.07); }
.grid text { font-family: var(--font-mono); font-size: 11px; fill: var(--ink-muted); }
.zero-line { stroke: rgba(15, 20, 19, 0.45); stroke-width: 1.5; }
.area { opacity: 0.08; }
.line { fill: none; stroke-width: 3; stroke-linejoin: round; stroke-linecap: round; }
.s.dim { opacity: 0.35; }
.end { font-family: var(--font-mono); font-size: 13px; font-weight: 700; }
.pay line { stroke: var(--brand-600); stroke-dasharray: 3 5; }
.pay circle { fill: #fff; stroke: var(--brand-600); stroke-width: 3; }
.pay text { font-size: 12px; font-weight: 700; fill: var(--brand-700); }
.legend { display: flex; flex-wrap: wrap; gap: 6px 18px; }
.legend i { display: inline-block; width: 18px; height: 4px; border-radius: 2px; margin-right: 6px; vertical-align: 3px; }
</style>
