<script setup lang="ts">
import { PhPlus, PhTrash, PhDotsSixVertical, PhCheckCircle, PhWarningCircle, PhCaretDown, PhCaretRight, PhArrowSquareOut, PhCheckSquare, PhSquare } from '@phosphor-icons/vue'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { fetchErrorMessage } from '~/utils/errors'
import { pluralRu } from '~/data/adminLabels'
import { replaceQuery } from '~/composables/useQuerySync'

definePageMeta({ layout: 'admin', middleware: 'admin', pageTransition: false })
useHead({ title: 'Админка · Процессы' })

interface Input { key: string; label: string }
interface StoredFilter { name: string; mode: string; inputs: Input[]; formula: string }
interface Filter {
  id: number
  name: string
  mode: 'hard' | 'conditional'
  robot_key: string
  op: string
  side: 'value' | 'number'
  input_key: string
  input_label: string
  number: string
  locked: string
}
interface Piece { id: number; kind: 'attr' | 'site' | 'num'; key: string; label: string; value: string }
interface RobotAttr { key: string; label: string; products: number; on_process: number }
interface LayoutItem { key: string; label: string; role: string; shape: string; min_count: number; count_rule: string; hint: string }
interface ObjectField { key: string; label: string; unit: string; default: unknown }
interface LinkedObject { code: string; name: string; bindings: Record<string, string>; fields: ObjectField[] }
interface Setup {
  code: string
  name: string
  product_count: number
  filters: StoredFilter[]
  count_inputs: Input[]
  count_formula: string
  rank_key: string
  rank_order: string
  layout_items: LayoutItem[]
  layout_items_default: boolean
  objects: LinkedObject[]
}
interface Dictionary { roles: Record<string, string>; shapes: Record<string, string>; count_rules: Record<string, string> }
interface ProcItem { code: string; name: string; product_count: number; filter_count: number; has_count: boolean; has_layout: boolean; objects: { code: string; name: string }[] }
interface Preview {
  object: { code: string; name: string }
  site: Record<string, unknown>
  tally: Record<string, number>
  reasons: { verdict: string; reason: string; count: number }[]
  best_product_id: string | null
  robots: { product_id: string; name: string; slug: string; verdict: string; notes: string[]; count: number | null; count_note: string }[]
}

const route = useRoute()
const processes = ref<ProcItem[]>([])
const allObjects = ref<{ code: string; name: string }[]>([])
const robotAttrs = ref<RobotAttr[]>([])
const draft = ref<Setup | null>(null)
const filters = ref<Filter[]>([])
const notice = ref<{ ok: boolean; text: string } | null>(null)
const saving = ref(false)
const dirty = ref(false)
const selected = ref('')
const listQuery = ref('')
const creating = ref<{ name: string; objects: string[] } | null>(null)
const wrap = ref('')
const countLocked = ref('')
const pieces = ref<Piece[]>([])
const joins = ref<string[]>([])
const dictionary = ref<Dictionary>({ roles: {}, shapes: {}, count_rules: {} })
const previewObject = ref('')
const preview = ref<Preview | null>(null)
const previewError = ref('')
const previewBusy = ref(false)
const showRobots = ref(false)
const dragIndex = ref<number | null>(null)
let seq = 1

/* ---------- словари ---------- */
const opWords: Record<string, string> = { '>=': 'не меньше', '<=': 'не больше', '>': 'больше', '<': 'меньше', '==': 'равна' }
const verdictLabel: Record<string, string> = { pass: 'Подходит', conditional: 'С условием', unknown: 'Уточнить', fail: 'Не подходит' }
const verdictTone: Record<string, string> = { pass: 'ok', conditional: 'warn', unknown: '', fail: 'danger' }
const templates = [
  { title: 'Проходит в проезд', name: 'Проезд', robot: 'min_aisle_width_m', op: '<=', key: 'aisle', label: 'Ширина проезда', field: 'aisle_width_m', mode: 'hard' as const },
  { title: 'Поднимает груз', name: 'Груз', robot: 'payload_kg', op: '>=', key: 'load', label: 'Масса груза', field: 'pallet_mass_kg', mode: 'hard' as const },
  { title: 'Хватает заряда на смену', name: 'Автономность смены', robot: 'work_time_h', op: '>=', key: 'shift', label: 'Длительность смены', field: 'shift_hours', mode: 'conditional' as const },
  { title: 'Не шумнее допустимого', name: 'Шум', robot: 'uroven_shuma', op: '<=', key: 'noise', label: 'Лимит шума', field: 'noise_limit_dba', mode: 'conditional' as const },
  { title: 'Работает в холоде', name: 'Температура', robot: 'temp_min_c', op: '<=', key: 'temp', label: 'Минимальная температура', field: 'temp_min_c', mode: 'hard' as const },
]

const attrLabel = (key: string) => robotAttrs.value.find((item) => item.key === key)?.label || key
const attrCoverage = (key: string) => robotAttrs.value.find((item) => item.key === key)?.on_process ?? 0
const attrsHere = computed(() => robotAttrs.value.filter((item) => item.on_process > 0))
const attrsElse = computed(() => robotAttrs.value.filter((item) => item.on_process === 0))
const siteFields = computed(() => {
  const map = new Map<string, ObjectField>()
  for (const obj of draft.value?.objects ?? []) for (const field of obj.fields) if (!map.has(field.key)) map.set(field.key, field)
  return [...map.values()]
})
const fieldText = (field: { label: string; unit: string }) => (field.unit ? `${field.label}, ${field.unit}` : field.label)
const siteLabel = (key: string) => siteFields.value.find((field) => field.key === key)?.label || key

/* ---------- список процессов ---------- */
const listGroups = computed(() => {
  const text = listQuery.value.trim().toLowerCase()
  const shown = processes.value.filter((item) => !text || `${item.name} ${item.code}`.toLowerCase().includes(text))
  const groups: { name: string; items: ProcItem[] }[] = allObjects.value.map((obj) => ({ name: obj.name, items: shown.filter((item) => item.objects.some((o) => o.code === obj.code)) }))
  groups.push({ name: 'Не привязан к объекту', items: shown.filter((item) => !item.objects.length) })
  return groups.filter((group) => group.items.length)
})
const flags = (item: ProcItem) => [
  !item.product_count && 'нет роботов',
  !item.filter_count && 'нет условий',
  !item.has_count && 'нет формулы',
  !item.has_layout && 'нет схемы',
].filter(Boolean) as string[]

/* ---------- разбор сохранённого ---------- */
const parseFilter = (stored: StoredFilter): Filter => {
  const base: Filter = { id: seq++, name: stored.name, mode: stored.mode === 'conditional' ? 'conditional' : 'hard', robot_key: '', op: '>=', side: 'value', input_key: '', input_label: '', number: '', locked: '' }
  const match = stored.formula.trim().match(/^(?:robot\.)?([A-Za-z_]\w*)\s*(<=|>=|==|<|>)\s*(?:([A-Za-z_]\w*)|(-?\d+(?:[.,]\d+)?))$/)
  if (!match) return { ...base, locked: stored.formula }
  base.robot_key = match[1]!
  base.op = match[2]!
  if (match[3]) {
    const input = stored.inputs.find((item) => item.key === match[3])
    if (!input) return { ...base, locked: stored.formula }
    base.input_key = input.key
    base.input_label = input.label
  } else {
    base.side = 'number'
    base.number = match[4]!.replace(',', '.')
  }
  return base
}

const applyCount = (formula: string, inputs: Input[]) => {
  pieces.value = []
  joins.value = []
  wrap.value = ''
  countLocked.value = ''
  const text = formula.trim()
  if (!text) return
  let body = text
  const wrapped = text.match(/^(ceil|floor|round)\((.*)\)$/)
  if (wrapped) {
    wrap.value = wrapped[1]!
    body = wrapped[2]!
  }
  const labels = new Map(inputs.map((item) => [item.key, item.label]))
  const nextPieces: Piece[] = []
  const nextJoins: string[] = []
  for (const part of body.split(/\s*(\+|-|\*|\/)\s*/).filter(Boolean)) {
    if (part === '+' || part === '-' || part === '*' || part === '/') { nextJoins.push(part); continue }
    if (/^robot\.[A-Za-z_]\w*$/.test(part)) nextPieces.push({ id: seq++, kind: 'attr', key: part.slice(6), label: '', value: '' })
    else if (/^\d+(?:\.\d+)?$/.test(part)) nextPieces.push({ id: seq++, kind: 'num', key: '', label: '', value: part })
    else if (/^[A-Za-z_]\w*$/.test(part)) nextPieces.push({ id: seq++, kind: 'site', key: part, label: labels.get(part) || part, value: '' })
    else { countLocked.value = text; return }
  }
  pieces.value = nextPieces
  joins.value = nextJoins
  if (compileCount() !== text) {
    pieces.value = []
    joins.value = []
    wrap.value = ''
    countLocked.value = text
  }
}

const compileCount = () => {
  const tokens = pieces.value.map((piece) => {
    if (piece.kind === 'attr') return piece.key ? `robot.${piece.key}` : ''
    if (piece.kind === 'num') return piece.value || '0'
    return piece.key
  }).filter(Boolean)
  if (!tokens.length) return ''
  let body = tokens[0]!
  for (let index = 1; index < tokens.length; index += 1) body += ` ${joins.value[index - 1] || '/'} ${tokens[index]}`
  return wrap.value ? `${wrap.value}(${body})` : body
}

const countSentence = computed(() => {
  if (countLocked.value) return 'Количество считается по формуле цикла или обхода.'
  if (!pieces.value.length) return 'Формула не задана: в подборе количество роботов не покажется.'
  const word = (piece: Piece) => {
    if (piece.kind === 'attr') return piece.key ? `«${attrLabel(piece.key)}» робота` : 'характеристика'
    if (piece.kind === 'num') return piece.value || 'число'
    return piece.key ? `«${siteLabel(piece.key)}» объекта` : 'параметр объекта'
  }
  const sign: Record<string, string> = { '+': 'плюс', '-': 'минус', '*': 'умножить на', '/': 'разделить на' }
  let text = word(pieces.value[0]!)
  for (let index = 1; index < pieces.value.length; index += 1) text += ` ${sign[joins.value[index - 1] || '/']} ${word(pieces.value[index]!)}`
  const tail: Record<string, string> = { ceil: ', с округлением вверх', floor: ', с округлением вниз', round: ', до ближайшего целого' }
  return `Роботов нужно: ${text}${tail[wrap.value] ?? ''}.`
})

/* ---------- загрузка ---------- */
const loadList = async () => {
  const [items, dict, tree] = await Promise.all([
    platformGet<ProcItem[]>('/admin/processes'),
    platformGet<Dictionary>('/layout-items/dictionary'),
    platformGet<{ objects: { code: string; name: string }[] }>('/catalog/tree'),
  ])
  processes.value = items
  dictionary.value = dict
  allObjects.value = tree.objects
}

const open = async (code: string) => {
  if (dirty.value && !confirm('Есть несохранённые изменения. Перейти без сохранения?')) return
  selected.value = code
  notice.value = null
  preview.value = null
  showRobots.value = false
  const [attrs, setup] = await Promise.all([
    platformGet<RobotAttr[]>(`/admin/robot-attributes?process=${code}`),
    platformGet<Setup>(`/admin/processes/${code}`),
  ])
  robotAttrs.value = attrs
  draft.value = setup
  filters.value = setup.filters.map(parseFilter)
  applyCount(setup.count_formula, setup.count_inputs)
  previewObject.value = setup.objects[0]?.code ?? ''
  replaceQuery({ code })
  await nextTick()
  dirty.value = false
  void runPreview()
}

onMounted(async () => {
  try {
    await loadList()
    const wanted = typeof route.query.code === 'string' ? route.query.code : processes.value[0]?.code
    if (wanted) await open(wanted)
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось загрузить процессы') }
  }
})

/* ---------- условия ---------- */
const usedInputKeys = () => new Set(filters.value.map((item) => item.input_key).filter(Boolean))
const freshKey = (wanted: string) => {
  const taken = usedInputKeys()
  if (wanted && !taken.has(wanted)) return wanted
  let n = 1
  while (taken.has(`${wanted || 'v'}${n}`)) n += 1
  return `${wanted || 'v'}${n}`
}
const addFilter = () => {
  filters.value.push({ id: seq++, name: 'Новое условие', mode: 'hard', robot_key: '', op: '>=', side: 'value', input_key: freshKey('v'), input_label: '', number: '', locked: '' })
}
const addTemplate = (item: typeof templates[number]) => {
  const key = freshKey(item.key)
  filters.value.push({ id: seq++, name: item.name, mode: item.mode, robot_key: item.robot, op: item.op, side: 'value', input_key: key, input_label: item.label, number: '', locked: '' })
  for (const obj of draft.value?.objects ?? []) {
    if (!obj.bindings[key] && obj.fields.some((field) => field.key === item.field)) obj.bindings[key] = item.field
  }
}
const removeFilter = (index: number) => { filters.value.splice(index, 1) }
const unlockFilter = (filter: Filter) => {
  filter.locked = ''
  filter.robot_key = ''
  filter.input_key = freshKey('v')
}
const setSide = (filter: Filter, side: Filter['side']) => {
  filter.side = side
  if (side === 'value' && !filter.input_key) filter.input_key = freshKey('v')
}
const coverageText = (filter: Filter) => {
  if (!filter.robot_key || !draft.value) return ''
  const has = attrCoverage(filter.robot_key)
  const total = draft.value.product_count
  const rest = Math.max(0, total - has)
  if (!total) return 'У процесса пока нет роботов.'
  return `Заполнено у ${has} из ${total} роботов процесса.${rest ? ` У ${rest} будет «уточнить у вендора».` : ''}`
}
const sentence = (filter: Filter) => {
  if (filter.locked || !filter.robot_key) return ''
  const right = filter.side === 'number' ? (filter.number || '…') : `«${filter.input_label || 'величина объекта'}»`
  const otherwise = filter.mode === 'hard' ? 'иначе робот исключается' : 'иначе робот остаётся с пометкой «требует проверки»'
  return `Робот подходит, если «${attrLabel(filter.robot_key)}» ${opWords[filter.op] ?? filter.op} ${right}; ${otherwise}.`
}
const compileFilter = (filter: Filter): StoredFilter | null => {
  if (filter.locked) return { name: filter.name, mode: filter.mode, inputs: draft.value?.filters.find((item) => item.formula === filter.locked)?.inputs ?? [], formula: filter.locked }
  if (!filter.name.trim() || !filter.robot_key) return null
  if (filter.side === 'number') {
    const value = Number(filter.number.replace(',', '.'))
    if (!Number.isFinite(value)) return null
    return { name: filter.name.trim(), mode: filter.mode, inputs: [], formula: `robot.${filter.robot_key} ${filter.op} ${value}` }
  }
  const key = filter.input_key || freshKey('v')
  return { name: filter.name.trim(), mode: filter.mode, inputs: [{ key, label: filter.input_label.trim() || attrLabel(filter.robot_key) }], formula: `robot.${filter.robot_key} ${filter.op} ${key}` }
}

/* ---------- количество ---------- */
const addPiece = (kind: Piece['kind']) => {
  countLocked.value = ''
  if (pieces.value.length) joins.value.push('/')
  pieces.value.push({ id: seq++, kind, key: '', label: '', value: '' })
}
const removePiece = (index: number) => {
  pieces.value.splice(index, 1)
  if (index === 0) joins.value.shift()
  else joins.value.splice(index - 1, 1)
}
const unlockCount = () => { countLocked.value = ''; pieces.value = []; joins.value = []; wrap.value = '' }

/* ---------- схема ---------- */
const areaRole = (role: string) => role === 'work_zone' || role === 'obstacle'
const addItem = () => {
  if (!draft.value) return
  draft.value.layout_items.push({ key: `item${seq++}`, label: 'Новый объект', role: 'pickup', shape: 'point', min_count: 1, count_rule: 'fixed', hint: '' })
  draft.value.layout_items_default = false
}
const onRole = (row: LayoutItem) => {
  row.shape = areaRole(row.role) ? 'area' : 'point'
  if (row.role === 'charge') row.count_rule = 'by_charge'
  else if (row.role === 'pickup' || row.role === 'dropoff') row.count_rule = 'by_flow'
  else row.count_rule = 'fixed'
  if (row.role === 'waypoint' && row.min_count < 2) row.min_count = 2
}
const onDrop = (target: number) => {
  const rows = draft.value?.layout_items
  if (!rows || dragIndex.value === null || dragIndex.value === target) { dragIndex.value = null; return }
  const [row] = rows.splice(dragIndex.value, 1)
  rows.splice(target, 0, row!)
  dragIndex.value = null
}

/* ---------- сборка запроса ---------- */
const payload = () => {
  if (!draft.value) return null
  const compiled = filters.value.map(compileFilter).filter((item): item is StoredFilter => item !== null)
  const countInputs = countLocked.value
    ? draft.value.count_inputs
    : pieces.value.filter((piece) => piece.kind === 'site' && piece.key).map((piece) => ({ key: piece.key, label: siteLabel(piece.key) }))
  const bindings: { object_code: string; input_key: string; site_key: string }[] = []
  for (const obj of draft.value.objects) {
    for (const filter of filters.value) {
      if (filter.locked || filter.side !== 'value' || !filter.input_key) continue
      bindings.push({ object_code: obj.code, input_key: filter.input_key, site_key: obj.bindings[filter.input_key] || '' })
    }
    for (const input of countInputs) {
      const current = obj.bindings[input.key]
      if (current) bindings.push({ object_code: obj.code, input_key: input.key, site_key: current })
      else if (obj.fields.some((field) => field.key === input.key)) bindings.push({ object_code: obj.code, input_key: input.key, site_key: input.key })
    }
  }
  return {
    name: draft.value.name,
    filters: compiled,
    count_inputs: countInputs,
    count_formula: countLocked.value || compileCount(),
    rank_key: draft.value.rank_key,
    rank_order: draft.value.rank_order,
    layout_items: draft.value.layout_items.filter((row) => row.label.trim()).map((row) => ({ ...row, key: row.key.trim() || `item${seq++}` })),
    bindings,
  }
}

watch([draft, filters, pieces, joins, wrap, countLocked], () => { dirty.value = true }, { deep: true })

const save = async () => {
  const body = payload()
  if (!body || !draft.value || saving.value) return
  saving.value = true
  notice.value = null
  try {
    const setup = await platformSend<Setup>(`/admin/processes/${draft.value.code}/setup`, 'PUT', body)
    draft.value = setup
    filters.value = setup.filters.map(parseFilter)
    applyCount(setup.count_formula, setup.count_inputs)
    processes.value = await platformGet<ProcItem[]>('/admin/processes')
    await nextTick()
    dirty.value = false
    notice.value = { ok: true, text: 'Процесс сохранён. Новые расчёты подбора идут по этой настройке.' }
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось сохранить') }
  } finally {
    saving.value = false
  }
}

/* ---------- предпросмотр ---------- */
let previewTimer: ReturnType<typeof setTimeout> | undefined
const runPreview = async () => {
  const body = payload()
  if (!body || !previewObject.value || !draft.value) { preview.value = null; return }
  previewBusy.value = true
  previewError.value = ''
  try {
    preview.value = await platformSend<Preview>(`/admin/processes/${draft.value.code}/preview`, 'POST', { ...body, object_code: previewObject.value })
  } catch (err) {
    previewError.value = fetchErrorMessage(err, 'Проверка не посчиталась')
  } finally {
    previewBusy.value = false
  }
}
watch([filters, pieces, joins, wrap, () => draft.value?.rank_key, () => draft.value?.rank_order, () => draft.value?.objects, previewObject], () => {
  clearTimeout(previewTimer)
  previewTimer = setTimeout(() => { void runPreview() }, 700)
}, { deep: true })

/* ---------- шаги ---------- */
const steps = computed(() => {
  const setup = draft.value
  if (!setup) return []
  const ready = filters.value.filter((item) => item.locked || item.robot_key).length
  const unbound = (setup.objects ?? []).reduce((sum, obj) => sum + filters.value.filter((f) => !f.locked && f.side === 'value' && f.input_key && !obj.bindings[f.input_key]).length, 0)
  return [
    { id: 'step-filters', label: 'Условия подбора', ok: ready > 0 && !unbound, note: ready ? `${ready} ${pluralRu(ready, 'условие', 'условия', 'условий')}${unbound ? `, ${unbound} без поля` : ''}` : 'проходят все роботы' },
    { id: 'step-count', label: 'Сколько роботов', ok: Boolean(countLocked.value || compileCount()), note: countLocked.value ? 'формула цикла' : compileCount() ? 'формула задана' : 'не задано' },
    { id: 'step-best', label: 'Кто лучший', ok: true, note: setup.rank_key ? attrLabel(setup.rank_key) : 'по цене' },
    { id: 'step-layout', label: 'Схема', ok: setup.layout_items.length > 0, note: setup.layout_items.length ? `${setup.layout_items.length} ${pluralRu(setup.layout_items.length, 'объект', 'объекта', 'объектов')}${setup.layout_items_default ? ', по умолчанию' : ''}` : 'роботы не ездят' },
  ]
})
const jump = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })

/* ---------- создание ---------- */
const createProcess = async () => {
  if (!creating.value?.name.trim()) return
  try {
    const setup = await platformSend<Setup>('/admin/processes', 'POST', { name: creating.value.name, objects: creating.value.objects })
    creating.value = null
    processes.value = await platformGet<ProcItem[]>('/admin/processes')
    dirty.value = false
    await open(setup.code)
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось создать процесс') }
  }
}
const toggleNewObject = (code: string) => {
  if (!creating.value) return
  const set = new Set(creating.value.objects)
  if (set.has(code)) set.delete(code); else set.add(code)
  creating.value.objects = [...set]
}
const formatSite = (value: unknown) => (value === null || value === undefined || value === '' ? 'не задано' : typeof value === 'number' ? value.toLocaleString('ru-RU') : String(value))
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Модель подбора" title="Процессы" lead="Процесс отвечает на три вопроса: какие роботы подходят, сколько их нужно и какой лучший. Справа видно, как настройка работает на демо-данных объекта, ещё до сохранения.">
      <UiButton @click="creating = { name: '', objects: [] }"><template #icon><PhPlus :size="16" weight="bold" /></template>Новый процесс</UiButton>
    </AdminHead>
    <UiCallout v-if="notice" :tone="notice.ok ? 'ok' : 'danger'">{{ notice.text }}</UiCallout>

    <section v-if="creating" class="glass glass-xl a-panel">
      <div class="h3">Новый процесс</div>
      <label class="a-fld"><span class="caption">Название</span><input v-model="creating.name" class="input" placeholder="Например, Доставка белья"></label>
      <div class="a-fld">
        <span class="caption">У каких объектов</span>
        <div class="checks">
          <button v-for="obj in allObjects" :key="obj.code" type="button" class="check" :class="{ on: creating.objects.includes(obj.code) }" @click="toggleNewObject(obj.code)">
            <PhCheckSquare v-if="creating.objects.includes(obj.code)" :size="18" weight="fill" /><PhSquare v-else :size="18" />{{ obj.name }}
          </button>
        </div>
      </div>
      <p class="caption">Роботов процессу назначают на странице «Список продуктов» или в карточке продукта.</p>
      <div class="a-row">
        <UiButton :disabled="!creating.name.trim()" @click="createProcess">Создать</UiButton>
        <UiButton variant="secondary" @click="creating = null">Отмена</UiButton>
      </div>
    </section>

    <div class="layout">
      <aside class="glass a-list plist">
        <input v-model="listQuery" class="input find" placeholder="Поиск процессов">
        <template v-for="group in listGroups" :key="group.name">
          <div class="a-sub">{{ group.name }}</div>
          <button v-for="item in group.items" :key="`${group.name}-${item.code}`" type="button" class="a-item" :class="{ on: item.code === selected }" @click="open(item.code)">
            <span class="body-sm strong">{{ item.name }}</span>
            <span class="caption">{{ item.product_count }} {{ pluralRu(item.product_count, 'робот', 'робота', 'роботов') }} · {{ item.filter_count }} {{ pluralRu(item.filter_count, 'условие', 'условия', 'условий') }}</span>
            <span v-if="flags(item).length" class="a-chips"><span v-for="flag in flags(item)" :key="flag" class="a-pill warn">{{ flag }}</span></span>
          </button>
        </template>
      </aside>

      <template v-if="draft">
        <div class="editor">
          <section class="glass glass-xl a-panel">
            <div class="a-head">
              <label class="a-fld name"><span class="caption">Название процесса</span><input v-model="draft.name" class="input"></label>
              <div class="save">
                <span v-if="dirty" class="caption warn-t">Есть несохранённые изменения</span>
                <UiButton :disabled="saving" @click="save">{{ saving ? 'Сохраняем…' : 'Сохранить' }}</UiButton>
              </div>
            </div>
            <div class="a-chips">
              <span class="caption">Объекты:</span>
              <NuxtLink v-for="obj in draft.objects" :key="obj.code" :to="`/admin/objects?code=${obj.code}`" class="a-pill ok">{{ obj.name }}</NuxtLink>
              <span v-if="!draft.objects.length" class="a-pill warn">не привязан — в подбор не попадает</span>
              <span class="caption sep">Роботов:</span>
              <NuxtLink :to="`/admin/coverage?process=${draft.code}`" class="a-pill" :class="{ warn: !draft.product_count }">{{ draft.product_count }} · открыть список</NuxtLink>
            </div>
          </section>

          <!-- 1. Условия -->
          <section id="step-filters" class="glass glass-xl a-panel">
            <div>
              <div class="h3">1. Условия подбора</div>
              <p class="caption">Каждое условие сравнивает характеристику робота с величиной объекта или с числом. Если условий нет, в подбор проходят все роботы процесса.</p>
            </div>
            <div v-for="(filter, index) in filters" :key="filter.id" class="cond">
              <template v-if="filter.locked">
                <div class="a-head">
                  <input v-model="filter.name" class="input cname" aria-label="Название условия">
                  <button type="button" class="a-x" aria-label="Убрать условие" @click="removeFilter(index)"><PhTrash :size="16" /></button>
                </div>
                <p class="caption">Условие задано формулой, которую фраза не повторяет: <span class="mono-sm">{{ filter.locked }}</span></p>
                <div><UiButton size="sm" variant="secondary" @click="unlockFilter(filter)">Собрать фразой заново</UiButton></div>
              </template>
              <template v-else>
                <div class="a-head">
                  <input v-model="filter.name" class="input cname" aria-label="Название условия" placeholder="Коротко: Проезд, Груз">
                  <button type="button" class="a-x" aria-label="Убрать условие" @click="removeFilter(index)"><PhTrash :size="16" /></button>
                </div>
                <div class="phrase">
                  <span class="w">Робот подходит, если</span>
                  <select v-model="filter.robot_key" class="select attr" aria-label="Характеристика робота">
                    <option value="">характеристика робота</option>
                    <optgroup v-if="attrsHere.length" label="Есть у роботов процесса">
                      <option v-for="attr in attrsHere" :key="attr.key" :value="attr.key">{{ attr.label }} · {{ attr.on_process }}</option>
                    </optgroup>
                    <optgroup v-if="attrsElse.length" label="Есть только у других роботов">
                      <option v-for="attr in attrsElse" :key="`o-${attr.key}`" :value="attr.key">{{ attr.label }} · {{ attr.products }}</option>
                    </optgroup>
                  </select>
                  <select v-model="filter.op" class="select op" aria-label="Сравнение">
                    <option v-for="(word, op) in opWords" :key="op" :value="op">{{ word }}</option>
                  </select>
                  <span class="side">
                    <button type="button" :class="{ on: filter.side === 'value' }" @click="setSide(filter, 'value')">величины объекта</button>
                    <button type="button" :class="{ on: filter.side === 'number' }" @click="setSide(filter, 'number')">числа</button>
                  </span>
                  <input v-if="filter.side === 'value'" v-model="filter.input_label" class="input val" placeholder="название величины: Ширина проезда">
                  <input v-else v-model="filter.number" class="input input-mono num" inputmode="decimal" placeholder="54">
                </div>
                <div class="phrase">
                  <span class="w">Иначе</span>
                  <select v-model="filter.mode" class="select mode" aria-label="Что делать, если не выполнено">
                    <option value="hard">исключить робота</option>
                    <option value="conditional">оставить с пометкой «требует проверки»</option>
                  </select>
                </div>
                <p v-if="sentence(filter)" class="body-sm said">{{ sentence(filter) }}</p>
                <p v-if="coverageText(filter)" class="caption" :class="{ 'warn-t': draft.product_count && attrCoverage(filter.robot_key) < draft.product_count }">{{ coverageText(filter) }}</p>
                <div v-if="filter.side === 'value' && draft.objects.length" class="binds">
                  <span class="caption">Откуда брать «{{ filter.input_label || 'величину' }}»:</span>
                  <label v-for="obj in draft.objects" :key="obj.code" class="bind" :class="{ miss: !obj.bindings[filter.input_key] }">
                    <span class="body-sm strong">{{ obj.name }}</span>
                    <select v-model="obj.bindings[filter.input_key]" class="select">
                      <option :value="undefined">поле не задано</option>
                      <option v-for="field in obj.fields" :key="field.key" :value="field.key">{{ fieldText(field) }}</option>
                    </select>
                  </label>
                  <span v-if="draft.objects.some((obj) => !obj.bindings[filter.input_key])" class="caption warn-t">Где поле не задано, условие не проверяется и робот получает «уточнить».</span>
                </div>
              </template>
            </div>
            <div class="a-block">
              <div class="a-row">
                <UiButton size="sm" variant="secondary" @click="addFilter"><template #icon><PhPlus :size="14" weight="bold" /></template>Пустое условие</UiButton>
              </div>
              <div class="a-chips">
                <span class="caption">Готовые:</span>
                <button v-for="item in templates" :key="item.title" type="button" class="a-pill ok tpl" @click="addTemplate(item)"><PhPlus :size="12" weight="bold" /> {{ item.title }}</button>
              </div>
            </div>
          </section>

          <!-- 2. Количество -->
          <section id="step-count" class="glass glass-xl a-panel">
            <div>
              <div class="h3">2. Сколько роботов нужно</div>
              <p class="body-sm said">{{ countSentence }}</p>
            </div>
            <div v-if="countLocked" class="a-block">
              <p class="caption">Формулу цикла или обхода блоки не повторяют, поэтому она показана как есть и при сохранении не упростится.</p>
              <p class="mono-sm formula">{{ countLocked }}</p>
              <div><UiButton size="sm" variant="secondary" @click="unlockCount">Собрать заново из блоков</UiButton></div>
            </div>
            <template v-else>
              <div class="chain">
                <template v-for="(piece, index) in pieces" :key="piece.id">
                  <select v-if="index > 0" v-model="joins[index - 1]" class="select jn" aria-label="Действие">
                    <option value="+">+</option><option value="-">−</option><option value="*">×</option><option value="/">÷</option>
                  </select>
                  <div class="chip">
                    <select v-model="piece.kind" class="select kind" aria-label="Что это">
                      <option value="site">Поле объекта</option>
                      <option value="attr">Характеристика робота</option>
                      <option value="num">Число</option>
                    </select>
                    <select v-if="piece.kind === 'attr'" v-model="piece.key" class="select">
                      <option value="">выберите</option>
                      <optgroup v-if="attrsHere.length" label="Есть у роботов процесса">
                        <option v-for="attr in attrsHere" :key="attr.key" :value="attr.key">{{ attr.label }} · {{ attr.on_process }}</option>
                      </optgroup>
                      <optgroup v-if="attrsElse.length" label="Есть у других">
                        <option v-for="attr in attrsElse" :key="`c-${attr.key}`" :value="attr.key">{{ attr.label }}</option>
                      </optgroup>
                    </select>
                    <select v-else-if="piece.kind === 'site'" v-model="piece.key" class="select">
                      <option value="">поле объекта</option>
                      <option v-for="field in siteFields" :key="field.key" :value="field.key">{{ fieldText(field) }}</option>
                    </select>
                    <input v-else v-model="piece.value" class="input input-mono num" inputmode="decimal" placeholder="0">
                    <button type="button" class="a-x" aria-label="Убрать блок" @click="removePiece(index)">×</button>
                  </div>
                </template>
              </div>
              <div class="a-row">
                <UiButton size="sm" variant="secondary" @click="addPiece('site')">+ Поле объекта</UiButton>
                <UiButton size="sm" variant="secondary" @click="addPiece('attr')">+ Характеристика робота</UiButton>
                <UiButton size="sm" variant="secondary" @click="addPiece('num')">+ Число</UiButton>
                <label class="a-fld narrow"><span class="caption">Округление</span>
                  <select v-model="wrap" class="select">
                    <option value="">как получилось</option><option value="ceil">вверх до целого</option><option value="floor">вниз до целого</option><option value="round">до ближайшего</option>
                  </select>
                </label>
              </div>
              <p v-if="compileCount()" class="caption">Формула: <span class="mono-sm">{{ compileCount() }}</span></p>
              <p class="caption">Из текста характеристики берётся первое число: «1 200 м²/ч» считается как 1 200. Поле объекта в формуле подставляется у каждого объекта процесса само.</p>
            </template>
          </section>

          <!-- 3. Лучший -->
          <section id="step-best" class="glass glass-xl a-panel">
            <div>
              <div class="h3">3. Кто лучший</div>
              <p class="caption">В сравнение по умолчанию попадает первый среди подошедших. Если характеристика не выбрана — дешевле, затем по названию.</p>
            </div>
            <div class="a-row">
              <label class="a-fld"><span class="caption">Сравнивать по</span>
                <select v-model="draft.rank_key" class="select">
                  <option value="">цене, затем названию</option>
                  <optgroup v-if="attrsHere.length" label="Есть у роботов процесса">
                    <option v-for="attr in attrsHere" :key="attr.key" :value="attr.key">{{ attr.label }} · {{ attr.on_process }}</option>
                  </optgroup>
                </select>
              </label>
              <label class="a-fld narrow"><span class="caption">Лучше, когда</span>
                <select v-model="draft.rank_order" class="select" :disabled="!draft.rank_key">
                  <option value="asc">меньше</option><option value="desc">больше</option>
                </select>
              </label>
            </div>
          </section>

          <!-- 4. Схема -->
          <section id="step-layout" class="glass glass-xl a-panel">
            <div>
              <div class="h3">4. Схема для визуализации</div>
              <p class="caption">Что процессу нужно на схеме объекта. Роли читает модель движения: откуда робот берёт груз, куда везёт, где заряжается. Порядок меняется перетаскиванием за ручку.</p>
            </div>
            <UiCallout v-if="draft.layout_items_default" tone="info">Показан набор по умолчанию. После сохранения он станет настройкой этого процесса.</UiCallout>
            <div
              v-for="(row, index) in draft.layout_items"
              :key="row.key"
              class="litem"
              :class="{ dragging: dragIndex === index }"
              @dragover.prevent
              @drop="onDrop(index)"
            >
              <span class="handle" draggable="true" title="Перетащить" @dragstart="dragIndex = index" @dragend="dragIndex = null"><PhDotsSixVertical :size="18" weight="bold" /></span>
              <div class="lbody">
                <div class="a-row">
                  <label class="a-fld"><span class="caption">Название на схеме</span><input v-model="row.label" class="input"></label>
                  <label class="a-fld"><span class="caption">Роль в модели</span>
                    <select v-model="row.role" class="select" @change="onRole(row)">
                      <option v-for="(label, role) in dictionary.roles" :key="role" :value="role">{{ label }}</option>
                    </select>
                  </label>
                  <label class="a-fld narrow"><span class="caption">Минимум, шт.</span><input v-model.number="row.min_count" class="input input-mono" type="number" min="0"></label>
                </div>
                <label class="a-fld"><span class="caption">Подсказка пользователю</span><input v-model="row.hint" class="input" placeholder="Что это и куда ставить"></label>
                <details class="more">
                  <summary class="caption">Дополнительно: вид, авторасстановка, ключ</summary>
                  <div class="a-row">
                    <label class="a-fld narrow"><span class="caption">Вид</span>
                      <select v-model="row.shape" class="select"><option v-for="(label, shape) in dictionary.shapes" :key="shape" :value="shape">{{ label }}</option></select>
                    </label>
                    <label class="a-fld"><span class="caption">Сколько ставить автоматически</span>
                      <select v-model="row.count_rule" class="select"><option v-for="(label, rule) in dictionary.count_rules" :key="rule" :value="rule">{{ label }}</option></select>
                    </label>
                    <label class="a-fld narrow"><span class="caption">Ключ</span><input v-model="row.key" class="input input-mono"></label>
                  </div>
                </details>
              </div>
              <button type="button" class="a-x" aria-label="Убрать объект схемы" @click="draft.layout_items.splice(index, 1)"><PhTrash :size="16" /></button>
            </div>
            <div class="a-row">
              <UiButton size="sm" variant="secondary" @click="addItem"><template #icon><PhPlus :size="14" weight="bold" /></template>Объект на схеме</UiButton>
              <span class="caption">Без объектов процесс на схеме виден, но роботы по нему не ездят.</span>
            </div>
          </section>
        </div>

        <aside class="rail">
          <nav class="glass a-panel steps" aria-label="Шаги настройки">
            <button v-for="step in steps" :key="step.id" type="button" class="step" @click="jump(step.id)">
              <component :is="step.ok ? PhCheckCircle : PhWarningCircle" :size="18" weight="fill" :class="step.ok ? 'ok' : 'warn'" />
              <span><span class="body-sm strong">{{ step.label }}</span><span class="caption block">{{ step.note }}</span></span>
            </button>
          </nav>

          <section class="glass a-panel pv">
            <div class="a-head">
              <div class="h4">Проверка на примере</div>
              <span v-if="previewBusy" class="caption">считаем…</span>
            </div>
            <label v-if="draft.objects.length" class="a-fld"><span class="caption">Демо-данные объекта</span>
              <select v-model="previewObject" class="select">
                <option v-for="obj in draft.objects" :key="obj.code" :value="obj.code">{{ obj.name }}</option>
              </select>
            </label>
            <p v-else class="caption">Привяжите процесс к объекту, чтобы проверить его на данных объекта.</p>
            <p v-if="previewError" class="caption warn-t">{{ previewError }}</p>
            <template v-if="preview">
              <div class="tally">
                <div v-for="key in ['pass', 'conditional', 'unknown', 'fail']" :key="key" class="t" :class="verdictTone[key]">
                  <span class="mono-lg">{{ preview.tally[key] ?? 0 }}</span>
                  <span class="caption">{{ verdictLabel[key] }}</span>
                </div>
              </div>
              <p v-if="preview.best_product_id" class="caption">Лучший: <span class="strong">{{ preview.robots.find((r) => r.product_id === preview!.best_product_id)?.name }}</span></p>
              <div v-if="preview.reasons.length" class="reasons">
                <div class="caption">Почему отсеялись и что уточнить</div>
                <div v-for="item in preview.reasons.slice(0, 6)" :key="`${item.verdict}-${item.reason}`" class="reason">
                  <span class="a-pill" :class="verdictTone[item.verdict]">{{ verdictLabel[item.verdict] }}</span>
                  <span class="body-sm">{{ item.reason }}</span>
                  <span class="mono-sm">{{ item.count }}</span>
                </div>
              </div>
              <details class="more">
                <summary class="caption">Значения объекта в проверке</summary>
                <div v-for="(value, key) in preview.site" :key="key" class="kv"><span class="caption">{{ siteLabel(String(key)) }}</span><span class="mono-sm">{{ formatSite(value) }}</span></div>
              </details>
              <button type="button" class="link body-sm" @click="showRobots = !showRobots">
                <component :is="showRobots ? PhCaretDown : PhCaretRight" :size="12" weight="bold" /> {{ showRobots ? 'Скрыть роботов' : 'Показать роботов' }}
              </button>
              <div v-if="showRobots" class="robots">
                <div v-for="robot in preview.robots" :key="robot.product_id" class="robot">
                  <div class="a-head">
                    <NuxtLink :to="`/admin/products/${robot.slug}`" class="body-sm strong">{{ robot.name }}</NuxtLink>
                    <span class="a-pill" :class="verdictTone[robot.verdict]">{{ verdictLabel[robot.verdict] }}</span>
                  </div>
                  <span v-if="robot.count != null" class="caption">Нужно: {{ robot.count }} шт.</span>
                  <span v-else-if="robot.count_note" class="caption">Количество: {{ robot.count_note }}</span>
                  <span v-for="note in robot.notes" :key="note" class="caption block">{{ note }}</span>
                </div>
                <NuxtLink :to="`/admin/coverage?process=${draft.code}`" class="link body-sm">Все роботы процесса <PhArrowSquareOut :size="12" /></NuxtLink>
              </div>
            </template>
          </section>
        </aside>
      </template>
    </div>
  </div>
</template>

<style scoped>
.layout { display: grid; grid-template-columns: 260px minmax(0, 1fr) 300px; gap: var(--space-5); align-items: start; }
.plist .find { position: sticky; top: 0; z-index: 2; }
.editor { display: grid; gap: var(--space-5); min-width: 0; }
.rail { position: sticky; top: 96px; display: grid; gap: var(--space-4); max-height: calc(100vh - 110px); overflow: auto; }
.name { max-width: 460px; }
.save { display: flex; gap: 12px; align-items: center; }
.warn-t { color: var(--state-warn); }
.sep { margin-left: 10px; }
.checks { display: flex; flex-wrap: wrap; gap: 8px; }
.check { display: inline-flex; align-items: center; gap: 8px; min-height: 36px; padding: 0 12px; border-radius: 10px; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px var(--border-hairline); font-weight: 600; font-size: 14px; }
.check svg { color: var(--ink-faint); }
.check.on { box-shadow: inset 0 0 0 1px var(--brand-400); background: #fff; }
.check.on svg { color: var(--brand-600); }
.cond { display: grid; gap: 10px; padding: 14px; border-radius: 14px; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px var(--border-hairline); }
.cname { max-width: 320px; font-weight: 700; }
.phrase { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.phrase .w { font-weight: 600; color: var(--ink-strong); font-size: 15px; }
.phrase .attr { flex: 1 1 220px; min-width: 200px; }
.phrase .op { width: 140px; }
.phrase .val { flex: 1 1 220px; min-width: 200px; }
.phrase .num { width: 110px; }
.phrase .mode { flex: 0 1 340px; }
.side { display: inline-flex; padding: 3px; border-radius: 10px; background: rgba(15, 20, 19, 0.05); }
.side button { padding: 6px 10px; border-radius: 8px; font-size: 13.5px; font-weight: 600; color: var(--ink-muted); }
.side button.on { background: #fff; color: var(--ink-strong); box-shadow: 0 1px 2px rgba(15, 20, 19, 0.1); }
.said { color: var(--ink-body); padding: 8px 12px; border-radius: 10px; background: var(--surface-brand-tint); }
.binds { display: grid; gap: 6px; }
.bind { display: grid; grid-template-columns: 140px minmax(0, 1fr); gap: 10px; align-items: center; padding: 4px 8px; border-radius: 10px; }
.bind.miss { background: var(--state-warn-tint); }
.tpl { cursor: pointer; }
.chain { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.chip { display: flex; gap: 8px; align-items: center; padding: 8px; border-radius: 14px; background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); }
.kind { width: 200px; }
.jn { width: 70px; }
.num { width: 100px; }
.formula { word-break: break-all; padding: 10px; border-radius: 10px; background: rgba(15, 20, 19, 0.04); }
.litem { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 10px; align-items: start; padding: 12px; border-radius: 14px; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px var(--border-hairline); }
.litem.dragging { opacity: 0.5; }
.handle { cursor: grab; color: var(--ink-faint); padding: 6px 2px; }
.lbody { display: grid; gap: 10px; }
.more summary { cursor: pointer; }
.more[open] { display: grid; gap: 10px; }
.steps { gap: 4px; }
.step { display: grid; grid-template-columns: auto 1fr; gap: 10px; align-items: start; text-align: left; padding: 8px; border-radius: 10px; }
.step:hover { background: rgba(15, 20, 19, 0.04); }
.step .ok { color: var(--brand-600); }
.step .warn { color: var(--state-warn); }
.block { display: block; }
.tally { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.t { display: grid; gap: 2px; padding: 10px; border-radius: 12px; background: rgba(15, 20, 19, 0.04); }
.t.ok { background: var(--surface-brand-tint); }
.t.warn { background: var(--state-warn-tint); }
.t.danger { background: var(--state-danger-tint); }
.reasons { display: grid; gap: 6px; }
.reason { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 8px; align-items: center; }
.kv { display: flex; justify-content: space-between; gap: 8px; }
.robots { display: grid; gap: 10px; }
.robot { display: grid; gap: 2px; padding-top: 8px; border-top: 1px solid var(--border-hairline); }
.link { display: inline-flex; gap: 4px; align-items: center; }
@media (max-width: 1400px) {
  .layout { grid-template-columns: 240px minmax(0, 1fr); }
  .rail { grid-column: 2; position: static; max-height: none; }
}
@media (max-width: 1100px) {
  .layout { grid-template-columns: 1fr; }
  .rail { grid-column: auto; }
}
</style>
