<script setup lang="ts">
import { PhArrowRight, PhArrowCounterClockwise, PhFloppyDisk } from '@phosphor-icons/vue'
import {
  figValue,
  millions,
  PARAM_GROUPS,
  PRELIMINARY,
  usePlatformEconomy,
  type EconParam,
  type EconReport,
} from '~/composables/usePlatformEconomy'
import { fetchErrorMessage } from '~/composables/useCalc'

const route = useRoute()
const id = computed(() => route.params.id as string)
const { project, isDemo, report, loading, failure, pending, error, source, choices, load, request, saveOverrides } = usePlatformEconomy(id)
useHead({ title: () => `What-if · ${project.value?.name ?? 'проект'}` })

const draft = ref<Record<string, number>>({})
const saved = ref<Record<string, number>>({})
const standard = ref<EconReport | null>(null)
const params = ref<EconParam[]>([])
const saving = ref(false)
const savedNote = ref('')
const opened = ref<string[]>(['whatif', 'staff'])
let started = false
let timer: ReturnType<typeof setTimeout> | undefined

const boot = async () => {
  if (!source.value) return
  await load()
  if (!report.value) return
  saved.value = { ...report.value.saved_overrides }
  draft.value = { ...report.value.saved_overrides }
  params.value = report.value.params
  started = true
  try {
    standard.value = await request({})
  } catch {
    standard.value = null
  }
}

onMounted(() => { void boot() })
watch([() => JSON.stringify(source.value ?? null), () => JSON.stringify(choices.value)], () => {
  started = false
  void boot()
})
watch(draft, (value) => {
  if (!started) return
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => { void load({ ...value }) }, 250)
}, { deep: true })
watch(report, (value) => { if (value) params.value = value.params })

const standardOf = (item: EconParam) => standard.value?.params.find((row) => row.key === item.key)?.value ?? item.standard
const valueOf = (item: EconParam) => draft.value[item.key] ?? item.value
const setValue = (item: EconParam, raw: number) => {
  if (!Number.isFinite(raw)) return
  draft.value = { ...draft.value, [item.key]: raw }
}
const resetOne = (item: EconParam) => {
  const next = { ...draft.value }
  delete next[item.key]
  draft.value = next
}
const resetAll = () => { draft.value = {} }
const changed = computed(() => Object.keys(draft.value).length)
const dirty = computed(() => JSON.stringify(sorted(draft.value)) !== JSON.stringify(sorted(saved.value)))
const sorted = (value: Record<string, number>) => Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)))

const save = async () => {
  saving.value = true
  savedNote.value = ''
  try {
    await saveOverrides({ ...draft.value })
    saved.value = { ...draft.value }
    savedNote.value = 'Сохранено для проекта'
  } catch (err: unknown) {
    savedNote.value = fetchErrorMessage(err, 'Не удалось сохранить')
  } finally {
    saving.value = false
  }
}

const groups = computed(() => PARAM_GROUPS.map((group) => ({
  ...group,
  items: params.value.filter((item) => item.group === group.id),
  changed: params.value.filter((item) => item.group === group.id && draft.value[item.key] !== undefined).length,
})).filter((group) => group.items.length))
const toggleGroup = (key: string) => {
  opened.value = opened.value.includes(key) ? opened.value.filter((item) => item !== key) : [...opened.value, key]
}

const pct = (item: EconParam) => `${Math.min(100, Math.max(0, ((valueOf(item) - item.min) / (item.max - item.min)) * 100))}%`
const digits = (item: EconParam) => (item.step < 1 ? (item.step < 0.1 ? 2 : 1) : 0)
const num = (value: number, d: number) => value.toLocaleString('ru-RU', { maximumFractionDigits: d, minimumFractionDigits: d })

const robotScenarios = computed(() => report.value?.scenarios ?? [])
const baseOf = (key: string) => standard.value?.scenarios.find((item) => item.key === key)
const paybackDelta = (key: string) => {
  const now = report.value?.scenarios.find((item) => item.key === key)?.payback.value
  const was = baseOf(key)?.payback.value
  if (now == null || was == null || Math.abs(now - was) < 0.05) return ''
  return `${now > was ? '+' : '−'}${num(Math.abs(now - was), 1)} года к стандарту`
}
const effectDelta = (key: string) => {
  const now = report.value?.scenarios.find((item) => item.key === key)?.effect.value
  const was = baseOf(key)?.effect.value
  if (now == null || was == null || Math.abs(now - was) < 50_000) return ''
  return `${now > was ? '+' : '−'}${millions(Math.abs(now - was))} к стандарту`
}

const sens = computed(() => report.value?.sensitivity ?? [])
const sensMax = computed(() => Math.max(1, ...sens.value.map((item) => Math.abs(item.effect_high - item.effect_low))))
const purchase = computed(() => report.value?.scenarios.find((item) => item.key === 'purchase'))
</script>

<template>
  <ProjectShell
    v-if="project"
    :project="project"
    current="what-if"
    title="What-if: свои допущения"
    lead="Все коэффициенты расчёта. Базовые значения — стандарт из админки. Любой можно поменять для этого проекта: сценарии пересчитываются сразу, а после сохранения значения проекта увидит и шаг «Экономика»."
  >
    <template #actions>
      <UiButton variant="secondary" :disabled="!changed" @click="resetAll"><template #icon><PhArrowCounterClockwise :size="16" weight="bold" /></template>К стандарту</UiButton>
      <UiButton variant="secondary" :disabled="!dirty || saving" @click="save"><template #icon><PhFloppyDisk :size="16" weight="bold" /></template>{{ saving ? 'Сохраняем' : 'Сохранить для проекта' }}</UiButton>
      <UiButton :to="`/projects/${project.id}/economics`" size="lg">К экономике<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
    </template>

    <UiCallout tone="warn" title="Предварительная оценка">{{ report?.disclaimer ?? PRELIMINARY }}</UiCallout>

    <UiCallout v-if="isDemo" tone="info" title="Демо-проект">Площадка из датасета объекта, коэффициенты стандартные. Изменения сохраняются только для этого демо-проекта.</UiCallout>

    <section v-if="(pending || loading) && !report" class="waiting glass"><div class="h3">Считаем сценарии</div></section>
    <UiCallout v-else-if="(failure || error) && !report" tone="danger" title="Сценарии не посчитались">{{ failure || fetchErrorMessage(error, 'Сервер не ответил.') }}</UiCallout>
    <div v-else-if="report" class="wi">
      <section class="knobs glass">
        <div class="k-in">
          <div class="between">
            <div class="h3">Допущения</div>
            <span class="caption">{{ savedNote || (changed ? `своих значений: ${changed}${dirty ? ', не сохранено' : ''}` : 'все значения стандартные') }}</span>
          </div>
          <div v-for="group in groups" :key="group.id" class="group">
            <button type="button" class="group-head" @click="toggleGroup(group.id)">
              <span class="label">{{ group.label }}</span>
              <span class="caption">{{ group.changed ? `изменено ${group.changed}` : `${group.items.length}` }}</span>
            </button>
            <template v-if="opened.includes(group.id)">
              <div v-for="item in group.items" :key="item.key" class="knob" :class="{ changed: draft[item.key] !== undefined }">
                <div class="knob-head">
                  <span class="knob-name"><UiTex :tex="item.symbol" class="sym" /><span class="body-sm strong">{{ item.label }}</span></span>
                  <span class="knob-val">
                    <input class="input input-mono num" type="number" :min="item.min" :max="item.max" :step="item.step" :value="valueOf(item)" :aria-label="item.label" @change="setValue(item, Number(($event.target as HTMLInputElement).value))">
                    <span class="muted unit">{{ item.unit }}</span>
                  </span>
                </div>
                <input type="range" class="range" :min="item.min" :max="item.max" :step="item.step" :value="valueOf(item)" :style="{ '--pct': pct(item) }" :aria-label="item.label" @input="setValue(item, Number(($event.target as HTMLInputElement).value))">
                <div class="knob-foot caption">
                  <span>{{ num(item.min, digits(item)) }}</span>
                  <span v-if="draft[item.key] !== undefined" class="std">
                    стандарт {{ num(standardOf(item), digits(item)) }}
                    <button type="button" class="reset" @click="resetOne(item)">вернуть</button>
                  </span>
                  <span v-else-if="item.source === 'site'">с площадки</span>
                  <span>{{ num(item.max, digits(item)) }}</span>
                </div>
                <p class="caption why">{{ item.rationale }}</p>
              </div>
            </template>
          </div>
        </div>
      </section>

      <div class="out">
        <section class="res glass-graphite glass-graphite-solid">
          <div class="between"><span class="label">Сценарии при этих допущениях</span><span v-if="loading" class="caption live">пересчёт</span></div>
          <div class="rows">
            <div v-for="item in robotScenarios" :key="item.key" class="srow">
              <div class="s-name"><span class="h4">{{ item.title }}</span><span class="caption">{{ item.subtitle }}</span></div>
              <div class="s-cell">
                <span class="caption">Окупаемость</span>
                <span class="mono-lg">{{ item.key === 'asis' ? '—' : item.payback.value != null ? figValue(item.payback.value, 'лет') : 'нет' }}</span>
                <span v-if="paybackDelta(item.key)" class="caption delta">{{ paybackDelta(item.key) }}</span>
              </div>
              <div class="s-cell">
                <span class="caption">Эффект в год</span>
                <span class="mono-md">{{ item.key === 'asis' ? 'база' : millions(item.effect.value) }}</span>
                <span v-if="effectDelta(item.key)" class="caption delta">{{ effectDelta(item.key) }}</span>
              </div>
              <div class="s-cell">
                <span class="caption">CAPEX</span>
                <span class="mono-md">{{ millions(item.capex.value) }}</span>
              </div>
              <div class="s-cell">
                <span class="caption">TCO за {{ report.horizon_years }} лет</span>
                <span class="mono-md">{{ millions(item.tco.value) }}</span>
              </div>
            </div>
          </div>
          <div v-if="purchase" class="interp">
            <div class="h4">{{ purchase.verdict }}</div>
            <p class="body-sm">Пороги из ТЗ: до 3 лет — целесообразно, 3–5 лет — анализ рисков, больше 5 лет — отдельное обоснование.</p>
            <p class="caption prelim">{{ report.disclaimer }}</p>
          </div>
        </section>

        <section class="sens glass">
          <div class="k-in">
            <div><div class="h3">Чувствительность покупки</div><div class="caption">Как меняется эффект в год и срок окупаемости, если параметр меньше или больше на 20%</div></div>
            <div class="sens-list">
              <div v-for="item in sens" :key="item.key" class="sens-row">
                <span class="body-sm">{{ item.label }}</span>
                <span class="sens-bar"><span :style="{ width: `${(Math.abs(item.effect_high - item.effect_low) / sensMax) * 100}%` }" /></span>
                <span class="mono-sm sens-v">
                  {{ millions(item.effect_low) }} … {{ millions(item.effect_high) }}
                  <span class="caption block">окупаемость {{ item.payback_low != null ? num(item.payback_low, 1) : 'нет' }} … {{ item.payback_high != null ? num(item.payback_high, 1) : 'нет' }}</span>
                </span>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  </ProjectShell>
  <section v-else class="container gone">
    <UiCallout tone="danger" title="Проект не найден">Нет сохранённого расчёта с таким адресом.</UiCallout>
  </section>
</template>

<style scoped>
.waiting { padding: var(--space-10); }
.waiting > * { position: relative; z-index: 1; }
.gone { padding-top: var(--space-12); }
.wi { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); gap: var(--space-4); align-items: start; }
.k-in { position: relative; z-index: 1; padding: var(--space-6); display: grid; gap: var(--space-4); }
.group { display: grid; gap: 6px; }
.group-head { display: flex; justify-content: space-between; align-items: center; padding: 8px 2px; border-top: 1px solid rgba(15, 20, 19, 0.08); text-align: left; }
.knob { display: grid; gap: 8px; padding: 12px 14px; border-radius: 12px; transition: background var(--dur-fast) var(--ease); }
.knob.changed { background: var(--surface-brand-tint); }
.knob-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.knob-name { display: inline-flex; align-items: baseline; gap: 10px; min-width: 0; }
.sym { color: var(--ink-muted); flex: none; }
.knob-val { display: inline-flex; align-items: center; gap: 8px; flex: none; }
.num { width: 96px; text-align: right; }
.unit { font-size: 12px; max-width: 120px; line-height: 1.2; }
.knob-foot { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.std { display: inline-flex; gap: 8px; align-items: center; }
.reset { color: var(--brand-700); font-weight: 700; }
.why { margin: 0; }
.out { display: grid; gap: var(--space-4); position: sticky; top: 96px; }
.res { padding: var(--space-6); display: grid; gap: var(--space-5); }
.live { color: var(--brand-300); }
.rows { display: grid; gap: 0; }
.srow { display: grid; grid-template-columns: minmax(0, 1.3fr) repeat(4, minmax(0, 1fr)); gap: 12px; align-items: start; padding: 14px 0; border-top: 1px solid rgba(255, 255, 255, 0.1); }
.srow:first-child { border-top: 0; }
.s-name, .s-cell { display: grid; gap: 3px; min-width: 0; }
.srow .caption { color: var(--ink-muted-graphite); }
.srow .mono-lg { color: var(--brand-300); font-size: 22px; }
.srow .mono-md { color: var(--ink-on-graphite); }
.srow .delta { color: #f0ad45; }
.interp { display: grid; gap: 6px; padding-top: var(--space-4); border-top: 1px solid rgba(255, 255, 255, 0.1); }
.interp .h4 { color: var(--brand-300); }
.interp p { margin: 0; }
.interp .prelim { color: #f0ad45; }
.sens-list { display: grid; gap: 12px; }
.sens-row { display: grid; grid-template-columns: 190px 1fr 220px; gap: 14px; align-items: center; }
.sens-bar { height: 8px; border-radius: 4px; background: rgba(15, 20, 19, 0.06); overflow: hidden; }
.sens-bar span { display: block; height: 100%; border-radius: 4px; background: linear-gradient(90deg, var(--brand-400), var(--brand-600)); transition: width var(--dur-mid) var(--ease); }
.sens-v { color: var(--ink-strong); text-align: right; }
.block { display: block; }
@media (max-width: 1100px) {
  .wi { grid-template-columns: 1fr; }
  .out { position: static; }
  .srow { grid-template-columns: 1fr 1fr; }
  .s-name { grid-column: 1 / -1; }
  .sens-row { grid-template-columns: 1fr; }
  .sens-v { text-align: left; }
}
</style>
