<script setup lang="ts">
import { PhArrowRight, PhCaretDown, PhPencilSimple, PhSlidersHorizontal } from '@phosphor-icons/vue'
import { photoFor } from '~/data/placeholders'
import { conditionText, millions, signedMillions, yearsText, type EconFix, type EconProcess } from '~/composables/usePlatformEconomy'

/** Процесс одной строкой с выводом; раскрывается в историю «сейчас → с роботами → итог» и настройки. */
const props = defineProps<{ process: EconProcess; busy?: boolean; open?: boolean; horizon?: number; page?: boolean; fteHours?: number; fixes?: EconFix[]; rateEditable?: boolean; tuneSummary?: string; tuneHint?: string }>()
const emit = defineEmits<{ off: [boolean]; staff: [number | null, number | null, number | null, number | null]; toggle: []; apply: []; rate: [number | null]; undo: [EconFix] }>()

const story = computed(() => props.process.story ?? null)
const tone = computed(() => props.process.off ? 'off'
  : props.process.profitable ? 'ok'
    : props.process.status === 'conditional' ? 'cond'
      : story.value?.needs_staff ? 'warn' : 'bad')
const STATUS = { ok: 'выгоден', cond: 'окупится с условием', bad: 'невыгоден', warn: 'нет данных о людях', off: 'исключён' } as const
const BADGE = { ok: 'ok', cond: 'warn', bad: 'danger', warn: 'info', off: 'neutral' } as const
const condition = computed(() => props.process.condition ? conditionText(props.process.condition) : '')

const fmt = (value: number, digits = 1) => value.toLocaleString('ru-RU', { maximumFractionDigits: digits })
const rub = (value: number) => `${Math.round(value).toLocaleString('ru-RU')} ₽`
const unit = computed(() => story.value?.unit ?? null)
const unitRub = (value: number) => `${value.toLocaleString('ru-RU', { maximumFractionDigits: value < 100 ? 1 : 0 })} ₽`
const pi = computed(() => props.process.scenarios.find((row) => row.key === 'purchase')?.pi?.value ?? null)

/* Ввод людей: открыт сам, если данных нет; иначе по карандашу. */
const editing = ref(false)
/* Два способа ответить: люди и зарплата — или все затраты на эту работу в месяц одной суммой. */
const mode = ref<'people' | 'cost'>('people')
const people = ref<number | null>(null)
const wage = ref<number | null>(null)
const cost = ref<number | null>(null)
const other = ref<number | null>(null)
const startEdit = () => {
  mode.value = story.value?.by_cost ? 'cost' : 'people'
  people.value = story.value?.by_cost ? null : story.value?.staff || null
  wage.value = story.value?.wage_month ? Math.round(story.value.wage_month) : null
  cost.value = story.value?.cost_month ? Math.round(story.value.cost_month) : null
  other.value = story.value?.other_month ? Math.round(story.value.other_month) : null
  editing.value = true
}
watch(() => props.process.process_code, () => { editing.value = false }, { immediate: true })
const showForm = computed(() => editing.value || Boolean(story.value?.needs_staff))
const canSave = computed(() => mode.value === 'cost' ? (cost.value ?? 0) > 0 : (people.value ?? 0) > 0 && (wage.value ?? 0) > 0)
const save = () => {
  if (!canSave.value) return
  if (mode.value === 'cost') emit('staff', null, null, cost.value, null)
  else emit('staff', people.value, wage.value, null, other.value || null)
  editing.value = false
}
const expanded = computed(() => props.page || props.open)
/* Настройки процесса — второй слой: сначала общая картина процесса, по кнопке — что можно поменять. */
const tuneOpen = ref(false)
watch(() => props.process.process_code, () => { tuneOpen.value = false })
/* Правки платформы на этом процессе: показываем причину и даём вернуть. */
const countFix = computed(() => props.fixes?.find((fix) => fix.kind === 'count') ?? null)
const offFix = computed(() => props.fixes?.find((fix) => fix.kind === 'off') ?? null)

/* Полоски «было / стало»: затраты в год на эту работу. */
const scale = computed(() => Math.max(1, story.value?.cost_before ?? 0, story.value?.cost_after ?? 0))
const width = (value: number) => `${Math.max(0.5, (value / scale.value) * 100)}%`
const conclusion = computed(() => {
  const s = story.value
  if (!s || props.process.off) return ''
  if (s.needs_staff) return 'Укажите, сколько людей сейчас на этой работе и сколько они получают — или сколько она стоит в месяц. Без этого роботы будут только стоить денег.'
  if (props.process.status === 'conditional' && props.process.condition) {
    const pay = props.process.condition.payback
    const now = s.saving_year <= 0 ? `роботы дороже людей на ${millions(-s.saving_year)} в год`
      : s.payback != null ? `окупается за ${yearsText(s.payback)}, но с учётом стоимости денег уходит в минус ${signedMillions(s.npv)}`
        : `экономии ${millions(s.saving_year)} в год не хватает, чтобы вернуть вложения`
    const hard = props.process.condition.hard ? ' Условие жёсткое: на такое вендор или площадка идут редко, проверьте другие варианты ниже.' : ''
    return `Окупится ${condition.value}${pay != null ? ` — за ${yearsText(pay)}` : ''}. Сейчас ${now}.${hard}`
  }
  if (s.saving_year <= 0) return `Роботы обойдутся дороже людей на ${millions(-s.saving_year)} в год.`
  if (!props.process.profitable) return `Экономия ${millions(s.saving_year)} в год не возвращает вложения ${millions(s.capex)} за горизонт с учётом стоимости денег.`
  return `Экономия ${millions(s.saving_year)} в год, вложения вернутся за ${yearsText(s.payback)}.`
})
</script>

<template>
  <article class="card glass" :class="tone">
    <header class="head">
      <button type="button" class="switch" role="switch" :aria-checked="!process.off" :aria-label="`${process.process_name} в расчёте`" :disabled="busy" @click="emit('off', !process.off)"><i /></button>
      <component :is="page ? 'div' : 'button'" :type="page ? undefined : 'button'" class="row" :class="{ static: page }" :aria-expanded="page ? undefined : open" @click="!page && emit('toggle')">
        <img :src="photoFor(process.image_url, process.robot_name, process.process_code)" :alt="process.robot_name">
        <span class="title">
          <span class="name"><span class="h4">{{ process.process_name }}</span><UiBadge :tone="BADGE[tone]" size="sm">{{ STATUS[tone] }}</UiBadge></span>
          <span class="caption">{{ process.robot_name }}{{ process.count ? ` · ${fmt(process.count, 0)} шт.` : '' }}</span>
        </span>
        <template v-if="!page">
        <span v-if="story && !story.needs_staff" class="sum-flow caption">
          <span>{{ millions(story.cost_before) }}</span><PhArrowRight :size="12" weight="bold" /><span>{{ millions(story.cost_after) }} в год</span>
        </span>
        <span v-else class="sum-flow caption" />
        <span v-if="story?.needs_staff" class="sum-val muted">
          <span class="mono-md">{{ millions(story.robots_year) }}</span>
          <span class="caption">роботы в год</span>
        </span>
        <span v-else class="sum-val">
          <span class="mono-md" :class="(story?.saving_year ?? 0) > 0 ? 'pos' : 'neg'">{{ story ? `${story.saving_year > 0 ? '+' : '−'}${millions(Math.abs(story.saving_year))}` : '—' }}</span>
          <span v-if="tone === 'cond'" class="caption cond-text">{{ condition }}<template v-if="process.condition?.hard"> · жёсткое условие</template></span>
          <span v-else class="caption">{{ story?.payback != null ? `окупится за ${yearsText(story.payback)}` : 'в год, не окупается' }}</span>
        </span>
        </template>
        <PhCaretDown v-if="!page" :size="16" weight="bold" class="caret" :class="{ up: open }" />
      </component>
    </header>

    <template v-if="expanded">
    <slot name="why" />
    <UiHint v-if="countFix">
      Платформа изменила число роботов: {{ countFix.change.replace('роботов ', '') }}. {{ countFix.reason }}
      <template #action><UiButton variant="secondary" size="sm" :disabled="busy" @click="emit('undo', countFix)">Вернуть как было</UiButton></template>
    </UiHint>
    <EconWork v-if="story?.work" :work="story.work" :by-cost="story.by_cost" :manual-note="process.release?.auto_note" :fte-hours="fteHours" :busy="busy" :editable="rateEditable" @rate="(value) => emit('rate', value)" />
    <div v-if="story" class="story">
      <!-- Сейчас -->
      <section class="col now">
        <span class="label">Сейчас, вручную</span>
        <template v-if="!showForm && story.by_cost">
          <span class="big">{{ millions((story.cost_month ?? 0) * 12) }} <small>в год</small></span>
          <span class="body-sm">{{ story.cost_month ? rub(story.cost_month) : '—' }} в месяц — все затраты на эту работу</span>
          <span class="caption">людей не считали: экономия — по доле операций, которые берут роботы</span>
          <button type="button" class="edit" @click="startEdit"><PhPencilSimple :size="13" weight="bold" /> изменить</button>
        </template>
        <template v-else-if="!showForm">
          <span class="big">{{ fmt(story.staff, 0) }} <small>чел.</small></span>
          <span class="body-sm">× {{ story.wage_month ? rub(story.wage_month) : '—' }} в месяц</span>
          <span class="sum">= {{ millions(story.payroll_now) }} в год</span>
          <span v-if="story.other_month" class="body-sm">+ техника и прочее {{ rub(story.other_month) }} в месяц</span>
          <span class="caption">с взносами 30,2%{{ story.source === 'role' ? ` · роль «${story.role}»` : '' }}{{ story.other_month ? ' · техника уходит вместе с людьми' : '' }}</span>
          <button type="button" class="edit" @click="startEdit"><PhPencilSimple :size="13" weight="bold" /> изменить</button>
        </template>
        <form v-else class="form" @submit.prevent="save">
          <span class="modes" role="radiogroup" aria-label="Как указать затраты">
            <button type="button" role="radio" :aria-checked="mode === 'people'" :class="{ on: mode === 'people' }" @click="mode = 'people'">Люди и зарплата</button>
            <button type="button" role="radio" :aria-checked="mode === 'cost'" :class="{ on: mode === 'cost' }" @click="mode = 'cost'">Затраты суммой</button>
          </span>
          <template v-if="mode === 'people'">
            <label><span class="caption">Сколько человек на этой работе сейчас</span><span class="in"><input v-model.number="people" class="input input-mono" type="number" min="0" step="1" placeholder="12"><span class="caption">чел., все смены</span></span></label>
            <label><span class="caption">Средняя зарплата одного</span><span class="in"><input v-model.number="wage" class="input input-mono" type="number" min="0" step="1000" placeholder="80 000"><span class="caption">₽ в месяц до НДФЛ</span></span></label>
            <label><span class="caption">Техника и прочее, если есть</span><span class="in"><input v-model.number="other" class="input input-mono" type="number" min="0" step="10000" placeholder="0"><span class="caption">₽ в месяц: погрузчики, топливо, аренда</span></span></label>
          </template>
          <label v-else><span class="caption">Сколько в месяц стоит эта работа сейчас</span><span class="in"><input v-model.number="cost" class="input input-mono" type="number" min="0" step="10000" placeholder="1 000 000"><span class="caption">₽ в месяц: зарплаты с взносами, подрядчик</span></span></label>
          <span class="f-actions">
            <UiButton type="submit" size="sm" :disabled="!canSave || busy">Посчитать</UiButton>
            <UiButton v-if="editing" variant="ghost" size="sm" @click="editing = false">Отмена</UiButton>
          </span>
        </form>
      </section>

      <span class="arrow" aria-hidden="true"><PhArrowRight :size="20" weight="bold" /></span>

      <!-- С роботами -->
      <section class="col robots">
        <span class="label">С роботами</span>
        <span class="big">{{ fmt(story.robots, 0) }} <small>роб.</small></span>
        <ul class="lines">
          <li><span>Вложения разово</span><b>{{ millions(story.capex) }}</b></li>
          <li v-if="!story.needs_staff"><span>{{ story.by_cost ? `Уходит ${fmt(story.released * 100, 0)}% затрат` : `Уходят ${fmt(story.released)} чел.` }}</span><b class="pos">−{{ millions(story.payroll_now - story.payroll_after) }}/год</b></li>
          <li v-if="!story.needs_staff && story.remaining > 0.05 && !story.by_cost"><span>Остаются {{ fmt(story.remaining) }} чел.</span><b>{{ millions(story.payroll_after) }}/год</b></li>
          <li v-if="!story.needs_staff && story.by_cost && story.remaining > 0.005"><span>Остаётся вручную</span><b>{{ millions(story.payroll_after) }}/год</b></li>
          <li><span>Роботы в год<template v-if="story.dispatchers"> · {{ fmt(story.dispatchers) }} дисп.</template></span><b class="neg">+{{ millions(story.robots_year) }}/год</b></li>
        </ul>
      </section>

      <span class="arrow" aria-hidden="true"><PhArrowRight :size="20" weight="bold" /></span>

      <!-- Итог -->
      <section class="col result">
        <span class="label">Итог</span>
        <span class="big" :class="story.saving_year > 0 ? 'pos' : 'neg'">{{ story.saving_year > 0 ? '+' : '−' }}{{ millions(Math.abs(story.saving_year)) }}<small> в год</small></span>
        <span class="body-sm">{{ story.payback != null ? `окупится за ${yearsText(story.payback)}` : 'не окупается' }}</span>
        <span class="caption">NPV {{ signedMillions(story.npv) }}{{ pi != null ? ` · PI ${fmt(pi, 2)}` : '' }}{{ story.total != null ? ` · за ${yearsText(horizon ?? 5)} ${signedMillions(story.total)}` : '' }}</span>
      </section>
    </div>

    <div v-if="story && !story.needs_staff" class="bars">
      <template v-if="!page">
      <div class="bar-row"><span class="caption">Затраты в год: было</span><span class="track"><i class="before" :style="{ width: width(story.cost_before) }" /></span><span class="mono-sm">{{ millions(story.cost_before) }}</span></div>
      <div class="bar-row">
        <span class="caption">стало</span>
        <span class="track">
          <i class="people" :style="{ width: width(story.payroll_after) }" /><i class="bots" :style="{ width: width(story.robots_year) }" />
        </span>
        <span class="mono-sm">{{ millions(story.cost_after) }}</span>
      </div>
      <span class="legend caption"><i class="sw people" />оставшиеся люди <i class="sw bots" />роботы: сервис, энергия, диспетчеры</span>
      </template>
      <div v-if="unit" class="unit" :class="{ flat: page }">
        <span class="body-sm">Одна {{ unit.label }}: <b class="mono-md">{{ unitRub(unit.before) }}</b> вручную → <b class="mono-md" :class="unit.after < unit.before ? 'pos' : 'neg'">{{ unitRub(unit.after) }}</b> с роботами</span>
        <span class="caption" :title="unit.note">с учётом вложений · {{ fmt(unit.volume_year / 1000, 0) }} тыс. в год</span>
      </div>
    </div>

    <UiHint v-if="conclusion && (story?.needs_staff || tone === 'cond')">
      {{ conclusion }}
      <template v-if="tone === 'cond' && process.condition?.scope !== 'site'" #action><UiButton size="sm" :disabled="busy" @click="emit('apply')">Применить условие</UiButton></template>
    </UiHint>
    <p v-else-if="conclusion && !page" class="conclusion body-sm">
      <span>{{ conclusion }}</span>
    </p>
    <p v-if="story?.shared_with.length && !process.off" class="caption shared">Те же люди работают на процессах: {{ story.shared_with.join(', ') }}. Если роботизировать их вместе, люди уйдут один раз.</p>
    <UiHint v-if="process.off">
      {{ offFix ? `Платформа убрала процесс из итога объекта: ${offFix.reason.charAt(0).toLowerCase()}${offFix.reason.slice(1)}` : 'Вы исключили процесс из итога объекта.' }} Цифры выше — если его вернуть.
      <template #action><UiButton variant="secondary" size="sm" :disabled="busy" @click="offFix ? emit('undo', offFix) : emit('off', false)">Вернуть в итог</UiButton></template>
    </UiHint>
    <p v-if="!story" class="caption shared">{{ process.reason }}</p>
    <template v-if="page && $slots.default">
      <UiHint v-if="tuneHint && !tuneOpen">
        {{ tuneHint }}
        <template #action><UiButton size="sm" @click="tuneOpen = true">Указать</UiButton></template>
      </UiHint>
      <section class="tune-box" :class="{ open: tuneOpen }">
        <button type="button" class="tune-head" :aria-expanded="tuneOpen" @click="tuneOpen = !tuneOpen">
          <PhSlidersHorizontal :size="18" weight="bold" class="t-ic" />
          <span class="t-copy"><span class="h4">Настроить процесс</span><span v-if="tuneSummary" class="caption">{{ tuneSummary }}</span></span>
          <span class="t-go">{{ tuneOpen ? 'Свернуть' : 'Открыть' }}<PhCaretDown :size="12" weight="bold" class="caret" :class="{ up: tuneOpen }" /></span>
        </button>
        <div v-if="tuneOpen" class="tune-body"><slot /></div>
      </section>
    </template>
    <slot v-else />
    </template>
  </article>
</template>

<style scoped>
.card { border-radius: var(--radius-lg); padding: 10px 14px; display: grid; gap: var(--space-4); box-shadow: inset 4px 0 0 var(--tone); }
.card:has(.row[aria-expanded='true']), .card:has(.row.static) { padding: 14px 18px 20px; }
.card > * { position: relative; z-index: 1; }
.card.ok { --tone: var(--brand-500); }
.card.bad { --tone: #e5584b; }
.card.cond { --tone: #f0b14a; }
.card.warn { --tone: #6ea8ff; }
.card.off { --tone: rgba(15, 20, 19, 0.2); }
/* Исключённый процесс: деньги приглушены, а ввод людей и выработки — нет, его как раз и нужно заполнить. */
.card.off .story .col:not(.now), .card.off .bars, .card.off .story .arrow { opacity: 0.5; }
.head { display: grid; grid-template-columns: 38px minmax(0, 1fr); gap: 12px; align-items: center; }
.row { display: grid; grid-template-columns: 48px minmax(0, 1fr) minmax(150px, auto) 230px 16px; gap: 14px; align-items: center; text-align: left; padding: 4px; border-radius: 12px; }
.row:hover { background: rgba(255, 255, 255, 0.5); }
.row.static { grid-template-columns: 48px minmax(0, 1fr); }
.row.static:hover { background: none; }
.modes { display: inline-flex; justify-self: start; padding: 3px; border-radius: 999px; background: rgba(15, 20, 19, 0.06); }
.modes button { height: 28px; padding: 0 12px; border-radius: 999px; font-size: 13px; font-weight: 700; color: var(--ink-muted); }
.modes button.on { background: #fff; color: var(--brand-700); box-shadow: 0 1px 3px rgba(15, 20, 19, 0.15); }
.row img { width: 48px; height: 38px; object-fit: contain; border-radius: 8px; background: #e9eeec; }
.title { display: grid; gap: 1px; min-width: 0; }
.name { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; }
.name .h4 { margin: 0; }
.off .name .h4 { text-decoration: line-through; text-decoration-color: rgba(15, 20, 19, 0.3); color: var(--ink-muted); }
.sum-flow { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; font-family: var(--font-mono); }
.sum-val { display: grid; justify-items: end; gap: 1px; }
.sum-val .mono-md { font-weight: 700; }
.sum-val .pos { color: var(--brand-700); }
.sum-val .neg { color: #c0392b; }
.sum-val.muted .mono-md { color: var(--ink-muted); font-weight: 600; }
.off .sum-val, .off .sum-flow { opacity: 0.5; }
.caret { color: var(--ink-faint); transition: transform var(--dur-fast) var(--ease); }
.caret.up { transform: rotate(180deg); }
.switch { position: relative; width: 38px; height: 22px; border-radius: 999px; background: rgba(15, 20, 19, 0.14); transition: background var(--dur-fast) var(--ease); }
.switch i { position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(15, 20, 19, 0.25); transition: transform var(--dur-fast) var(--ease); }
.switch[aria-checked='true'] { background: var(--brand-600); }
.switch[aria-checked='true'] i { transform: translateX(16px); }
.story { display: grid; grid-template-columns: minmax(0, 1fr) 24px minmax(0, 1.15fr) 24px minmax(0, 1fr); gap: 12px; align-items: stretch; }
.col { display: grid; gap: 4px; align-content: start; padding: 14px 16px; border-radius: 16px; background: rgba(255, 255, 255, 0.65); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.col .label { color: var(--ink-muted); margin-bottom: 2px; }
.result { background: var(--surface-graphite); }
.result .label, .result .caption, .result .body-sm { color: var(--ink-muted-graphite); }
.big { font-family: var(--font-mono); font-weight: 700; font-size: clamp(22px, 1.8vw, 28px); line-height: 1.1; color: var(--ink-strong); font-variant-numeric: tabular-nums; }
.big small { font-size: 0.5em; font-weight: 600; opacity: 0.7; }
.result .big { color: #fff; }
.result .big.pos { color: var(--brand-300); }
.result .big.neg { color: #ff8a80; }
.sum { font-family: var(--font-mono); font-weight: 700; color: var(--ink-strong); }
.arrow { align-self: center; color: var(--ink-faint); }
.unit { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 4px 12px; margin-top: 6px; padding-top: 10px; border-top: 1px dashed rgba(15, 20, 19, 0.1); }
.unit .pos { color: var(--brand-700); }
.unit .neg { color: #c0392b; }
.unit.flat { margin-top: 0; padding-top: 0; border-top: 0; }
.tune-box { border-radius: 14px; box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.1); background: rgba(255, 255, 255, 0.5); }
.tune-box.open { background: #fff; }
.tune-head { width: 100%; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 12px; padding: 12px 16px; text-align: left; }
.tune-head:hover .h4 { color: var(--link); }
.t-ic { color: var(--brand-700); }
.t-copy { display: grid; gap: 2px; min-width: 0; }
.t-copy .h4 { margin: 0; }
.t-go { display: inline-flex; align-items: center; gap: 4px; font-size: 13px; font-weight: 700; color: var(--link); }
.tune-body { padding: 0 16px 16px; }
.tune-body :deep(.tune) { border-top: 0; padding-top: 0; }
.edit { justify-self: start; display: inline-flex; align-items: center; gap: 4px; margin-top: 4px; font-size: 12px; font-weight: 700; color: var(--link); }
.form { display: grid; gap: 8px; }
.form label { display: grid; gap: 3px; }
.in { display: grid; grid-template-columns: minmax(0, 110px) auto; gap: 8px; align-items: center; }
.in .input { height: 36px; padding: 6px 10px; }
.f-actions { display: flex; gap: 6px; }
.lines { list-style: none; margin: 4px 0 0; padding: 0; display: grid; gap: 4px; }
.lines li { display: flex; justify-content: space-between; gap: 10px; font-size: 13px; color: var(--ink-body); }
.lines b { font-family: var(--font-mono); font-weight: 700; white-space: nowrap; color: var(--ink-strong); }
.lines b.pos { color: var(--brand-700); }
.lines b.neg { color: #b4473d; }
.bars { display: grid; gap: 6px; }
.bar-row { display: grid; grid-template-columns: 150px minmax(0, 1fr) 100px; gap: 12px; align-items: center; }
.bar-row .caption { text-align: right; }
.bar-row .mono-sm { text-align: right; font-weight: 700; color: var(--ink-strong); }
.track { display: flex; height: 16px; border-radius: 8px; background: rgba(15, 20, 19, 0.05); overflow: hidden; }
.track i { display: block; height: 100%; }
.track .before { background: #8a9692; border-radius: 8px; }
.track .people { background: #b8c2be; }
.track .bots { background: var(--tone); }
.legend { display: flex; flex-wrap: wrap; gap: 4px 12px; align-items: center; padding-left: 162px; }
.sw { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 4px; vertical-align: -1px; }
.sw.people { background: #b8c2be; }
.sw.bots { background: var(--tone); }
.cond-text { color: #9a5b00; font-weight: 700; text-align: right; max-width: 220px; }
.conclusion :deep(.btn) { margin-left: auto; flex: none; }
.conclusion { display: flex; align-items: center; gap: 8px; margin: 0; padding: 10px 14px; border-radius: 12px; background: color-mix(in srgb, var(--tone) 12%, white); color: var(--ink-strong); font-weight: 600; }
.shared { margin: 0; }
@media (max-width: 1100px) {
  .story { grid-template-columns: 1fr; }
  .arrow { transform: rotate(90deg); justify-self: center; }
  .bar-row { grid-template-columns: 90px minmax(0, 1fr) 80px; }
  .legend { padding-left: 0; }
  .row { grid-template-columns: 40px minmax(0, 1fr) 16px; }
  .sum-flow { display: none; }
  .sum-val { grid-column: 2; justify-items: start; }
}
</style>
