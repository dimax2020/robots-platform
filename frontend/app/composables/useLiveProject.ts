import type { MaybeRefOrGetter } from 'vue'
import { steps, type ObjectType, type Project } from '~/data/projects'
import { platformGet, platformSend } from '~/composables/usePlatform'

export interface LiveProcess {
  code: string
  name: string
  enabled: boolean
  /** Почему процесс выключили на шаге экономики. Пусто, если выключили вручную на шаге параметров. */
  disabled_reason?: string | null
}

export interface LiveRecord {
  id: string
  slug: string | null
  name: string
  object_code: string
  object_name: string | null
  industry: string
  site: Record<string, unknown>
  tasks: Record<string, unknown>[]
  processes: LiveProcess[]
  is_demo: boolean
  published: boolean
  owner_id: string | null
  /** Сервер решает: администратор правит всё, владелец — свой проект, демо для остальных только читается. */
  can_edit: boolean
}

export const asObjectType = (code: string): ObjectType =>
  code === 'airport' || code === 'hospital' ? code : 'warehouse'

export const shellOf = (record: LiveRecord): Project => ({
  id: record.slug || record.id,
  name: record.name,
  objectType: asObjectType(record.object_code),
  industry: record.industry || record.object_name || '',
  updatedAt: '',
  catalogVersion: 'платформа',
  modelVersion: 'платформа',
  step: steps.length + 1,
  tasks: record.processes.filter((item) => item.enabled).length,
  isDemo: record.is_demo,
  published: record.published,
  readonly: !record.can_edit,
})

/**
 * Проект платформы по UUID или постоянному адресу демо (demo-warehouse).
 * Демо больше не живёт в коде: это обычный проект администратора, опубликованный для просмотра.
 */
export function useLiveProject(id: MaybeRefOrGetter<string>) {
  const key = computed(() => toValue(id))
  const record = ref<LiveRecord | null>(null)
  const pending = ref(true)
  const error = ref<unknown>(null)

  const load = async () => {
    error.value = null
    pending.value = true
    try {
      record.value = await platformGet<LiveRecord>(`/projects/${key.value}`)
    } catch (err) {
      record.value = null
      error.value = err
    } finally {
      pending.value = false
    }
  }

  watch(key, () => { void load() }, { immediate: true })

  const shell = computed<Project | undefined>(() => (record.value ? shellOf(record.value) : undefined))
  const site = computed(() => record.value?.site ?? {})
  const tasks = computed(() => record.value?.tasks ?? [])
  const isDemo = computed(() => Boolean(record.value?.is_demo))
  const canEdit = computed(() => Boolean(record.value?.can_edit))
  const readonly = computed(() => Boolean(record.value) && !record.value!.can_edit)
  const objectCode = computed(() => record.value?.object_code ?? '')

  const save = async (nextSite: Record<string, unknown>, nextTasks: unknown[], enabled?: Record<string, boolean>, reasons?: Record<string, string>) => {
    const body: Record<string, unknown> = { site: nextSite, tasks: nextTasks }
    if (enabled) body.enabled = enabled
    if (reasons) body.reasons = reasons
    record.value = await platformSend<LiveRecord>(`/projects/${key.value}`, 'PATCH', body)
  }

  return { shell, record, site, tasks, pending, error, isDemo, canEdit, readonly, objectCode, load, save }
}
