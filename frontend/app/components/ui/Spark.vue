<script setup lang="ts">
/** Маленький живой график: линия с заливкой, подпись последнего значения, необязательная целевая линия. */
const props = withDefaults(defineProps<{
  series: { points: number[]; color?: string; label?: string }[]
  height?: number
  target?: number | null
  unit?: string
  format?: (value: number) => string
  max?: number | null
}>(), { height: 64, target: null, unit: '', max: null })

const W = 240
const pad = 4
const all = computed(() => props.series.flatMap((row) => row.points).concat(props.target != null ? [props.target] : []))
const top = computed(() => {
  const peak = Math.max(props.max ?? 0, ...all.value, 1e-6)
  return peak * 1.08
})
const len = computed(() => Math.max(2, ...props.series.map((row) => row.points.length)))
const x = (index: number) => pad + (index / (len.value - 1)) * (W - pad * 2)
const y = (value: number) => props.height - pad - (Math.max(0, value) / top.value) * (props.height - pad * 2)
const path = (points: number[]) => points.map((value, index) => `${index ? 'L' : 'M'}${x(index).toFixed(1)},${y(value).toFixed(1)}`).join(' ')
const area = (points: number[]) => points.length ? `${path(points)} L${x(points.length - 1).toFixed(1)},${(props.height - pad).toFixed(1)} L${x(0).toFixed(1)},${(props.height - pad).toFixed(1)} Z` : ''
const fmt = (value: number) => (props.format ? props.format(value) : value.toLocaleString('ru-RU', { maximumFractionDigits: value >= 100 ? 0 : 1 }))
</script>

<template>
  <div class="spark">
    <svg :viewBox="`0 0 ${W} ${height}`" preserveAspectRatio="none" :style="{ height: `${height}px` }">
      <line v-if="target != null" :x1="pad" :x2="W - pad" :y1="y(target)" :y2="y(target)" class="target" />
      <template v-for="(row, index) in series" :key="index">
        <path v-if="row.points.length > 1" :d="area(row.points)" :fill="row.color ?? '#0d8455'" opacity="0.1" />
        <path v-if="row.points.length > 1" :d="path(row.points)" :stroke="row.color ?? '#0d8455'" fill="none" stroke-width="1.8" vector-effect="non-scaling-stroke" stroke-linejoin="round" />
      </template>
    </svg>
    <div class="legend">
      <span v-for="(row, index) in series" :key="index" class="mono-sm" :style="{ color: row.color ?? '#0d8455' }">{{ row.points.length ? fmt(row.points.at(-1)!) : '—' }}<span v-if="unit" class="unit"> {{ unit }}</span><span v-if="row.label" class="caption"> {{ row.label }}</span></span>
      <span v-if="target != null" class="caption">цель {{ fmt(target) }}</span>
    </div>
  </div>
</template>

<style scoped>
.spark { display: grid; gap: 4px; }
svg { width: 100%; display: block; border-radius: 8px; background: rgba(15, 20, 19, 0.03); }
.target { stroke: #8a5200; stroke-width: 1; stroke-dasharray: 4 3; vector-effect: non-scaling-stroke; }
.legend { display: flex; flex-wrap: wrap; gap: 10px; align-items: baseline; }
.unit { font-family: var(--font-sans); font-weight: 500; font-size: 11px; color: var(--ink-muted); }
</style>
