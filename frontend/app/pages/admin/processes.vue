<script setup lang="ts">
import { platformGet, platformSend } from '~/composables/usePlatform'
import { siteFieldMeta } from '~/data/siteFields'

definePageMeta({ layout: 'admin' })
useHead({ title: 'Админка · Процессы' })

interface Input { key: string; label: string }
interface Filter {
  name: string
  mode: string
  robot_key: string
  op: string
  input_key: string
  inputs: Input[]
  formula: string
}
interface Piece { id: number; kind: 'attr' | 'site' | 'num'; key: string; label: string; value: string }
interface RobotAttr { key: string; label: string; products: number; on_process: number }
interface Setup {
  code: string
  name: string
  filters: Filter[]
  count_inputs: Input[]
  count_formula: string
  rank_key: string
  rank_order: string
  objects: { code: string; name: string; bindings: Record<string, string> }[]
}
interface Proc { code: string; name: string; product_count: number }

const processes = ref<Proc[]>([])
const robotAttrs = ref<RobotAttr[]>([])
const draft = ref<Setup | null>(null)
const notice = ref('')
const saving = ref(false)
const selected = ref('')
const tab = ref('filters')
const listQuery = ref('')
const attrQuery = ref('')
const siteQuery = ref('')
const wrap = ref('')
const countLocked = ref('')
const pieces = ref<Piece[]>([])
const joins = ref<string[]>([])
let pieceSeq = 1

const fields = siteFieldMeta.map((field) => ({ key: field.key, label: field.plain || field.label, unit: field.unit || '' }))
const fieldText = (field: { label: string; unit: string }) => (field.unit ? `${field.label} · ${field.unit}` : field.label)
const attrLabel = (key: string) => robotAttrs.value.find((item) => item.key === key)?.label || key
const paneTabs = computed(() => [
  { id: 'filters', label: 'Фильтры', count: draft.value?.filters.length ?? 0 },
  { id: 'count', label: 'Количество роботов' },
  { id: 'best', label: 'Лучший робот' },
])
const shownProcesses = computed(() => {
  const query = listQuery.value.trim().toLowerCase()
  if (!query) return processes.value
  return processes.value.filter((item) => `${item.name} ${item.code}`.toLowerCase().includes(query))
})
const pickedAttrKeys = computed(() => {
  const keys = new Set<string>()
  if (draft.value?.rank_key) keys.add(draft.value.rank_key)
  for (const filter of draft.value?.filters ?? []) if (filter.robot_key) keys.add(filter.robot_key)
  for (const piece of pieces.value) if (piece.kind === 'attr' && piece.key) keys.add(piece.key)
  return keys
})
const shownAttrs = computed(() => {
  const query = attrQuery.value.trim().toLowerCase()
  const matches = (item: RobotAttr) => `${item.label} ${item.key}`.toLowerCase().includes(query)
  if (!query) {
    const common = robotAttrs.value.filter((item) => item.on_process > 0).slice(0, 12)
    const picked = robotAttrs.value.filter((item) => pickedAttrKeys.value.has(item.key) && !common.some((row) => row.key === item.key))
    const here = [...common, ...picked.filter((item) => item.on_process > 0)]
    const rest = picked.filter((item) => item.on_process === 0)
    return { here, rest }
  }
  const list = robotAttrs.value.filter((item) => matches(item) || pickedAttrKeys.value.has(item.key))
  return { here: list.filter((item) => item.on_process > 0), rest: list.filter((item) => item.on_process === 0) }
})
const pickedSiteKeys = computed(() => {
  const keys = new Set<string>()
  for (const object of draft.value?.objects ?? []) {
    for (const value of Object.values(object.bindings)) if (value) keys.add(value)
  }
  for (const piece of pieces.value) if (piece.kind === 'site' && piece.key) keys.add(piece.key)
  return keys
})
const shownFields = computed(() => {
  const query = siteQuery.value.trim().toLowerCase()
  return fields.filter((field) => pickedSiteKeys.value.has(field.key) || !query || `${field.label} ${field.key}`.toLowerCase().includes(query))
})
const countSentence = computed(() => {
  if (!pieces.value.length) return ''
  const word = (piece: Piece) => {
    if (piece.kind === 'attr') return piece.key ? attrLabel(piece.key) : 'характеристика'
    if (piece.kind === 'num') return piece.value || 'число'
    const field = fields.find((item) => item.key === piece.key)
    return field ? field.label : 'параметр объекта'
  }
  const sign: Record<string, string> = { '+': '+', '-': '−', '*': '×', '/': '÷' }
  let text = word(pieces.value[0])
  for (let index = 1; index < pieces.value.length; index += 1) text += ` ${sign[joins.value[index - 1]] || '÷'} ${word(pieces.value[index])}`
  if (wrap.value === 'ceil') return `Округление вверх: ${text}`
  if (wrap.value === 'floor') return `Округление вниз: ${text}`
  if (wrap.value === 'round') return `До ближайшего целого: ${text}`
  return text
})

const parseFilter = (formula: string, inputs: Input[]) => {
  const match = formula.trim().match(/^(?:robot\.)?([A-Za-z_][\w]*)\s*(<=|>=|==|!=|<|>)\s*([A-Za-z_][\w]*)$/)
  return {
    robot_key: match?.[1] || '',
    op: match?.[2] || '>=',
    input_key: match?.[3] || inputs[0]?.key || '',
  }
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
    wrap.value = wrapped[1]
    body = wrapped[2]
  }
  const labels = new Map(inputs.map((item) => [item.key, item.label]))
  const nextPieces: Piece[] = []
  const nextJoins: string[] = []
  for (const part of body.split(/\s*(\+|-|\*|\/)\s*/).filter(Boolean)) {
    if (part === '+' || part === '-' || part === '*' || part === '/') {
      nextJoins.push(part)
      continue
    }
    if (part.startsWith('robot.') && /^robot\.[A-Za-z_][\w]*$/.test(part)) nextPieces.push({ id: pieceSeq++, kind: 'attr', key: part.slice(6), label: '', value: '' })
    else if (/^\d+(?:\.\d+)?$/.test(part)) nextPieces.push({ id: pieceSeq++, kind: 'num', key: '', label: '', value: part })
    else if (/^[A-Za-z_][\w]*$/.test(part)) nextPieces.push({ id: pieceSeq++, kind: 'site', key: part, label: labels.get(part) || attrLabel(part), value: '' })
    else {
      countLocked.value = text
      return
    }
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
  let body = tokens[0]
  for (let index = 1; index < tokens.length; index += 1) body += ` ${joins.value[index - 1] || '/'} ${tokens[index]}`
  return wrap.value ? `${wrap.value}(${body})` : body
}

const loadList = async () => {
  const tree = await platformGet<{ processes: Proc[] }>('/catalog/tree')
  processes.value = tree.processes
  if (!selected.value && processes.value[0]) await open(processes.value[0].code)
}

const open = async (code: string) => {
  selected.value = code
  tab.value = 'filters'
  attrQuery.value = ''
  robotAttrs.value = await platformGet<RobotAttr[]>(`/admin/robot-attributes?process=${code}`)
  draft.value = await platformGet<Setup>(`/admin/processes/${code}`)
  draft.value.filters = draft.value.filters.map((filter) => ({ ...filter, ...parseFilter(filter.formula, filter.inputs) }))
  applyCount(draft.value.count_formula, draft.value.count_inputs)
  for (const piece of pieces.value) if (piece.kind === 'site' && piece.key) onSiteKey(piece)
  notice.value = ''
}

const addFilter = () => {
  draft.value?.filters.push({ name: 'Новый фильтр', mode: 'hard', robot_key: '', op: '>=', input_key: `v${pieceSeq++}`, inputs: [], formula: '' })
}
const unlockCount = () => {
  countLocked.value = ''
  pieces.value = []
  joins.value = []
  wrap.value = ''
}
const addPiece = (kind: Piece['kind']) => {
  countLocked.value = ''
  if (pieces.value.length) joins.value.push('/')
  const key = ''
  pieces.value.push({ id: pieceSeq++, kind, key, label: kind === 'site' ? 'Параметр объекта' : '', value: '' })
}
const removePiece = (index: number) => {
  pieces.value.splice(index, 1)
  if (index === 0) joins.value.shift()
  else joins.value.splice(index - 1, 1)
}
const onSiteKey = (piece: Piece) => {
  const field = fields.find((item) => item.key === piece.key)
  piece.label = field?.label || piece.key
}

const save = async () => {
  if (!draft.value) return
  saving.value = true
  notice.value = ''
  try {
    draft.value = await platformSend<Setup>(`/admin/processes/${draft.value.code}/setup`, 'PUT', {
      filters: draft.value.filters.filter((item) => item.name.trim() && item.robot_key).map((item, index) => {
        const key = item.input_key || `v${index}`
        return { name: item.name, mode: item.mode, inputs: [{ key, label: attrLabel(item.robot_key) }], formula: `robot.${item.robot_key} ${item.op} ${key}` }
      }),
      count_inputs: countLocked.value ? draft.value.count_inputs : pieces.value.filter((piece) => piece.kind === 'site' && piece.key).map((piece) => ({ key: piece.key, label: piece.label || attrLabel(piece.key) })),
      count_formula: countLocked.value || compileCount(),
      rank_key: draft.value.rank_key,
      rank_order: draft.value.rank_order,
    })
    draft.value.filters = draft.value.filters.map((filter) => ({ ...filter, ...parseFilter(filter.formula, filter.inputs) }))
    applyCount(draft.value.count_formula, draft.value.count_inputs)
    notice.value = 'Настройка сохранена'
  } catch (err) {
    notice.value = err instanceof Error ? err.message : 'Не удалось сохранить'
  } finally {
    saving.value = false
  }
}

onMounted(() => { void loadList().catch((err) => { notice.value = String(err) }) })
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Процессы" title="Настройка процессов" lead="Фильтр сравнивает характеристику робота с величиной. Какое поле объекта в неё подставлять, задаётся на вкладке объектов. Формула количества считает, сколько роботов нужно." />
    <UiCallout v-if="notice" :tone="notice === 'Настройка сохранена' ? 'ok' : 'danger'">{{ notice }}</UiCallout>

    <div class="split">
      <aside class="glass list">
        <input v-model="listQuery" class="input find" placeholder="Поиск процессов">
        <button v-for="process in shownProcesses" :key="process.code" type="button" class="proc" :class="{ on: process.code === selected }" @click="open(process.code)">
          <span class="body-sm strong">{{ process.name }}</span>
          <span class="caption">{{ process.product_count }} роботов</span>
        </button>
      </aside>

      <div v-if="draft" class="editor">
        <section class="glass glass-xl panel">
          <div class="in">
            <div class="head">
              <div>
                <div class="h3">{{ draft.name }}</div>
                <div class="caption">{{ draft.filters.length }} фильтров</div>
              </div>
              <UiButton size="sm" :disabled="saving" @click="save">{{ saving ? 'Сохраняем…' : 'Сохранить' }}</UiButton>
            </div>
            <UiTabs v-model="tab" :tabs="paneTabs" />

            <div v-if="tab === 'filters'" class="pane">
              <label class="fld"><span class="caption">Характеристика робота</span><input v-model="attrQuery" class="input" placeholder="проезд, шум, производительность"></label>
              <p class="caption">В списке — самые частые характеристики роботов этого процесса. Введите слово, чтобы открыть остальные и весь каталог.</p>
              <div v-for="(filter, index) in draft.filters" :key="filter.input_key || index" class="block">
                <div class="row">
                  <label class="fld"><span class="caption">Название</span><input v-model="filter.name" class="input"></label>
                  <label class="fld narrow"><span class="caption">Режим</span>
                    <select v-model="filter.mode" class="select">
                      <option value="hard">Жёсткий отказ</option>
                      <option value="conditional">С условием</option>
                    </select>
                  </label>
                  <UiButton size="sm" variant="secondary" @click="draft.filters.splice(index, 1)">Убрать</UiButton>
                </div>
                <div class="row">
                  <label class="fld"><span class="caption">Характеристика робота</span>
                    <select v-model="filter.robot_key" class="select">
                      <option value="">выберите</option>
                      <optgroup v-if="shownAttrs.here.length" label="У роботов этого процесса">
                        <option v-for="attr in shownAttrs.here" :key="attr.key" :value="attr.key">{{ attr.label }} · {{ attr.on_process }}</option>
                      </optgroup>
                      <optgroup v-if="shownAttrs.rest.length" label="У остальных роботов">
                        <option v-for="attr in shownAttrs.rest" :key="`all-${attr.key}`" :value="attr.key">{{ attr.label }} · {{ attr.products }}</option>
                      </optgroup>
                    </select>
                  </label>
                  <label class="fld narrow"><span class="caption">Сравнение</span>
                    <select v-model="filter.op" class="select">
                      <option value=">=">робот ≥ параметр</option>
                      <option value=">">робот &gt; параметр</option>
                      <option value="<=">робот ≤ параметр</option>
                      <option value="<">робот &lt; параметр</option>
                      <option value="==">робот = параметр</option>
                    </select>
                  </label>
                </div>
              </div>
              <UiButton size="sm" variant="secondary" @click="addFilter">Фильтр</UiButton>
            </div>

            <div v-else-if="tab === 'count'" class="pane">
              <div v-if="countLocked" class="block">
                <p class="caption">Количество задано формулой цикла или обхода. Блоки её не повторяют, чтобы сохранение не упростило расчёт.</p>
                <p class="caption">{{ countLocked }}</p>
                <UiButton size="sm" variant="secondary" @click="unlockCount">Собрать заново</UiButton>
              </div>
              <template v-else>
              <div class="row">
                <label class="fld"><span class="caption">Характеристика робота</span><input v-model="attrQuery" class="input" placeholder="производительность, время работы"></label>
                <label class="fld"><span class="caption">Параметр объекта</span><input v-model="siteQuery" class="input" placeholder="площадь, смена"></label>
              </div>
              <p class="caption">Из текста берётся первое число, если строка сама число или рядом есть единица. «1 200 м²/ч» считается как 1 200. «4 режима» числом не считается, и количество для такого робота не показывается.</p>
              <label class="fld narrow"><span class="caption">Округление</span>
                <select v-model="wrap" class="select">
                  <option value="">как получилось</option>
                  <option value="ceil">вверх до целого</option>
                  <option value="floor">вниз до целого</option>
                  <option value="round">до ближайшего целого</option>
                </select>
              </label>
              <div class="chain">
                <template v-for="(piece, index) in pieces" :key="piece.id">
                  <select v-if="index > 0" v-model="joins[index - 1]" class="select op" aria-label="Операция">
                    <option value="+">+</option>
                    <option value="-">−</option>
                    <option value="*">×</option>
                    <option value="/">÷</option>
                  </select>
                  <div class="chip">
                    <select v-model="piece.kind" class="select kind">
                      <option value="attr">Характеристика</option>
                      <option value="site">Параметр объекта</option>
                      <option value="num">Число</option>
                    </select>
                    <select v-if="piece.kind === 'attr'" v-model="piece.key" class="select">
                      <option value="">выберите</option>
                      <optgroup v-if="shownAttrs.here.length" label="У роботов этого процесса">
                        <option v-for="attr in shownAttrs.here" :key="attr.key" :value="attr.key">{{ attr.label }} · {{ attr.on_process }}</option>
                      </optgroup>
                      <optgroup v-if="shownAttrs.rest.length" label="У остальных">
                        <option v-for="attr in shownAttrs.rest" :key="`c-${attr.key}`" :value="attr.key">{{ attr.label }} · {{ attr.products }}</option>
                      </optgroup>
                    </select>
                    <select v-else-if="piece.kind === 'site'" v-model="piece.key" class="select" @change="onSiteKey(piece)">
                      <option value="">параметр площадки</option>
                      <option v-for="field in shownFields" :key="field.key" :value="field.key">{{ fieldText(field) }}</option>
                    </select>
                    <input v-else v-model="piece.value" class="input num" inputmode="decimal" placeholder="0">
                    <button type="button" class="x" aria-label="Убрать блок" @click="removePiece(index)">×</button>
                  </div>
                </template>
              </div>
              <div class="row">
                <UiButton size="sm" variant="secondary" @click="addPiece('site')">Параметр объекта</UiButton>
                <UiButton size="sm" variant="secondary" @click="addPiece('attr')">Характеристика</UiButton>
                <UiButton size="sm" variant="secondary" @click="addPiece('num')">Число</UiButton>
              </div>
              <p v-if="countSentence" class="caption">{{ countSentence }}</p>
              <p v-if="compileCount()" class="caption">Формула: {{ compileCount() }}</p>
              </template>
            </div>

            <div v-else class="pane">
              <label class="fld"><span class="caption">Характеристика робота</span><input v-model="attrQuery" class="input" placeholder="производительность, цена"></label>
              <p class="caption">В корзину попадает первый среди прошедших фильтр. Пустая характеристика значит: меньше цена, затем название. Если у робота в тексте есть единица измерения, сравнивается первое число.</p>
              <div class="row">
                <label class="fld"><span class="caption">Характеристика</span>
                  <select v-model="draft.rank_key" class="select">
                    <option value="">Ниже цена, затем название</option>
                    <optgroup v-if="shownAttrs.here.length" label="У роботов этого процесса">
                      <option v-for="attr in shownAttrs.here" :key="attr.key" :value="attr.key">{{ attr.label }} · {{ attr.on_process }}</option>
                    </optgroup>
                    <optgroup v-if="shownAttrs.rest.length" label="У остальных роботов">
                      <option v-for="attr in shownAttrs.rest" :key="`rank-${attr.key}`" :value="attr.key">{{ attr.label }} · {{ attr.products }}</option>
                    </optgroup>
                  </select>
                </label>
                <label class="fld narrow"><span class="caption">Порядок</span>
                  <select v-model="draft.rank_order" class="select">
                    <option value="asc">Меньше лучше</option>
                    <option value="desc">Больше лучше</option>
                  </select>
                </label>
              </div>
            </div>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.split { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: var(--space-5); align-items: start; }
.list { padding: 8px; display: grid; gap: 6px; max-height: 70vh; overflow: auto; }
.find { position: sticky; top: 0; z-index: 2; }
.list > *:not(.find) { position: relative; z-index: 1; }
.proc { display: grid; gap: 2px; text-align: left; padding: 10px 12px; border-radius: 14px; background: rgba(255, 255, 255, 0.55); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.proc.on { background: #fff; box-shadow: inset 0 0 0 1px var(--brand-400); }
.proc .body-sm { color: var(--ink-strong); }
.editor { display: grid; gap: var(--space-5); }
.panel { overflow: hidden; }
.in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: var(--space-4); }
.head, .row { display: flex; gap: 12px; align-items: end; justify-content: space-between; flex-wrap: wrap; }
.block { display: grid; gap: 10px; padding-top: 12px; border-top: 1px solid var(--border-hairline); }
.inputs { display: grid; gap: 8px; }
.fld { display: grid; gap: 6px; flex: 1; min-width: 180px; }
.pane { display: grid; gap: var(--space-4); }
.kind { width: 180px; }
.chain { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.chip { display: flex; gap: 8px; align-items: center; padding: 8px; border-radius: 14px; background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); }
.op { width: 72px; }
.num { width: 96px; }
.x { width: 32px; height: 32px; border-radius: 8px; color: var(--ink-muted); }
.x:hover { background: var(--state-danger-tint); color: var(--state-danger); }
.select, .input { width: 100%; }
@media (max-width: 1100px) { .split { grid-template-columns: 1fr; } }
</style>
