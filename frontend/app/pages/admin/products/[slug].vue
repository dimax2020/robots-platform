<script setup lang="ts">
import { PhArrowLeft, PhFloppyDisk, PhArrowSquareOut, PhUploadSimple, PhQuotes, PhPlus, PhCheckSquare, PhSquare } from '@phosphor-icons/vue'
import { platformGet, platformSend, usePlatformBase } from '~/composables/usePlatform'
import { fetchErrorMessage } from '~/utils/errors'
import { attrGroupLabel, attrGroupOrder, confidenceOf, needsRationale, platformSourceKinds, sourceKindName } from '~/data/adminLabels'
import { photoFor } from '~/data/placeholders'

definePageMeta({ layout: 'admin', middleware: 'admin', pageTransition: false })

interface Source { id: number; kind: string; publisher: string; url: string | null; title: string | null; parser_code: string | null }
interface Attr { approximate?: boolean; condition?: string | null; key: string; label: string; unit: string | null; group: string; datatype: string; sort: number; status: string; value: unknown; quote: string | null; fetched_at: string | null; confirmed: boolean; source: Source | null }
interface Card {
  slug: string
  name: string
  manufacturer: string | null
  availability: string | null
  trl: number | null
  price_rub: number | null
  image_url: string | null
  summary: string | null
  solution_type: string | null
  processes: string[]
  legal_entity: string | null
  region: string | null
  market_potential: string | null
  columns: Record<string, Source | null>
  attrs: Attr[]
  quality: { completeness: number; filled: number; total: number; sources: number }
}
interface DictItem { key: string; label: string; unit: string | null; group: string; datatype: string; sort: number; products: number }
interface Row { approximate?: boolean; condition?: string | null; key: string; label: string; unit: string | null; group: string; sort: number; status: string; value: string; quote: string; confirmed: boolean; source: Source | null; fetched_at: string | null; initial: string; present: boolean }

const route = useRoute()
const slug = computed(() => route.params.slug as string)
const card = ref<Card | null>(null)
const dictionary = ref<DictItem[]>([])
const types = ref<{ code: string; name: string; group: string }[]>([])
const processes = ref<{ code: string; name: string; objects: { name: string }[] }[]>([])
const rows = ref<Row[]>([])
const columns = reactive<Record<string, string>>({})
const columnsInitial = ref<Record<string, string>>({})
const typeCode = ref('')
const processCodes = ref<string[]>([])
const source = reactive({ kind: 'vendor', publisher: '', url: '', title: '', rationale: '' })
const notice = ref<{ ok: boolean; text: string } | null>(null)
const saving = ref(false)
const processQuery = ref('')
const addKey = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
useHead({ title: () => `Админка · ${card.value?.name ?? 'Продукт'}` })

const COLUMN_KEYS = ['name', 'manufacturer', 'availability', 'trl', 'price_rub', 'summary'] as const
const statusLabel: Record<string, string> = { known: 'Есть данные', unknown: 'Нет данных', not_applicable: 'Не применимо' }
const availabilityOptions = [
  { value: 'operation', label: 'В эксплуатации' },
  { value: 'piloting', label: 'Пилот' },
  { value: 'rnd', label: 'Разработка' },
]
const text = (value: unknown) => (value === null || value === undefined ? '' : String(value))
const rowState = (row: { status: string; value: string; quote: string }) => JSON.stringify([row.status, row.value, row.quote])

const build = (data: Card) => {
  card.value = data
  for (const key of COLUMN_KEYS) columns[key] = text(data[key])
  columns.region = text(data.region)
  columns.market_potential = text(data.market_potential)
  columnsInitial.value = { ...columns }
  typeCode.value = data.solution_type ?? ''
  processCodes.value = [...data.processes]
  const present = new Map(data.attrs.map((item) => [item.key, item]))
  const next: Row[] = []
  for (const item of data.attrs) {
    if (item.key === 'region' || item.key === 'market_potential') continue
    const row = { key: item.key, label: item.label, approximate: item.approximate, condition: item.condition, unit: item.unit, group: item.group, sort: item.sort, status: item.status, value: text(item.value), quote: item.quote ?? '', confirmed: item.confirmed, source: item.source, fetched_at: item.fetched_at, initial: '', present: true }
    row.initial = rowState(row)
    next.push(row)
  }
  for (const item of dictionary.value) {
    if (present.has(item.key) || !item.group || item.group === 'identification' || item.group === 'data_quality') continue
    const row = { key: item.key, label: item.label, unit: item.unit, group: item.group, sort: item.sort, status: 'unknown', value: '', quote: '', confirmed: false, source: null, fetched_at: null, initial: '', present: false }
    row.initial = rowState(row)
    next.push(row)
  }
  rows.value = next.sort((a, b) => a.sort - b.sort || a.label.localeCompare(b.label, 'ru'))
}

const load = async () => {
  try {
    const [dict, typeList, processList] = await Promise.all([
      platformGet<DictItem[]>('/admin/attribute-dictionary'),
      platformGet<{ code: string; name: string; group: string }[]>('/admin/solution-types'),
      platformGet<{ code: string; name: string; objects: { name: string }[] }[]>('/admin/processes'),
    ])
    dictionary.value = dict
    types.value = typeList
    processes.value = processList
    build(await platformGet<Card>(`/admin/products/${slug.value}`))
    source.publisher = card.value?.manufacturer ?? ''
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Карточка не загрузилась') }
  }
}
onMounted(load)

const groups = computed(() => attrGroupOrder
  .map((code) => ({ code, label: code === 'identification' ? 'Идентификация: дополнительные поля' : (attrGroupLabel[code] ?? code), rows: rows.value.filter((row) => (row.group || '') === code) }))
  .filter((group) => group.rows.length))
const changedRows = computed(() => rows.value.filter((row) => rowState(row) !== row.initial))
const changedColumns = computed(() => Object.keys(columns).filter((key) => columns[key] !== columnsInitial.value[key]))
const confirmChanges = computed(() => {
  const out: Record<string, boolean> = {}
  for (const item of card.value?.attrs ?? []) {
    const row = rows.value.find((r) => r.key === item.key)
    if (row && row.confirmed !== item.confirmed && rowState(row) === row.initial) out[item.key] = row.confirmed
  }
  return out
})
const typeChanged = computed(() => (card.value?.solution_type ?? '') !== typeCode.value)
const processesChanged = computed(() => [...(card.value?.processes ?? [])].sort().join('|') !== [...processCodes.value].sort().join('|'))
const pendingCount = computed(() => changedRows.value.length + changedColumns.value.length + Object.keys(confirmChanges.value).length + (typeChanged.value ? 1 : 0) + (processesChanged.value ? 1 : 0))
const needsSource = computed(() => changedRows.value.length + changedColumns.value.length > 0)
const sourceProblem = computed(() => (needsSource.value && needsRationale(source.kind) && !source.rationale.trim() ? 'Для оценки по аналогу и допущения нужно обоснование.' : ''))

const shownProcesses = computed(() => {
  const q = processQuery.value.trim().toLowerCase()
  return processes.value.filter((item) => processCodes.value.includes(item.code) || (q && item.name.toLowerCase().includes(q)))
})
const toggleProcess = (code: string) => {
  processCodes.value = processCodes.value.includes(code) ? processCodes.value.filter((item) => item !== code) : [...processCodes.value, code]
}
const typeGroups = computed(() => {
  const map = new Map<string, { code: string; name: string }[]>()
  for (const item of types.value) map.set(item.group || 'Без группы', [...(map.get(item.group || 'Без группы') ?? []), item])
  return [...map.entries()]
})
const addable = computed(() => {
  const taken = new Set(rows.value.map((row) => row.key))
  return dictionary.value.filter((item) => !taken.has(item.key))
})
const addAttr = () => {
  const item = dictionary.value.find((entry) => entry.key === addKey.value)
  if (!item) return
  rows.value.push({ key: item.key, label: item.label, unit: item.unit, group: item.group, sort: item.sort, status: 'known', value: '', quote: '', confirmed: false, source: null, fetched_at: null, initial: rowState({ status: 'unknown', value: '', quote: '' }), present: false })
  addKey.value = ''
}

const castValue = (row: Row, datatype: string) => {
  if (row.status !== 'known') return null
  if (datatype === 'number') {
    const n = Number(row.value.replace(/\s/g, '').replace(',', '.'))
    return Number.isFinite(n) && row.value.trim() ? n : row.value
  }
  if (datatype === 'bool') return /^(да|true|1|yes)$/i.test(row.value.trim())
  return row.value
}
const datatypeOf = (key: string) => dictionary.value.find((item) => item.key === key)?.datatype ?? 'text'

const save = async () => {
  if (!card.value || saving.value || !pendingCount.value || sourceProblem.value) return
  saving.value = true
  notice.value = null
  const cols: Record<string, string | number | null> = {}
  const attrs: Record<string, unknown> = {}
  for (const key of changedColumns.value) {
    const value = columns[key]!.trim()
    if (key === 'region' || key === 'market_potential') {
      attrs[key] = { status: value ? 'known' : 'unknown', value: value || null }
      continue
    }
    if (key === 'trl' || key === 'price_rub') cols[key] = value ? Number(value.replace(/\s/g, '').replace(',', '.')) : null
    else cols[key] = value || null
  }
  for (const row of changedRows.value) attrs[row.key] = { status: row.status, value: castValue(row, datatypeOf(row.key)), quote: row.quote || null, confirmed: row.confirmed, label: row.label, unit: row.unit }
  try {
    const data = await platformSend<Card>(`/admin/products/${card.value.slug}`, 'PATCH', {
      columns: cols,
      attrs,
      confirm: confirmChanges.value,
      source: { ...source },
      solution_type: typeCode.value || null,
      set_type: typeChanged.value,
      processes: processesChanged.value ? processCodes.value : null,
    })
    build(data)
    notice.value = { ok: true, text: 'Карточка сохранена. Ручные значения не затрутся следующим импортом.' }
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось сохранить') }
  } finally {
    saving.value = false
  }
}
const reset = () => { if (card.value) build(card.value) }

const upload = async (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file || !card.value) return
  const body = new FormData()
  body.set('file', file)
  try {
    const result = await $fetch<{ image_url: string }>(`${usePlatformBase()}/admin/products/${card.value.slug}/image`, { method: 'POST', body })
    card.value.image_url = result.image_url
    notice.value = { ok: true, text: 'Фото загружено' }
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Фото не загрузилось') }
  }
}

const sourceText = (item: Source | null | undefined) => (item ? `${sourceKindName(item.kind)} · ${item.publisher}` : 'источник не указан')
</script>

<template>
  <div v-if="card" class="admin-page">
    <NuxtLink to="/admin/products" class="back body-sm"><PhArrowLeft :size="14" weight="bold" /> Все продукты</NuxtLink>
    <AdminHead label="Карточка продукта" :title="card.name" lead="Каждое значение хранит источник, дату и отметку «подтверждено» (ТЗ 3.3.4). Буква достоверности выводится из типа источника.">
      <UiButton variant="secondary" :to="`/catalog/card/${card.slug}`"><template #icon><PhArrowSquareOut :size="16" /></template>На витрине</UiButton>
      <UiButton variant="secondary" :disabled="!pendingCount" @click="reset">Отменить</UiButton>
      <UiButton :disabled="!pendingCount || saving || !!sourceProblem" @click="save">
        <template #icon><PhFloppyDisk :size="16" weight="bold" /></template>{{ saving ? 'Сохраняем…' : pendingCount ? `Сохранить (${pendingCount})` : 'Сохранить' }}
      </UiButton>
    </AdminHead>
    <UiCallout v-if="notice" :tone="notice.ok ? 'ok' : 'danger'">{{ notice.text }}</UiCallout>

    <div class="top">
      <section class="glass glass-xl a-panel photo">
        <img :src="photoFor(card.image_url, card.name)" :alt="card.name" class="img">
        <UiButton size="sm" variant="secondary" @click="fileInput?.click()"><template #icon><PhUploadSimple :size="14" weight="bold" /></template>Загрузить фото</UiButton>
        <input ref="fileInput" type="file" accept="image/png,image/jpeg,image/webp" class="sr" @change="upload">
        <span class="caption">PNG, JPG или WebP до 10 МБ. {{ card.columns.image_url ? sourceText(card.columns.image_url) : 'Фото из источника не пришло.' }}</span>
      </section>

      <section class="glass glass-xl a-panel quality">
        <div class="h4">Качество данных</div>
        <div class="q">
          <UiStat label="Заполнено полей ТЗ" :value="`${Math.round(card.quality.completeness * 100)}%`" :note="`${card.quality.filled} из ${card.quality.total}`" />
          <UiStat label="Источников" :value="String(card.quality.sources)" />
          <UiStat label="Процессов" :value="String(processCodes.length)" :note="processCodes.length ? '' : 'в подбор не попадает'" />
        </div>
      </section>
    </div>

    <section class="glass glass-xl a-panel">
      <div class="h3">Идентификация</div>
      <div class="grid2">
        <label class="a-fld"><span class="caption">Название</span><input v-model="columns.name" class="input"><span class="caption src">{{ sourceText(card.columns.name) }}</span></label>
        <label class="a-fld"><span class="caption">Производитель</span><input v-model="columns.manufacturer" class="input"><span class="caption src">{{ sourceText(card.columns.manufacturer) }}</span></label>
        <label class="a-fld"><span class="caption">Юрлицо</span><input class="input" :value="card.legal_entity ?? ''" disabled><span class="caption src">из строки каталога организатора</span></label>
        <label class="a-fld"><span class="caption">Регион</span><input v-model="columns.region" class="input"></label>
        <label class="a-fld"><span class="caption">Статус доступности</span>
          <select v-model="columns.availability" class="select">
            <option value="">не указан</option>
            <option v-for="item in availabilityOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            <option v-if="columns.availability && !availabilityOptions.some((o) => o.value === columns.availability)" :value="columns.availability">{{ columns.availability }}</option>
          </select>
          <span class="caption src">{{ sourceText(card.columns.availability) }}</span>
        </label>
        <label class="a-fld"><span class="caption">УГТ, 1–9</span><input v-model="columns.trl" class="input input-mono" inputmode="numeric"><span class="caption src">{{ sourceText(card.columns.trl) }}</span></label>
        <label class="a-fld"><span class="caption">Рыночный потенциал, 1–5</span><input v-model="columns.market_potential" class="input input-mono"></label>
        <label class="a-fld"><span class="caption">Цена, ₽ с НДС</span><input v-model="columns.price_rub" class="input input-mono" inputmode="decimal"><span class="caption src">{{ sourceText(card.columns.price_rub) }}</span></label>
        <label class="a-fld"><span class="caption">Тип решения</span>
          <select v-model="typeCode" class="select">
            <option value="">не задан</option>
            <optgroup v-for="[group, list] in typeGroups" :key="group" :label="group">
              <option v-for="item in list" :key="item.code" :value="item.code">{{ item.name }}</option>
            </optgroup>
          </select>
        </label>
      </div>
      <label class="a-fld"><span class="caption">Описание</span><textarea v-model="columns.summary" class="textarea" rows="4" /><span class="caption src">{{ sourceText(card.columns.summary) }}</span></label>
    </section>

    <section class="glass glass-xl a-panel">
      <div>
        <div class="h3">Процессы продукта</div>
        <p class="caption">В подбор робот попадает только через процесс. Отмеченные процессы показаны всегда, остальные — по поиску.</p>
      </div>
      <input v-model="processQuery" class="input" placeholder="Найти процесс: уборка, паллеты, доставка">
      <div class="checks">
        <button v-for="item in shownProcesses" :key="item.code" type="button" class="check" :class="{ on: processCodes.includes(item.code) }" @click="toggleProcess(item.code)">
          <PhCheckSquare v-if="processCodes.includes(item.code)" :size="18" weight="fill" /><PhSquare v-else :size="18" />
          <span>{{ item.name }}</span><span class="caption">{{ item.objects.map((o) => o.name).join(', ') }}</span>
        </button>
      </div>
    </section>

    <section class="glass glass-xl a-panel" :class="{ need: needsSource }">
      <div>
        <div class="h3">Источник правки</div>
        <p class="caption">Один источник на все значения, изменённые в этот раз. Без него изменения не сохраняются.</p>
      </div>
      <div class="a-row">
        <label class="a-fld narrow"><span class="caption">Тип источника</span>
          <select v-model="source.kind" class="select">
            <option v-for="kind in platformSourceKinds.filter((k) => k.manual)" :key="kind.code" :value="kind.code">{{ kind.label }}</option>
          </select>
        </label>
        <span class="a-letter lg" :class="`c-${confidenceOf(source.kind)}`" :title="`Достоверность ${confidenceOf(source.kind)}`">{{ confidenceOf(source.kind) }}</span>
        <label class="a-fld"><span class="caption">Кто опубликовал</span><input v-model="source.publisher" class="input" :placeholder="card.manufacturer ?? ''"></label>
        <label class="a-fld"><span class="caption">Ссылка</span><input v-model="source.url" class="input" placeholder="https://"></label>
        <label class="a-fld"><span class="caption">Документ</span><input v-model="source.title" class="input" placeholder="Техническое описание"></label>
      </div>
      <label v-if="needsRationale(source.kind)" class="a-fld"><span class="caption">Обоснование</span><input v-model="source.rationale" class="input" placeholder="Какой аналог взят или почему такое допущение"></label>
      <p v-if="sourceProblem" class="caption warn-t">{{ sourceProblem }}</p>
    </section>

    <section v-for="group in groups" :key="group.code" class="glass glass-xl a-panel">
      <div class="h3">{{ group.label }}</div>
      <div class="attrs">
        <div class="arow head caption"><span>Характеристика</span><span>Значение</span><span>Статус</span><span>Цитата</span><span>Источник</span></div>
        <div v-for="row in group.rows" :key="row.key" class="arow" :class="{ changed: rowState(row) !== row.initial, empty: !row.present && row.status !== 'known' }">
          <span class="body-sm strong">{{ row.label }}<span v-if="row.approximate || row.condition" class="caption block">{{ [row.approximate ? 'Приблизительно' : '', row.condition].filter(Boolean).join(' · ') }}</span><span v-if="row.unit" class="caption block">{{ row.unit }}</span></span>
          <input v-model="row.value" class="input" :class="{ 'input-mono': datatypeOf(row.key) === 'number' }" :disabled="row.status !== 'known'" :placeholder="row.status === 'known' ? '' : statusLabel[row.status]">
          <select v-model="row.status" class="select"><option v-for="(label, key) in statusLabel" :key="key" :value="key">{{ label }}</option></select>
          <span class="quote"><PhQuotes :size="14" weight="fill" /><input v-model="row.quote" class="input" placeholder="Цитата из источника"></span>
          <span class="src-cell">
            <template v-if="row.source && rowState(row) === row.initial">
              <span class="a-letter" :class="`c-${confidenceOf(row.source.kind)}`">{{ confidenceOf(row.source.kind) }}</span>
              <span class="caption">
                <a v-if="row.source.url" :href="row.source.url" target="_blank" rel="noreferrer" class="link">{{ row.source.publisher }}</a><template v-else>{{ row.source.publisher }}</template>
                <template v-if="row.fetched_at"> · {{ row.fetched_at }}</template>
              </span>
            </template>
            <span v-else class="caption">{{ rowState(row) !== row.initial ? 'будет источник правки' : 'нет данных' }}</span>
            <label v-if="row.present || rowState(row) !== row.initial" class="conf" title="Значение подтверждено"><input v-model="row.confirmed" type="checkbox"> <span class="caption">подтв.</span></label>
          </span>
        </div>
      </div>
    </section>

    <section class="glass glass-xl a-panel">
      <div class="h4">Добавить характеристику</div>
      <div class="a-row">
        <label class="a-fld"><span class="caption">Из справочника</span>
          <select v-model="addKey" class="select">
            <option value="">выберите характеристику</option>
            <option v-for="item in addable" :key="item.key" :value="item.key">{{ item.label }}{{ item.unit ? `, ${item.unit}` : '' }} · у {{ item.products }}</option>
          </select>
        </label>
        <UiButton variant="secondary" :disabled="!addKey" @click="addAttr"><template #icon><PhPlus :size="14" weight="bold" /></template>Добавить</UiButton>
      </div>
      <p class="caption">Новые характеристики заводятся в справочнике: <NuxtLink to="/admin/products/attributes" class="link">Продукты → Характеристики</NuxtLink>.</p>
    </section>
  </div>
  <div v-else class="admin-page">
    <UiCallout v-if="notice" tone="danger">{{ notice.text }}</UiCallout>
    <p v-else class="body-sm muted">Загружаем карточку…</p>
  </div>
</template>

<style scoped>
.back { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-muted); font-weight: 600; }
.top { display: grid; grid-template-columns: 320px minmax(0, 1fr); gap: var(--space-5); }
.photo { justify-items: start; }
.img { width: 100%; aspect-ratio: 4 / 3; object-fit: contain; border-radius: 14px; background: #fff; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
.q { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-6); }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 20px; }
.src { color: var(--ink-faint); }
.checks { display: flex; flex-wrap: wrap; gap: 8px; }
.check { display: inline-flex; align-items: center; gap: 8px; min-height: 36px; padding: 0 12px; border-radius: 10px; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px var(--border-hairline); font-weight: 600; font-size: 14px; }
.check svg { color: var(--ink-faint); }
.check.on { box-shadow: inset 0 0 0 1px var(--brand-400); background: #fff; }
.check.on svg { color: var(--brand-600); }
.need { box-shadow: inset 0 0 0 2px var(--brand-400); }
.a-letter.lg { width: 34px; height: 34px; font-size: 14px; align-self: end; margin-bottom: 5px; }
.warn-t { color: var(--state-warn); }
.attrs { display: grid; gap: 6px; }
.arow { display: grid; grid-template-columns: 200px minmax(0, 1fr) 150px minmax(0, 1.2fr) minmax(0, 1.2fr); gap: 10px; align-items: center; padding: 4px 6px; border-radius: 10px; }
.arow.head { padding-bottom: 0; }
.arow.changed { background: var(--surface-brand-tint); }
.arow.empty .strong { color: var(--ink-muted); }
.block { display: block; }
.quote { position: relative; display: flex; align-items: center; }
.quote svg { position: absolute; left: 10px; color: var(--ink-faint); }
.quote .input { padding-left: 30px; width: 100%; }
.src-cell { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.conf { display: inline-flex; gap: 4px; align-items: center; margin-left: auto; }
.arow .input, .arow .select { width: 100%; }
@media (max-width: 1100px) {
  .top, .grid2, .q { grid-template-columns: 1fr; }
  .arow { grid-template-columns: 1fr 1fr; }
}
</style>
