import type { Ref } from 'vue'

export interface RobotSpec { key: string; label: string; unit: string; direction: 'high' | 'low'; value: number }
export interface MatchHit {
  product_id: string
  name: string
  slug: string
  verdict: string
  notes: string[]
  image_url?: string | null
  count?: number | null
  count_note?: string
  specs?: RobotSpec[]
}
export interface MatchGroup { process_code: string; process_name: string; best_product_id?: string | null; hits: MatchHit[] }

interface CompareStore {
  extra: Record<string, string[]>
  excluded: Record<string, string[]>
  chosen: Record<string, string>
  confirmed: Record<string, boolean>
}

const emptyStore = (): CompareStore => ({ extra: {}, excluded: {}, chosen: {}, confirmed: {} })

export function usePlatformCompare(projectId: Ref<string>) {
  const store = ref<CompareStore>(emptyStore())

  const read = () => {
    if (!import.meta.client || !projectId.value) return
    try {
      const raw = JSON.parse(localStorage.getItem(`platform-compare:${projectId.value}`) || '{}') as Partial<CompareStore>
      store.value = {
        extra: raw.extra ?? {},
        excluded: raw.excluded ?? {},
        chosen: raw.chosen ?? {},
        confirmed: raw.confirmed ?? {},
      }
    } catch {
      store.value = emptyStore()
    }
  }

  onMounted(read)
  watch(projectId, read)
  watch(store, (value) => {
    if (!import.meta.client || !projectId.value) return
    localStorage.setItem(`platform-compare:${projectId.value}`, JSON.stringify(value))
  }, { deep: true })

  const listed = (bucket: Record<string, string[]>, process: string) => bucket[process] ?? []

  const inCompare = (process: string, hit: MatchHit) => {
    if (listed(store.value.excluded, process).includes(hit.product_id)) return false
    if (hit.verdict === 'pass') return true
    return listed(store.value.extra, process).includes(hit.product_id)
  }

  const toggleCompare = (process: string, hit: MatchHit) => {
    const next = { ...store.value, extra: { ...store.value.extra }, excluded: { ...store.value.excluded } }
    const drop = (rows: string[]) => rows.filter((id) => id !== hit.product_id)
    if (hit.verdict === 'pass') {
      const excluded = listed(next.excluded, process)
      next.excluded[process] = excluded.includes(hit.product_id) ? drop(excluded) : [...excluded, hit.product_id]
    } else {
      const extra = listed(next.extra, process)
      next.extra[process] = extra.includes(hit.product_id) ? drop(extra) : [...extra, hit.product_id]
    }
    store.value = next
  }

  const includedHits = (group: MatchGroup) => group.hits.filter((hit) => inCompare(group.process_code, hit))

  const chosenId = (group: MatchGroup) => {
    const pool = includedHits(group)
    const saved = store.value.chosen[group.process_code]
    if (saved && pool.some((hit) => hit.product_id === saved)) return saved
    if (group.best_product_id && pool.some((hit) => hit.product_id === group.best_product_id)) return group.best_product_id
    return pool.find((hit) => hit.verdict === 'pass')?.product_id ?? pool[0]?.product_id ?? ''
  }

  const choose = (process: string, productId: string) => {
    store.value = {
      ...store.value,
      chosen: { ...store.value.chosen, [process]: productId },
      confirmed: { ...store.value.confirmed, [process]: true },
    }
  }

  const isConfirmed = (process: string) => Boolean(store.value.confirmed[process])

  return { inCompare, toggleCompare, includedHits, chosenId, choose, isConfirmed }
}
