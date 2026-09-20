<script setup lang="ts">
// Интервальная оценка: нижняя, центральная, верхняя. Числа справа, моноширинно.
const props = withDefaults(defineProps<{
  low: number; mid: number; high: number
  min?: number; max?: number
  unit?: string
  digits?: number
  graphite?: boolean
  bands?: { to: number; label: string }[]
}>(), { digits: 1 })

const range = computed(() => {
  const min = props.min ?? Math.min(0, props.low)
  const max = props.max ?? props.high * 1.25
  return { min, max }
})
const pct = (v: number) => `${((v - range.value.min) / (range.value.max - range.value.min)) * 100}%`
const f = (v: number) => v.toLocaleString('ru-RU', { maximumFractionDigits: props.digits, minimumFractionDigits: props.digits })
</script>

<template>
  <div class="interval" :class="{ graphite }">
    <div class="track">
      <template v-if="bands">
        <span v-for="(b, i) in bands" :key="b.label" class="band" :style="{ left: pct(i === 0 ? range.min : bands[i - 1]!.to), width: `calc(${pct(b.to)} - ${pct(i === 0 ? range.min : bands[i - 1]!.to)})` }">
          <span class="band-label">{{ b.label }}</span>
        </span>
      </template>
      <span class="fill" :style="{ left: pct(low), width: `calc(${pct(high)} - ${pct(low)})` }" />
      <span class="tick tick-mid" :style="{ left: pct(mid) }" />
      <span class="tick tick-edge" :style="{ left: pct(low) }" />
      <span class="tick tick-edge" :style="{ left: pct(high) }" />
    </div>
    <div class="nums">
      <span class="n"><span class="k">нижняя</span><span class="mono-md">{{ f(low) }}<i v-if="unit"> {{ unit }}</i></span></span>
      <span class="n mid"><span class="k">центральная</span><span class="mono-lg">{{ f(mid) }}<i v-if="unit"> {{ unit }}</i></span></span>
      <span class="n"><span class="k">верхняя</span><span class="mono-md">{{ f(high) }}<i v-if="unit"> {{ unit }}</i></span></span>
    </div>
  </div>
</template>

<style scoped>
.interval { display: grid; gap: 14px; }
.track { position: relative; height: 28px; border-radius: var(--radius-pill); background: rgba(15, 20, 19, 0.05); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.05); overflow: visible; }
.graphite .track { background: rgba(255, 255, 255, 0.06); box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08); }
.band { position: absolute; top: 0; bottom: 0; border-right: 1px dashed rgba(15, 20, 19, 0.14); }
.band:last-child { border-right: 0; }
.band-label { position: absolute; top: calc(100% + 6px); left: 50%; transform: translateX(-50%); font-family: var(--font-mono); font-size: 11px; color: var(--ink-muted); white-space: nowrap; }
.fill { position: absolute; top: 4px; bottom: 4px; border-radius: var(--radius-pill); background: linear-gradient(90deg, rgba(20, 167, 111, 0.55), var(--brand-500), rgba(20, 167, 111, 0.55)); box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.45); transition: left var(--dur-slow) var(--ease), width var(--dur-slow) var(--ease); }
.tick { position: absolute; top: -4px; bottom: -4px; width: 2px; margin-left: -1px; border-radius: 1px; background: var(--brand-900); transition: left var(--dur-slow) var(--ease); }
.graphite .tick { background: #fff; }
.tick-edge { top: 8px; bottom: 8px; background: rgba(255, 255, 255, 0.9); }
.nums { display: grid; grid-template-columns: 1fr auto 1fr; align-items: end; gap: 16px; }
.n { display: grid; gap: 2px; }
.n:last-child { text-align: right; }
.n.mid { text-align: center; }
.k { font-family: var(--font-mono); font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-muted); }
.mono-md, .mono-lg { color: var(--ink-strong); }
.graphite .mono-md, .graphite .mono-lg { color: var(--ink-on-graphite); }
i { font-style: normal; color: var(--ink-muted); font-size: 0.8em; }
.bands ~ .nums { margin-top: 12px; }
</style>
