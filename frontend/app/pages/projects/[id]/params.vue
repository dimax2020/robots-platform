<script setup lang="ts">
import { PhPlus, PhTrash, PhPencilSimple, PhArrowRight, PhArrowLeft, PhFloppyDisk, PhUploadSimple } from '@phosphor-icons/vue'
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
  activeTask.value = tasks.value.length - 1
  pane.value = 'tasks'
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

const pane = ref<'site' | 'tasks'>('site')
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

const groups = computed(() => {
  const used = new Set<string>()
  const out = fieldGroups.map((g) => {
    const items = g.keys
      .map((k) => siteFieldMeta.find((f) => f.key === k))
      .filter((f): f is (typeof siteFieldMeta)[number] => Boolean(f))
    items.forEach((f) => used.add(f.key))
    return { title: g.title, hint: g.hint, fields: items }
  })
  const rest = siteFieldMeta.filter((f) => !used.has(f.key))
  if (rest.length) out.push({ title: 'Прочее', hint: '', fields: rest })
  return out
})

const panes = computed(() => [
  { id: 'site', label: 'Предприятие' },
  { id: 'tasks', label: 'Процессы', count: tasks.value.length },
])

const siteErrorCount = computed(() => Object.keys(siteErrors).length)
const currentTask = computed(() => tasks.value[activeTask.value] ?? null)
const taskHasError = (i: number) => Boolean(taskErrors[i] && Object.keys(taskErrors[i]!).length)

const taskSummary = (t: ApiTask) => {
  if (t.flow_per_day != null) return `${t.flow_per_day.toLocaleString('ru-RU')} опер./сутки`
  if (t.flow_per_hour != null) return `${t.flow_per_hour.toLocaleString('ru-RU')} опер./час`
  return 'поток не задан'
}

const focusErrorPane = () => {
  if (siteErrorCount.value) {
    pane.value = 'site'
    return
  }
  const first = Number(Object.keys(taskErrors).find((k) => taskHasError(Number(k))))
  if (Number.isInteger(first)) {
    pane.value = 'tasks'
    activeTask.value = first
  }
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
    title="Параметры предприятия"
    lead="Сначала общие данные предприятия. Процессы — следующим шагом: внутрискладская логистика, сборка и остальные не делят с ними один экран."
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

    <div v-else-if="pending && !hydrated" class="params">
      <UiSkeleton h="44px" />
      <UiSkeleton h="320px" />
    </div>

    <template v-else-if="live">
      <UiCallout v-if="notice" :tone="notice.ok ? 'ok' : 'danger'" :title="!notice.ok && fieldErrorCount ? `${fieldErrorCount} ${fieldErrorCount === 1 ? 'проблема' : fieldErrorCount < 5 ? 'проблемы' : 'проблем'} на форме` : undefined">{{ notice.text }}</UiCallout>
      <p class="caption upload-note">Загрузка Excel или CSV — заглушка: пока принимается только ручной ввод.</p>

      <div class="pane-switch">
        <UiTabs v-model="pane" :tabs="panes" />
      </div>

      <div v-if="pane === 'site'" class="groups">
        <section v-for="g in groups" :key="g.title" class="group glass">
          <div class="sec-head">
            <div>
              <div class="h3">{{ g.title }}</div>
              <div v-if="g.hint" class="caption">{{ g.hint }}</div>
            </div>
            <UiBadge v-if="g.title === 'Площадь и геометрия'" tone="info" size="sm">{{ objectTypeLabel[objectType] }}</UiBadge>
          </div>
          <div class="fields">
            <label v-for="f in g.fields" :key="f.key" class="fld" :class="{ edited: siteEdited(f.key), err: !!siteError(f.key) }">
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
                  placeholder="не задано"
                  @input="setSiteNum(f.key, ($event.target as HTMLInputElement).value, f.kind === 'int')"
                >
                <PhPencilSimple v-if="siteEdited(f.key)" :size="14" weight="bold" class="edit-ic" />
              </span>
              <span v-if="siteError(f.key)" class="caption err-note">{{ siteError(f.key) }}</span>
              <span v-else-if="siteEdited(f.key)" class="caption edited-note">Правка вручную. Значение из профиля не используется.</span>
              <span v-else-if="siteSource(f.key)" class="caption src-note">{{ siteSource(f.key) }}</span>
            </label>
          </div>
        </section>
        <div class="pane-foot">
          <UiButton @click="pane = 'tasks'">Дальше: процессы<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
        </div>
      </div>

      <div v-else class="proc-layout">
        <aside class="proc-nav">
          <button
            v-for="(t, i) in tasks"
            :key="`${t.process_code}-${i}`"
            type="button"
            class="proc"
            :class="{ on: i === activeTask, err: taskHasError(i) }"
            :aria-current="i === activeTask ? 'true' : undefined"
            @click="activeTask = i"
          >
            <span class="mono-sm tn">{{ i + 1 }}</span>
            <span class="proc-copy">
              <span class="body-sm strong">{{ labelProcess(t.process_code, t.name) }}</span>
              <span class="caption">{{ taskHasError(i) ? 'есть замечание' : taskSummary(t) }}</span>
            </span>
          </button>
          <UiButton variant="secondary" size="sm" @click="addTask"><template #icon><PhPlus :size="14" weight="bold" /></template>Добавить процесс</UiButton>
        </aside>

        <div v-if="!currentTask" class="task glass empty-proc">
          <div class="h3">Процессов пока нет</div>
          <p class="body-sm muted">Добавьте внутрискладскую логистику, сборку или другой процесс — у каждого свои поля.</p>
        </div>

        <div v-else class="task glass">
          <div class="task-top">
            <span class="mono-sm tn">{{ activeTask + 1 }}</span>
            <select class="select task-proc" :value="currentTask.process_code" @change="onProcess(currentTask, ($event.target as HTMLSelectElement).value)">
              <option v-for="code in processesByObject[objectType]" :key="code" :value="code">{{ labelProcess(code) }}</option>
            </select>
            <button type="button" class="ic" aria-label="Удалить процесс" @click="removeTask(activeTask)"><PhTrash :size="16" /></button>
          </div>
          <div class="task-grid">
            <label class="tf" :class="{ edited: taskEdited(currentTask, 'flow_per_day'), err: !!taskError(activeTask, 'flow_per_day') }">
              <span class="caption">Поток · опер./сутки</span>
              <input class="input input-mono" :value="fmt(currentTask.flow_per_day)" placeholder="не задано" @input="setTaskNum(currentTask, 'flow_per_day', ($event.target as HTMLInputElement).value)">
              <span v-if="taskError(activeTask, 'flow_per_day')" class="caption err-note">{{ taskError(activeTask, 'flow_per_day') }}</span>
              <span v-else-if="!taskEdited(currentTask, 'flow_per_day') && taskSource(currentTask.process_code, 'flow_per_day')" class="caption src-note">{{ taskSource(currentTask.process_code, 'flow_per_day') }}</span>
            </label>
            <label class="tf" :class="{ edited: taskEdited(currentTask, 'flow_per_hour'), err: !!taskError(activeTask, 'flow_per_hour') }">
              <span class="caption">Поток · опер./час</span>
              <input class="input input-mono" :value="fmt(currentTask.flow_per_hour)" placeholder="пересчитает движок" @input="setTaskNum(currentTask, 'flow_per_hour', ($event.target as HTMLInputElement).value)">
              <span v-if="taskError(activeTask, 'flow_per_hour')" class="caption err-note">{{ taskError(activeTask, 'flow_per_hour') }}</span>
            </label>
            <label class="tf" :class="{ edited: taskEdited(currentTask, 'route_len_m'), err: !!taskError(activeTask, 'route_len_m') }">
              <span class="caption">Длина маршрута · м</span>
              <input class="input input-mono" :value="fmt(currentTask.route_len_m)" placeholder="не применимо" @input="setTaskNum(currentTask, 'route_len_m', ($event.target as HTMLInputElement).value)">
              <span v-if="taskError(activeTask, 'route_len_m')" class="caption err-note">{{ taskError(activeTask, 'route_len_m') }}</span>
              <span v-else-if="!taskEdited(currentTask, 'route_len_m') && taskSource(currentTask.process_code, 'route_len_m')" class="caption src-note">{{ taskSource(currentTask.process_code, 'route_len_m') }}</span>
            </label>
            <label class="tf" :class="{ edited: taskEdited(currentTask, 'max_load_kg'), err: !!taskError(activeTask, 'max_load_kg') }">
              <span class="caption">Макс. груз · кг</span>
              <input class="input input-mono" :value="fmt(currentTask.max_load_kg)" placeholder="не задано" @input="setTaskNum(currentTask, 'max_load_kg', ($event.target as HTMLInputElement).value)">
              <span v-if="taskError(activeTask, 'max_load_kg')" class="caption err-note">{{ taskError(activeTask, 'max_load_kg') }}</span>
              <span v-else-if="!taskEdited(currentTask, 'max_load_kg') && taskSource(currentTask.process_code, 'max_load_kg')" class="caption src-note">{{ taskSource(currentTask.process_code, 'max_load_kg') }}</span>
            </label>
            <label class="tf" :class="{ edited: taskEdited(currentTask, 'peak_factor'), err: !!taskError(activeTask, 'peak_factor') }">
              <span class="caption">Пиковая нагрузка · коэф.</span>
              <input class="input input-mono" :value="fmt(currentTask.peak_factor)" placeholder="как у площадки" @input="setTaskNum(currentTask, 'peak_factor', ($event.target as HTMLInputElement).value)">
              <span v-if="taskError(activeTask, 'peak_factor')" class="caption err-note">{{ taskError(activeTask, 'peak_factor') }}</span>
            </label>
            <label class="tf" :class="{ err: !!taskError(activeTask, 'container_types') }">
              <span class="caption">Тара</span>
              <input class="input" :value="(currentTask.container_types ?? []).join(', ')" placeholder="pallet, piece" @input="currentTask.container_types = ($event.target as HTMLInputElement).value.split(',').map((s) => s.trim()).filter(Boolean)">
              <span v-if="taskError(activeTask, 'container_types')" class="caption err-note">{{ taskError(activeTask, 'container_types') }}</span>
            </label>
            <label class="tf" :class="{ err: !!taskError(activeTask, 't_load_s') }">
              <span class="caption">Погрузка · с</span>
              <input class="input input-mono" :value="fmt(currentTask.t_load_s)" placeholder="из норматива" @input="setTaskNum(currentTask, 't_load_s', ($event.target as HTMLInputElement).value)">
              <span v-if="taskError(activeTask, 't_load_s')" class="caption err-note">{{ taskError(activeTask, 't_load_s') }}</span>
            </label>
            <label class="tf" :class="{ err: !!taskError(activeTask, 't_unload_s') }">
              <span class="caption">Разгрузка · с</span>
              <input class="input input-mono" :value="fmt(currentTask.t_unload_s)" placeholder="из норматива" @input="setTaskNum(currentTask, 't_unload_s', ($event.target as HTMLInputElement).value)">
              <span v-if="taskError(activeTask, 't_unload_s')" class="caption err-note">{{ taskError(activeTask, 't_unload_s') }}</span>
            </label>
            <label class="tf" :class="{ edited: taskEdited(currentTask, 'staff_fte_now'), err: !!taskError(activeTask, 'staff_fte_now') }">
              <span class="caption">Персонал сейчас · чел.</span>
              <input class="input input-mono" :value="fmt(currentTask.staff_fte_now)" placeholder="не задано" @input="setTaskNum(currentTask, 'staff_fte_now', ($event.target as HTMLInputElement).value)">
              <span v-if="taskError(activeTask, 'staff_fte_now')" class="caption err-note">{{ taskError(activeTask, 'staff_fte_now') }}</span>
              <span v-else-if="!taskEdited(currentTask, 'staff_fte_now') && taskSource(currentTask.process_code, 'staff_fte_now')" class="caption src-note">{{ taskSource(currentTask.process_code, 'staff_fte_now') }}</span>
            </label>
          </div>
          <div v-if="!taskEdited(currentTask, 'flow_per_day') && taskSource(currentTask.process_code) && !taskSource(currentTask.process_code, 'flow_per_day')" class="caption src-note">{{ taskSource(currentTask.process_code) }}</div>
          <div class="pane-foot">
            <UiButton variant="secondary" @click="pane = 'site'"><template #icon><PhArrowLeft :size="16" weight="bold" /></template>К предприятию</UiButton>
            <UiButton v-if="activeTask < tasks.length - 1" @click="activeTask += 1">Следующий процесс<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
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
.params { display: grid; gap: var(--space-4); }
.pane-switch { max-width: 480px; }
.groups { display: grid; gap: var(--space-4); }
.group { padding: var(--space-6); display: grid; gap: var(--space-5); }
.group > * { position: relative; z-index: 1; }
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
.upload-note { margin: 0; }
.pane-foot { display: flex; flex-wrap: wrap; gap: 10px; }
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
  .fields, .task-grid { grid-template-columns: 1fr; }
  .proc-layout { grid-template-columns: 1fr; }
  .proc-nav { position: static; }
}
</style>
