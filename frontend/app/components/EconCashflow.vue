<script setup lang="ts">
import { signedMillions, type EconCashRow, type EconScenario } from '~/composables/usePlatformEconomy'

/** Деньги по годам: что приходит и уходит каждый год, столбиками и таблицей. Год 0 — вложения. */
/* other — вторая схема (покупка или аренда): её итог по годам строками под таблицей, чтобы сравнить не переключаясь. */
const props = defineProps<{ scenario: EconScenario; other?: EconScenario | null }>()

interface Part { key: keyof EconCashRow; label: string; color: string }
const PARTS: Part[] = [
  { key: 'saving_rub', label: 'Экономия ФОТ', color: 'var(--brand-500)' },
  { key: 'support_rub', label: 'Господдержка', color: '#3fb8a4' },
  { key: 'residual_rub', label: 'Остаточная стоимость', color: '#6ea8ff' },
  { key: 'opex_rub', label: 'Эксплуатация', color: '#8a9692' },
  { key: 'payouts_rub', label: 'Выплаты при сокращении', color: '#f0b14a' },
  { key: 'reinvest_rub', label: 'Повторная закупка парка', color: '#2b3533' },
  { key: 'tax_rub', label: 'Налог на прибыль', color: '#e57d72' },
]
const rows = computed(() => props.scenario.cashflow ?? [])
const capex = computed(() => props.scenario.capex.value ?? 0)
/* У аренды «эксплуатация» — это прежде всего платёж за аренду: так и подписываем. */
const parts = computed(() => PARTS.map((part) => part.key === 'opex_rub' && props.scenario.key === 'raas' ? { ...part, label: 'Аренда и обслуживание' } : part).filter((part) => rows.value.some((row) => Math.abs(Number(row[part.key]) || 0) > 1)))

/* Рисуем в реальную ширину контейнера: так подписи не растягиваются вместе с графиком. */
const box = ref<HTMLElement | null>(null)
const W = ref(760)
const H = 300
let observer: ResizeObserver | undefined
onMounted(() => {
  if (!box.value) return
  observer = new ResizeObserver(([entry]) => { if (entry) W.value = Math.max(320, Math.round(entry.contentRect.width)) })
  observer.observe(box.value)
})
onBeforeUnmount(() => observer?.disconnect())
const PAD = { left: 56, right: 16, top: 16, bottom: 34 }
const cols = computed(() => rows.value.length + 1)
const slot = computed(() => (W.value - PAD.left - PAD.right) / cols.value)
const bar = computed(() => Math.min(64, slot.value * 0.56))

/* Стопки: притоки вверх, оттоки вниз от нуля. Год 0 — один столбик вложений. */
const stacks = computed(() => {
  const out = [{ year: 0, up: [] as { color: string; from: number; to: number; label: string; value: number }[], down: [{ color: '#2b3533', from: 0, to: -capex.value, label: 'Вложения', value: -capex.value }], cf: -capex.value }]
  for (const row of rows.value) {
    let up = 0
    let down = 0
    const stack = { year: row.year, up: [] as typeof out[0]['up'], down: [] as typeof out[0]['down'], cf: row.cf_rub }
    for (const part of parts.value) {
      const value = Number(row[part.key]) || 0
      if (value > 0) { stack.up.push({ color: part.color, from: up, to: up + value, label: part.label, value }); up += value }
      else if (value < 0) { stack.down.push({ color: part.color, from: down, to: down + value, label: part.label, value }); down += value }
    }
    out.push(stack)
  }
  return out
})
const range = computed(() => {
  const highs = stacks.value.map((s) => s.up.reduce((sum, p) => sum + (p.to - p.from), 0))
  const lows = stacks.value.map((s) => s.down.reduce((sum, p) => sum + (p.to - p.from), 0))
  const max = Math.max(0, ...highs)
  const min = Math.min(0, ...lows)
  const pad = (max - min || 1) * 0.06
  return { min: min - pad, max: max + pad }
})
const y = (value: number) => PAD.top + (1 - (value - range.value.min) / (range.value.max - range.value.min)) * (H - PAD.top - PAD.bottom)
const cx = (index: number) => PAD.left + slot.value * (index + 0.5)
const ticks = computed(() => {
  const raw = (range.value.max - range.value.min) / 4
  const power = 10 ** Math.floor(Math.log10(raw || 1))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((m) => m >= raw) ?? raw
  const out: number[] = []
  for (let v = Math.ceil(range.value.min / step) * step; v <= range.value.max; v += step) out.push(v)
  return out
})
const mln = (value: number) => (value / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: 1 })
const cell = (value: number) => Math.abs(value) < 1 ? '—' : mln(value)
const hover = ref<number | null>(null)

const table = computed(() => [
  { label: 'Вложения (CAPEX)', values: [-capex.value, ...rows.value.map(() => 0)] },
  ...parts.value.map((part) => ({ label: part.label, values: [0, ...rows.value.map((row) => Number(row[part.key]) || 0)] })),
])
const totals = computed(() => [-capex.value, ...rows.value.map((row) => row.cf_rub)])
const cumulative = computed(() => [-capex.value, ...rows.value.map((row) => row.cumulative)])
const NAMES: Record<string, string> = { purchase: 'покупка', raas: 'аренда' }
const name = (item: EconScenario) => NAMES[item.key] ?? item.title.toLowerCase()
const compare = computed(() => {
  const other = props.other
  if (!other?.cashflow?.length) return null
  const start = -(other.capex.value ?? 0)
  const flow = [start, ...other.cashflow.map((row) => row.cf_rub)]
  const total = [start, ...other.cashflow.map((row) => row.cumulative)]
  return {
    title: `Для сравнения: ${name(other)}`,
    rows: [
      { label: 'Поток года', values: flow },
      { label: 'Накоплено', values: total },
      { label: `Разница: ${name(other)} − ${name(props.scenario)}`, values: total.map((value, index) => value - (cumulative.value[index] ?? 0)), diff: true },
    ],
  }
})
const depreciation = computed(() => [0, ...rows.value.map((row) => row.depreciation_rub)])
</script>

<template>
  <div class="cash">
    <figure ref="box" class="chart">
      <svg :viewBox="`0 0 ${W} ${H}`" role="img" aria-label="Денежный поток по годам">
        <g class="grid">
          <line v-for="t in ticks" :key="t" :x1="PAD.left" :x2="W - PAD.right" :y1="y(t)" :y2="y(t)" />
          <text v-for="t in ticks" :key="`l${t}`" :x="PAD.left - 8" :y="y(t) + 4" text-anchor="end">{{ mln(t) }}</text>
        </g>
        <line :x1="PAD.left" :x2="W - PAD.right" :y1="y(0)" :y2="y(0)" class="zero" />
        <g v-for="(s, index) in stacks" :key="s.year" class="col" :class="{ on: hover === index }" @mouseenter="hover = index" @mouseleave="hover = null">
          <rect :x="cx(index) - slot / 2" :y="PAD.top" :width="slot" :height="H - PAD.top - PAD.bottom" class="hit" />
          <rect v-for="p in [...s.up, ...s.down]" :key="p.label" :x="cx(index) - bar / 2" :y="y(Math.max(p.from, p.to))" :width="bar" :height="Math.max(1, Math.abs(y(p.from) - y(p.to)))" :fill="p.color" rx="3" />
          <circle :cx="cx(index)" :cy="y(s.cf)" r="5" class="cf" />
          <text :x="cx(index)" :y="H - 10" text-anchor="middle" class="yl">{{ s.year === 0 ? 'старт' : `${s.year} год` }}</text>
        </g>
      </svg>
      <figcaption class="legend caption">
        <span v-for="p in parts" :key="p.key"><i :style="{ background: p.color }" />{{ p.label }}</span>
        <span><i class="dot" />итог года</span>
      </figcaption>
      <p class="caption tip">{{ hover != null ? `${hover === 0 ? 'Старт' : `${hover} год`}: итог ${signedMillions(totals[hover])}, накоплено ${signedMillions(cumulative[hover])}` : 'Наведите на год, чтобы увидеть итог и накопленную сумму. Млн ₽, без НДС, после налога на прибыль.' }}</p>
    </figure>

    <div class="t-wrap">
      <table class="tbl">
        <thead>
          <tr><th>млн ₽</th><th v-for="(_v, index) in totals" :key="index">{{ index === 0 ? 'Старт' : `${index} год` }}</th></tr>
        </thead>
        <tbody>
          <tr v-for="row in table" :key="row.label">
            <th>{{ row.label }}</th>
            <td v-for="(value, index) in row.values" :key="index" :class="{ neg: value < -1, pos: value > 1 }">{{ cell(value) }}</td>
          </tr>
          <tr class="total"><th>Поток года</th><td v-for="(value, index) in totals" :key="index" :class="{ neg: value < 0 }">{{ mln(value) }}</td></tr>
          <tr class="total"><th>Накоплено</th><td v-for="(value, index) in cumulative" :key="index" :class="{ neg: value < 0 }">{{ mln(value) }}</td></tr>
          <tr class="aside"><th>Амортизация, уменьшает налог</th><td v-for="(value, index) in depreciation" :key="index">{{ cell(value) }}</td></tr>
          <template v-if="compare">
            <tr class="sec"><th :colspan="totals.length + 1">{{ compare.title }}</th></tr>
            <tr v-for="row in compare.rows" :key="row.label" :class="{ diff: row.diff }">
              <th>{{ row.label }}</th>
              <td v-for="(value, index) in row.values" :key="index" :class="{ neg: value < -1, pos: row.diff && value > 1 }">{{ row.diff ? (Math.abs(value) < 1 ? '—' : `${value > 0 ? '+' : ''}${mln(value)}`) : mln(value) }}</td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.cash { display: grid; gap: var(--space-5); }
.chart { margin: 0; display: grid; gap: 8px; }
svg { width: 100%; height: auto; display: block; }
.grid line { stroke: rgba(15, 20, 19, 0.07); }
.grid text, .yl { font-family: var(--font-mono); font-size: 11px; fill: var(--ink-muted); }
.zero { stroke: rgba(15, 20, 19, 0.45); stroke-width: 1.5; }
.hit { fill: transparent; }
.col.on .hit { fill: rgba(13, 132, 85, 0.06); }
.cf { fill: #fff; stroke: var(--ink-strong); stroke-width: 2.5; }
.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; }
.legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px; vertical-align: -1px; }
.legend i.dot { border-radius: 50%; background: #fff; box-shadow: inset 0 0 0 2px var(--ink-strong); }
.tip { margin: 0; min-height: 1.5em; }
.t-wrap { overflow-x: auto; }
.tbl { width: 100%; border-collapse: collapse; font-size: 13px; }
.tbl th, .tbl td { padding: 8px 10px; border-bottom: 1px solid rgba(15, 20, 19, 0.06); white-space: nowrap; }
.tbl thead th { font-size: 12px; font-weight: 700; color: var(--ink-muted); text-align: right; }
.tbl thead th:first-child, .tbl tbody th { text-align: left; font-weight: 600; color: var(--ink-body); }
.tbl td { text-align: right; font-family: var(--font-mono); font-variant-numeric: tabular-nums; color: var(--ink-strong); }
.tbl td.neg { color: #b4473d; }
.tbl td.pos { color: var(--brand-700); }
.tbl tr.total th, .tbl tr.total td { font-weight: 700; border-top: 1.5px solid rgba(15, 20, 19, 0.18); }
.tbl tr.aside th, .tbl tr.aside td { color: var(--ink-muted); font-size: 12px; }
.tbl tr.sec th { padding-top: 20px; font-size: 12px; font-weight: 700; letter-spacing: 0.02em; text-transform: uppercase; color: var(--ink-muted); }
.tbl tr.diff th, .tbl tr.diff td { font-weight: 700; }
</style>
