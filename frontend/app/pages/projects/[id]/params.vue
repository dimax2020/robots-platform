<script setup lang="ts">
import { PhPencilSimple, PhArrowRight, PhSparkle, PhCopy, PhDownloadSimple, PhUploadSimple } from '@phosphor-icons/vue'
import { objectTypeLabel, isFullPath, type ObjectType } from '~/data/projects'
import { fieldSources, labelProcess, processLabel, processesByObject, siteFieldMeta, warehouseDatasetGroups } from '~/data/siteFields'
import { fetchErrorMessage } from '~/utils/errors'
import { downloadBytes, downloadText } from '~/utils/exportTables'
import { parseCell, parseTables, readImportTables, TASK_COLUMNS, templateCsv, templateSheets, templateXlsx, type ImportField } from '~/utils/siteImport'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { asObjectType, useLiveProject } from '~/composables/useLiveProject'
import { useDemoProjects } from '~/composables/useDemoProjects'
import type { ApiSiteProfile, ApiTask } from '~/types/api'

interface FormField {
  key: string
  label: string
  unit: string
  kind: 'number' | 'int' | 'bool' | 'text'
  min: number | null
  max: number | null
  hint: string
  group: string
  required: boolean
  default: number | boolean | string | null
  source: string
}

const route = useRoute()
const router = useRouter()
const id = computed(() => route.params.id as string)
const doc = useLiveProject(id)
const project = doc.shell
const shell = doc.shell
const pending = doc.pending
const error = doc.error
const live = computed(() => Boolean(project.value))
const readonly = doc.readonly
const { role } = useRole()
const demos = useDemoProjects()
const detail = computed(() => doc.record.value
  ? { id: doc.record.value.id, object_type_code: doc.record.value.object_code, site: doc.record.value.site, tasks: doc.record.value.tasks }
  : null)
useHead({ title: () => `Параметры · ${shell.value?.name ?? 'проект'}` })

const objectType = computed<ObjectType>(() => asObjectType(detail.value?.object_type_code ?? shell.value?.objectType ?? 'warehouse'))
const sources = computed(() => fieldSources[objectType.value] ?? {})

const emptySite = (code: string): ApiSiteProfile => ({
  object_type_code: code,
  area_m2: null,
  free_m2: null,
  aisle_width_m: null,
  temp_min_c: null,
  temp_max_c: null,
  shifts_per_day: 1,
  shift_hours: 8,
  days_year: 250,
  staff_salary_year_rub: null,
  energy_tariff_rub_kwh: null,
  budget_rub: null,
  clean_area_m2: null,
  pallet_places: null,
  storage_height_m: null,
  floor_load_kg_m2: null,
  floor_flatness_mm: null,
  peak_factor: 1,
  power_kw: null,
  noise_limit_dba: null,
  has_wms: null,
  floors_count: null,
  main_aisle_width_m: null,
  floor_type: null,
  inbound_pallets_per_day: null,
  outbound_pallets_per_day: null,
  pick_lines_per_day: null,
  pick_units_per_day: null,
  piece_pick_share_pct: null,
  sku_count: null,
  sku_a_share_pct: null,
  staff_total: null,
  pickers_count: null,
  forklift_operators: null,
  pack_operators: null,
  picker_salary_month_rub: null,
  forklift_salary_month_rub: null,
  payroll_burden: null,
  picker_lines_per_hour: null,
  time_loss_pct: null,
  picker_route_m: null,
  conveyor_length_m: null,
  rack_type: null,
  pallet_mass_kg: null,
  unit_mass_kg: null,
  pallet_dims_mm: null,
  unit_dims_mm: null,
  oversized_share_pct: null,
  erp_name: null,
  payback_years: null,
})

const emptyTask = (code: string): ApiTask => ({
  process_code: code,
  name: labelProcess(code),
  flow_per_hour: null,
  flow_per_day: null,
  peak_factor: null,
  route_len_m: null,
  max_load_kg: null,
  t_load_s: 0,
  t_unload_s: 0,
  container_types: [],
  staff_fte_now: null,
})

const site = reactive<ApiSiteProfile>(emptySite('warehouse'))
const tasks = ref<ApiTask[]>([])
const hydrated = ref('')

const applyDetail = () => {
  const p = detail.value
  if (!p) return
  Object.assign(site, emptySite(p.object_type_code), p.site)
  tasks.value = (p.tasks as unknown as ApiTask[]).map((t) => ({
    ...emptyTask(t.process_code),
    ...t,
    container_types: [...(t.container_types ?? [])],
  }))
  hydrated.value = String(p.id)
}

watch([detail, () => doc.pending.value], () => {
  if (doc.pending.value) return
  const key = detail.value?.id ?? ''
  if (key && hydrated.value !== String(key)) applyDetail()
}, { immediate: true })

/* «Подставить демо-данные»: параметры опубликованного демо того же типа объекта, иначе значения по умолчанию из полей. */
const demoSource = computed(() => demos.byObject(objectType.value))
const demoFilling = ref(false)
const fillFromDemo = async () => {
  if (readonly.value || demoFilling.value) return
  demoFilling.value = true
  try {
    let values: Record<string, unknown> = {}
    let taskRows: ApiTask[] = []
    let label = ''
    const demo = demoSource.value
    if (demo) {
      const record = await platformGet<{ site: Record<string, unknown>; tasks: Record<string, unknown>[] }>(`/projects/${demo.slug || demo.id}`)
      values = record.site
      taskRows = (record.tasks as unknown as ApiTask[]).map((t) => ({ ...emptyTask(t.process_code), ...t, container_types: [...(t.container_types ?? [])] }))
      label = `демо-объекта «${demo.name}»`
    } else {
      for (const field of formFields.value ?? []) {
        if (field.default !== null && field.default !== undefined && field.default !== '') values[field.key] = field.default
      }
      label = 'по умолчанию из справочника объекта'
    }
    Object.assign(site, emptySite(objectType.value), values)
    if (taskRows.length) tasks.value = taskRows
    clearFieldErrors()
    notice.value = { ok: true, text: `Подставлены параметры ${label}. Проверьте значения и нажмите «${advanceLabel.value}» — тогда они сохранятся.` }
  } catch (e: unknown) {
    notice.value = { ok: false, text: fetchErrorMessage(e, 'Не удалось получить демо-данные') }
  } finally {
    demoFilling.value = false
  }
}

const sameNum = (a: unknown, b: unknown) => {
  if (a == null && b == null) return true
  if (typeof a === 'boolean' || typeof b === 'boolean') return a === b
  if (typeof a === 'number' && typeof b === 'number') return a === b
  return a === b
}

/* Поля формы ведёт админка платформы. Если платформа не ответила, форма собирается из прежнего справочника. */
const formFields = ref<FormField[] | null>(null)
const formFallback = ref(false)
watch(objectType, async (code) => {
  if (!code) return
  try {
    const form = await platformGet<{ fields: FormField[] }>(`/catalog/objects/${code}/fields`)
    formFields.value = form.fields
    formFallback.value = false
  } catch {
    formFields.value = null
    formFallback.value = true
  }
}, { immediate: true })
const fieldMeta = (key: string) => formFields.value?.find((f) => f.key === key)

const siteValue = (key: string) => (site as unknown as Record<string, unknown>)[key]
const profileVal = (key: string) => fieldMeta(key)?.default
const siteEdited = (key: string) => {
  const base = profileVal(key)
  const value = siteValue(key)
  if (base === undefined || base === null) return false
  return !sameNum(value, base)
}
const siteSource = (key: string) => fieldMeta(key)?.source || sources.value[key]
const defaultHint = (f: FormField) => {
  const base = profileVal(f.key)
  if (base === undefined || base === null || base === '') return ''
  if (typeof base === 'boolean') return base ? 'да' : 'нет'
  return typeof base === 'number' ? `${base.toLocaleString('ru-RU')}${f.unit ? ` ${f.unit}` : ''}` : String(base)
}
const rangeHint = (f: FormField) => {
  if (f.min == null && f.max == null) return ''
  if (f.min != null && f.max != null) return `от ${f.min.toLocaleString('ru-RU')} до ${f.max.toLocaleString('ru-RU')}`
  return f.min != null ? `не меньше ${f.min.toLocaleString('ru-RU')}` : `не больше ${f.max!.toLocaleString('ru-RU')}`
}

/** Проверка до отправки: обязательные поля и границы из справочника (ТЗ 3.2.4). Сервер проверяет ещё раз. */
const validateSite = () => {
  for (const k of Object.keys(siteErrors)) delete siteErrors[k]
  for (const f of formFields.value ?? []) {
    const value = siteValue(f.key)
    const empty = value === null || value === undefined || value === ''
    if (empty) {
      if (f.required) siteErrors[f.key] = 'Обязательное поле: укажите значение.'
      continue
    }
    if ((f.kind === 'number' || f.kind === 'int') && typeof value === 'number') {
      if (f.min != null && value < f.min) siteErrors[f.key] = `Меньше допустимого: минимум ${f.min.toLocaleString('ru-RU')}${f.unit ? ` ${f.unit}` : ''}.`
      else if (f.max != null && value > f.max) siteErrors[f.key] = `Больше допустимого: максимум ${f.max.toLocaleString('ru-RU')}${f.unit ? ` ${f.unit}` : ''}.`
    }
  }
  return Object.keys(siteErrors).length === 0
}
const problemLines = () => {
  const fields = formFields.value ?? legacyFields()
  return Object.entries(siteErrors).map(([key, msg]) => `${fields.find((field) => field.key === key)?.label ?? key}: ${msg}`)
}
const taskSource = (process: string, field?: string) =>
  (field && sources.value[`tasks.${process}.${field}`]) || sources.value[`tasks.${process}`]
const taskEdited = (_t: ApiTask, _field: keyof ApiTask) => false

const parseNum = (raw: string, asInt = false): number | null => {
  const t = raw.trim().replace(/\s/g, '').replace(',', '.')
  if (!t) return null
  const n = asInt ? Number.parseInt(t, 10) : Number(t)
  return Number.isFinite(n) ? n : null
}
const setSiteNum = (key: string, raw: string, asInt = false) => {
  ;(site as unknown as Record<string, unknown>)[key] = parseNum(raw, asInt)
}
const setSiteText = (key: string, raw: string) => {
  const t = raw.trim()
  ;(site as unknown as Record<string, unknown>)[key] = t || null
}
const setSiteBool = (key: string, raw: string) => {
  ;(site as unknown as Record<string, unknown>)[key] = raw === '' ? null : raw === 'true'
}
const setTaskNum = (t: ApiTask, key: keyof ApiTask, raw: string, asInt = false) => {
  ;(t as unknown as Record<string, unknown>)[key] = parseNum(raw, asInt)
}
const fmt = (v: number | null | undefined) => (v == null ? '' : String(v))

const addTask = () => {
  const used = new Set(tasks.value.map((t) => t.process_code))
  const next = (processesByObject[objectType.value] ?? []).find((c) => !used.has(c))
    ?? processesByObject[objectType.value]?.[0]
    ?? 'warehouse_logistics'
  tasks.value.push(emptyTask(next))
}
const removeTask = (i: number) => { tasks.value.splice(i, 1) }
const onProcess = (t: ApiTask, code: string) => {
  t.process_code = code
  t.name = labelProcess(code)
}

const saving = ref(false)
const notice = ref<{ ok: boolean; text: string; items?: string[] } | null>(null)
const siteErrors = reactive<Record<string, string>>({})
const taskErrors = reactive<Record<number, Record<string, string>>>({})

const clearFieldErrors = () => {
  for (const k of Object.keys(siteErrors)) delete siteErrors[k]
  for (const k of Object.keys(taskErrors)) delete taskErrors[Number(k)]
}

const fieldErrorCount = computed(() => {
  let n = Object.keys(siteErrors).length
  for (const row of Object.values(taskErrors)) n += Object.keys(row).length
  return n
})

const siteError = (key: string) => siteErrors[key]
const taskError = (i: number, key: string) => taskErrors[i]?.[key]

const applyFieldErrors = (e: unknown): boolean => {
  const detail = (e as { data?: { detail?: unknown } })?.data?.detail
  if (!Array.isArray(detail)) return false
  clearFieldErrors()
  let applied = 0
  for (const raw of detail) {
    const item = raw as { loc?: unknown[]; msg?: string }
    const loc = item.loc
    const msg = item.msg
    if (!Array.isArray(loc) || !msg) continue
    if (loc[0] !== 'body') continue
    if (loc[1] === 'site' && typeof loc[2] === 'string') {
      siteErrors[loc[2]] = msg
      applied += 1
      continue
    }
    if (loc[1] === 'tasks') {
      const idx = typeof loc[2] === 'number' ? loc[2] : Number(loc[2])
      const key = loc[3]
      if (Number.isInteger(idx) && typeof key === 'string') {
        if (!taskErrors[idx]) taskErrors[idx] = {}
        taskErrors[idx]![key] = msg
        applied += 1
      }
    }
  }
  return applied > 0
}

const payload = (): { site: ApiSiteProfile; tasks: ApiTask[] } => ({
  site: { ...site },
  tasks: tasks.value.map((t) => ({
    ...t,
    name: t.name || labelProcess(t.process_code),
    container_types: t.container_types ?? [],
  })),
})

const save = async (quiet = false) => {
  if (!project.value || saving.value || readonly.value) return false
  if (!validateSite()) {
    notice.value = { ok: false, text: 'Сохранить нельзя: часть значений вне допустимых границ.', items: problemLines() }
    focusErrorPane()
    return false
  }
  saving.value = true
  notice.value = null
  try {
    const body = payload()
    await doc.save(body.site as unknown as Record<string, unknown>, body.tasks)
    applyDetail()
    clearFieldErrors()
    if (!quiet) notice.value = { ok: true, text: 'Параметры сохранены' }
    return true
  } catch (e: unknown) {
    if (applyFieldErrors(e)) {
      notice.value = { ok: false, text: 'Сервер не принял часть значений.', items: problemLines() }
      focusErrorPane()
    } else {
      clearFieldErrors()
      notice.value = { ok: false, text: fetchErrorMessage(e, 'Не удалось сохранить') }
    }
    return false
  } finally {
    saving.value = false
  }
}

const part = computed<'object' | 'processes'>(() => route.query.part === 'processes' ? 'processes' : 'object')
const setupRef = ref<{ save: () => Promise<void> } | null>(null)
const substages = computed(() => [
  { id: 'object', label: 'Параметры объекта', to: `/projects/${id.value}/params` },
  { id: 'processes', label: 'Процессы объекта', to: `/projects/${id.value}/params?part=processes` },
])
const advanceLabel = computed(() => part.value === 'object' ? 'К процессам' : 'К подбору')

const advance = async () => {
  if (!project.value || saving.value) return
  if (readonly.value) {
    await router.push(part.value === 'object' ? { path: `/projects/${id.value}/params`, query: { part: 'processes' } } : `/projects/${id.value}/match`)
    return
  }
  if (part.value === 'object') {
    const ok = await save(true)
    if (!ok) return
    await router.push({ path: `/projects/${id.value}/params`, query: { part: 'processes' } })
    return
  }
  const ok = await save(true)
  if (!ok) return
  try {
    await setupRef.value?.save()
  } catch (e: unknown) {
    notice.value = { ok: false, text: fetchErrorMessage(e, 'Не удалось сохранить процессы') }
    return
  }
  await router.push(`/projects/${id.value}/match`)
}

watch(part, async (next, prev) => {
  if (readonly.value) return
  if (prev === 'processes' && next !== 'processes') {
    try { await setupRef.value?.save() } catch { /* кнопка «К подбору» покажет ошибку, если сохранить не вышло */ }
  }
})

onBeforeRouteLeave(async () => {
  if (part.value !== 'processes' || readonly.value) return
  try { await setupRef.value?.save() } catch { return false }
})

/* Копия демо в свои проекты: единственный способ править опубликованное демо не администратору. */
const copying = ref(false)
const copyDemo = async () => {
  if (copying.value) return
  copying.value = true
  try {
    const copy = await platformSend<{ id: string }>(`/projects/${id.value}/copy`, 'POST')
    await router.push(`/projects/${copy.id}/params`)
  } catch (e: unknown) {
    notice.value = { ok: false, text: fetchErrorMessage(e, 'Не удалось скопировать демо') }
  } finally {
    copying.value = false
  }
}
const activeTask = ref(0)

const fieldGroups: { title: string; hint: string; keys: (keyof ApiSiteProfile)[] }[] = [
  {
    title: 'Площадь и геометрия',
    hint: 'Размеры площадки, проезды и пол',
    keys: ['area_m2', 'free_m2', 'clean_area_m2', 'aisle_width_m', 'storage_height_m', 'floor_flatness_mm', 'floor_load_kg_m2', 'pallet_places'],
  },
  {
    title: 'Режим работы',
    hint: 'Смены, календарь, температура и пик',
    keys: ['shifts_per_day', 'shift_hours', 'days_year', 'temp_min_c', 'temp_max_c', 'peak_factor'],
  },
  {
    title: 'Инженерия',
    hint: 'Мощность, шум и учётная система',
    keys: ['power_kw', 'noise_limit_dba', 'has_wms'],
  },
  {
    title: 'Деньги',
    hint: 'Бюджет, фонд оплаты и тариф',
    keys: ['budget_rub', 'staff_salary_year_rub', 'energy_tariff_rub_kwh'],
  },
]

const EXTRA_GROUP = 'Дополнительно'
const legacyField = (f: (typeof siteFieldMeta)[number], group: string): FormField => ({
  key: f.key,
  label: objectType.value === 'warehouse' ? f.label : (f.plain ?? f.label),
  unit: f.unit ?? '',
  kind: f.kind,
  min: null,
  max: null,
  hint: '',
  group,
  required: false,
  default: null,
  source: '',
})
const legacyFields = (): FormField[] => {
  const pick = (keys: (keyof ApiSiteProfile)[], group: string) =>
    keys
      .map((k) => siteFieldMeta.find((f) => f.key === k))
      .filter((f): f is (typeof siteFieldMeta)[number] => Boolean(f))
      .map((f) => legacyField(f, group))
  if (objectType.value === 'warehouse') {
    return [
      ...warehouseDatasetGroups.flatMap((g) => pick(g.keys, g.title)),
      ...siteFieldMeta.filter((f) => f.tier === 'extra').map((f) => legacyField(f, EXTRA_GROUP)),
    ]
  }
  return fieldGroups.flatMap((g) => pick(g.keys, g.title))
}

const groups = computed(() => {
  const fields = formFields.value ?? legacyFields()
  const out: { title: string; hint: string; fields: FormField[]; extra: boolean }[] = []
  for (const f of fields) {
    const title = f.group || 'Параметры'
    let group = out.find((g) => g.title === title)
    if (!group) {
      group = {
        title,
        hint: title === EXTRA_GROUP ? 'Этих параметров нет в исходном листе датасета. Они остаются для расчёта.' : '',
        fields: [],
        extra: title === EXTRA_GROUP,
      }
      out.push(group)
    }
    group.fields.push(f)
  }
  return out
})

const siteErrorCount = computed(() => Object.keys(siteErrors).length)
const currentTask = computed(() => tasks.value[activeTask.value] ?? null)
const taskHasError = (i: number) => Boolean(taskErrors[i] && Object.keys(taskErrors[i]!).length)

const taskSummary = (t: ApiTask) => {
  if (t.flow_per_day != null) return `${t.flow_per_day.toLocaleString('ru-RU')} опер./сутки`
  if (t.flow_per_hour != null) return `${t.flow_per_hour.toLocaleString('ru-RU')} опер./час`
  return 'поток не задан'
}

const importFields = (): ImportField[] => (formFields.value ?? legacyFields()).map((field) => ({
  key: field.key,
  label: field.label,
  unit: field.unit,
  kind: field.kind,
  group: field.group,
}))

const templateOf = () => templateSheets(
  importFields(),
  site as unknown as Record<string, unknown>,
  tasks.value as unknown as Record<string, unknown>[],
)

const downloadTemplate = (kind: 'csv' | 'xlsx') => {
  const sheets = templateOf()
  if (kind === 'csv') downloadText('parametry-ploshchadki.csv', 'text/csv;charset=utf-8', templateCsv(sheets))
  else downloadBytes('parametry-ploshchadki.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', templateXlsx(sheets))
}

const fileRef = ref<HTMLInputElement | null>(null)
const importing = ref(false)
const dragOver = ref(false)
const importFile = async (file: File) => {
  if (readonly.value) return
  const name = file.name.toLowerCase()
  if (!name.endsWith('.csv') && !name.endsWith('.xls') && !name.endsWith('.xlsx')) {
    notice.value = { ok: false, text: 'Нужен файл CSV или Excel (.xlsx, .xls) по шаблону с этого экрана.' }
    return
  }
  importing.value = true
  try {
    const parsed = parseTables(await readImportTables(await file.arrayBuffer(), file.name), importFields())
    const fields = importFields()
    let applied = 0
    const skipped: string[] = []
    for (const item of parsed.site) {
      const field = fields.find((row) => row.key === item.key)
      if (!field) continue
      const value = parseCell(item.raw, field.kind)
      if (value === null) {
        skipped.push(`${field.label}: в файле «${item.raw}». ${field.kind === 'bool' ? 'Нужно «да» или «нет».' : 'Число не разобрано.'}`)
        continue
      }
      ;(site as unknown as Record<string, unknown>)[item.key] = value
      applied += 1
    }
    const byCode = new Map(tasks.value.map((task) => [task.process_code, task]))
    let taskCount = 0
    for (const row of parsed.tasks) {
      const named = Object.entries(processLabel).find(([, label]) => label.toLowerCase() === (row.name ?? '').trim().toLowerCase())
      const code = row.process_code?.trim() || named?.[0] || ''
      if (!code) continue
      const task = byCode.get(code) ?? emptyTask(code)
      if (!byCode.has(code)) {
        tasks.value.push(task)
        byCode.set(code, task)
      }
      if (row.name) task.name = row.name
      for (const col of TASK_COLUMNS) {
        if (col.kind !== 'number' || !row[col.key]) continue
        const value = parseCell(row[col.key]!, 'number')
        if (typeof value === 'number') (task as unknown as Record<string, unknown>)[col.key] = value
      }
      taskCount += 1
    }
    if (!applied && !taskCount && !skipped.length) {
      notice.value = { ok: false, text: 'В файле нет значений по шаблону. Скачайте шаблон и заполните столбец «Значение».' }
      return
    }
    clearFieldErrors()
    const valid = validateSite()
    const unknown = parsed.unknown.filter(Boolean).slice(0, 4)
    const tail = unknown.length ? ` Не распознаны строки: ${unknown.join(', ')}.` : ''
    const items = [...problemLines(), ...skipped]
    if (!valid || skipped.length) {
      notice.value = {
        ok: false,
        text: `Файл прочитан: параметров ${applied}${taskCount ? `, процессов ${taskCount}` : ''}. Сохранить нельзя, пока значения не попадут в допустимые границы.${tail}`,
        items,
      }
      focusErrorPane()
      return
    }
    notice.value = {
      ok: true,
      text: `Из файла прочитано параметров: ${applied}${taskCount ? `, процессов: ${taskCount}` : ''}. Проверьте значения и нажмите «${advanceLabel.value}», чтобы сохранить.${tail}`,
    }
  } catch {
    notice.value = { ok: false, text: 'Файл не разобран. Скачайте шаблон CSV или Excel, заполните столбец «Значение» и загрузите его снова.' }
  } finally {
    importing.value = false
  }
}
const onImport = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (file) await importFile(file)
}
const onDrop = async (event: DragEvent) => {
  dragOver.value = false
  const file = event.dataTransfer?.files?.[0]
  if (file) await importFile(file)
}

const rejectedTitle = (count: number) => {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return `${count} значение не принято`
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return `${count} значения не приняты`
  return `${count} значений не принято`
}
const focusErrorPane = () => {
  if (siteErrorCount.value && part.value !== 'object') {
    void router.replace({ path: `/projects/${id.value}/params` })
  }
  void nextTick(() => document.querySelector('.fld.err')?.scrollIntoView({ behavior: 'smooth', block: 'center' }))
}

watch(() => tasks.value.length, (n) => {
  if (activeTask.value >= n) activeTask.value = Math.max(0, n - 1)
})
</script>

<template>
  <ProjectShell
    v-if="shell"
    :project="shell"
    current="params"
    :substages="substages"
    :current-sub="part"
    :title="part === 'object' ? 'Параметры объекта' : 'Процессы объекта'"
    :lead="part === 'object' ? 'Общие данные площадки: вручную или из шаблона Excel и CSV. Дальше — какие процессы объекта включать в подбор.' : 'Снимите процесс, если его не нужно включать в подбор.'"
  >
    <template #actions>
      <UiButton v-if="live && !readonly && part === 'object'" variant="secondary" size="lg" :disabled="demoFilling" @click="fillFromDemo">
        <template #icon><PhSparkle :size="18" weight="duotone" /></template>{{ demoFilling ? 'Подставляем…' : 'Подставить демо-данные' }}
      </UiButton>
      <UiButton v-if="live" size="lg" :disabled="saving" @click="advance">
        {{ saving ? 'Сохраняем…' : advanceLabel }}<template #after><PhArrowRight :size="18" weight="bold" /></template>
      </UiButton>
    </template>

    <UiCallout v-if="error" tone="danger" title="Не удалось загрузить проект">
      {{ fetchErrorMessage(error, 'Сервер не ответил. Проверьте, что API запущен.') }}
    </UiCallout>

    <div v-else-if="pending && !hydrated" class="params">
      <UiSkeleton h="44px" />
      <UiSkeleton h="320px" />
    </div>

    <template v-else-if="live">
      <UiCallout v-if="readonly" tone="info" title="Демо-объект · только просмотр">
        Параметры этого объекта задал администратор. Пройдите по шагам, чтобы посмотреть подбор{{ isFullPath(shell!) ? ', экономику и визуализацию' : ' и сравнение' }}.
        <div class="call-actions">
          <UiButton v-if="role !== 'guest'" size="sm" :disabled="copying" @click="copyDemo"><template #icon><PhCopy :size="14" weight="bold" /></template>{{ copying ? 'Копируем…' : 'Скопировать в мои проекты' }}</UiButton>
          <UiButton v-else to="/login" size="sm">Войти, чтобы скопировать и править</UiButton>
        </div>
      </UiCallout>
      <UiCallout v-else-if="notice" :tone="notice.ok ? 'ok' : 'danger'" :title="notice.items?.length ? rejectedTitle(notice.items.length) : undefined">
        {{ notice.text }}
        <ul v-if="notice.items?.length" class="notice-list">
          <li v-for="item in notice.items" :key="item">{{ item }}</li>
        </ul>
      </UiCallout>

      <div v-if="part === 'object'" class="groups" :class="{ still: readonly }">
        <section
          v-if="!readonly"
          class="import-bar glass"
          :class="{ over: dragOver }"
          @dragover.prevent="dragOver = true"
          @dragleave.prevent="dragOver = false"
          @drop.prevent="onDrop"
        >
          <div>
            <div class="h4">Загрузка из файла</div>
            <p class="caption">Скачайте шаблон, заполните столбец «Значение» и лист «Процессы». Затем перетащите сюда CSV или Excel либо выберите файл. Пустая ячейка не затирает то, что уже введено. После проверки нажмите «{{ advanceLabel }}», чтобы сохранить.</p>
          </div>
          <div class="import-actions">
            <UiButton variant="secondary" size="sm" @click="downloadTemplate('csv')"><template #icon><PhDownloadSimple :size="14" weight="bold" /></template>Шаблон CSV</UiButton>
            <UiButton variant="secondary" size="sm" @click="downloadTemplate('xlsx')"><template #icon><PhDownloadSimple :size="14" weight="bold" /></template>Шаблон Excel</UiButton>
            <UiButton variant="secondary" size="sm" :disabled="importing" @click="fileRef?.click()"><template #icon><PhUploadSimple :size="14" weight="bold" /></template>{{ importing ? 'Читаем…' : 'Загрузить файл' }}</UiButton>
            <input ref="fileRef" class="file-in" type="file" accept=".csv,.xls,.xlsx,text/csv,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" @change="onImport">
          </div>
        </section>
        <UiCallout v-if="formFallback" tone="warn">Справочник полей платформы не ответил: форма собрана из встроенного набора, без границ и значений по умолчанию.</UiCallout>
        <section v-for="(g, gi) in groups" :key="g.title" class="group" :class="g.extra ? 'extra' : 'glass'">
          <div class="sec-head">
            <div>
              <div class="h3">{{ g.title }}</div>
              <div v-if="g.hint" class="caption">{{ g.hint }}</div>
            </div>
            <UiBadge v-if="gi === 0" tone="info" size="sm">{{ objectTypeLabel[objectType] ?? detail?.object_type_code }}</UiBadge>
          </div>
          <div class="fields">
            <label v-for="f in g.fields" :key="f.key" class="fld" :class="{ edited: siteEdited(f.key), err: !!siteError(f.key) }" :title="f.hint || undefined">
              <span class="fld-label body-sm">{{ f.label }}<span v-if="f.required" class="req" title="Обязательное поле"> *</span><span v-if="f.unit" class="muted"> · {{ f.unit }}</span></span>
              <span class="fld-in">
                <select
                  v-if="f.kind === 'bool'"
                  class="select"
                  :disabled="readonly"
                  :value="siteValue(f.key) === true ? 'true' : siteValue(f.key) === false ? 'false' : ''"
                  @change="setSiteBool(f.key, ($event.target as HTMLSelectElement).value)"
                >
                  <option value="">не задано</option>
                  <option value="true">Да</option>
                  <option value="false">Нет</option>
                </select>
                <input
                  v-else-if="f.kind === 'text'"
                  class="input"
                  :disabled="readonly"
                  :value="typeof siteValue(f.key) === 'string' ? siteValue(f.key) : ''"
                  :placeholder="defaultHint(f) ? `по умолчанию ${defaultHint(f)}` : 'не задано'"
                  @input="setSiteText(f.key, ($event.target as HTMLInputElement).value)"
                >
                <input
                  v-else
                  class="input input-mono"
                  :disabled="readonly"
                  :value="fmt(siteValue(f.key) as number | null)"
                  :placeholder="defaultHint(f) ? `по умолчанию ${defaultHint(f)}` : 'не задано'"
                  @input="setSiteNum(f.key, ($event.target as HTMLInputElement).value, f.kind === 'int')"
                >
                <PhPencilSimple v-if="siteEdited(f.key)" :size="14" weight="bold" class="edit-ic" />
              </span>
              <span v-if="siteError(f.key)" class="caption err-note">{{ siteError(f.key) }}</span>
              <span v-else-if="siteEdited(f.key)" class="caption edited-note">Изменено. По умолчанию {{ defaultHint(f) }}.</span>
              <span v-else-if="siteSource(f.key)" class="caption src-note">{{ siteSource(f.key) }}</span>
              <span v-if="rangeHint(f) && !siteError(f.key)" class="caption range-note">Допустимо {{ rangeHint(f) }}</span>
            </label>
          </div>
        </section>
      </div>

      <PlatformSetup v-else ref="setupRef" :object-code="objectType" :readonly="readonly" />
    </template>
  </ProjectShell>

  <section v-else class="container missing">
    <UiCallout tone="danger" title="Проект не найден">Нет ни сохранённого расчёта, ни демо-макета с таким адресом.</UiCallout>
    <UiButton to="/projects">К списку проектов</UiButton>
  </section>
</template>

<style scoped>
.params { display: grid; gap: var(--space-4); }
.pane-switch { max-width: 480px; }
.groups { display: grid; gap: var(--space-4); }
.import-bar { padding: var(--space-5); display: flex; justify-content: space-between; align-items: center; gap: var(--space-5); }
.import-bar.over { outline: 2px dashed var(--brand-600); outline-offset: -8px; }
.import-bar > * { position: relative; z-index: 1; }
.import-bar .h4 { margin-bottom: 4px; }
.import-bar .caption { max-width: 62ch; }
.import-actions { display: flex; flex-wrap: wrap; gap: 8px; }
.notice-list { margin: 8px 0 0; padding-left: 18px; display: grid; gap: 2px; }
.file-in { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); border: 0; }
.groups.still .input:disabled, .groups.still .select:disabled { opacity: 1; color: var(--ink-strong); background: rgba(255, 255, 255, 0.5); cursor: default; }
.group { padding: var(--space-6); display: grid; gap: var(--space-5); }
.group > * { position: relative; z-index: 1; }
.group.extra {
  padding: var(--space-4) 4px var(--space-2);
  gap: var(--space-3);
  background: transparent;
  box-shadow: none;
}
.group.extra .h3,
.group.extra .fld-label { font-weight: 500; color: var(--ink-muted); font-size: 13px; }
.group.extra .input,
.group.extra .select { background: transparent; color: var(--ink-muted); }
.sec-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-4); }
.fields { display: grid; grid-template-columns: 1fr 1fr; gap: 16px 24px; }
.fld { display: grid; gap: 6px; align-content: start; }
.fld-label { font-weight: 600; color: var(--ink-strong); }
.fld-in { position: relative; }
.edit-ic { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); color: var(--state-warn); }
.edited .input, .edited .select { border-color: rgba(138, 82, 0, 0.35); background: #fff8ee; }
.err .input, .err .select { border-color: rgba(176, 40, 36, 0.45); background: #fff5f4; }
.edited-note { color: var(--state-warn); }
.err-note { color: var(--state-danger); }
.src-note { color: var(--ink-muted); }
.range-note { color: var(--ink-faint); }
.req { color: var(--state-danger); }
.upload-note { margin: 0; }
.pane-foot { display: flex; flex-wrap: wrap; gap: 10px; }
.proc-col { display: grid; gap: var(--space-5); }
.proc-layout { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: var(--space-5); align-items: start; }
.proc-nav { display: grid; gap: 8px; position: sticky; top: 96px; }
.proc { display: grid; grid-template-columns: auto 1fr; gap: 10px; align-items: center; text-align: left; padding: 10px 12px; border-radius: 14px; background: rgba(255, 255, 255, 0.55); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.proc.on { background: #fff; box-shadow: inset 0 0 0 1px var(--brand-400); }
.proc.err { box-shadow: inset 0 0 0 1px rgba(176, 40, 36, 0.45); }
.proc-copy { display: grid; gap: 2px; min-width: 0; }
.proc-copy .body-sm { color: var(--ink-strong); font-weight: 650; }
.task { padding: 18px 20px 20px; display: grid; gap: 14px; }
.task > * { position: relative; z-index: 1; }
.empty-proc { align-content: start; }
.task-top { display: grid; grid-template-columns: auto 1fr auto; gap: 10px; align-items: center; }
.tn { width: 28px; height: 28px; border-radius: 8px; background: var(--surface-graphite); color: var(--brand-300); display: inline-flex; align-items: center; justify-content: center; flex: none; }
.task-proc { font-weight: 700; color: var(--ink-strong); }
.ic { width: 36px; height: 36px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; color: var(--ink-muted); transition: all var(--dur-fast) var(--ease); }
.ic:hover { background: var(--state-danger-tint); color: var(--state-danger); }
.task-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px 16px; }
.tf { display: grid; gap: 4px; align-content: start; }
.call-actions { margin-top: 10px; }
.missing { padding-top: var(--space-12); display: grid; gap: var(--space-4); justify-items: start; }
@media (max-width: 1100px) {
  .import-bar { flex-direction: column; align-items: stretch; }
  .fields, .task-grid { grid-template-columns: 1fr; }
  .proc-layout { grid-template-columns: 1fr; }
  .proc-nav { position: static; }
}
</style>
