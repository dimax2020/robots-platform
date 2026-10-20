<script setup lang="ts">
import { yearsText, type EconBreakeven, type EconChance, type EconFig, type EconInterval, type EconScenario, type EconSensitivity } from '~/composables/usePlatformEconomy'

/** Показатели для экономиста: плотная сетка метрик покупки, у каждой — формула с подстановкой по клику. */
const props = defineProps<{
  buy: EconScenario
  asis: EconScenario | null
  discount?: EconFig | null
  chance?: EconChance | null
  interval?: EconInterval | null
  breakeven: EconBreakeven[]
  sensitivity: EconSensitivity[]
  horizon: number
}>()

const fmt = (value: number | null | undefined, digits = 1) => value == null ? '—' : value.toLocaleString('ru-RU', { maximumFractionDigits: digits })
/* Компактно, чтобы сумма помещалась в плитку: миллиарды — «млрд», сотни миллионов — без дробной части. */
const money = (value: number | null | undefined, signed = false) => {
  if (value == null) return '—'
  const abs = Math.abs(value)
  const sign = value < 0 ? '−' : signed && value > 0 ? '+' : ''
  if (abs >= 1e9) return `${sign}${(abs / 1e9).toLocaleString('ru-RU', { maximumFractionDigits: 2 })} млрд ₽`
  return `${sign}${(abs / 1e6).toLocaleString('ru-RU', { maximumFractionDigits: abs >= 1e8 ? 0 : 1 })} млн ₽`
}
const rate = computed(() => props.discount?.value ?? null)

/* Запас прочности по цене парка: насколько может подорожать, прежде чем NPV уйдёт в ноль. */
const priceMargin = computed(() => props.breakeven.find((item) => item.key === 'price_factor') ?? null)
/* Доля разброса результата, которая держится на допущениях команды (уровень D). */
const assumed = computed(() => props.sensitivity.filter((item) => item.level === 'D').reduce((sum, item) => sum + (item.share ?? 0), 0))

interface Metric { key: string; label: string; value: string; hint: string; tone?: 'good' | 'bad'; fig?: EconFig | null; text?: string }
const metrics = computed<Metric[]>(() => {
  const b = props.buy
  const npv = b.npv?.value ?? null
  const irr = b.irr?.value ?? null
  const pi = b.pi?.value ?? null
  const eacBuy = b.eac?.value ?? null
  const eacNow = props.asis?.eac?.value ?? null
  const margin = priceMargin.value
  const out: Metric[] = [
    { key: 'npv', label: 'NPV', value: money(npv, true), hint: `за ${props.horizon} лет, ставка ${fmt(rate.value)}%`, tone: (npv ?? 0) >= 0 ? 'good' : 'bad', fig: b.npv },
    { key: 'irr', label: 'IRR', value: irr != null ? `${fmt(irr)}%` : 'нет', hint: rate.value != null ? `против ставки ${fmt(rate.value)}%` : 'внутренняя доходность', tone: irr != null && rate.value != null && irr >= rate.value ? 'good' : 'bad', fig: b.irr },
    { key: 'pi', label: 'PI', value: fmt(pi, 2), hint: 'приведённый ₽ на ₽ вложений', tone: (pi ?? 0) >= 1 ? 'good' : 'bad', fig: b.pi },
    { key: 'payback', label: 'PBP / DPP', value: `${b.payback.value != null ? fmt(b.payback.value) : '—'} / ${b.dpp?.value != null ? fmt(b.dpp.value) : '—'}`, hint: 'лет: простая / дисконтированная', fig: b.dpp ?? b.payback },
    { key: 'roi', label: 'Чистый ROI', value: b.roi.value != null ? `${fmt(b.roi.value, 0)}%` : '—', hint: `за ${props.horizon} лет после возврата CAPEX`, tone: (b.roi.value ?? 0) >= 0 ? 'good' : 'bad', fig: b.roi },
    { key: 'eac', label: 'EAC', value: money(eacBuy), hint: eacNow != null ? `в год против ${money(eacNow)} вручную` : 'в год с учётом вложений', tone: eacBuy != null && eacNow != null && eacBuy <= eacNow ? 'good' : 'bad', fig: b.eac },
    { key: 'tco', label: `TCO ${props.horizon} лет`, value: money(b.tco.value), hint: props.asis ? `вручную ${money(props.asis.tco.value)}` : 'без налогов и дисконта', fig: b.tco },
    { key: 'rate', label: 'Ставка r', value: rate.value != null ? `${fmt(rate.value)}%` : '—', hint: 'реальная: ключевая ЦБ за вычетом цели по инфляции', fig: props.discount },
  ]
  if (props.interval?.npv_low != null && props.interval.npv_high != null) {
    out.push({ key: 'interval', label: 'Интервал NPV, от', value: money(props.interval.npv_low, true), hint: `до ${money(props.interval.npv_high, true)} · по диапазонам параметров`, text: props.interval.note })
  }
  if (props.chance) {
    out.push({ key: 'chance', label: 'P(NPV ≥ 0)', value: `${Math.round(props.chance.npv_positive * 100)}%`, hint: `P10…P90: ${money(props.chance.p10, true)} … ${money(props.chance.p90, true)}`, tone: props.chance.npv_positive >= 0.8 ? 'good' : props.chance.npv_positive < 0.5 ? 'bad' : undefined, text: props.chance.note })
  }
  if (margin) {
    const value = margin.value == null ? (margin.reachable ? 'весь диапазон' : 'нет') : `${margin.margin_pct != null && margin.margin_pct >= 0 ? '+' : ''}${fmt(margin.margin_pct, 0)}%`
    out.push({ key: 'margin', label: 'Запас по цене', value, hint: margin.value != null ? `NPV = 0 при цене ${fmt(margin.value, 0)}% карточки` : 'точки безубыточности нет', tone: (margin.margin_pct ?? (margin.reachable ? 1 : -1)) >= 0 ? 'good' : 'bad', text: 'Насколько может подорожать парк, прежде чем NPV покупки станет нулевым. Остальные точки — во вкладке «Надёжность».' })
  }
  out.push({ key: 'assumed', label: 'На допущениях', value: `${Math.round(assumed.value * 100)}%`, hint: 'разброса NPV от допущений уровня D', tone: assumed.value > 0.5 ? 'bad' : undefined, text: 'Доля квадрата разброса NPV из торнадо, которую дают параметры без данных и источника (уровень D). Каждое такое допущение — в запросах вендору или заказчику.' })
  return out
})

const open = ref('')
const opened = computed(() => metrics.value.find((item) => item.key === open.value) ?? null)
</script>

<template>
  <div class="metrics">
    <div class="grid">
      <button v-for="item in metrics" :key="item.key" type="button" class="m" :class="[item.tone, { on: open === item.key }]" :aria-expanded="open === item.key" @click="open = open === item.key ? '' : item.key">
        <span class="m-label">{{ item.label }}</span>
        <span class="m-val">{{ item.value }}</span>
        <span class="m-hint">{{ item.hint }}</span>
      </button>
    </div>
    <EconFormula v-if="opened?.fig" :fig="opened.fig" />
    <p v-else-if="opened?.text" class="caption note">{{ opened.text }}</p>
    <p class="caption foot">Покупка за свои средства, без НДС, после налога на прибыль, в постоянных ценах. Нажмите на показатель — откроется формула с подстановкой.<template v-if="buy.payback.value != null"> Окупаемость {{ yearsText(buy.payback.value) }}.</template></p>
  </div>
</template>

<style scoped>
.metrics { display: grid; gap: 10px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; }
.m { display: grid; gap: 2px; align-content: start; text-align: left; padding: 10px 12px; border-radius: 12px; background: #fff; box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.08); transition: box-shadow var(--dur-fast) var(--ease); }
.m:hover, .m.on { box-shadow: inset 0 0 0 1.5px var(--brand-400); }
.m-label { font-size: 12px; font-weight: 700; color: var(--ink-muted); letter-spacing: 0.01em; }
.m-val { font-family: var(--font-mono); font-weight: 700; font-size: 17px; line-height: 1.25; color: var(--ink-strong); font-variant-numeric: tabular-nums; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.m.good .m-val { color: var(--brand-700); }
.m.bad .m-val { color: #c0392b; }
.m-hint { font-size: 11.5px; line-height: 1.3; color: var(--ink-muted); }
.note, .foot { margin: 0; }
.foot { color: var(--ink-faint); }
</style>
