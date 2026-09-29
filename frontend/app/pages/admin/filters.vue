<script setup lang="ts">
import { PhCheckSquare, PhSquare } from '@phosphor-icons/vue'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { fetchErrorMessage } from '~/utils/errors'

definePageMeta({ layout: 'admin', middleware: 'admin', pageTransition: false })
useHead({ title: 'Общие фильтры' })

interface Readiness { enabled: boolean; min_trl: number; review_stages: string[]; review_missing_trl: boolean }
interface FiltersPayload {
  readiness: Readiness
  stages: { code: string; label: string }[]
  products: { trl: number | null; stage: string | null; count: number }[]
}

const DEFAULTS: Readiness = { enabled: true, min_trl: 6, review_stages: ['rnd'], review_missing_trl: false }
const TRL_STEPS = [
  { from: 1, to: 3, text: 'исследование и концепция' },
  { from: 4, to: 6, text: 'макет и прототип в условиях, близких к реальным' },
  { from: 7, to: 9, text: 'система работает в реальной эксплуатации' },
]

const data = ref<FiltersPayload | null>(null)
const form = reactive<Readiness>({ ...DEFAULTS })
const saved = ref<Readiness>({ ...DEFAULTS })
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const notice = ref('')

const apply = (payload: FiltersPayload) => {
  data.value = payload
  saved.value = { ...payload.readiness, review_stages: [...payload.readiness.review_stages] }
  Object.assign(form, { ...payload.readiness, review_stages: [...payload.readiness.review_stages] })
}

onMounted(async () => {
  try {
    apply(await platformGet<FiltersPayload>('/admin/match-filters'))
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Не удалось загрузить общие фильтры')
  } finally {
    loading.value = false
  }
})

const same = (a: Readiness, b: Readiness) => a.enabled === b.enabled && a.min_trl === b.min_trl && a.review_missing_trl === b.review_missing_trl
  && [...a.review_stages].sort().join() === [...b.review_stages].sort().join()
const dirty = computed(() => !same(form, saved.value))
const isDefault = computed(() => same(form, DEFAULTS))

const toggleStage = (code: string) => {
  form.review_stages = form.review_stages.includes(code) ? form.review_stages.filter((item) => item !== code) : [...form.review_stages, code]
}
/* Та же логика, что в подборе на сервере: робот уходит в «Уточнить», если сработал хотя бы один признак. */
const impact = computed(() => {
  const rows = data.value?.products ?? []
  let total = 0
  let flagged = 0
  let lowTrl = 0
  let byStage = 0
  let noTrl = 0
  for (const row of rows) {
    total += row.count
    if (!form.enabled) continue
    const low = row.trl != null && form.min_trl > 0 && row.trl < form.min_trl
    const stage = row.stage != null && form.review_stages.includes(row.stage)
    const missing = row.trl == null && form.review_missing_trl
    if (low) lowTrl += row.count
    if (stage) byStage += row.count
    if (missing) noTrl += row.count
    if (low || stage || missing) flagged += row.count
  }
  return { total, flagged, lowTrl, byStage, noTrl }
})
const trlCounts = computed(() => {
  const counts = new Map<number | null, number>()
  for (const row of data.value?.products ?? []) counts.set(row.trl, (counts.get(row.trl) ?? 0) + row.count)
  return counts
})
const stageCounts = computed(() => {
  const counts = new Map<string | null, number>()
  for (const row of data.value?.products ?? []) counts.set(row.stage, (counts.get(row.stage) ?? 0) + row.count)
  return counts
})

const save = async () => {
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    apply(await platformSend<FiltersPayload>('/admin/match-filters', 'PUT', { readiness: { ...form } }))
    notice.value = 'Сохранено. Новый подбор в проектах и предпросмотр процессов уже считаются по этим правилам.'
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Не удалось сохранить фильтр')
  } finally {
    saving.value = false
  }
}
const reset = () => Object.assign(form, { ...DEFAULTS, review_stages: [...DEFAULTS.review_stages] })
const revert = () => Object.assign(form, { ...saved.value, review_stages: [...saved.value.review_stages] })
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Модель подбора" title="Общие фильтры" lead="Правила для подбора всех процессов и объектов сразу, поверх условий конкретного процесса. Такой фильтр не исключает робота, а переносит его во вкладку «Уточнить» с пояснением: пользователь видит причину и может добавить робота в сравнение вручную." />

    <UiCallout v-if="error" tone="danger">{{ error }}</UiCallout>
    <UiCallout v-if="notice" tone="ok">{{ notice }}</UiCallout>

    <section v-if="loading" class="glass glass-xl card"><div class="in"><UiSkeleton h="280px" /></div></section>

    <section v-else-if="data" class="glass glass-xl card">
      <div class="in">
        <div class="head">
          <div>
            <div class="h3">Готовность робота</div>
            <p class="caption">Незрелые решения не попадают в «Подходит» и не выбираются оптимальными по умолчанию. УГТ и стадия эксплуатации берутся из карточки робота.</p>
          </div>
          <button type="button" class="check" :class="{ on: form.enabled }" :aria-pressed="form.enabled" @click="form.enabled = !form.enabled">
            <PhCheckSquare v-if="form.enabled" :size="18" weight="fill" /><PhSquare v-else :size="18" />
            <span class="body-sm strong">{{ form.enabled ? 'Фильтр включён' : 'Фильтр выключен' }}</span>
          </button>
        </div>

        <div class="block" :class="{ off: !form.enabled }">
          <div class="block-head">
            <span class="body-sm strong">Минимальный УГТ</span>
            <span class="caption">Роботы с УГТ ниже порога уходят в «Уточнить». Числа на кнопках — сколько роботов с таким УГТ назначено на процессы.</span>
          </div>
          <div class="trl">
            <button type="button" class="trl-btn" :class="{ on: form.min_trl === 0 }" :disabled="!form.enabled" @click="form.min_trl = 0">
              <span class="body-sm strong">не проверять</span>
            </button>
            <button
              v-for="n in 9"
              :key="n"
              type="button"
              class="trl-btn"
              :class="{ on: form.min_trl === n, below: form.min_trl > 0 && n < form.min_trl }"
              :disabled="!form.enabled"
              :title="`Порог УГТ ${n}: в «Уточнить» уйдут роботы с УГТ ${n > 1 ? `1–${n - 1}` : 'ниже 1'}`"
              @click="form.min_trl = n"
            >
              <span class="mono-md">{{ n }}</span>
              <span class="caption">{{ trlCounts.get(n) ?? 0 }}</span>
            </button>
          </div>
          <ul class="scale caption">
            <li v-for="step in TRL_STEPS" :key="step.from"><b>{{ step.from }}–{{ step.to }}</b> {{ step.text }}</li>
          </ul>
        </div>

        <div class="block" :class="{ off: !form.enabled }">
          <div class="block-head">
            <span class="body-sm strong">Стадии, которые нужно уточнить</span>
            <span class="caption">Робот на отмеченной стадии уходит в «Уточнить», даже если УГТ проходит порог.</span>
          </div>
          <div class="stages">
            <button v-for="stage in data.stages" :key="stage.code" type="button" class="check" :class="{ on: form.review_stages.includes(stage.code) }" :disabled="!form.enabled" @click="toggleStage(stage.code)">
              <PhCheckSquare v-if="form.review_stages.includes(stage.code)" :size="18" weight="fill" /><PhSquare v-else :size="18" />
              <span class="body-sm">{{ stage.label }}</span>
              <span class="caption">{{ stageCounts.get(stage.code) ?? 0 }}</span>
            </button>
          </div>
        </div>

        <div class="block" :class="{ off: !form.enabled }">
          <button type="button" class="check" :class="{ on: form.review_missing_trl }" :disabled="!form.enabled" @click="form.review_missing_trl = !form.review_missing_trl">
            <PhCheckSquare v-if="form.review_missing_trl" :size="18" weight="fill" /><PhSquare v-else :size="18" />
            <span class="body-sm">Робот без УГТ в карточке — тоже в «Уточнить»</span>
            <span class="caption">{{ trlCounts.get(null) ?? 0 }} без УГТ</span>
          </button>
          <p class="caption">По умолчанию выключено: у большей части каталога УГТ не заполнен, и вкладка «Подходит» опустела бы.</p>
        </div>

        <div class="impact">
          <div>
            <div class="label">Эффект правила</div>
            <div class="h3">{{ impact.flagged }} из {{ impact.total }} роботов уйдут в «Уточнить»</div>
            <p class="caption">
              <template v-if="!form.enabled">Фильтр выключен: вердикты считают только условия процессов.</template>
              <template v-else>УГТ ниже порога: {{ impact.lowTrl }} · по стадии: {{ impact.byStage }}<template v-if="form.review_missing_trl"> · без УГТ: {{ impact.noTrl }}</template>. Один робот может попасть сразу под несколько признаков. Считаются роботы, назначенные хотя бы на один процесс.</template>
            </p>
            <p v-if="stageCounts.get(null)" class="caption">У {{ stageCounts.get(null) }} роботов стадия эксплуатации не указана: по стадии они не проверяются.</p>
          </div>
          <div class="actions">
            <UiButton v-if="dirty" variant="ghost" size="sm" @click="revert">Отменить</UiButton>
            <UiButton v-if="!isDefault" variant="secondary" size="sm" @click="reset">По умолчанию</UiButton>
            <UiButton size="sm" :disabled="!dirty || saving" @click="save">{{ saving ? 'Сохраняем…' : 'Сохранить' }}</UiButton>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.card { overflow: hidden; }
.in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: var(--space-5); }
.head { display: flex; gap: var(--space-4); align-items: flex-start; justify-content: space-between; flex-wrap: wrap; }
.head > div { max-width: 70ch; display: grid; gap: 4px; }
.head p { margin: 0; }
.block { display: grid; gap: 10px; padding-top: var(--space-4); border-top: 1px solid var(--border-hairline); transition: opacity var(--dur-fast) var(--ease); }
.block.off { opacity: 0.5; }
.block p { margin: 0; }
.block-head { display: grid; gap: 2px; }
.check { display: inline-flex; align-items: center; gap: 10px; min-height: 36px; padding: 0 8px; border-radius: 8px; text-align: left; color: var(--ink-body); justify-self: start; }
.check:hover:not(:disabled) { background: rgba(15, 20, 19, 0.05); }
.check:disabled { cursor: not-allowed; }
.check svg { color: var(--ink-faint); flex: none; }
.check.on svg { color: var(--brand-600); }
.trl { display: flex; flex-wrap: wrap; gap: 6px; }
.trl-btn { display: grid; justify-items: center; gap: 2px; min-width: 52px; min-height: 52px; padding: 6px 10px; border-radius: 12px; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px var(--border-hairline); transition: background var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease); }
.trl-btn:hover:not(:disabled) { background: #fff; }
.trl-btn:disabled { cursor: not-allowed; }
.trl-btn.below { background: var(--state-warn-tint); box-shadow: inset 0 0 0 1px rgba(176, 106, 0, 0.18); }
.trl-btn.on { background: var(--surface-graphite); color: var(--ink-on-graphite); box-shadow: none; }
.trl-btn.on .caption { color: var(--ink-muted-graphite); }
.scale { display: flex; flex-wrap: wrap; gap: 4px 18px; margin: 0; padding: 0; list-style: none; }
.scale b { color: var(--ink-strong); font-family: var(--font-mono); margin-right: 4px; }
.stages { display: flex; flex-wrap: wrap; gap: 4px 12px; }
.impact { display: flex; justify-content: space-between; align-items: flex-end; gap: var(--space-4); flex-wrap: wrap; padding: var(--space-4); border-radius: var(--radius-lg); background: var(--surface-brand-tint); }
.impact > div:first-child { display: grid; gap: 4px; max-width: 70ch; }
.impact p { margin: 0; }
.actions { display: flex; gap: 8px; }
</style>
