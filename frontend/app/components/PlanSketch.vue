<script setup lang="ts">
import type { Floor } from '~/sim/types'

/** Схема этажа для отчёта: пол, стеллажи и препятствия, рабочие зоны и точки операций процессов. Чистый SVG — печатается как на экране. */
const props = defineProps<{ floor: Floor; colors: Record<string, string>; names: Record<string, string> }>()

/* Рамка схемы — по всем объектам этажа, с полем в метр. */
const box = computed(() => {
  const xs: number[] = []
  const ys: number[] = []
  for (const area of props.floor.areas) for (let i = 0; i < area.points.length; i += 2) { xs.push(area.points[i]!); ys.push(area.points[i + 1]!) }
  for (const item of [...props.floor.blocks, ...props.floor.zones]) { xs.push(item.x, item.x + item.w); ys.push(item.y, item.y + item.h) }
  for (const st of props.floor.stations) { xs.push(st.x); ys.push(st.y) }
  if (!xs.length) return { x: 0, y: 0, w: props.floor.width || 10, h: props.floor.height || 10 }
  const x = Math.min(...xs) - 1
  const y = Math.min(...ys) - 1
  return { x, y, w: Math.max(...xs) - x + 1, h: Math.max(...ys) - y + 1 }
})
const color = (code?: string) => (code && props.colors[code]) || '#0d8455'
const areaPath = (points: number[]) => points.reduce((acc, value, index) => acc + (index % 2 ? `,${value} ` : `${index ? 'L' : 'M'}${value}`), '') + 'Z'
/* Подписи станций — только у первой станции процесса каждого вида, чтобы схема не тонула в тексте. */
const stations = computed(() => props.floor.stations.filter((st) => st.kind !== 'waypoint'))
const used = computed(() => [...new Set([...props.floor.stations.map((st) => st.process), ...props.floor.zones.map((zone) => zone.process)])].filter(Boolean))
/* Каждый процесс подписан один раз — на своей самой большой зоне, даже узкой (например, периметр под мойку фасадов). */
const label = computed(() => Math.max(0.6, Math.min(box.value.w, box.value.h) / 38))
const labelled = computed(() => {
  const best = new Map<string, (typeof props.floor.zones)[number]>()
  for (const zone of props.floor.zones) {
    const prev = best.get(zone.process)
    if (!prev || zone.w * zone.h > prev.w * prev.h) best.set(zone.process, zone)
  }
  return [...best.values()]
})
const r = computed(() => Math.max(0.35, Math.min(box.value.w, box.value.h) / 70))
</script>

<template>
  <figure class="sketch">
    <svg :viewBox="`${box.x} ${box.y} ${box.w} ${box.h}`" preserveAspectRatio="xMidYMid meet" role="img" :aria-label="`Схема: ${floor.name}`">
      <path v-for="area in floor.areas" :key="area.id" :d="areaPath(area.points)" class="floor" />
      <rect v-for="block in floor.blocks" :key="block.id" :x="block.x" :y="block.y" :width="block.w" :height="block.h" class="block" />
      <rect v-for="zone in floor.zones" :key="zone.id" :x="zone.x" :y="zone.y" :width="zone.w" :height="zone.h" class="zone" :style="{ stroke: color(zone.process), fill: color(zone.process) }" />
      <!-- Подпись пунктирной зоны: какой процесс здесь работает. -->
      <text v-for="zone in labelled" :key="`t-${zone.id}`" :x="zone.x + label * 0.4" :y="zone.h < label * 1.6 ? zone.y - label * 0.35 : zone.y + label * 1.15" :font-size="label" class="z-text" :style="{ fill: color(zone.process) }">{{ names[zone.process] ?? zone.process }}</text>
      <g v-for="st in stations" :key="st.id">
        <rect v-if="st.kind === 'charge'" :x="st.x - r" :y="st.y - r" :width="r * 2" :height="r * 2" class="charge" />
        <circle v-else :cx="st.x" :cy="st.y" :r="r" :class="st.kind" :style="{ fill: st.kind === 'load' ? color(st.process) : '#fff', stroke: color(st.process) }" />
      </g>
    </svg>
    <figcaption class="legend">
      <span v-for="code in used" :key="code"><i :style="{ background: color(code) }" />{{ names[code] ?? code }}</span>
      <span><i class="dot-load" />откуда берут</span>
      <span><i class="dot-unload" />куда везут</span>
      <span><i class="sq-charge" />зарядка</span>
      <span><i class="sq-zone" />пунктир — зона работы процесса, цвет и подпись — какого</span>
    </figcaption>
  </figure>
</template>

<style scoped>
.sketch { margin: 0; display: grid; gap: 6px; break-inside: avoid; }
svg { width: 100%; max-height: 120mm; display: block; background: #f6f8f7; border-radius: 6px; }
.floor { fill: #fff; stroke: #1c2421; stroke-width: 0.25; vector-effect: non-scaling-stroke; }
.block { fill: rgba(15, 20, 19, 0.12); stroke: rgba(15, 20, 19, 0.35); stroke-width: 1; vector-effect: non-scaling-stroke; }
.zone { fill-opacity: 0.08; stroke-width: 1.2; stroke-dasharray: 4 3; vector-effect: non-scaling-stroke; }
.load, .unload { stroke-width: 1.5; vector-effect: non-scaling-stroke; }
.charge { fill: #fff; stroke: #e6a23c; stroke-width: 1.5; vector-effect: non-scaling-stroke; }
.z-text { font-family: inherit; font-weight: 700; paint-order: stroke; stroke: #fff; stroke-width: 0.35; stroke-linejoin: round; }
.legend { display: flex; flex-wrap: wrap; gap: 3px 12px; font-size: 8pt; color: #3d4845; }
.legend i { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 4px; vertical-align: -1px; }
.legend .dot-load { background: #3d4845; }
.legend .dot-unload { background: #fff; box-shadow: inset 0 0 0 1.5px #3d4845; }
.legend .sq-charge { border-radius: 2px; background: #fff; box-shadow: inset 0 0 0 1.5px #e6a23c; }
.legend .sq-zone { border-radius: 2px; box-shadow: inset 0 0 0 1px #3d4845; background: rgba(15, 20, 19, 0.06); }
</style>
