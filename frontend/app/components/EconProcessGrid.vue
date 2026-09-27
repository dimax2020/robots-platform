<script setup lang="ts">
import { photoFor } from '~/data/placeholders'
import { figValue, millions, type EconProcess, type EconScenario } from '~/composables/usePlatformEconomy'

/** Карточки процессов: окупаемость покупки против горизонта. Пустой код — весь парк. */
const props = defineProps<{
  processes: EconProcess[]
  fleet: EconScenario | null
  robots: number
  horizon: number
  modelValue: string
}>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()

const purchaseOf = (item: EconProcess) => item.scenarios.find((row) => row.key === 'purchase') ?? null
const paybackOf = (item: EconProcess) => purchaseOf(item)?.payback.value ?? null

const rank = (item: EconProcess) => (!item.included ? 2 : item.profitable ? 1 : 0)
const sorted = computed(() => [...props.processes].sort((a, b) => rank(a) - rank(b) || (paybackOf(a) ?? 1e9) - (paybackOf(b) ?? 1e9)))
const counted = computed(() => props.processes.filter((item) => item.included))
const good = computed(() => counted.value.filter((item) => item.profitable).length)

/* Шкала — два горизонта: риска на середине показывает границу окупаемости. */
const barOf = (payback: number | null) => {
  if (payback == null) return { width: '100%', tone: 'none' }
  const width = Math.min(100, Math.max(4, (payback / (props.horizon * 2)) * 100))
  return { width: `${width}%`, tone: payback <= props.horizon ? 'ok' : 'bad' }
}
const paybackText = (payback: number | null) => payback == null ? 'нет' : figValue(payback, 'лет')
const fleetPayback = computed(() => props.fleet?.payback.value ?? null)
</script>

<template>
  <section class="procs glass">
    <div class="p-in">
      <div class="p-head">
        <div>
          <div class="h3">Экономика по процессам</div>
          <div class="caption">Покупка на горизонте {{ horizon }} лет. Каждый процесс посчитан отдельно, как если бы роботизировали только его.</div>
        </div>
        <div class="tally">
          <span class="tally-n mono-md"><b>{{ good }}</b> из {{ counted.length }}</span>
          <span class="caption">окупаются</span>
        </div>
      </div>

      <div class="grid">
        <button type="button" class="card fleet" :class="{ on: !modelValue }" @click="emit('update:modelValue', '')">
          <span class="c-top">
            <span class="c-name">
              <span class="body-sm strong">Весь парк</span>
              <span class="caption">{{ counted.length }} процессов · {{ robots.toLocaleString('ru-RU') }} роботов</span>
            </span>
          </span>
          <span class="c-pay">
            <span class="c-pay-v">
              <span class="caption">Окупаемость парка</span>
              <span class="mono-lg">{{ paybackText(fleetPayback) }}</span>
            </span>
          </span>
          <span class="bar"><i :class="barOf(fleetPayback).tone" :style="{ width: barOf(fleetPayback).width }" /><em /></span>
          <span class="c-nums">
            <span><span class="caption">Эффект в год</span><span class="mono-sm">{{ millions(fleet?.effect.value) }}</span></span>
            <span><span class="caption">CAPEX</span><span class="mono-sm">{{ millions(fleet?.capex.value) }}</span></span>
          </span>
        </button>

        <button
          v-for="item in sorted"
          :key="item.process_code"
          type="button"
          class="card"
          :class="{ on: modelValue === item.process_code, bad: item.included && item.profitable === false, off: !item.included }"
          @click="emit('update:modelValue', item.process_code)"
        >
          <span class="c-top">
            <img :src="photoFor(item.image_url, item.robot_name, item.process_code)" :alt="item.robot_name">
            <span class="c-name">
              <span class="body-sm strong">{{ item.process_name }}</span>
              <span class="caption">{{ item.robot_name }}{{ item.count ? ` · ${item.count.toLocaleString('ru-RU')} шт.` : '' }}</span>
            </span>
          </span>
          <template v-if="item.included">
            <span class="c-pay">
              <span class="c-pay-v">
                <span class="caption">Окупаемость</span>
                <span class="mono-lg">{{ paybackText(paybackOf(item)) }}</span>
              </span>
              <span class="pill" :class="item.profitable ? 'ok' : 'bad'">{{ item.profitable ? 'окупается' : 'не окупается' }}</span>
            </span>
            <span class="bar"><i :class="barOf(paybackOf(item)).tone" :style="{ width: barOf(paybackOf(item)).width }" /><em /></span>
            <span class="c-nums">
              <span><span class="caption">Эффект в год</span><span class="mono-sm" :class="{ neg: (purchaseOf(item)?.effect.value ?? 0) < 0 }">{{ millions(purchaseOf(item)?.effect.value) }}</span></span>
              <span><span class="caption">CAPEX</span><span class="mono-sm">{{ millions(purchaseOf(item)?.capex.value) }}</span></span>
            </span>
          </template>
          <template v-else>
            <span class="pill muted">нет цены</span>
            <span class="caption c-note">{{ item.note }}</span>
          </template>
        </button>
      </div>
      <div class="legend caption"><span><i class="lg ok" /> в пределах горизонта</span><span><i class="lg bad" /> дольше горизонта</span><span><i class="lg mark" /> граница {{ horizon }} лет</span></div>
    </div>
  </section>
</template>

<style scoped>
.p-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: var(--space-4); }
.p-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-4); }
.tally { display: grid; justify-items: end; gap: 2px; flex: none; }
.tally-n { color: var(--ink-muted); font-size: 18px; }
.tally-n b { color: var(--ink-strong); font-size: 28px; font-weight: 600; letter-spacing: -0.03em; }

.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 10px; }
.card {
  display: grid; gap: 10px; align-content: start; text-align: left; padding: 14px; border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.62); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06);
  transition: transform var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease), background var(--dur-fast) var(--ease);
}
.card:hover { transform: translateY(-2px); background: #fff; box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.08), 0 10px 24px rgba(15, 20, 19, 0.06); }
.card.bad { box-shadow: inset 3px 0 0 var(--state-danger), inset 0 0 0 1px rgba(179, 42, 38, 0.18); }
.card.off { opacity: 0.7; }
.card.on { background: var(--surface-graphite); box-shadow: 0 12px 28px rgba(15, 20, 19, 0.22); }
.card.on .body-sm, .card.on .mono-lg, .card.on .mono-sm { color: var(--ink-on-graphite); }
.card.on .caption { color: var(--ink-muted-graphite); }
.card.on .bar { background: rgba(255, 255, 255, 0.1); }
.card.on .bar em { background: rgba(255, 255, 255, 0.55); }
.card.fleet .mono-lg { color: var(--brand-700); }
.card.fleet.on .mono-lg { color: var(--brand-300); }

.c-top { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 10px; align-items: center; min-height: 40px; }
.fleet .c-top { grid-template-columns: minmax(0, 1fr); }
.c-top img { width: 44px; height: 36px; object-fit: contain; border-radius: 8px; background: #e9eeec; }
.c-name { display: grid; gap: 1px; min-width: 0; }
.c-name .body-sm { color: var(--ink-strong); line-height: 1.25; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.c-name .caption { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.pill { justify-self: start; font-size: 11px; font-weight: 700; padding: 3px 8px; border-radius: 999px; white-space: nowrap; }
.pill.ok { background: var(--state-ok-tint); color: var(--state-ok); }
.pill.bad { background: var(--state-danger-tint); color: var(--state-danger); }
.pill.muted { background: rgba(15, 20, 19, 0.06); color: var(--ink-muted); }

.c-pay { display: flex; align-items: flex-end; justify-content: space-between; gap: 8px; }
.c-pay-v { display: grid; gap: 4px; }
.c-pay .mono-lg { font-size: 26px; line-height: 1; color: var(--ink-strong); letter-spacing: -0.02em; }
.bad .c-pay .mono-lg { color: var(--state-danger); }
.card.on.bad .c-pay .mono-lg { color: #ff8a80; }

.bar { position: relative; display: block; height: 6px; border-radius: 3px; background: rgba(15, 20, 19, 0.07); overflow: hidden; }
.bar i { position: absolute; inset: 0 auto 0 0; border-radius: 3px; transition: width var(--dur-mid) var(--ease); }
.bar i.ok { background: linear-gradient(90deg, var(--brand-400), var(--brand-600)); }
.bar i.bad { background: linear-gradient(90deg, #f0ad45, var(--state-danger)); }
.bar i.none { background: repeating-linear-gradient(135deg, rgba(179, 42, 38, 0.35) 0 6px, rgba(179, 42, 38, 0.12) 6px 12px); }
.bar em { position: absolute; left: 50%; top: -2px; bottom: -2px; width: 2px; background: rgba(15, 20, 19, 0.45); }

.c-nums { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding-top: 8px; border-top: 1px solid rgba(15, 20, 19, 0.06); }
.card.on .c-nums { border-top-color: rgba(255, 255, 255, 0.1); }
.c-nums > span { display: grid; gap: 1px; }
.c-nums .mono-sm { color: var(--ink-strong); }
.c-nums .neg { color: var(--state-danger) !important; }
.c-note { margin: 0; }

.legend { display: flex; flex-wrap: wrap; gap: 14px; }
.lg { display: inline-block; width: 14px; height: 6px; border-radius: 3px; vertical-align: 1px; margin-right: 4px; }
.lg.ok { background: var(--brand-600); }
.lg.bad { background: var(--state-danger); }
.lg.mark { width: 2px; height: 10px; background: rgba(15, 20, 19, 0.45); vertical-align: -1px; }
@media (max-width: 720px) {
  .p-head { flex-direction: column; }
  .tally { justify-items: start; }
}
</style>
