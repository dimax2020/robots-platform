import { platformGet } from '~/composables/usePlatform'
import { asObjectType } from '~/composables/useLiveProject'

/** Опубликованный демо-объект: обычный проект платформы, который ведёт администратор. */
export interface DemoProject {
  id: string
  slug: string | null
  name: string
  object_code: string
  object_name: string
  industry: string
  is_demo: boolean
  published: boolean
  area_m2: number | null
  shifts_per_day: number | null
  processes: number
  tasks: number
  has_layout: boolean
  overrides: number
}

export const demoPath = (row: Pick<DemoProject, 'id' | 'slug'>) => `/projects/${row.slug || row.id}`
export const demoObjectType = (row: Pick<DemoProject, 'object_code'>) => asObjectType(row.object_code)

/** Список опубликованных демо: один запрос на сессию, общий для шапки, подвала, главной и списка проектов. */
export function useDemoProjects() {
  const items = useState<DemoProject[]>('demo-projects', () => [])
  const loaded = useState('demo-projects-loaded', () => false)
  const pending = useState('demo-projects-pending', () => false)

  const load = async (force = false) => {
    if (import.meta.server || pending.value || (loaded.value && !force)) return
    pending.value = true
    try {
      const page = await platformGet<{ items: DemoProject[] }>('/projects/demo')
      items.value = page.items
      loaded.value = true
    } catch {
      /* без платформы демо просто не показываются */
    } finally {
      pending.value = false
    }
  }

  onMounted(() => { void load() })

  const byObject = (code: string) => items.value.find((row) => row.object_code === code) ?? null
  const first = computed(() => items.value.find((row) => row.object_code === 'warehouse') ?? items.value[0] ?? null)

  return { items, pending, loaded, load, byObject, first }
}
