<script setup lang="ts">
import { PhPlus, PhTrash, PhPencilSimple, PhArrowRight, PhFloppyDisk, PhUploadSimple } from '@phosphor-icons/vue'
import { objectTypeLabel, projects, type ObjectType } from '~/data/projects'
import { fieldSources, labelProcess, processesByObject, siteFieldMeta } from '~/data/siteFields'
import { asObjectType, fetchErrorMessage } from '~/composables/useCalc'
import type { ApiSiteProfile, ApiTask } from '~/types/api'

const route = useRoute()
const router = useRouter()
const id = computed(() => route.params.id as string)
const { project, detail, pending, error, refresh, update, calculate } = useCalc(id)
const demoProject = computed(() => projects.find((p) => p.id === id.value))
const shell = computed(() => project.value ?? demoProject.value)
useHead({ title: () => `Параметры · ${shell.value?.name ?? 'проект'}` })

const objectType = computed<ObjectType>(() => asObjectType(detail.value?.object_type_code ?? shell.value?.objectType ?? 'warehouse'))
const { profile } = useSiteProfile(computed(() => detail.value?.object_type_code ?? ''))
const sources = computed(() => ({
  ...(fieldSources[objectType.value] ?? {}),
  ...(profile.value?.field_sources ?? {}),
}))

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
  tasks.value = p.tasks.map((t) => ({
    ...emptyTask(t.process_code),
    ...t,
    container_types: [...(t.container_types ?? [])],
  }))
  hydrated.value = String(p.id)
}

watch(detail, (p) => {
  if (p && hydrated.value !== String(p.id)) applyDetail()
}, { immediate: true })

const sameNum = (a: unknown, b: unknown) => {
  if (a == null && b == null) return true
  if (typeof a === 'boolean' || typeof b === 'boolean') return a === b
  if (typeof a === 'number' && typeof b === 'number') return a === b
  return a === b
}

const profileVal = (key: keyof ApiSiteProfile) => profile.value?.site?.[key]
const siteEdited = (key: keyof ApiSiteProfile) => !sameNum(site[key], profileVal(key))
const siteSource = (key: string) => sources.value[key]
const taskSource = (process: string, field?: string) =>
  (field && sources.value[`tasks.${process}.${field}`]) || sources.value[`tasks.${process}`]
const taskEdited = (t: ApiTask, field: keyof ApiTask) => {
  const orig = profile.value?.tasks.find((x) => x.process_code === t.process_code)
  if (!orig) return true
  if (field === 'container_types') {
    return (t.container_types ?? []).join('|') !== (orig.container_types ?? []).join('|')
  }
  return !sameNum(t[field], orig[field])
}

const parseNum = (raw: string, asInt = false): number | null => {
  const t = raw.trim().replace(/\s/g, '').replace(',', '.')
  if (!t) return null
  const n = asInt ? Number.parseInt(t, 10) : Number(t)
  return Number.isFinite(n) ? n : null
}
const setSiteNum = (key: keyof ApiSiteProfile, raw: string, asInt = false) => {
  ;(site as Record<string, unknown>)[key] = parseNum(raw, asInt)
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
const calculating = ref(false)
const notice = ref<{ ok: boolean; text: string } | null>(null)
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
  site: { ...site, object_type_code: detail.value?.object_type_code ?? objectType.value },
  tasks: tasks.value.map((t) => ({
    ...t,
    name: t.name || labelProcess(t.process_code),
    container_types: t.container_types ?? [],
  })),
})

const save = async () => {
  if (!project.value || saving.value) return false
  saving.value = true
  notice.value = null
  try {
    await update(payload())
    await refresh()
    applyDetail()
    clearFieldErrors()
    notice.value = { ok: true, text: 'Параметры сохранены' }
    return true
  } catch (e: unknown) {
    if (applyFieldErrors(e)) {
      const n = fieldErrorCount.value
      notice.value = { ok: false, text: `На форме ${n} ${n === 1 ? 'проблема' : n < 5 ? 'проблемы' : 'проблем'} — исправьте поля ниже` }
    } else {
      clearFieldErrors()
      notice.value = { ok: false, text: fetchErrorMessage(e, 'Не удалось сохранить') }
    }
    return false
  } finally {
    saving.value = false
  }
}

const runCalc = async () => {
  if (!project.value || calculating.value) return
  calculating.value = true
  const ok = await save()
  if (!ok) { calculating.value = false; return }
  try {
    await calculate()
    await router.push(`/projects/${id.value}/match`)
  } catch (e: unknown) {
    notice.value = { ok: false, text: fetchErrorMessage(e, 'Не удалось запустить подбор') }
  } finally {
    calculating.value = false
  }
}

const live = computed(() => Boolean(project.value))
const fields = siteFieldMeta
</script>

<template>
  <ProjectShell
    v-if="shell"
    :project="shell"
    current="params"
    title="Параметры площадки и задач"
    lead="Поля площадки зависят от типа объекта и приходят из справочника. Ручные правки видны как правки и не растворяются в исходных данных."
  >
    <template #actions>
      <UiButton v-if="live" variant="secondary" disabled title="Заглушка: пока принимается только ручной ввод">
        <template #icon><PhUploadSimple :size="16" weight="bold" /></template>
        Загрузить Excel или CSV
      </UiButton>
      <UiButton v-if="live" variant="secondary" :disabled="saving || calculating" @click="save">
        <template #icon><PhFloppyDisk :size="16" weight="bold" /></template>
        {{ saving ? 'Сохранение…' : 'Сохранить' }}
      </UiButton>
      <UiButton v-if="live" size="lg" :disabled="saving || calculating" @click="runCalc">
        {{ calculating ? 'Считаем…' : 'Запустить подбор' }}<template #after><PhArrowRight :size="18" weight="bold" /></template>
      </UiButton>
    </template>

    <UiCallout v-if="!live" tone="warn" title="Это демонстрационный макет">
      Живая форма открывается у проекта, созданного через «Новый проект». Площадка и задачи тогда предзаполняются из профиля объекта.
      <div class="call-actions">
        <UiButton to="/projects/new" size="sm">Создать проект</UiButton>
      </div>
    </UiCallout>

    <UiCallout v-else-if="error" tone="danger" title="Не удалось загрузить проект">
      {{ fetchErrorMessage(error, 'Сервер не ответил. Проверьте, что API запущен.') }}
    </UiCallout>

    <div v-else-if="pending && !hydrated" class="grid-12 params">
      <div class="span-5 site glass"><UiSkeleton h="320px" /></div>
      <div class="span-7"><UiSkeleton h="320px" /></div>
    </div>

    <template v-else-if="live">
      <UiCallout v-if="notice" :tone="notice.ok ? 'ok' : 'danger'" :title="!notice.ok && fieldErrorCount ? `${fieldErrorCount} ${fieldErrorCount === 1 ? 'проблема' : fieldErrorCount < 5 ? 'проблемы' : 'проблем'} на форме` : undefined">{{ notice.text }}</UiCallout>
      <p v-if="live" class="caption upload-note">Загрузка Excel или CSV — заглушка: пока принимается только ручной ввод.</p>

      <div class="grid-12 params">
        <div class="span-5 site glass" v-reveal>
          <div class="sec-head">
            <div>
              <div class="h3">Площадка</div>
              <div class="caption">{{ objectTypeLabel[objectType] }} · {{ fields.length }} полей из справочника</div>
            </div>
            <UiBadge tone="info" size="sm">из профиля объекта</UiBadge>
          </div>
          <div class="fields">
            <label v-for="f in fields" :key="f.key" class="fld" :class="{ edited: siteEdited(f.key), err: !!siteError(f.key) }">
              <span class="fld-label body-sm">{{ f.label }}<span v-if="f.unit" class="muted"> · {{ f.unit }}</span></span>
              <span class="fld-in">
                <select
                  v-if="f.kind === 'bool'"
                  class="select"
                  :value="site[f.key] === true ? 'true' : site[f.key] === false ? 'false' : ''"
                  @change="(site as Record<string, unknown>)[f.key] = ($event.target as HTMLSelectElement).value === '' ? null : ($event.target as HTMLSelectElement).value === 'true'"
                >
                  <option value="">не задано</option>
                  <option value="true">Да</option>
                  <option value="false">Нет</option>
                </select>
                <input
                  v-else
                  class="input input-mono"
                  :value="fmt(site[f.key] as number | null)"
                  :placeholder="'не задано'"
                  @input="setSiteNum(f.key, ($event.target as HTMLInputElement).value, f.kind === 'int')"
                >
                <PhPencilSimple v-if="siteEdited(f.key)" :size="14" weight="bold" class="edit-ic" />
              </span>
              <span v-if="siteError(f.key)" class="caption err-note">{{ siteError(f.key) }}</span>
              <span v-else-if="siteEdited(f.key)" class="caption edited-note">Правка вручную. Значение из профиля не используется.</span>
              <span v-else-if="siteSource(f.key)" class="caption src-note">{{ siteSource(f.key) }}</span>
            </label>
          </div>
        </div>

        <div class="span-7 tasks" v-reveal="1">
          <div class="tasks-head sec-head">
            <div>
              <div class="h3">Задачи</div>
              <div class="caption">Процесс, суточный и часовой поток, маршрут, тара, пик, времена погрузки и разгрузки</div>
            </div>
            <UiButton variant="secondary" size="sm" @click="addTask"><template #icon><PhPlus :size="14" weight="bold" /></template>Добавить задачу</UiButton>
          </div>
          <div class="task-list">
            <div v-for="(t, i) in tasks" :key="`${t.process_code}-${i}`" class="task glass">
              <div class="task-top">
                <span class="mono-sm tn">{{ i + 1 }}</span>
                <select class="select task-proc" :value="t.process_code" @change="onProcess(t, ($event.target as HTMLSelectElement).value)">
                  <option v-for="code in processesByObject[objectType]" :key="code" :value="code">{{ labelProcess(code) }}</option>
                </select>
                <button type="button" class="ic" aria-label="Удалить задачу" @click="removeTask(i)"><PhTrash :size="16" /></button>
              </div>
              <div class="task-grid">
                <label class="tf" :class="{ edited: taskEdited(t, 'flow_per_day'), err: !!taskError(i, 'flow_per_day') }">
                  <span class="caption">Поток · опер./сутки</span>
                  <input class="input input-mono" :value="fmt(t.flow_per_day)" placeholder="не задано" @input="setTaskNum(t, 'flow_per_day', ($event.target as HTMLInputElement).value)">
                  <span v-if="taskError(i, 'flow_per_day')" class="caption err-note">{{ taskError(i, 'flow_per_day') }}</span>
                  <span v-else-if="!taskEdited(t, 'flow_per_day') && taskSource(t.process_code, 'flow_per_day')" class="caption src-note">{{ taskSource(t.process_code, 'flow_per_day') }}</span>
                </label>
                <label class="tf" :class="{ edited: taskEdited(t, 'flow_per_hour'), err: !!taskError(i, 'flow_per_hour') }">
                  <span class="caption">Поток · опер./час</span>
                  <input class="input input-mono" :value="fmt(t.flow_per_hour)" placeholder="пересчитает движок" @input="setTaskNum(t, 'flow_per_hour', ($event.target as HTMLInputElement).value)">
                  <span v-if="taskError(i, 'flow_per_hour')" class="caption err-note">{{ taskError(i, 'flow_per_hour') }}</span>
                </label>
                <label class="tf" :class="{ edited: taskEdited(t, 'route_len_m'), err: !!taskError(i, 'route_len_m') }">
                  <span class="caption">Длина маршрута · м</span>
                  <input class="input input-mono" :value="fmt(t.route_len_m)" placeholder="не применимо" @input="setTaskNum(t, 'route_len_m', ($event.target as HTMLInputElement).value)">
                  <span v-if="taskError(i, 'route_len_m')" class="caption err-note">{{ taskError(i, 'route_len_m') }}</span>
                  <span v-else-if="!taskEdited(t, 'route_len_m') && taskSource(t.process_code, 'route_len_m')" class="caption src-note">{{ taskSource(t.process_code, 'route_len_m') }}</span>
                </label>
                <label class="tf" :class="{ edited: taskEdited(t, 'max_load_kg'), err: !!taskError(i, 'max_load_kg') }">
                  <span class="caption">Макс. груз · кг</span>
                  <input class="input input-mono" :value="fmt(t.max_load_kg)" placeholder="не задано" @input="setTaskNum(t, 'max_load_kg', ($event.target as HTMLInputElement).value)">
                  <span v-if="taskError(i, 'max_load_kg')" class="caption err-note">{{ taskError(i, 'max_load_kg') }}</span>
                  <span v-else-if="!taskEdited(t, 'max_load_kg') && taskSource(t.process_code, 'max_load_kg')" class="caption src-note">{{ taskSource(t.process_code, 'max_load_kg') }}</span>
                </label>
                <label class="tf" :class="{ edited: taskEdited(t, 'peak_factor'), err: !!taskError(i, 'peak_factor') }">
                  <span class="caption">Пиковая нагрузка · коэф.</span>
                  <input class="input input-mono" :value="fmt(t.peak_factor)" placeholder="как у площадки" @input="setTaskNum(t, 'peak_factor', ($event.target as HTMLInputElement).value)">
                  <span v-if="taskError(i, 'peak_factor')" class="caption err-note">{{ taskError(i, 'peak_factor') }}</span>
                </label>
                <label class="tf" :class="{ err: !!taskError(i, 'container_types') }">
                  <span class="caption">Тара</span>
                  <input class="input" :value="(t.container_types ?? []).join(', ')" placeholder="pallet, piece" @input="t.container_types = ($event.target as HTMLInputElement).value.split(',').map((s) => s.trim()).filter(Boolean)">
                  <span v-if="taskError(i, 'container_types')" class="caption err-note">{{ taskError(i, 'container_types') }}</span>
                </label>
                <label class="tf" :class="{ err: !!taskError(i, 't_load_s') }">
                  <span class="caption">Погрузка · с</span>
                  <input class="input input-mono" :value="fmt(t.t_load_s)" placeholder="из норматива" @input="setTaskNum(t, 't_load_s', ($event.target as HTMLInputElement).value)">
                  <span v-if="taskError(i, 't_load_s')" class="caption err-note">{{ taskError(i, 't_load_s') }}</span>
                </label>
                <label class="tf" :class="{ err: !!taskError(i, 't_unload_s') }">
                  <span class="caption">Разгрузка · с</span>
                  <input class="input input-mono" :value="fmt(t.t_unload_s)" placeholder="из норматива" @input="setTaskNum(t, 't_unload_s', ($event.target as HTMLInputElement).value)">
                  <span v-if="taskError(i, 't_unload_s')" class="caption err-note">{{ taskError(i, 't_unload_s') }}</span>
                </label>
                <label class="tf" :class="{ edited: taskEdited(t, 'staff_fte_now'), err: !!taskError(i, 'staff_fte_now') }">
                  <span class="caption">Персонал сейчас · чел.</span>
                  <input class="input input-mono" :value="fmt(t.staff_fte_now)" placeholder="не задано" @input="setTaskNum(t, 'staff_fte_now', ($event.target as HTMLInputElement).value)">
                  <span v-if="taskError(i, 'staff_fte_now')" class="caption err-note">{{ taskError(i, 'staff_fte_now') }}</span>
                  <span v-else-if="!taskEdited(t, 'staff_fte_now') && taskSource(t.process_code, 'staff_fte_now')" class="caption src-note">{{ taskSource(t.process_code, 'staff_fte_now') }}</span>
                </label>
              </div>
              <div v-if="!taskEdited(t, 'flow_per_day') && taskSource(t.process_code) && !taskSource(t.process_code, 'flow_per_day')" class="caption src-note">{{ taskSource(t.process_code) }}</div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </ProjectShell>

  <section v-else class="container missing">
    <UiCallout tone="danger" title="Проект не найден">Нет ни сохранённого расчёта, ни демо-макета с таким адресом.</UiCallout>
    <UiButton to="/projects">К списку проектов</UiButton>
  </section>
</template>

<style scoped>
.params { align-items: start; }
.site { padding: var(--space-6); display: grid; gap: var(--space-5); position: sticky; top: 96px; }
.site > * { position: relative; z-index: 1; }
.sec-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-4); }
.fields { display: grid; gap: 12px; }
.fld { display: grid; gap: 6px; }
.fld-label { font-weight: 600; color: var(--ink-strong); }
.fld-in { position: relative; }
.edit-ic { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); color: var(--state-warn); }
.edited .input, .edited .select { border-color: rgba(138, 82, 0, 0.35); background: #fff8ee; }
.err .input, .err .select { border-color: rgba(176, 40, 36, 0.45); background: #fff5f4; }
.edited-note { color: var(--state-warn); }
.err-note { color: var(--state-danger); }
.src-note { color: var(--ink-muted); }
.upload-note { margin: 0; }
.tasks { display: grid; gap: var(--space-4); }
.task-list { display: grid; gap: 10px; }
.task { padding: 14px 16px 16px; display: grid; gap: 12px; }
.task > * { position: relative; z-index: 1; }
.task-top { display: grid; grid-template-columns: auto 1fr auto; gap: 10px; align-items: center; }
.tn { width: 28px; height: 28px; border-radius: 8px; background: var(--surface-graphite); color: var(--brand-300); display: inline-flex; align-items: center; justify-content: center; }
.task-proc { max-width: 360px; font-weight: 700; color: var(--ink-strong); }
.ic { width: 36px; height: 36px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; color: var(--ink-muted); transition: all var(--dur-fast) var(--ease); }
.ic:hover { background: var(--state-danger-tint); color: var(--state-danger); }
.task-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.tf { display: grid; gap: 4px; }
.call-actions { margin-top: 10px; }
.missing { padding-top: var(--space-12); display: grid; gap: var(--space-4); justify-items: start; }
@media (max-width: 1100px) { .span-5, .span-7 { grid-column: span 12; } .site { position: static; } .task-grid { grid-template-columns: 1fr 1fr; } }
</style>
