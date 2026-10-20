<script setup lang="ts">
import { PhCheckCircle, PhWarningCircle, PhXCircle, PhArrowRight, PhCaretDown, PhChartLineUp } from '@phosphor-icons/vue'
import { millions, signedMillions, yearsText, type EconPlan, type EconChance, type EconFig, type EconScenario, type EconStress } from '~/composables/usePlatformEconomy'

/** Общая картина экономики: ответ словами, четыре понятные цифры и затраты «сейчас / с роботами». Без жаргона. */
const props = defineProps<{
  buy: EconScenario
  horizon: number
  staffNow: number
  costNow: number
  released: number
  dispatchers: number | null
  good: number
  total: number
  losers: number
  conditional: number
  applicable: number
  noStaff: number
  uncounted: number
  chance?: EconChance | null
  worst?: EconStress | null
  plan?: EconPlan | null
  busy?: boolean
}>()
const emit = defineEmits<{ keepGood: []; applyConditions: []; applyPlan: []; goto: [string]; horizon: [number] }>()

/* Горизонт расчёта: ТЗ требует не меньше 5 лет, короче и длиннее — для сравнения. */
const HORIZONS = [3, 5, 7, 10]

/* Насколько уверены — одной фразой для всех; цифры для экономиста — в раскрывающейся панели. */
const sure = computed(() => {
  const c = props.chance
  if (!c) return null
  const share = Math.round(c.npv_positive * 10)
  const tone = c.npv_positive >= 0.8 ? 'ok' : c.npv_positive >= 0.5 ? 'warn' : 'bad'
  const text = share >= 10 ? 'Расчёт в плюсе почти при любых ценах, ставках и зарплатах'
    : share <= 0 ? 'Расчёт в минусе почти при любых ценах, ставках и зарплатах'
      : `Расчёт в плюсе в ${share} из 10 вариантов цен, ставок и зарплат`
  const worst = props.worst?.npv == null ? ''
    : props.worst.ok ? 'выдержит, даже если всё пойдёт плохо сразу'
      : `${share > 0 ? 'но ' : ''}если всё пойдёт плохо сразу — ${signedMillions(props.worst.npv)}`
  return { tone, text, worst }
})
const planStep = computed(() => {
  const plan = props.plan
  if (!plan?.changes.length || plan.npv == null) return null
  return plan
})
const plural = (n: number, one: string, few: string, many: string) => {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few
  return many
}
/* Главный совет — одно действие с наибольшим эффектом. */
interface Advice { tone: 'best' | 'cond' | 'bad'; title: string; text: string; button: string; act: () => void }
const advice = computed<Advice | null>(() => {
  const plan = planStep.value
  if (plan) {
    const n = plan.changes.length
    return {
      tone: 'best',
      title: `Платформа нашла, как улучшить итог: ${n} ${plural(n, 'правка', 'правки', 'правок')}.`,
      text: `Итог ${signedMillions(plan.npv)} вместо ${signedMillions(plan.current_npv)}${plan.payback != null ? `, окупится за ${yearsText(plan.payback)}` : ''}${plan.budget ? ` · в бюджете ${millions(plan.budget)}` : ''}.`,
      button: 'Применить',
      act: () => emit('applyPlan'),
    }
  }
  if (props.conditional) {
    const n = props.conditional
    return {
      tone: 'cond',
      title: `Ещё ${n} ${plural(n, 'процесс окупится', 'процесса окупятся', 'процессов окупятся')} с условием.`,
      text: 'Скидка вендора, господдержка или другой сервис — условие у каждого процесса.',
      button: props.applicable ? 'Применить условия' : 'Посмотреть',
      act: () => props.applicable ? emit('applyConditions') : emit('goto', 'processes'),
    }
  }
  if (props.losers) {
    return {
      tone: 'bad',
      title: `Выгодны ${props.good} из ${props.total} процессов.`,
      text: 'Невыгодные тянут итог вниз.',
      button: `Убрать невыгодные · ${props.losers}`,
      act: () => emit('keepGood'),
    }
  }
  return null
})
const missing = computed(() => [
  props.noStaff ? `люди у ${props.noStaff} ${plural(props.noStaff, 'процесса', 'процессов', 'процессов')}` : '',
  props.uncounted ? `число роботов у ${props.uncounted}` : '',
].filter(Boolean).join(', '))
/* Панель экономиста помнится между заходами: кто открыл её раз, видит её сразу. */
const expert = ref(false)
onMounted(() => { try { expert.value = localStorage.getItem('econ-expert') === '1' } catch { /* хранилище недоступно */ } })
const toggleExpert = () => {
  expert.value = !expert.value
  try { localStorage.setItem('econ-expert', expert.value ? '1' : '0') } catch { /* хранилище недоступно */ }
}

const fmt = (value: number, digits = 1) => value.toLocaleString('ru-RU', { maximumFractionDigits: digits })
const payback = computed(() => props.buy.payback.value)
const saving = computed(() => props.buy.effect.value ?? 0)
const capex = computed(() => props.buy.capex.value ?? 0)
const flow = computed(() => props.buy.cashflow ?? [])
const net = computed(() => flow.value.length ? flow.value[flow.value.length - 1]!.cumulative : null)
/* Экономия на людях и затраты на роботов в год: из них складывается «с роботами». */
const robotsYear = computed(() => props.buy.opex.value ?? 0)
const savingPeople = computed(() => saving.value + robotsYear.value)
const after = computed(() => Math.max(0, props.costNow - savingPeople.value) + robotsYear.value)
const peopleAfter = computed(() => Math.max(0, props.costNow - savingPeople.value))

const tone = computed<'ok' | 'warn' | 'bad'>(() => {
  if (payback.value != null && payback.value <= props.horizon && (props.buy.npv?.value ?? 0) >= 0) return 'ok'
  if (payback.value != null) return 'warn'
  return 'bad'
})
const headline = computed(() => {
  if (!props.total) return 'Нет процессов в расчёте'
  if (tone.value === 'ok') return `Роботизация окупится за ${yearsText(payback.value)}`
  if (tone.value === 'warn') return `Окупится только за ${yearsText(payback.value)} — дольше горизонта или в минус с учётом стоимости денег`
  return `Роботизация не окупится за ${yearsText(props.horizon)}`
})
const why = computed(() => {
  if (tone.value === 'ok') return `Каждый год вы будете тратить на ${millions(saving.value)} меньше, вложив ${millions(capex.value)} один раз.`
  if (saving.value <= 0) return 'Роботы и их обслуживание обходятся дороже, чем люди, которых они заменяют.'
  return `Экономия ${millions(saving.value)} в год слишком мала, чтобы вернуть ${millions(capex.value)} вложений.`
})

interface Tile { key: string; label: string; value: string; hint: string; fig: EconFig | null; tone?: 'good' | 'bad' }
const tiles = computed<Tile[]>(() => [
  { key: 'capex', label: 'Вложения', value: millions(capex.value), hint: 'один раз: роботы, внедрение, интеграция', fig: props.buy.capex },
  { key: 'effect', label: 'Экономия в год', value: `${saving.value >= 0 ? '' : '−'}${millions(Math.abs(saving.value))}`, hint: 'меньше людей минус расходы на роботов', fig: props.buy.effect, tone: saving.value > 0 ? 'good' : 'bad' },
  { key: 'payback', label: 'Окупаемость', value: payback.value != null ? yearsText(payback.value) : 'нет', hint: `когда вложения вернутся · горизонт ${props.horizon} лет`, fig: props.buy.payback, tone: payback.value != null && payback.value <= props.horizon ? 'good' : 'bad' },
  { key: 'net', label: `Итог за ${props.horizon} лет`, value: signedMillions(net.value), hint: 'чистыми: после налогов и возврата вложений', fig: props.buy.roi, tone: (net.value ?? 0) >= 0 ? 'good' : 'bad' },
])
const open = ref('')
const opened = computed(() => tiles.value.find((tile) => tile.key === open.value)?.fig ?? null)
const scale = computed(() => Math.max(1, props.costNow, after.value))
const pct = (value: number) => `${Math.max(0.4, (value / scale.value) * 100)}%`
</script>

<template>
  <section class="ov glass" :class="tone">
    <div class="o-in">
      <div class="head">
        <span class="icon" aria-hidden="true">
          <PhCheckCircle v-if="tone === 'ok'" :size="34" weight="fill" />
          <PhWarningCircle v-else-if="tone === 'warn'" :size="34" weight="fill" />
          <PhXCircle v-else :size="34" weight="fill" />
        </span>
        <div class="copy">
          <span class="label">Общая картина · покупка роботов</span>
          <h2 class="h2">{{ headline }}</h2>
          <p class="body-lg why">{{ why }}</p>
        </div>
        <div class="horizon">
          <span class="caption">Считаем на</span>
          <div class="seg" role="radiogroup" aria-label="Горизонт расчёта">
            <button v-for="years in HORIZONS" :key="years" type="button" role="radio" :aria-checked="horizon === years" :class="{ on: horizon === years }" :disabled="busy" @click="horizon !== years && emit('horizon', years)">{{ years }}</button>
          </div>
          <span class="caption">лет<template v-if="!HORIZONS.includes(horizon)"> · сейчас {{ horizon }}</template></span>
        </div>
      </div>

      <div class="tiles">
        <button v-for="tile in tiles" :key="tile.key" type="button" class="tile" :class="[tile.tone, { on: open === tile.key }]" :aria-expanded="open === tile.key" @click="open = open === tile.key ? '' : tile.key">
          <span class="t-label">{{ tile.label }}</span>
          <span class="t-val">{{ tile.value }}</span>
          <span class="caption">{{ tile.hint }}</span>
          <span class="caption how">{{ open === tile.key ? 'скрыть расчёт' : 'как посчитано' }}</span>
        </button>
      </div>
      <EconFormula v-if="opened" :fig="opened" />

      <div class="belt">
        <button v-if="sure" type="button" class="sure" :class="sure.tone" @click="emit('goto', 'risk')">
          <span class="dot" aria-hidden="true" />
          <span class="body-sm"><b>{{ sure.text }}</b><template v-if="sure.worst"> · {{ sure.worst }}</template></span>
          <PhArrowRight :size="14" weight="bold" />
        </button>
        <button type="button" class="expert-btn" :aria-expanded="expert" @click="toggleExpert">
          <PhChartLineUp :size="16" weight="bold" />
          <span>Показатели для экономиста</span>
          <PhCaretDown :size="14" weight="bold" class="caret" :class="{ up: expert }" />
        </button>
      </div>
      <div v-if="expert" class="expert"><slot name="expert" /></div>

      <div v-if="costNow" class="compare">
        <div class="c-title">
          <span class="h4">Затраты на эти операции в год</span>
          <span class="caption">сейчас на них {{ fmt(staffNow, 0) }} чел. · с роботами уходят {{ fmt(released) }}<template v-if="dispatchers"> · нужны {{ fmt(dispatchers) }} диспетчера</template></span>
        </div>
        <div class="bar-row">
          <span class="b-label body-sm">Сейчас</span>
          <span class="track"><i class="now" :style="{ width: pct(costNow) }" /></span>
          <span class="b-val mono-md">{{ millions(costNow) }}</span>
        </div>
        <div class="bar-row">
          <span class="b-label body-sm">С роботами</span>
          <span class="track"><i class="people" :style="{ width: pct(peopleAfter) }" /><i class="bots" :style="{ width: pct(robotsYear) }" /></span>
          <span class="b-val mono-md">{{ millions(after) }}</span>
        </div>
        <span class="legend caption"><i class="sw now" />люди сейчас <i class="sw people" />люди, которые остаются <i class="sw bots" />роботы: сервис, энергия, диспетчеры</span>
      </div>

      <!-- Один главный совет и тихая строка о недостающих данных: остальное — во вкладке процессов. -->
      <div v-if="advice || missing || $slots.fixes" class="next">
        <slot name="fixes" />
        <UiHint v-if="advice">
          <b>{{ advice.title }}</b> {{ advice.text }}
          <template #action><UiButton size="sm" :disabled="busy" @click="advice.act()">{{ advice.button }}</UiButton></template>
        </UiHint>
        <UiHint v-if="missing">
          Не хватает данных: {{ missing }} — пока они не дают экономии.
          <template #action><UiButton variant="secondary" size="sm" @click="emit('goto', 'processes')">Заполнить<template #after><PhArrowRight :size="14" weight="bold" /></template></UiButton></template>
        </UiHint>
      </div>
    </div>
  </section>
</template>

<style scoped>
.ov { border-radius: var(--radius-xl); box-shadow: inset 5px 0 0 var(--tone); }
.ov.ok { --tone: var(--brand-500); }
.ov.warn { --tone: #f0b14a; }
.ov.bad { --tone: #e5584b; }
.o-in { position: relative; z-index: 1; padding: var(--space-6); display: grid; gap: var(--space-5); }
.head { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 16px; align-items: start; }
.horizon { display: inline-flex; align-items: center; gap: 8px; margin-top: 18px; white-space: nowrap; }
.seg { display: inline-flex; padding: 3px; border-radius: 999px; background: rgba(15, 20, 19, 0.06); }
.seg button { min-width: 34px; height: 28px; padding: 0 10px; border-radius: 999px; font-family: var(--font-mono); font-size: 13px; font-weight: 700; color: var(--ink-muted); }
.seg button:not(:disabled):hover { color: var(--ink-strong); }
.seg button.on { background: #fff; color: var(--brand-700); box-shadow: 0 1px 3px rgba(15, 20, 19, 0.15); }
.icon { display: inline-flex; color: var(--tone); margin-top: 22px; }
.copy { display: grid; gap: 6px; }
.copy .label { color: var(--ink-muted); }
.copy .h2 { margin: 0; font-size: clamp(24px, 2.2vw, 34px); }
.why { margin: 0; color: var(--ink-body); max-width: 72ch; }
.tiles { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.tile { display: grid; gap: 4px; align-content: start; text-align: left; padding: 16px 18px; border-radius: 18px; background: #fff; box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.08); transition: box-shadow var(--dur-fast) var(--ease); }
.tile:hover, .tile.on { box-shadow: inset 0 0 0 1.5px var(--brand-400); }
.t-label { font-size: 14px; font-weight: 700; color: var(--ink-body); }
.t-val { font-family: var(--font-mono); font-weight: 700; font-size: clamp(24px, 2.2vw, 34px); line-height: 1.1; letter-spacing: -0.02em; color: var(--ink-strong); font-variant-numeric: tabular-nums; }
.tile.good .t-val { color: var(--brand-700); }
.tile.bad .t-val { color: #c0392b; }
.how { margin-top: 4px; color: var(--link); font-weight: 600; opacity: 0; transition: opacity var(--dur-fast) var(--ease); }
.tile:hover .how, .tile.on .how, .tile:focus-visible .how { opacity: 1; }
@media (hover: none) { .how { opacity: 1; } }
.compare { display: grid; gap: 8px; padding: 16px 18px; border-radius: 18px; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.c-title { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 4px 16px; align-items: baseline; }
.c-title .h4 { margin: 0; }
.bar-row { display: grid; grid-template-columns: 110px minmax(0, 1fr) 120px; gap: 12px; align-items: center; }
.b-val { text-align: right; font-weight: 700; color: var(--ink-strong); }
.track { display: flex; height: 22px; border-radius: 11px; background: rgba(15, 20, 19, 0.05); overflow: hidden; }
.track i { display: block; height: 100%; }
.track .now { background: #8a9692; border-radius: 11px; }
.track .people { background: #b8c2be; }
.track .bots { background: var(--tone); }
.legend { display: flex; flex-wrap: wrap; gap: 4px 14px; align-items: center; padding-left: 122px; }
.sw { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 4px; vertical-align: -1px; }
.sw.now { background: #8a9692; }
.sw.people { background: #b8c2be; }
.sw.bots { background: var(--tone); }
.belt { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 10px 16px; }
.sure { display: inline-flex; align-items: center; gap: 10px; text-align: left; padding: 8px 14px; border-radius: 999px; background: rgba(255, 255, 255, 0.65); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.07); color: var(--ink-body); }
.sure:hover { box-shadow: inset 0 0 0 1.5px var(--brand-400); }
.sure .dot { width: 10px; height: 10px; border-radius: 50%; flex: none; background: var(--brand-500); }
.sure.warn .dot { background: #f0b14a; }
.sure.bad .dot { background: #e5584b; }
.expert-btn { display: inline-flex; align-items: center; gap: 8px; padding: 8px 14px; border-radius: 999px; font-size: 14px; font-weight: 700; color: var(--link); }
.expert-btn:hover, .expert-btn[aria-expanded='true'] { background: var(--surface-brand-tint); }
.caret { transition: transform var(--dur-fast) var(--ease); }
.caret.up { transform: rotate(180deg); }
.expert { padding: 14px; border-radius: 18px; background: rgba(255, 255, 255, 0.5); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.next { display: grid; gap: 6px; }
@media (max-width: 1100px) { .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 600px) {
  .tiles { grid-template-columns: 1fr; }
  .bar-row { grid-template-columns: 80px minmax(0, 1fr) 90px; }
  .legend { padding-left: 0; }
  .head { grid-template-columns: 1fr; }
  .horizon { margin-top: 0; }
  .icon { margin-top: 0; }
}
</style>
