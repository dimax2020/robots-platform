<script setup lang="ts">
import { PhPlus, PhTrash, PhArrowUp, PhArrowDown, PhCaretDown, PhCaretRight, PhWarningCircle, PhCheckSquare, PhSquare, PhArrowSquareOut } from '@phosphor-icons/vue'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { fetchErrorMessage } from '~/utils/errors'
import { fieldKindLabel, pluralRu } from '~/data/adminLabels'
import { replaceQuery } from '~/composables/useQuerySync'

definePageMeta({ layout: 'admin', middleware: 'admin', pageTransition: false })
useHead({ title: 'Админка · Объекты' })

interface SiteField { key: string; label: string; unit: string; kind: string; min: number | null; max: number | null; hint: string; objects?: number }
interface ObjectField extends SiteField { base_label: string; group: string; required: boolean; default: number | boolean | string | null; source: string }
interface Input { key: string; label: string; kind: 'filter' | 'count'; filter: string }
interface Proc { code: string; name: string; product_count: number; enabled: boolean; inputs: Input[]; bindings: Record<string, string> }
interface Setup { code: string; name: string; industries: string[]; fields: ObjectField[]; projects: number; processes: Proc[] }
interface Overview { code: string; name: string; fields: number; processes: number; unbound: number; projects: number }

const route = useRoute()
const list = ref<Overview[]>([])
const industries = ref<{ code: string; name: string }[]>([])
const dictionary = ref<SiteField[]>([])
const draft = ref<Setup | null>(null)
const selected = ref('')
const tab = ref('fields')
const notice = ref<{ ok: boolean; text: string } | null>(null)
const saving = ref(false)
const dirty = ref(false)
const expanded = reactive(new Set<string>())
const fieldQuery = ref('')
const processQuery = ref('')
const creating = ref<{ name: string; industries: string[]; copy: string } | null>(null)
const newField = ref<SiteField | null>(null)

const enabled = computed(() => draft.value?.processes.filter((item) => item.enabled) ?? [])
const unboundOf = (proc: Proc) => proc.inputs.filter((input) => !proc.bindings[input.key])
const unboundTotal = computed(() => enabled.value.reduce((sum, proc) => sum + unboundOf(proc).length, 0))
const tabs = computed(() => [
  { id: 'fields', label: 'Поля расчёта', count: draft.value?.fields.length ?? 0 },
  { id: 'processes', label: 'Процессы объекта', count: enabled.value.length },
  { id: 'bindings', label: 'Привязка величин', count: unboundTotal.value },
])
const groups = computed(() => {
  const map = new Map<string, ObjectField[]>()
  for (const field of draft.value?.fields ?? []) map.set(field.group || 'Без группы', [...(map.get(field.group || 'Без группы') ?? []), field])
  return [...map.entries()].map(([name, items]) => ({ name, items }))
})
const groupNames = computed(() => [...new Set((draft.value?.fields ?? []).map((item) => item.group).filter(Boolean))])
const available = computed(() => {
  const taken = new Set((draft.value?.fields ?? []).map((item) => item.key))
  const text = fieldQuery.value.trim().toLowerCase()
  return dictionary.value.filter((item) => !taken.has(item.key) && (!text || `${item.label} ${item.key}`.toLowerCase().includes(text))).slice(0, 12)
})
const addable = computed(() => {
  const text = processQuery.value.trim().toLowerCase()
  return (draft.value?.processes ?? []).filter((item) => !item.enabled && (!text || `${item.name} ${item.code}`.toLowerCase().includes(text)))
})
const boundKeys = computed(() => {
  const keys = new Set<string>()
  for (const proc of enabled.value) for (const value of Object.values(proc.bindings)) if (value) keys.add(value)
  return keys
})
const fieldText = (field: { label: string; unit: string }) => (field.unit ? `${field.label}, ${field.unit}` : field.label)
const dictLabel = (key: string) => dictionary.value.find((item) => item.key === key)?.label ?? key

const loadList = async () => {
  const [items, tree, fields] = await Promise.all([
    platformGet<Overview[]>('/admin/objects'),
    platformGet<{ industries: { code: string; name: string }[] }>('/catalog/tree'),
    platformGet<SiteField[]>('/admin/site-fields'),
  ])
  list.value = items
  industries.value = tree.industries
  dictionary.value = fields
}

const open = async (code: string) => {
  if (dirty.value && !confirm('Есть несохранённые изменения. Перейти без сохранения?')) return
  selected.value = code
  notice.value = null
  const setup = await platformGet<Setup>(`/admin/objects/${code}`)
  for (const proc of setup.processes) for (const input of proc.inputs) if (proc.bindings[input.key] == null) proc.bindings[input.key] = ''
  draft.value = setup
  expanded.clear()
  dirty.value = false
  replaceQuery({ code })
}

onMounted(async () => {
  try {
    await loadList()
    const wanted = typeof route.query.code === 'string' ? route.query.code : list.value[0]?.code
    if (wanted) await open(wanted)
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось загрузить объекты') }
  }
})
watch(draft, () => { dirty.value = true }, { deep: true, flush: 'sync' })

const toggleIndustry = (code: string) => {
  if (!draft.value) return
  const set = new Set(draft.value.industries)
  if (set.has(code)) set.delete(code); else set.add(code)
  draft.value.industries = [...set]
}

const addField = (field: SiteField) => {
  if (!draft.value) return
  draft.value.fields.push({ ...field, base_label: field.label, group: groupNames.value.at(-1) ?? '', required: false, default: null, source: '' })
  expanded.add(field.key)
  fieldQuery.value = ''
}
const removeField = (index: number) => {
  const field = draft.value?.fields[index]
  if (!field || !draft.value) return
  if (boundKeys.value.has(field.key) && !confirm(`Поле «${field.label}» подставляется в процессы. Убрать его из объекта? Привязка останется, но в форме проекта поле пропадёт.`)) return
  draft.value.fields.splice(index, 1)
}
const moveField = (index: number, step: number) => {
  const rows = draft.value?.fields
  if (!rows) return
  const target = index + step
  if (target < 0 || target >= rows.length) return
  const [row] = rows.splice(index, 1)
  rows.splice(target, 0, row!)
}
const indexOf = (field: ObjectField) => draft.value?.fields.indexOf(field) ?? -1
const toggleRow = (key: string) => { if (expanded.has(key)) expanded.delete(key); else expanded.add(key) }
const setDefault = (field: ObjectField, raw: string) => {
  const text = raw.trim()
  if (!text) { field.default = null; return }
  if (field.kind === 'number' || field.kind === 'int') {
    const value = Number(text.replace(/\s/g, '').replace(',', '.'))
    field.default = Number.isFinite(value) ? (field.kind === 'int' ? Math.round(value) : value) : null
    return
  }
  field.default = text
}
const defaultText = (field: ObjectField) => {
  if (field.default === null || field.default === undefined || field.default === '') return 'не задано'
  if (typeof field.default === 'boolean') return field.default ? 'да' : 'нет'
  if (typeof field.default === 'number') return `${field.default.toLocaleString('ru-RU')}${field.unit ? ` ${field.unit}` : ''}`
  return String(field.default)
}

const saveDictField = async (field: ObjectField) => {
  try {
    const saved = await platformSend<SiteField>('/admin/site-fields', 'POST', { key: field.key, label: field.base_label || field.label, unit: field.unit, kind: field.kind, min: field.min, max: field.max, hint: field.hint })
    dictionary.value = dictionary.value.map((item) => (item.key === saved.key ? { ...item, ...saved } : item))
    notice.value = { ok: true, text: `Общие свойства поля «${saved.label}» сохранены для всех объектов` }
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось сохранить поле') }
  }
}
const startNewField = () => { newField.value = { key: '', label: fieldQuery.value.trim(), unit: '', kind: 'number', min: null, max: null, hint: '' } }
const createField = async () => {
  if (!newField.value) return
  try {
    const saved = await platformSend<SiteField>('/admin/site-fields', 'POST', { ...newField.value, key: null })
    dictionary.value.push({ ...saved, objects: 0 })
    addField(saved)
    newField.value = null
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось создать поле') }
  }
}

const suggestion = (input: Input) => {
  const text = input.label.toLowerCase()
  return (draft.value?.fields ?? []).find((field) => {
    const label = field.label.toLowerCase()
    return label === text || label.includes(text) || text.includes(label)
  })
}

const save = async () => {
  if (!draft.value || saving.value) return
  saving.value = true
  notice.value = null
  const bindings = []
  for (const proc of draft.value.processes) {
    for (const input of proc.inputs) {
      const siteKey = proc.bindings[input.key]
      if (siteKey) bindings.push({ process_code: proc.code, input_key: input.key, site_key: siteKey })
    }
  }
  try {
    const setup = await platformSend<Setup>(`/admin/objects/${draft.value.code}/setup`, 'PUT', {
      name: draft.value.name,
      industries: draft.value.industries,
      fields: draft.value.fields.map((field) => ({
        key: field.key,
        label: field.label === field.base_label ? '' : field.label,
        group: field.group,
        required: field.required,
        default: field.default,
        source: field.source,
      })),
      processes: draft.value.processes.filter((item) => item.enabled).map((item) => item.code),
      bindings,
    })
    for (const proc of setup.processes) for (const input of proc.inputs) if (proc.bindings[input.key] == null) proc.bindings[input.key] = ''
    draft.value = setup
    await nextTick()
    dirty.value = false
    notice.value = { ok: true, text: 'Объект сохранён. Форма параметров новых проектов строится по этим полям.' }
    list.value = await platformGet<Overview[]>('/admin/objects')
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось сохранить') }
  } finally {
    saving.value = false
  }
}

const createObject = async () => {
  if (!creating.value?.name.trim()) return
  try {
    const setup = await platformSend<Setup>('/admin/objects/new', 'POST', {
      name: creating.value.name, industries: creating.value.industries, copy_fields_from: creating.value.copy || null,
    })
    creating.value = null
    list.value = await platformGet<Overview[]>('/admin/objects')
    dirty.value = false
    await open(setup.code)
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось создать объект') }
  }
}
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Модель подбора" title="Объекты" lead="Объект задаёт форму параметров проекта и набор процессов. Процесс может быть у нескольких объектов, а какое поле площадки подставлять в его условия, решает каждый объект сам.">
      <UiButton @click="creating = { name: '', industries: [], copy: '' }"><template #icon><PhPlus :size="16" weight="bold" /></template>Новый объект</UiButton>
    </AdminHead>
    <UiCallout v-if="notice" :tone="notice.ok ? 'ok' : 'danger'">{{ notice.text }}</UiCallout>

    <section v-if="creating" class="glass glass-xl a-panel">
      <div class="h3">Новый объект</div>
      <div class="a-row">
        <label class="a-fld"><span class="caption">Название</span><input v-model="creating.name" class="input" placeholder="Например, Торговый центр"></label>
        <label class="a-fld"><span class="caption">Взять набор полей у объекта</span>
          <select v-model="creating.copy" class="select">
            <option value="">начать с пустого списка</option>
            <option v-for="item in list" :key="item.code" :value="item.code">{{ item.name }} · {{ item.fields }} полей</option>
          </select>
        </label>
      </div>
      <div class="a-fld">
        <span class="caption">Отрасли</span>
        <div class="checks">
          <button v-for="industry in industries" :key="industry.code" type="button" class="check" :class="{ on: creating.industries.includes(industry.code) }" @click="creating.industries = creating.industries.includes(industry.code) ? creating.industries.filter((c) => c !== industry.code) : [...creating.industries, industry.code]">
            <PhCheckSquare v-if="creating.industries.includes(industry.code)" :size="18" weight="fill" /><PhSquare v-else :size="18" />{{ industry.name }}
          </button>
        </div>
      </div>
      <p class="caption">Значения по умолчанию и источники не копируются: у нового объекта свои данные.</p>
      <div class="a-row">
        <UiButton :disabled="!creating.name.trim()" @click="createObject">Создать</UiButton>
        <UiButton variant="secondary" @click="creating = null">Отмена</UiButton>
      </div>
    </section>

    <div class="a-split">
      <aside class="glass a-list">
        <button v-for="item in list" :key="item.code" type="button" class="a-item" :class="{ on: item.code === selected }" @click="open(item.code)">
          <span class="body-sm strong">{{ item.name }}</span>
          <span class="caption">{{ item.fields }} полей · {{ item.processes }} {{ pluralRu(item.processes, 'процесс', 'процесса', 'процессов') }}</span>
          <span v-if="item.unbound" class="a-pill warn">{{ item.unbound }} не привязано</span>
        </button>
      </aside>

      <section v-if="draft" class="glass glass-xl a-panel">
        <div class="a-head">
          <label class="a-fld name"><span class="caption">Название объекта</span><input v-model="draft.name" class="input"></label>
          <div class="save">
            <span v-if="dirty" class="caption warn-t">Есть несохранённые изменения</span>
            <UiButton :disabled="saving" @click="save">{{ saving ? 'Сохраняем…' : 'Сохранить' }}</UiButton>
          </div>
        </div>
        <div class="a-fld">
          <span class="caption">Отрасли</span>
          <div class="checks">
            <button v-for="industry in industries" :key="industry.code" type="button" class="check" :class="{ on: draft.industries.includes(industry.code) }" @click="toggleIndustry(industry.code)">
              <PhCheckSquare v-if="draft.industries.includes(industry.code)" :size="18" weight="fill" /><PhSquare v-else :size="18" />{{ industry.name }}
            </button>
          </div>
        </div>
        <p class="caption">Проектов на этом объекте: {{ draft.projects }}. Уже созданные проекты список процессов не меняют.</p>

        <UiTabs v-model="tab" :tabs="tabs" />

        <!-- Поля расчёта -->
        <div v-if="tab === 'fields'" class="pane">
          <p class="caption">По этим полям строится форма «Параметры объекта» в проекте. Значение по умолчанию и источник показываются рядом с полем (ТЗ 3.2.5), границы проверяются при вводе (ТЗ 3.2.4).</p>
          <div v-for="group in groups" :key="group.name" class="grp">
            <div class="a-sub">{{ group.name }}</div>
            <div v-for="field in group.items" :key="field.key" class="frow" :class="{ open: expanded.has(field.key) }">
              <div class="fline">
                <button type="button" class="ftg" @click="toggleRow(field.key)">
                  <component :is="expanded.has(field.key) ? PhCaretDown : PhCaretRight" :size="14" weight="bold" />
                  <span class="body-sm strong">{{ field.label }}</span>
                  <span v-if="field.unit" class="caption">{{ field.unit }}</span>
                </button>
                <span class="fmeta">
                  <span v-if="field.required" class="a-pill ok">обязательное</span>
                  <span class="caption">{{ defaultText(field) }}</span>
                  <span v-if="!field.source" class="a-pill warn">нет источника</span>
                  <span v-if="boundKeys.has(field.key)" class="a-pill">в условиях</span>
                </span>
                <span class="facts">
                  <button type="button" class="a-x" :disabled="indexOf(field) === 0" aria-label="Выше" @click="moveField(indexOf(field), -1)"><PhArrowUp :size="14" /></button>
                  <button type="button" class="a-x" aria-label="Ниже" @click="moveField(indexOf(field), 1)"><PhArrowDown :size="14" /></button>
                  <button type="button" class="a-x" :aria-label="`Убрать ${field.label}`" @click="removeField(indexOf(field))"><PhTrash :size="14" /></button>
                </span>
              </div>
              <div v-if="expanded.has(field.key)" class="fedit">
                <div class="a-row">
                  <label class="a-fld"><span class="caption">Подпись в этом объекте</span><input v-model="field.label" class="input" :placeholder="field.base_label"></label>
                  <label class="a-fld"><span class="caption">Группа на форме</span><input v-model="field.group" class="input" list="object-groups"></label>
                  <label class="req"><input v-model="field.required" type="checkbox"> <span class="body-sm">обязательное</span></label>
                </div>
                <div class="a-row">
                  <label class="a-fld narrow">
                    <span class="caption">По умолчанию{{ field.unit ? `, ${field.unit}` : '' }}</span>
                    <select v-if="field.kind === 'bool'" class="select" :value="field.default === true ? 'true' : field.default === false ? 'false' : ''" @change="field.default = ($event.target as HTMLSelectElement).value === '' ? null : ($event.target as HTMLSelectElement).value === 'true'">
                      <option value="">не задано</option><option value="true">Да</option><option value="false">Нет</option>
                    </select>
                    <input v-else class="input" :class="{ 'input-mono': field.kind !== 'text' }" :value="field.default ?? ''" placeholder="не задано" @change="setDefault(field, ($event.target as HTMLInputElement).value)">
                  </label>
                  <label class="a-fld"><span class="caption">Источник значения по умолчанию</span><input v-model="field.source" class="input" placeholder="Лист «Склад», строка… или обоснование допущения"></label>
                </div>
                <details class="dict">
                  <summary class="caption">Общие свойства поля для всех объектов: ключ <span class="mono-sm">{{ field.key }}</span>, тип, границы</summary>
                  <div class="a-row">
                    <label class="a-fld"><span class="caption">Базовая подпись</span><input v-model="field.base_label" class="input"></label>
                    <label class="a-fld narrow"><span class="caption">Единица</span><input v-model="field.unit" class="input"></label>
                    <label class="a-fld narrow"><span class="caption">Тип</span>
                      <select v-model="field.kind" class="select"><option v-for="(label, kind) in fieldKindLabel" :key="kind" :value="kind">{{ label }}</option></select>
                    </label>
                    <label class="a-fld narrow"><span class="caption">Минимум</span><input v-model.number="field.min" class="input input-mono" type="number"></label>
                    <label class="a-fld narrow"><span class="caption">Максимум</span><input v-model.number="field.max" class="input input-mono" type="number"></label>
                  </div>
                  <label class="a-fld"><span class="caption">Обоснование границ</span><input v-model="field.hint" class="input"></label>
                  <div><UiButton size="sm" variant="secondary" @click="saveDictField(field)">Сохранить общие свойства</UiButton></div>
                </details>
              </div>
            </div>
          </div>
          <datalist id="object-groups"><option v-for="name in groupNames" :key="name" :value="name" /></datalist>

          <div class="a-block">
            <div class="h4">Добавить поле</div>
            <input v-model="fieldQuery" class="input" placeholder="Найти в справочнике полей: лифт, температура, шум">
            <div class="a-chips">
              <button v-for="item in available" :key="item.key" type="button" class="a-pill ok add" @click="addField(item)"><PhPlus :size="12" weight="bold" /> {{ fieldText(item) }}</button>
              <button type="button" class="a-pill add" @click="startNewField"><PhPlus :size="12" weight="bold" /> Новое поле{{ fieldQuery.trim() ? ` «${fieldQuery.trim()}»` : '' }}</button>
            </div>
            <div v-if="newField" class="newf">
              <div class="a-row">
                <label class="a-fld"><span class="caption">Подпись</span><input v-model="newField.label" class="input" placeholder="Число лифтов"></label>
                <label class="a-fld narrow"><span class="caption">Единица</span><input v-model="newField.unit" class="input" placeholder="шт"></label>
                <label class="a-fld narrow"><span class="caption">Тип</span>
                  <select v-model="newField.kind" class="select"><option v-for="(label, kind) in fieldKindLabel" :key="kind" :value="kind">{{ label }}</option></select>
                </label>
                <label class="a-fld narrow"><span class="caption">Минимум</span><input v-model.number="newField.min" class="input input-mono" type="number"></label>
                <label class="a-fld narrow"><span class="caption">Максимум</span><input v-model.number="newField.max" class="input input-mono" type="number"></label>
              </div>
              <label class="a-fld"><span class="caption">Обоснование границ</span><input v-model="newField.hint" class="input" placeholder="Почему именно такие минимум и максимум"></label>
              <p class="caption">Ключ поля для формул создаётся из подписи латиницей. Поле попадёт в общий справочник и станет доступно другим объектам.</p>
              <div class="a-row">
                <UiButton size="sm" :disabled="!newField.label.trim()" @click="createField">Создать и добавить</UiButton>
                <UiButton size="sm" variant="secondary" @click="newField = null">Отмена</UiButton>
              </div>
            </div>
          </div>
        </div>

        <!-- Процессы -->
        <div v-else-if="tab === 'processes'" class="pane">
          <p class="caption">Процессы, которые пользователь увидит в проекте этого объекта. Условия подбора, формула количества и схема настраиваются у самого процесса.</p>
          <div v-for="proc in enabled" :key="proc.code" class="pcard">
            <div>
              <div class="body-sm strong">{{ proc.name }}</div>
              <div class="caption">{{ proc.product_count }} {{ pluralRu(proc.product_count, 'робот', 'робота', 'роботов') }} · {{ proc.inputs.length }} {{ pluralRu(proc.inputs.length, 'величина', 'величины', 'величин') }}</div>
            </div>
            <span v-if="unboundOf(proc).length" class="a-pill warn"><PhWarningCircle :size="12" weight="fill" /> {{ unboundOf(proc).length }} не привязано</span>
            <span class="pacts">
              <UiButton size="sm" variant="secondary" :to="`/admin/processes?code=${proc.code}`">Настроить процесс</UiButton>
              <button type="button" class="a-x" :aria-label="`Убрать ${proc.name}`" @click="proc.enabled = false"><PhTrash :size="16" /></button>
            </span>
          </div>
          <p v-if="!enabled.length" class="body-sm muted">У объекта нет процессов: подбор в его проектах будет пустым.</p>
          <div class="a-block">
            <div class="h4">Добавить процесс</div>
            <input v-model="processQuery" class="input" placeholder="Найти процесс: уборка, паллеты, патруль">
            <div class="a-chips">
              <button v-for="proc in addable.slice(0, 16)" :key="proc.code" type="button" class="a-pill ok add" @click="proc.enabled = true"><PhPlus :size="12" weight="bold" /> {{ proc.name }} · {{ proc.product_count }}</button>
            </div>
            <p class="caption">Нужного процесса нет? Создайте его на странице <NuxtLink to="/admin/processes" class="link">Процессы</NuxtLink>.</p>
          </div>
        </div>

        <!-- Привязка величин -->
        <div v-else class="pane">
          <p class="caption">Процесс спрашивает величины: «ширина проезда», «масса груза». Здесь для каждой выбирается поле площадки этого объекта. Непривязанная величина в фильтре даёт роботу «требует проверки», в формуле количества — количество не считается.</p>
          <div v-for="proc in enabled.filter((item) => item.inputs.length)" :key="proc.code" class="a-block">
            <div class="a-head">
              <div class="h4">{{ proc.name }}</div>
              <NuxtLink :to="`/admin/processes?code=${proc.code}`" class="link body-sm">к процессу <PhArrowSquareOut :size="12" /></NuxtLink>
            </div>
            <div v-for="input in proc.inputs" :key="input.key" class="brow" :class="{ miss: !proc.bindings[input.key] }">
              <div class="bname">
                <span class="body-sm strong">{{ input.label }}</span>
                <span class="caption">{{ input.kind === 'count' ? 'в формуле количества' : `в условии «${input.filter}»` }}</span>
              </div>
              <span class="arrow">→</span>
              <div class="bpick">
                <select v-model="proc.bindings[input.key]" class="select">
                  <option value="">поле не задано</option>
                  <option v-for="field in draft.fields" :key="field.key" :value="field.key">{{ fieldText(field) }}</option>
                  <option v-if="proc.bindings[input.key] && !draft.fields.some((f) => f.key === proc.bindings[input.key])" :value="proc.bindings[input.key]">{{ dictLabel(proc.bindings[input.key]!) }} (нет в полях объекта)</option>
                </select>
                <span v-if="!proc.bindings[input.key]" class="caption warn-t">
                  {{ input.kind === 'count' ? 'Количество роботов не посчитается.' : 'Роботы получат «требует проверки».' }}
                  <button v-if="suggestion(input)" type="button" class="link" @click="proc.bindings[input.key] = suggestion(input)!.key">Подставить «{{ suggestion(input)!.label }}»</button>
                </span>
              </div>
            </div>
          </div>
          <p v-if="!enabled.some((item) => item.inputs.length)" class="body-sm muted">У процессов объекта нет величин: их задают условия подбора и формула количества на странице процесса.</p>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.name { max-width: 420px; }
.save { display: flex; gap: 12px; align-items: center; }
.warn-t { color: var(--state-warn); }
.checks { display: flex; flex-wrap: wrap; gap: 8px; }
.check { display: inline-flex; align-items: center; gap: 8px; min-height: 36px; padding: 0 12px; border-radius: 10px; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px var(--border-hairline); font-weight: 600; font-size: 14px; }
.check svg { color: var(--ink-faint); }
.check.on { box-shadow: inset 0 0 0 1px var(--brand-400); background: #fff; }
.check.on svg { color: var(--brand-600); }
.pane { display: grid; gap: var(--space-4); }
.grp { display: grid; gap: 4px; }
.frow { border-radius: 12px; }
.frow.open { background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px var(--border-hairline); }
.fline { display: grid; grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr) auto; gap: 10px; align-items: center; min-height: 40px; padding: 0 6px; }
.ftg { display: inline-flex; gap: 8px; align-items: center; text-align: left; min-width: 0; }
.fmeta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.facts { display: inline-flex; gap: 2px; }
.fedit { display: grid; gap: 12px; padding: 4px 12px 14px 30px; }
.req { display: inline-flex; gap: 8px; align-items: center; min-height: 44px; }
.dict { display: grid; gap: 10px; padding: 10px 12px; border-radius: 10px; background: rgba(15, 20, 19, 0.03); }
.dict[open] { gap: 12px; }
.dict summary { cursor: pointer; }
.add { cursor: pointer; }
.newf { display: grid; gap: 12px; padding: 14px; border-radius: 12px; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px var(--border-hairline); }
.pcard { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 12px; align-items: center; padding: 12px 14px; border-radius: 12px; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px var(--border-hairline); }
.pacts { display: inline-flex; gap: 6px; align-items: center; }
.brow { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1.2fr); gap: 12px; align-items: center; padding: 8px 10px; border-radius: 10px; }
.brow.miss { background: var(--state-warn-tint); }
.bname { display: grid; gap: 2px; }
.bpick { display: grid; gap: 4px; }
.arrow { color: var(--ink-faint); font-weight: 700; }
@media (max-width: 1100px) {
  .fline, .brow { grid-template-columns: 1fr; }
  .arrow { display: none; }
}
</style>
