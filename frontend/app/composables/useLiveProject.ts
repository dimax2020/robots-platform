import type { MaybeRefOrGetter } from 'vue'
import { projects, type ObjectType, type Project } from '~/data/projects'
import { platformGet, platformSend } from '~/composables/usePlatform'

export interface LiveProcess {
  code: string
  name: string
  enabled: boolean
}

export interface LiveRecord {
  id: string
  name: string
  object_code: string
  object_name: string | null
  industry: string
  site: Record<string, unknown>
  tasks: Record<string, unknown>[]
  processes: LiveProcess[]
}

export const asObjectType = (code: string): ObjectType =>
  code === 'airport' || code === 'hospital' ? code : 'warehouse'

export const shellOf = (record: LiveRecord): Project => ({
  id: record.id,
  name: record.name,
  objectType: asObjectType(record.object_code),
  industry: record.industry || record.object_name || '',
  updatedAt: '',
  catalogVersion: 'платформа',
  modelVersion: 'платформа',
  step: 2,
  tasks: record.processes.filter((item) => item.enabled).length,
})

export function useLiveProject(id: MaybeRefOrGetter<string>) {
  const key = computed(() => toValue(id))
  const demo = computed(() => projects.find((item) => item.isDemo && item.id === key.value))
  const record = ref<LiveRecord | null>(null)
  const demoSite = ref<Record<string, unknown>>({})
  const pending = ref(true)
  const error = ref<unknown>(null)

  const load = async () => {
    error.value = null
    if (demo.value) {
      record.value = null
      pending.value = true
      try {
        const form = await platformGet<{ fields: { key: string; default: unknown }[] }>(`/catalog/objects/${demo.value.objectType}/fields`)
        const site: Record<string, unknown> = {}
        for (const field of form.fields) {
          if (field.default !== null && field.default !== undefined && field.default !== '') site[field.key] = field.default
        }
        demoSite.value = site
      } catch (err) {
        error.value = err
      } finally {
        pending.value = false
      }
      return
    }
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

  const shell = computed<Project | undefined>(() => demo.value ?? (record.value ? shellOf(record.value) : undefined))
  const site = computed(() => (demo.value ? demoSite.value : record.value?.site ?? {}))
  const tasks = computed(() => record.value?.tasks ?? [])
  const isDemo = computed(() => Boolean(demo.value))
  const objectCode = computed(() => demo.value?.objectType ?? record.value?.object_code ?? '')

  const save = async (nextSite: Record<string, unknown>, nextTasks: unknown[], enabled?: Record<string, boolean>) => {
    const body: Record<string, unknown> = { site: nextSite, tasks: nextTasks }
    if (enabled) body.enabled = enabled
    record.value = await platformSend<LiveRecord>(`/projects/${key.value}`, 'PATCH', body)
  }

  return { shell, record, site, tasks, pending, error, isDemo, objectCode, load, save }
}
