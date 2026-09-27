<script setup lang="ts">
import { PhArrowRight, PhArrowCounterClockwise, PhFloppyDisk } from '@phosphor-icons/vue'
import {
  figValue,
  millions,
  PARAM_GROUPS,
  PRELIMINARY,
  PROCESS_PARAM_KEYS,
  subsidyKey,
  usePlatformEconomy,
  type EconParam,
  type EconReport,
} from '~/composables/usePlatformEconomy'
import { replaceQuery } from '~/composables/useQuerySync'
import { fetchErrorMessage } from '~/utils/errors'
import { isAccent } from '~/utils/accent'

const route = useRoute()
const id = computed(() => route.params.id as string)
const { project, isDemo, readonly, report, loading, failure, pending, error, source, choices, skipped, load, request, saveOverrides } = usePlatformEconomy(id)
useHead({ title: () => `What-if · ${project.value?.name ?? 'проект'}` })

const PROCESS_KEYS = new Set<string>(PROCESS_PARAM_KEYS)
const draft = ref<Record<string, number>>({})
const processDraft = ref<Record<string, Record<string, number>>>({})
const saved = ref<Record<string, number>>({})
const standard = ref<EconReport | null>(null)
const params = ref<EconParam[]>([])
const saving = ref(false)
const savedNote = ref('')
const processCode = ref(typeof route.query.process === 'string' ? route.query.process : '')
const opened = ref<string[]>(['site:whatif', 'site:staff', 'process:whatif', 'process:capex', 'process:opex'])
let started = false
let timer: ReturnType<typeof setTimeout> | undefined

const splitOverrides = (raw: Record<string, number>) => {
  const global: Record<string, number> = {}
  const by: Record<string, Record<string, number>> = {}
  for (const [key, value] of Object.entries(raw)) {
    const parts = key.split(':')
    if (parts.length === 3 && parts[0] === 'process' && parts[1]) by[parts[1]] = { ...(by[parts[1]] ?? {}), [parts[2]!]: value }
    else global[key] = value
  }
  return { global, by }
}
const flatten = (global: Record<string, number>, by: Record<string, Record<string, number>>) => {
  const out: Record<string, number> = { ...global }
  for (const [code, bag] of Object.entries(by)) {
    for (const [key, value] of Object.entries(bag)) out[`process:${code}:${key}`] = value
  }
  return out
}

const boot = async () => {
  if (!source.value) return
  await load()
  if (!report.value) return
  const split = splitOverrides(report.value.saved_overrides)
  saved.value = flatten(split.global, split.by)
  draft.value = { ...split.global }
  processDraft.value = split.by
  params.value = report.value.params
  started = true
  applyTune()
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
const preview = computed(() => flatten(draft.value, processDraft.value))
watch(preview, (value) => {
  if (!started) return
  if (timer) clearTimeout(timer)
  timer = setTimeout(() => { void load({ ...value }) }, 250)
})
watch(report, (value) => { if (value) params.value = value.params })
watch(processCode, (value) => replaceQuery({ process: value || undefined }))

const standardOf = (item: EconParam) => standard.value?.params.find((row) => row.key === item.key)?.value ?? item.standard
const valueOf = (item: EconParam, scope: 'process' | 'site') => {
  if (scope === 'process' && processCode.value) {
    const own = processDraft.value[processCode.value]?.[item.key]
    if (own !== undefined) return own
  }
  return draft.value[item.key] ?? item.value
}
const isChanged = (item: EconParam, scope: 'process' | 'site') =>
  scope === 'process' && processCode.value
    ? processDraft.value[processCode.value]?.[item.key] !== undefined
    : draft.value[item.key] !== undefined
const setValue = (item: EconParam, raw: number, scope: 'process' | 'site') => {
  if (!Number.isFinite(raw)) return
  if (scope === 'process' && processCode.value) {
    processDraft.value = { ...processDraft.value, [processCode.value]: { ...(processDraft.value[processCode.value] ?? {}), [item.key]: raw } }
    return
  }
  draft.value = { ...draft.value, [item.key]: raw }
}
const resetOne = (item: EconParam, scope: 'process' | 'site') => {
  if (scope === 'process' && processCode.value) {
    const bag = { ...(processDraft.value[processCode.value] ?? {}) }
    delete bag[item.key]
    processDraft.value = { ...processDraft.value, [processCode.value]: bag }
    return
  }
  const next = { ...draft.value }
  delete next[item.key]
  draft.value = next
}
const resetAll = () => { draft.value = {}; processDraft.value = {} }
const changed = computed(() => Object.keys(preview.value).length)
const dirty = computed(() => JSON.stringify(sorted(preview.value)) !== JSON.stringify(sorted(saved.value)))
const sorted = (value: Record<string, number>) => Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)))

const save = async () => {
  saving.value = true
  savedNote.value = ''
  try {
    await saveOverrides({ ...preview.value })
    saved.value = { ...preview.value }
    savedNote.value = 'Сохранено для проекта'
  } catch (err: unknown) {
    savedNote.value = fetchErrorMessage(err, 'Не удалось сохранить')
  } finally {
    saving.value = false
  }
}

interface KnobGroup { id: string; label: string; scope: 'process' | 'site'; items: EconParam[]; changed: number; toggle?: string; subtitle?: string }
const bundle = (items: EconParam[], scope: 'process' | 'site'): KnobGroup[] => PARAM_GROUPS.filter((group) => group.id !== 'subsidy').map((group) => ({
  id: `${scope}:${group.id}`,
  label: group.label,
  scope,
  items: items.filter((item) => item.group === group.id),
  changed: items.filter((item) => item.group === group.id && isChanged(item, scope)).length,
})).filter((group) => group.items.length)
const subsidyOn = (code: string) => Boolean(draft.value[subsidyKey(code)])
const toggleSubsidy = (code: string) => {
  const next = { ...draft.value }
  if (next[subsidyKey(code)]) delete next[subsidyKey(code)]
  else next[subsidyKey(code)] = 1
  draft.value = next
}
const subsidyGroups = computed<KnobGroup[]>(() => (report.value?.subsidies ?? []).map((item) => {
  const items = params.value.filter((row) => item.params.includes(row.key))
  return {
    id: `sub:${item.code}`,
    label: item.label,
    subtitle: item.subtitle,
    scope: 'site',
    toggle: item.code,
    items,
    changed: items.filter((row) => isChanged(row, 'site')).length,
  }
}))
const sections = computed(() => {
  const support = { id: 'subsidy', title: 'Господдержка', note: 'Меры входят в сценарий покупки. Включите меру, чтобы настроить её ставку и лимит.', groups: subsidyGroups.value }
  if (!processCode.value) return [{ id: 'all', title: '', note: '', groups: bundle(params.value, 'site') }, support]
  const name = report.value?.processes?.find((item) => item.process_code === processCode.value)?.process_name ?? 'процесс'
  return [
    { id: 'process', title: `Параметры процесса «${name}»`, note: '', groups: bundle(params.value.filter((item) => PROCESS_KEYS.has(item.key)), 'process') },
    { id: 'site', title: 'Для всей площадки', note: '', groups: bundle(params.value.filter((item) => !PROCESS_KEYS.has(item.key)), 'site') },
    support,
  ]
})
const applyTune = () => {
  const code = typeof route.query.process === 'string' ? route.query.process : ''
  if (code && report.value?.processes?.some((item) => item.process_code === code)) processCode.value = code
  const key = typeof route.query.tune === 'string' ? route.query.tune : ''
  const value = Number(route.query.value)
  if (!processCode.value || !key || !Number.isFinite(value)) return
  if (route.query.scope === 'site') draft.value = { ...draft.value, [key]: value }
  else processDraft.value = { ...processDraft.value, [processCode.value]: { ...(processDraft.value[processCode.value] ?? {}), [key]: value } }
}
const toggleGroup = (key: string) => {
  opened.value = opened.value.includes(key) ? opened.value.filter((item) => item !== key) : [...opened.value, key]
}

const pct = (item: EconParam, scope: 'process' | 'site') => `${Math.min(100, Math.max(0, ((valueOf(item, scope) - item.min) / (item.max - item.min)) * 100))}%`
const digits = (item: EconParam) => (item.step < 1 ? (item.step < 0.1 ? 2 : 1) : 0)
const num = (value: number, d: number) => value.toLocaleString('ru-RU', { maximumFractionDigits: d, minimumFractionDigits: d })

const shownProcess = computed(() => report.value?.processes?.find((item) => item.process_code === processCode.value) ?? null)
const robotScenarios = computed(() => shownProcess.value?.scenarios?.length ? shownProcess.value.scenarios : (report.value?.scenarios ?? []))
const baseOf = (key: string) => {
  const rows = shownProcess.value
    ? standard.value?.processes?.find((item) => item.process_code === shownProcess.value?.process_code)?.scenarios
    : standard.value?.scenarios
  return rows?.find((item) => item.key === key)
}
const paybackDelta = (key: string) => {
  const now = robotScenarios.value.find((item) => item.key === key)?.payback.value
  const was = baseOf(key)?.payback.value
  if (now == null || was == null || Math.abs(now - was) < 0.05) return ''
  return `${now > was ? '+' : '−'}${num(Math.abs(now - was), 1)} года к стандарту`
}
const effectDelta = (key: string) => {
  const now = robotScenarios.value.find((item) => item.key === key)?.effect.value
  const was = baseOf(key)?.effect.value
  if (now == null || was == null || Math.abs(now - was) < 50_000) return ''
  return `${now > was ? '+' : '−'}${millions(Math.abs(now - was))} к стандарту`
}

const sens = computed(() => report.value?.sensitivity ?? [])
const sensMax = computed(() => Math.max(1, ...sens.value.map((item) => Math.abs(item.effect_high - item.effect_low))))
const purchase = computed(() => robotScenarios.value.find((item) => item.key === 'purchase'))
</script>

<template>
  <ProjectShell
    v-if="project"
    :project="project"
    current="what-if"
    title="What-if: свои допущения"
    lead="Коэффициенты всего парка и, отдельно, одного процесса. Сценарий пересчитывается сразу. После сохранения шаг «Экономика» увидит и общие значения, и настройки процесса."
  >
    <template #actions>
      <UiButton variant="secondary" :disabled="!changed" @click="resetAll"><template #icon><PhArrowCounterClockwise :size="16" weight="bold" /></template>К стандарту</UiButton>
      <UiButton v-if="!readonly" variant="secondary" :disabled="!dirty || saving" @click="save"><template #icon><PhFloppyDisk :size="16" weight="bold" /></template>{{ saving ? 'Сохраняем' : 'Сохранить для проекта' }}</UiButton>
      <UiButton :to="`/projects/${project.id}/plan`" size="lg">К визуализации<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
    </template>

    <UiCallout tone="warn" title="Предварительная оценка">{{ report?.disclaimer ?? PRELIMINARY }}</UiCallout>
    <SkippedProcesses :rows="skipped" />

    <UiCallout v-if="readonly" tone="info" title="Демо-объект · только просмотр">Коэффициенты можно двигать и смотреть результат, но в демо они не сохранятся. Чтобы вести свои допущения, скопируйте демо в свои проекты.</UiCallout>
    <UiCallout v-else-if="isDemo" tone="info" title="Демо-объект">Вы правите демо как администратор: сохранённые коэффициенты увидят все после публикации.</UiCallout>

    <section v-if="(pending || loading) && !report" class="waiting glass"><div class="h3">Считаем сценарии</div></section>
    <UiCallout v-else-if="(failure || error) && !report" tone="danger" title="Сценарии не посчитались">{{ failure || fetchErrorMessage(error, 'Сервер не ответил.') }}</UiCallout>
    <div v-else-if="report" class="wi">
      <section class="knobs glass">
        <div class="k-in">
          <div class="between">
            <div class="h3">Допущения</div>
            <span class="caption">{{ savedNote || (changed ? `своих значений: ${changed}${dirty ? ', не сохранено' : ''}` : 'все значения стандартные') }}</span>
          </div>
          <div v-if="report.processes?.length" class="proc-switch">
            <button type="button" class="ps" :class="{ on: !processCode }" @click="processCode = ''">Весь парк</button>
            <button
              v-for="item in report.processes"
              :key="item.process_code"
              type="button"
              class="ps"
              :class="{ on: processCode === item.process_code, bad: item.profitable === false }"
              @click="processCode = item.process_code"
            >
              {{ item.process_name }}
            </button>
          </div>
          <section v-for="section in sections" :key="section.id" class="section">
            <div v-if="section.title" class="h4">{{ section.title }}</div>
            <p v-if="section.note" class="caption section-note">{{ section.note }}</p>
            <div v-for="group in section.groups" :key="group.id" class="group" :class="{ sub: group.toggle, 'sub-on': group.toggle && subsidyOn(group.toggle) }">
              <div v-if="group.toggle" class="group-head sub-head">
                <button type="button" class="switch" role="switch" :aria-checked="subsidyOn(group.toggle)" :aria-label="group.label" @click="toggleSubsidy(group.toggle)"><i /></button>
                <span class="sub-name">
                  <span class="body-sm strong">{{ group.label }}</span>
                  <span class="caption">{{ group.subtitle }}</span>
                </span>
                <span class="caption">{{ subsidyOn(group.toggle) ? (group.changed ? `изменено ${group.changed}` : 'включена') : 'выключена' }}</span>
              </div>
              <button v-else type="button" class="group-head" @click="toggleGroup(group.id)">
                <span class="label">{{ group.label }}</span>
                <span class="caption">{{ group.changed ? `изменено ${group.changed}` : `${group.items.length}` }}</span>
              </button>
              <template v-if="group.toggle ? subsidyOn(group.toggle) : opened.includes(group.id)">
                <div v-for="item in group.items" :key="item.key" class="knob" :class="{ changed: isChanged(item, group.scope) }">
                  <div class="knob-head">
                    <span class="knob-name"><UiTex :tex="item.symbol" class="sym" /><span class="body-sm strong" :class="{ 'cost-accent': isAccent(item.key, item.label) }">{{ item.label }}</span></span>
                    <span class="knob-val">
                      <input class="input input-mono num" type="number" :min="item.min" :max="item.max" :step="item.step" :value="valueOf(item, group.scope)" :aria-label="item.label" @change="setValue(item, Number(($event.target as HTMLInputElement).value), group.scope)">
                      <span class="muted unit">{{ item.unit }}</span>
                    </span>
                  </div>
                  <input type="range" class="range" :min="item.min" :max="item.max" :step="item.step" :value="valueOf(item, group.scope)" :style="{ '--pct': pct(item, group.scope) }" :aria-label="item.label" @input="setValue(item, Number(($event.target as HTMLInputElement).value), group.scope)">
                  <div class="knob-foot caption">
                    <span>{{ num(item.min, digits(item)) }}</span>
                    <span v-if="isChanged(item, group.scope)" class="std">
                      стандарт {{ num(standardOf(item), digits(item)) }}
                      <button type="button" class="reset" @click="resetOne(item, group.scope)">вернуть</button>
                    </span>
                    <span v-else-if="group.scope === 'site' && item.source === 'site'">с площадки</span>
                    <span>{{ num(item.max, digits(item)) }}</span>
                  </div>
                  <p class="caption why">{{ item.rationale }}</p>
                </div>
              </template>
            </div>
          </section>
        </div>
      </section>

      <div class="out">
        <section class="res glass-graphite glass-graphite-solid">
          <div class="between">
            <span class="label">{{ shownProcess ? `Процесс «${shownProcess.process_name}»` : 'Сценарии при этих допущениях' }}</span>
            <span v-if="loading" class="caption live">пересчёт</span>
          </div>
          <p v-if="shownProcess" class="caption process-reason">{{ shownProcess.reason }}</p>
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
            <div><div class="h3">Чувствительность покупки</div><div class="caption">Весь парк: как меняются эффект в год и срок окупаемости, если параметр меньше или больше на 20%</div></div>
            <div class="sens-list">
              <div v-for="item in sens" :key="item.key" class="sens-row">
                <span class="body-sm" :class="{ 'cost-accent': isAccent(item.key, item.label) }">{{ item.label }}</span>
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
.proc-switch { display: flex; flex-wrap: wrap; gap: 6px; }
.ps { padding: 6px 10px; border-radius: 999px; background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.08); font-size: 13px; font-weight: 650; color: var(--ink-muted); }
.ps.on { color: var(--ink-strong); box-shadow: inset 0 0 0 1px var(--brand-400); background: #fff; }
.ps.bad:not(.on) { box-shadow: inset 0 0 0 1px rgba(180, 60, 40, 0.45); }
.section { display: grid; gap: 6px; }
.section .h4 { margin: 8px 0 0; }
.section-note { margin: 0 0 4px; }
.group.sub { border-radius: 14px; background: rgba(255, 255, 255, 0.45); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); padding: 2px 4px 4px; }
.group.sub-on { background: #fff; box-shadow: inset 0 0 0 1px var(--brand-400); }
.sub-head { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 12px; align-items: center; border-top: 0; padding: 10px; }
.sub-name { display: grid; gap: 1px; min-width: 0; }
.sub-name .body-sm { color: var(--ink-strong); }
.switch { position: relative; width: 38px; height: 22px; border-radius: 999px; background: rgba(15, 20, 19, 0.14); transition: background var(--dur-fast) var(--ease); }
.switch i { position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(15, 20, 19, 0.25); transition: transform var(--dur-fast) var(--ease); }
.switch[aria-checked='true'] { background: var(--brand-600); }
.switch[aria-checked='true'] i { transform: translateX(16px); }
.group { display: grid; gap: 6px; }
.process-reason { margin: 0; color: var(--ink-muted-graphite); }
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
