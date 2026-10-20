<script setup lang="ts">
import { signedMillions, yearsText, type EconBreakeven, type EconChance, type EconInterval, type EconSensitivity, type EconStress } from '~/composables/usePlatformEconomy'

/** Насколько надёжен вывод: интервал NPV, стресс-сценарии, запас прочности до нуля и какие допущения раздувают разброс. */
const props = defineProps<{ interval?: EconInterval | null; breakeven: EconBreakeven[]; sensitivity: EconSensitivity[]; stress?: EconStress[]; chance?: EconChance | null; horizon?: number }>()
const stressMax = computed(() => Math.max(1, ...(props.stress ?? []).map((item) => Math.abs(item.npv ?? 0)), Math.abs(props.interval?.npv ?? 0)))
const stressWidth = (value: number | null) => `${Math.max(0.5, (Math.abs(value ?? 0) / stressMax.value) * 50)}%`

const fmt = (value: number, digits = 1) => value.toLocaleString('ru-RU', { maximumFractionDigits: digits })

const points = computed(() => props.breakeven.map((item) => {
  const v = item.value
  const now = item.current
  let text = ''
  let tone: 'ok' | 'warn' | 'bad' = 'ok'
  if (v == null) {
    text = item.reachable ? 'Окупается во всём разумном диапазоне' : 'Не окупается ни при каком значении'
    tone = item.reachable ? 'ok' : 'bad'
  } else if (item.key === 'price_factor') {
    text = v >= 100 ? `Окупится, даже если парк подорожает на ${fmt(v - 100, 0)}%` : `Нужна скидка ${fmt(100 - v, 0)}% от цены карточки`
  } else if (item.key === 'release') {
    text = v <= now ? `Хватит ${fmt(v, 0)} чел. вместо ${fmt(now, 0)}` : `Нужно высвободить хотя бы ${fmt(v, 0)} чел., сейчас ${fmt(now, 0)}`
  } else if (item.key === 'robots_per_operator') {
    text = v <= now ? `Окупится, если диспетчер ведёт от ${fmt(v, 0)} машин (заложено ${fmt(now, 0)})` : `Нужно, чтобы диспетчер вёл от ${fmt(v, 0)} машин, заложено ${fmt(now, 0)}`
  } else if (item.key === 'salary_factor') {
    text = v <= now ? `Окупится, пока зарплаты не ниже ${fmt(v, 0)}% от нынешних` : `Окупится при зарплатах от ${fmt(v, 0)}% от нынешних`
  } else if (item.key === 'market_rate_pct') {
    text = v >= now ? `Выдержит ключевую ставку до ${fmt(v)}% годовых` : `Нужна ключевая ставка не выше ${fmt(v)}%, сейчас ${fmt(now)}%`
  }
  const margin = item.margin_pct
  if (v != null && margin != null) {
    const safe = item.direction === 'max' ? margin >= 0 : margin <= 0
    tone = !safe ? 'bad' : Math.abs(margin) < 15 ? 'warn' : 'ok'
  }
  return { ...item, text, tone, marginText: margin != null && v != null ? `запас ${fmt(Math.abs(margin), 0)}%` : '' }
}))

const TOP = 8
const showAll = ref(false)
/* Параметры, которые результат почти не двигают (меньше 0,5% разброса), не показываем: они только шумят. */
const rows = computed(() => props.sensitivity.filter((item) => item.npv_low != null && item.npv_high != null && (item.share ?? 1) >= 0.005))
const shown = computed(() => showAll.value ? rows.value : rows.value.slice(0, TOP))
const center = computed(() => props.interval?.npv ?? rows.value[0]?.npv ?? 0)
const span = computed(() => {
  const values = rows.value.flatMap((item) => [item.npv_low!, item.npv_high!, center.value])
  const lo = Math.min(...values, 0)
  const hi = Math.max(...values, 0)
  return { lo, hi: hi === lo ? lo + 1 : hi }
})
const pos = (value: number) => ((value - span.value.lo) / (span.value.hi - span.value.lo)) * 100
const rangeText = (item: EconSensitivity) => `${fmt(item.low_value, 2)}–${fmt(item.high_value, 2)} ${item.unit}`
const LEVEL_TEXT: Record<string, string> = { A: 'закон', B: 'данные', C: 'оценка', D: 'допущение' }
</script>

<template>
  <div class="risk">
    <div v-if="interval && interval.npv_low != null" class="band">
      <div class="b-copy">
        <span class="label">Интервал результата</span>
        <span class="h3">NPV от {{ signedMillions(interval.npv_low) }} до {{ signedMillions(interval.npv_high) }}</span>
        <span v-if="interval.payback_low != null && interval.payback_high != null" class="caption">окупаемость от {{ yearsText(interval.payback_low) }} до {{ yearsText(interval.payback_high) }} · центральная оценка {{ signedMillions(interval.npv) }}</span>
        <span v-if="chance" class="chance body-sm"><b>{{ Math.round(chance.npv_positive * 100) }}%</b> вероятность, что NPV ≥ 0 · P10 {{ signedMillions(chance.p10) }}, P90 {{ signedMillions(chance.p90) }}</span>
        <span class="caption">{{ interval.note }}{{ chance ? ` ${chance.note}` : '' }}</span>
      </div>
      <div class="b-scale" aria-hidden="true">
        <span class="b-zero" :style="{ left: `${pos(0)}%` }" />
        <span class="b-range" :style="{ left: `${pos(interval.npv_low)}%`, width: `${pos(interval.npv_high!) - pos(interval.npv_low)}%` }" />
        <span class="b-mid" :style="{ left: `${pos(interval.npv ?? 0)}%` }" />
      </div>
    </div>

    <section v-if="stress?.length" class="block">
      <div class="head"><div class="h3">Если пойдёт хуже</div><div class="caption">Покупка в неудачных условиях. Сдвиги взяты из источников: верх диапазона ставки Банка России, падение объёма, задержка запуска, рост цены.</div></div>
      <div class="stress">
        <div class="s-row base">
          <span class="s-label"><span class="body-sm strong">Как в расчёте</span><span class="caption">центральная оценка</span></span>
          <span class="s-track"><span class="s-zero" /><span class="s-bar" :class="(interval?.npv ?? 0) >= 0 ? 'pos' : 'neg'" :style="{ width: stressWidth(interval?.npv ?? null) }" /></span>
          <span class="s-val mono-sm">{{ signedMillions(interval?.npv ?? null) }}</span>
          <span class="s-pay caption">{{ interval?.payback != null ? yearsText(interval.payback) : 'не окупается' }}</span>
        </div>
        <div v-for="item in stress" :key="item.key" class="s-row" :class="{ all: item.key === 'all' }">
          <span class="s-label"><span class="body-sm strong">{{ item.label }}</span><span class="caption">{{ item.note }}</span></span>
          <span class="s-track"><span class="s-zero" /><span class="s-bar" :class="item.ok ? 'pos' : 'neg'" :style="{ width: stressWidth(item.npv) }" /></span>
          <span class="s-val mono-sm" :class="item.ok ? 'ok' : 'bad'">{{ signedMillions(item.npv) }}</span>
          <span class="s-pay caption">{{ item.payback != null ? `окупится за ${yearsText(item.payback)}` : 'не окупается' }}</span>
        </div>
      </div>
    </section>

    <section v-if="points.length" class="block">
      <div class="head"><div class="h3">Запас прочности</div><div class="caption">При каком значении покупка выходит в ноль по NPV. Чем дальше точка от текущего значения, тем надёжнее вывод.</div></div>
      <div class="points">
        <div v-for="p in points" :key="p.key" class="point" :class="p.tone">
          <span class="caption">{{ p.label }}</span>
          <span class="body-sm strong">{{ p.text }}</span>
          <span v-if="p.marginText" class="margin">{{ p.marginText }}</span>
        </div>
      </div>
    </section>

    <section v-if="rows.length" class="block">
      <div class="head">
        <div class="h3">Что сильнее всего двигает результат</div>
        <div class="caption">NPV покупки на границах диапазона каждого параметра. Диапазон — из источника норматива, а если его там нет, по уровню достоверности: закон ±5%, данные ±10%, оценка ±20%, допущение ±35%.</div>
      </div>
      <div class="tornado">
        <div v-for="item in shown" :key="item.key" class="t-row">
          <span class="t-label">
            <span class="body-sm strong">{{ item.label }}</span>
            <span class="caption">{{ rangeText(item) }}<template v-if="item.level"> · {{ LEVEL_TEXT[item.level] }}</template></span>
          </span>
          <span class="t-track">
            <span class="t-zero" :style="{ left: `${pos(0)}%` }" />
            <span class="t-mid" :style="{ left: `${pos(center)}%` }" />
            <span class="t-bar" :class="{ cross: Math.min(item.npv_low!, item.npv_high!) < 0 }" :style="{ left: `${pos(Math.min(item.npv_low!, item.npv_high!))}%`, width: `${Math.max(0.5, Math.abs(pos(item.npv_high!) - pos(item.npv_low!)))}%` }" />
          </span>
          <span class="t-vals mono-sm">{{ signedMillions(Math.min(item.npv_low!, item.npv_high!)) }} … {{ signedMillions(Math.max(item.npv_low!, item.npv_high!)) }}</span>
          <span class="t-share mono-sm">{{ item.share != null ? `${Math.round(item.share * 100)}%` : '' }}</span>
        </div>
      </div>
      <div class="t-foot caption">
        <span>Последняя колонка — доля параметра в разбросе результата. Сверху — то, что стоит уточнить первым.</span>
        <button v-if="rows.length > TOP" type="button" class="link" @click="showAll = !showAll">{{ showAll ? 'Свернуть' : `Ещё ${rows.length - TOP}` }}</button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.risk { display: grid; gap: var(--space-6); }
.band { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: var(--space-5); align-items: center; padding: 18px 20px; border-radius: 18px; background: rgba(240, 177, 74, 0.1); box-shadow: inset 0 0 0 1px rgba(240, 177, 74, 0.35); }
.b-copy { display: grid; gap: 4px; }
.b-scale { position: relative; height: 26px; border-radius: 13px; background: rgba(15, 20, 19, 0.06); }
.b-range { position: absolute; top: 6px; bottom: 6px; border-radius: 8px; background: linear-gradient(90deg, #f0b14a, var(--brand-500)); }
.b-mid { position: absolute; top: 2px; bottom: 2px; width: 4px; margin-left: -2px; border-radius: 2px; background: var(--ink-strong); }
.b-zero, .t-zero { position: absolute; top: -4px; bottom: -4px; width: 0; border-left: 1.5px dashed rgba(15, 20, 19, 0.45); }
.block { display: grid; gap: var(--space-4); }
.head { display: grid; gap: 4px; }
.points { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 10px; }
.point { display: grid; gap: 6px; align-content: start; padding: 14px; border-radius: 14px; background: rgba(255, 255, 255, 0.6); box-shadow: inset 3px 0 0 var(--brand-500), inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.point.warn { box-shadow: inset 3px 0 0 #f0b14a, inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.point.bad { box-shadow: inset 3px 0 0 #e57d72, inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.margin { justify-self: start; font-size: 12px; font-weight: 700; padding: 3px 8px; border-radius: 999px; background: var(--state-ok-tint); color: var(--state-ok); }
.warn .margin { background: var(--state-warn-tint); color: var(--state-warn); }
.bad .margin { background: var(--state-danger-tint); color: var(--state-danger); }
.chance b { font-family: var(--font-mono); color: var(--ink-strong); }
.stress { display: grid; gap: 4px; }
.s-row { display: grid; grid-template-columns: minmax(200px, 2fr) minmax(0, 2fr) 130px 150px; gap: 14px; align-items: center; padding: 8px 6px; border-radius: 10px; }
.s-row.base { background: rgba(255, 255, 255, 0.5); }
.s-row.all { border-top: 1px dashed rgba(15, 20, 19, 0.15); border-radius: 0 0 10px 10px; }
.s-label { display: grid; gap: 1px; min-width: 0; }
.s-track { position: relative; height: 16px; }
.s-zero { position: absolute; left: 50%; top: -4px; bottom: -4px; border-left: 1.5px dashed rgba(15, 20, 19, 0.4); }
.s-bar { position: absolute; top: 2px; bottom: 2px; border-radius: 5px; }
.s-bar.pos { left: 50%; background: var(--brand-500); }
.s-bar.neg { right: 50%; background: #e57d72; }
.s-val { text-align: right; font-weight: 700; white-space: nowrap; }
.s-val.ok { color: var(--brand-700); }
.s-val.bad { color: #c0392b; }
.s-pay { white-space: nowrap; }
.tornado { display: grid; gap: 4px; }
.t-row { display: grid; grid-template-columns: minmax(180px, 2fr) minmax(0, 3fr) 190px 44px; gap: 14px; align-items: center; padding: 6px 4px; border-radius: 10px; }
.t-row:hover { background: rgba(255, 255, 255, 0.5); }
.t-label { display: grid; gap: 1px; min-width: 0; }
.t-track { position: relative; height: 18px; }
.t-mid { position: absolute; top: -3px; bottom: -3px; width: 2px; margin-left: -1px; background: var(--ink-strong); z-index: 1; }
.t-bar { position: absolute; top: 3px; bottom: 3px; border-radius: 5px; background: var(--brand-500); opacity: 0.85; }
.t-bar.cross { background: linear-gradient(90deg, #e57d72, var(--brand-500)); }
.t-vals { color: var(--ink-muted); text-align: right; white-space: nowrap; }
.t-share { text-align: right; color: var(--ink-strong); font-weight: 700; }
.t-foot { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.link { color: var(--link); font-weight: 600; }
@media (max-width: 900px) {
  .band { grid-template-columns: 1fr; }
  .t-row { grid-template-columns: 1fr 44px; }
  .t-track { grid-column: 1 / -1; }
  .t-vals { display: none; }
  .s-row { grid-template-columns: 1fr auto; }
  .s-track { grid-column: 1 / -1; grid-row: 2; }
  .s-pay { display: none; }
}
</style>
