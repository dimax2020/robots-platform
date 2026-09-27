<script setup lang="ts">
import { PhFloppyDisk, PhClockCounterClockwise, PhArrowCounterClockwise } from '@phosphor-icons/vue'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { fetchErrorMessage } from '~/utils/errors'
import { PARAM_GROUPS } from '~/composables/usePlatformEconomy'

definePageMeta({ layout: 'admin', middleware: 'admin', pageTransition: false })
useHead({ title: 'Админка · Нормативы экономики' })

interface NormItem {
  key: string
  group: string
  label: string
  symbol: string
  unit: string
  value: number
  default: number
  rationale: string
  origin: string
  url: string
  default_rationale: string
  default_origin: string
  site_key: string
  projects_custom: number
  projects_total: number
  min: number
  max: number
  step: number
  updated_at: string | null
}
interface LogItem { key: string; label: string; unit: string; old_value: number | null; new_value: number; note: string; origin: string | null; at: string | null }
interface SourceDraft { rationale: string; origin: string; url: string }

const items = ref<NormItem[]>([])
const log = ref<LogItem[]>([])
const edits = ref<Record<string, number>>({})
const sourceEdits = ref<Record<string, SourceDraft>>({})
const siteFieldLabel: Record<string, string> = { energy_tariff_rub_kwh: 'Тариф на энергию', payback_years: 'Горизонт расчёта окупаемости' }
const note = ref('')
const loading = ref(true)
const saving = ref(false)
const message = ref('')
const failure = ref('')

const load = async () => {
  loading.value = true
  failure.value = ''
  try {
    const [norms, history] = await Promise.all([
      platformGet<{ items: NormItem[] }>('/economy/norms'),
      platformGet<{ items: LogItem[] }>('/admin/economy/norms/log'),
    ])
    items.value = norms.items
    log.value = history.items
    edits.value = {}
    sourceEdits.value = {}
  } catch (err: unknown) {
    failure.value = fetchErrorMessage(err, 'Не удалось загрузить нормативы')
  } finally {
    loading.value = false
  }
}
onMounted(load)

const groups = computed(() => PARAM_GROUPS.map((group) => ({ ...group, items: items.value.filter((item) => item.group === group.id) })).filter((group) => group.items.length))
const current = (item: NormItem) => edits.value[item.key] ?? item.value
const edit = (item: NormItem, raw: string) => {
  const value = Number(raw.replace(',', '.'))
  if (!Number.isFinite(value)) return
  const next = { ...edits.value }
  if (Math.abs(value - item.value) < 1e-12) delete next[item.key]
  else next[item.key] = value
  edits.value = next
}
const restore = (item: NormItem) => { edits.value = { ...edits.value, [item.key]: item.default } }
const editSource = (item: NormItem) => {
  if (sourceEdits.value[item.key]) return
  sourceEdits.value = { ...sourceEdits.value, [item.key]: { rationale: item.rationale, origin: item.origin, url: item.url } }
}
const dropSource = (key: string) => {
  const next = { ...sourceEdits.value }
  delete next[key]
  sourceEdits.value = next
}
const resetSource = (item: NormItem) => {
  sourceEdits.value = { ...sourceEdits.value, [item.key]: { rationale: item.default_rationale, origin: item.default_origin, url: '' } }
}
const sourceChanged = (item: NormItem) => {
  const draft = sourceEdits.value[item.key]
  return Boolean(draft && (draft.rationale !== item.rationale || draft.origin !== item.origin || draft.url !== item.url))
}
const pending = computed(() => new Set([...Object.keys(edits.value), ...items.value.filter(sourceChanged).map((item) => item.key)]).size)
const changedWithoutSource = computed(() => Object.keys(edits.value).filter((key) => !sourceEdits.value[key]))

const save = async () => {
  saving.value = true
  message.value = ''
  const sources: Record<string, SourceDraft> = {}
  for (const item of items.value) if (sourceChanged(item)) sources[item.key] = sourceEdits.value[item.key]!
  try {
    const result = await platformSend<{ items: NormItem[] }>('/admin/economy/norms', 'PUT', { values: edits.value, sources, note: note.value.trim() })
    items.value = result.items
    edits.value = {}
    sourceEdits.value = {}
    note.value = ''
    log.value = (await platformGet<{ items: LogItem[] }>('/admin/economy/norms/log')).items
    message.value = 'Стандарт обновлён. Проекты без своих значений считаются по нему сразу.'
  } catch (err: unknown) {
    message.value = fetchErrorMessage(err, 'Не удалось сохранить')
  } finally {
    saving.value = false
  }
}

const num = (value: number | null) => value == null ? '—' : value.toLocaleString('ru-RU', { maximumFractionDigits: 3 })
const when = (value: string | null) => value ? new Date(value).toLocaleString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Нормативы" title="Стандартные коэффициенты экономики" lead="Эти значения подставляются во все проекты, где пользователь не задал своё. У каждого есть обоснование и источник. Правка пишется в историю.">
      <UiButton :disabled="!pending || saving" @click="save"><template #icon><PhFloppyDisk :size="16" weight="bold" /></template>{{ saving ? 'Сохраняем' : pending ? `Сохранить ${pending}` : 'Сохранить' }}</UiButton>
    </AdminHead>

    <UiCallout v-if="failure" tone="danger" title="Нормативы не загрузились">{{ failure }}</UiCallout>
    <UiCallout v-else tone="info" title="Как применяется стандарт">
      Проект берёт стандарт, пока пользователь не задал своё значение на шаге what-if. Тариф на электроэнергию и горизонт сначала берутся с площадки, если они там заданы.
    </UiCallout>

    <section v-if="pending" class="note glass">
      <div class="n-in">
        <label class="caption" for="norm-note">Почему меняем</label>
        <input id="norm-note" v-model="note" class="input" placeholder="Например: ставка сервиса по договору с вендором">
        <span v-if="changedWithoutSource.length" class="caption warn-t">
          У изменённых значений остаётся прежний источник. Если число взято из нового документа, обновите источник кнопкой «Источник» в строке.
        </span>
        <span v-if="message" class="caption">{{ message }}</span>
      </div>
    </section>
    <p v-else-if="message" class="caption">{{ message }}</p>

    <div v-if="loading" class="tbl glass glass-xl"><div class="t-in"><span class="body-sm muted">Загружаем нормативы</span></div></div>
    <div v-for="group in groups" v-else :key="group.id" class="tbl glass glass-xl">
      <div class="t-in">
        <div class="label g-title">{{ group.label }}</div>
        <div class="nrow head caption"><span>Норматив</span><span>Значение</span><span>Единица</span><span>Обоснование</span><span /></div>
        <template v-for="item in group.items" :key="item.key">
          <div class="nrow" :class="{ edited: edits[item.key] !== undefined || sourceChanged(item) }">
            <span class="nm">
              <span class="body strong">{{ item.label }}</span>
              <span class="nm-sym"><UiTex :tex="item.symbol" /><span class="mono-sm code">{{ item.key }}</span></span>
            </span>
            <span class="val"><input class="input input-mono" type="number" :step="item.step" :min="item.min" :max="item.max" :value="current(item)" :aria-label="item.label" @change="edit(item, ($event.target as HTMLInputElement).value)"></span>
            <span class="mono-sm">{{ item.unit }}</span>
            <span class="body-sm">
              {{ item.rationale }}
              <span class="caption block">
                Источник: <a v-if="item.url" :href="item.url" target="_blank" rel="noreferrer" class="link">{{ item.origin }}</a><template v-else>{{ item.origin }}</template>
                <template v-if="item.value !== item.default"> · исходно {{ num(item.default) }}</template>
              </span>
              <span v-if="item.site_key" class="caption block">Если в проекте заполнено поле объекта «{{ siteFieldLabel[item.site_key] ?? item.site_key }}», берётся оно, а не норматив.</span>
              <span v-if="item.projects_custom" class="caption block">Своё значение у {{ item.projects_custom }} из {{ item.projects_total }} проектов, остальные считаются по стандарту.</span>
            </span>
            <span class="act">
              <button type="button" class="src-btn caption" @click="sourceEdits[item.key] ? dropSource(item.key) : editSource(item)">{{ sourceEdits[item.key] ? 'Скрыть' : 'Источник' }}</button>
              <button v-if="current(item) !== item.default" type="button" class="reset" :title="`Вернуть исходное ${num(item.default)}`" @click="restore(item)"><PhArrowCounterClockwise :size="14" weight="bold" /></button>
            </span>
          </div>
          <div v-if="sourceEdits[item.key]" class="src-edit">
            <label class="fld"><span class="caption">Обоснование числа</span><textarea v-model="sourceEdits[item.key]!.rationale" class="textarea" rows="2" /></label>
            <div class="src-row">
              <label class="fld"><span class="caption">Источник</span><input v-model="sourceEdits[item.key]!.origin" class="input" placeholder="Документ, датасет, договор"></label>
              <label class="fld"><span class="caption">Ссылка</span><input v-model="sourceEdits[item.key]!.url" class="input" placeholder="https://"></label>
              <button type="button" class="link caption" @click="resetSource(item)">Вернуть текст из модели</button>
            </div>
          </div>
        </template>
      </div>
    </div>

    <section class="hist glass">
      <div class="h-in">
        <div class="h4"><PhClockCounterClockwise :size="16" /> История изменений</div>
        <p v-if="!log.length" class="body-sm muted">Правок ещё не было: действуют исходные значения.</p>
        <div v-for="(row, index) in log" :key="`${row.key}-${index}`" class="hrow">
          <span class="mono-sm muted">{{ when(row.at) }}</span>
          <span class="body-sm strong">{{ row.label }}</span>
          <span class="body-sm">{{ num(row.old_value) }} → {{ num(row.new_value) }} {{ row.unit }}<span v-if="row.note" class="caption block">{{ row.note }}</span><span v-if="row.origin" class="caption block">Источник: {{ row.origin }}</span></span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.tbl { padding: var(--space-3); }
.t-in { position: relative; z-index: 1; display: grid; gap: 4px; }
.g-title { padding: 10px 14px 0; }
.nrow { display: grid; grid-template-columns: 1.4fr 130px 150px 2fr 110px; gap: var(--space-4); align-items: center; padding: 12px 14px; border-radius: 12px; }
.nrow.head { padding-bottom: 4px; }
.nrow:not(.head):hover { background: rgba(255, 255, 255, 0.55); }
.nrow.edited { background: var(--surface-brand-tint); }
.nm { display: grid; gap: 4px; justify-items: start; }
.nm-sym { display: inline-flex; gap: 8px; align-items: center; color: var(--ink-muted); }
.code { color: var(--ink-muted); padding: 2px 6px; border-radius: 5px; background: rgba(15, 20, 19, 0.05); }
.val .input { width: 100%; text-align: right; }
.act { display: flex; justify-content: flex-end; }
.reset { color: var(--brand-700); display: inline-flex; padding: 6px; border-radius: 8px; }
.reset:hover { background: rgba(15, 20, 19, 0.05); }
.note .n-in { position: relative; z-index: 1; padding: var(--space-4) var(--space-5); display: grid; gap: 6px; }
.hist .h-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: 12px; }
.h4 { display: inline-flex; gap: 8px; align-items: center; }
.hrow { display: grid; grid-template-columns: 170px 220px 1fr; gap: var(--space-4); align-items: start; padding-top: 12px; border-top: 1px solid var(--border-hairline); }
.block { display: block; }
.warn-t { color: var(--state-warn); }
.act { gap: 4px; align-items: center; }
.src-btn { padding: 4px 8px; border-radius: 8px; font-weight: 700; color: var(--link); }
.src-btn:hover { background: rgba(15, 20, 19, 0.05); }
.src-edit { display: grid; gap: 10px; padding: 4px 14px 14px; margin-top: -2px; }
.src-row { display: grid; grid-template-columns: 1fr 1fr auto; gap: 12px; align-items: end; }
.fld { display: grid; gap: 6px; }
.fld .input, .fld .textarea { width: 100%; }
@media (max-width: 1100px) {
  .nrow { grid-template-columns: 1fr 120px 32px; }
  .nrow > :nth-child(3), .nrow > :nth-child(4) { grid-column: 1 / -1; }
  .nrow.head { display: none; }
  .hrow { grid-template-columns: 1fr; }
}
</style>
