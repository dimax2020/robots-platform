<script setup lang="ts">
// 2D-план склада: контур, зоны, маршруты, роботы, точки зарядки.
// Реплей прогона: движение по маршрутам через getPointAtLength в rAF.
const props = withDefaults(defineProps<{ robots?: number; speed?: number; playing?: boolean; scenario?: string }>(), { robots: 7, speed: 1, playing: true, scenario: 'Оптимальный состав парка' })
const emit = defineEmits<{ tick: [payload: { t: number; util: number; queue: number }] }>()

const W = 1200
const H = 720

const zones = [
  { id: 'rcv', x: 40, y: 60, w: 200, h: 600, label: 'Приёмка', tone: 'a' },
  { id: 'rack1', x: 300, y: 80, w: 560, h: 110, label: 'Стеллажи A', tone: 'b' },
  { id: 'rack2', x: 300, y: 250, w: 560, h: 110, label: 'Стеллажи B', tone: 'b' },
  { id: 'rack3', x: 300, y: 420, w: 560, h: 110, label: 'Стеллажи C', tone: 'b' },
  { id: 'pick', x: 300, y: 590, w: 560, h: 80, label: 'Станции комплектации', tone: 'c' },
  { id: 'ship', x: 920, y: 60, w: 240, h: 460, label: 'Отгрузка', tone: 'a' },
  { id: 'chg', x: 920, y: 580, w: 240, h: 90, label: 'Зарядка', tone: 'd' },
]
const chargers = [960, 1010, 1060, 1110].map((x) => ({ x, y: 625 }))
const routes = [
  'M 240 140 L 280 140 L 280 220 L 890 220 L 890 140 L 920 140',
  'M 240 300 L 280 300 L 280 390 L 890 390 L 890 300 L 920 300',
  'M 240 460 L 280 460 L 280 560 L 890 560 L 890 460 L 920 460',
  'M 240 620 L 280 620 L 280 560 L 890 560 L 890 620 L 940 620',
  'M 280 220 L 280 560',
  'M 890 220 L 890 560',
]

const pathEls = ref<SVGPathElement[]>([])
const robotsState = reactive<{ x: number; y: number; r: number; s: number; d: number; charging: boolean; id: number }[]>([])
const t = ref(0)
let raf = 0
let last = 0

const init = () => {
  robotsState.splice(0)
  for (let i = 0; i < props.robots; i++) {
    const r = i % 4
    robotsState.push({ id: i + 1, x: 0, y: 0, r, s: (i * 0.173) % 1, d: i % 2 === 0 ? 1 : -1, charging: i >= props.robots - 1 })
  }
}

const step = (now: number) => {
  if (!last) last = now
  const dt = Math.min(50, now - last) / 1000
  last = now
  if (props.playing) {
    t.value += dt * props.speed
    robotsState.forEach((rb, i) => {
      const el = pathEls.value[rb.r]
      if (!el) return
      const len = el.getTotalLength()
      if (rb.charging) {
        const c = chargers[i % chargers.length]!
        rb.x = c.x; rb.y = c.y
        if (Math.floor(t.value / 14) % 2 === 1 && i === props.robots - 1) rb.charging = false
        return
      }
      rb.s += (dt * props.speed * 90 * rb.d) / len
      if (rb.s > 1) { rb.s = 1; rb.d = -1 }
      if (rb.s < 0) { rb.s = 0; rb.d = 1 }
      const pt = el.getPointAtLength(rb.s * len)
      rb.x = pt.x; rb.y = pt.y
    })
    const active = robotsState.filter((r) => !r.charging).length
    emit('tick', { t: t.value, util: Math.min(0.99, 0.78 + 0.12 * Math.sin(t.value / 9)), queue: robotsState.filter((r) => r.charging).length + (Math.sin(t.value / 7) > 0.6 ? 1 : 0) })
    void active
  } else {
    last = now
  }
  raf = requestAnimationFrame(step)
}

onMounted(() => { init(); raf = requestAnimationFrame(step) })
onBeforeUnmount(() => cancelAnimationFrame(raf))
watch(() => props.robots, () => init())
defineExpose({ reset: () => { t.value = 0; init() } })
</script>

<template>
  <svg class="plan" :viewBox="`0 0 ${W} ${H}`" role="img" aria-label="2D-план склада с маршрутами роботов">
    <defs>
      <pattern id="grid40" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M 40 0 L 0 0 0 40" fill="none" stroke="var(--grid-line)" stroke-width="1" /></pattern>
      <filter id="soft"><feGaussianBlur stdDeviation="2" /></filter>
    </defs>
    <rect width="100%" height="100%" fill="url(#grid40)" opacity="0.5" />
    <rect x="20" y="40" :width="W - 40" :height="H - 60" rx="16" fill="none" stroke="var(--ink-strong)" stroke-width="2" />

    <g v-for="z in zones" :key="z.id" class="zone" :class="`tone-${z.tone}`">
      <rect :x="z.x" :y="z.y" :width="z.w" :height="z.h" rx="10" />
      <text :x="z.x + 12" :y="z.y + 22" class="zl">{{ z.label }}</text>
      <g v-if="z.tone === 'b'">
        <rect v-for="i in 13" :key="i" :x="z.x + 12 + (i - 1) * 42" :y="z.y + 36" width="30" :height="z.h - 48" rx="3" class="rack" />
      </g>
      <g v-if="z.id === 'pick'">
        <circle v-for="i in 6" :key="i" :cx="z.x + 60 + (i - 1) * 90" :cy="z.y + 52" r="10" class="station" />
      </g>
    </g>

    <g class="chargers">
      <g v-for="(c, i) in chargers" :key="i"><rect :x="c.x - 14" :y="c.y - 10" width="28" height="20" rx="4" /><path :d="`M ${c.x - 3} ${c.y - 6} l -4 7 h 6 l -4 7`" /></g>
    </g>

    <g class="routes">
      <path v-for="(d, i) in routes" :key="i" :ref="(el) => { if (el) pathEls[i] = el as SVGPathElement }" :d="d" />
    </g>

    <g class="robots">
      <g v-for="rb in robotsState" :key="rb.id" :transform="`translate(${rb.x} ${rb.y})`" :class="{ charging: rb.charging }">
        <circle r="16" class="halo" />
        <rect x="-12" y="-8" width="24" height="16" rx="4" class="body" />
        <rect x="-12" y="-8" width="24" height="3" rx="1.5" class="led" />
        <text y="4" class="rid">{{ rb.id }}</text>
      </g>
    </g>

    <text x="40" :y="H - 6" class="mono">шаг сетки 1 м · маршруты по осям проездов · {{ scenario }}</text>
  </svg>
</template>

<style scoped>
.plan { width: 100%; height: auto; display: block; }
.zone rect:first-child { fill: rgba(255, 255, 255, 0.55); stroke: var(--border-hairline); }
.tone-a rect:first-child { fill: rgba(23, 95, 176, 0.06); stroke: rgba(23, 95, 176, 0.25); }
.tone-c rect:first-child { fill: rgba(20, 167, 111, 0.08); stroke: rgba(20, 167, 111, 0.3); }
.tone-d rect:first-child { fill: rgba(138, 82, 0, 0.06); stroke: rgba(138, 82, 0, 0.3); }
.zl { font-family: var(--font-mono); font-size: 12px; letter-spacing: 0.06em; text-transform: uppercase; fill: var(--ink-muted); }
.rack { fill: rgba(15, 20, 19, 0.08); stroke: rgba(15, 20, 19, 0.18); }
.station { fill: #fff; stroke: var(--brand-600); stroke-width: 2; }
.chargers rect { fill: #fff; stroke: var(--state-warn); stroke-width: 1.5; }
.chargers path { fill: none; stroke: var(--state-warn); stroke-width: 1.5; stroke-linecap: round; stroke-linejoin: round; }
.routes path { fill: none; stroke: var(--brand-500); stroke-width: 1.5; stroke-dasharray: 6 6; opacity: 0.7; }
.robots .body { fill: var(--surface-graphite); }
.robots .led { fill: var(--brand-400); }
.robots .halo { fill: rgba(43, 209, 141, 0.18); }
.robots .charging .halo { fill: rgba(240, 173, 69, 0.22); }
.robots .charging .led { fill: var(--state-warn); }
.rid { font-family: var(--font-mono); font-size: 10px; font-weight: 700; fill: #fff; text-anchor: middle; }
.mono { font-family: var(--font-mono); font-size: 11px; fill: var(--ink-muted); }
</style>
