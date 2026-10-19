import type { Ref } from 'vue'
import type { DemoSyntheticValue } from '~/utils/demoSynthetic'
import { eligibleForEconomy, includedInTechnicalComparison, automaticChoice, selectionIssue, normalizeCompareStore } from '~/utils/fleetSelection'

export interface RobotSpec { key: string; label: string; unit: string; direction: 'high' | 'low'; value: number }
export interface MatchHit {
  uses_demo_synthetic?: boolean
  demo_synthetic?: DemoSyntheticValue[]
  vendor_confirmation_fields?: string[]
  product_id: string
  name: string
  slug: string
  verdict: string
  notes: string[]
  image_url?: string | null
  trl?: number | null
  stage?: string | null
  count?: number | null
  count_note?: string
  reasons?: { code: string; message: string; severity: string; field?: string | null; stage?: string }[]
  technical_ready?: boolean
  sizing_ready?: boolean
  economic_ready?: boolean
  demo_economic_ready?: boolean
  calculation_mode?: string
  economic_reasons?: { code: string; message: string }[]
  specs?: RobotSpec[]
  sizing?: { model?: string | null; reasons: { code: string; message: string }[] }
}
export interface MatchGroup { process_code: string; process_name: string; best_product_id?: string | null; demo_best_product_id?: string | null; calculation_mode?: string; technical_best_product_id?: string | null; hits: MatchHit[] }

interface CompareStore {
  extra: Record<string, string[]>
  excluded: Record<string, string[]>
  chosen: Record<string, string>
  confirmed: Record<string, boolean>
}

const emptyStore = (): CompareStore => ({ extra: {}, excluded: {}, chosen: {}, confirmed: {} })

export function usePlatformCompare(projectId: Ref<string>) {
  // Сравнение и экономика используют один выбор при переходах внутри приложения.
  const stores = useState<Record<string, CompareStore>>('platform-compare', () => ({}))
  const storageError = useState<string>('platform-compare-storage-error', () => '')
  const store = computed({
    get: () => stores.value[projectId.value] ?? emptyStore(),
    set: (value: CompareStore) => { stores.value[projectId.value] = value },
  })

  const read = () => {
    if (!import.meta.client || !projectId.value) return
    if (stores.value[projectId.value]) return
    try {
      store.value = normalizeCompareStore(JSON.parse(localStorage.getItem(`platform-compare:${projectId.value}`) || '{}'))
    } catch {
      store.value = emptyStore()
    }
  }

  read()
  watch(projectId, read, { flush: 'sync' })
  watch(store, (value) => {
    if (!import.meta.client || !projectId.value) return
    try {
      localStorage.setItem(`platform-compare:${projectId.value}`, JSON.stringify(value))
      storageError.value = ''
    } catch {
      storageError.value = 'Браузер не разрешил сохранить выбор. Он действует в этой вкладке до перезагрузки страницы.'
    }
  }, { deep: true, flush: 'sync' })

  const listed = (bucket: Record<string, string[]>, process: string) => bucket[process] ?? []

  const inCompare = (process: string, hit: MatchHit, group?: MatchGroup) => {
    if (listed(store.value.excluded, process).includes(hit.product_id)) return false
    if (includedInTechnicalComparison(hit)) return true
    if (listed(store.value.extra, process).includes(hit.product_id)) return true
    return false
  }

  const toggleCompare = (process: string, hit: MatchHit, group?: MatchGroup) => {
    const next = { ...store.value, extra: { ...store.value.extra }, excluded: { ...store.value.excluded } }
    const drop = (rows: string[]) => rows.filter((id) => id !== hit.product_id)
    if (includedInTechnicalComparison(hit)) {
      const excluded = listed(next.excluded, process)
      next.excluded[process] = excluded.includes(hit.product_id) ? drop(excluded) : [...excluded, hit.product_id]
    } else {
      const extra = listed(next.extra, process)
      next.extra[process] = extra.includes(hit.product_id) ? drop(extra) : [...extra, hit.product_id]
    }
    store.value = next
  }

  const includedHits = (group: MatchGroup) => group.hits.filter((hit) => inCompare(group.process_code, hit, group))

  const chosenId = (group: MatchGroup) => {
    const saved = store.value.chosen[group.process_code]
    // Устаревший выбор не заменяется другой машиной молча.
    if (saved) return eligibleForEconomy(group.hits.find((h) => h.product_id === saved))
      && !listed(store.value.excluded, group.process_code).includes(saved) ? saved : ''
    const id = automaticChoice(group)
    return listed(store.value.excluded, group.process_code).includes(id) ? '' : id
  }

  const skipReason = (group: MatchGroup) => {
    const saved = store.value.chosen[group.process_code]
    if (saved && !eligibleForEconomy(group.hits.find((h) => h.product_id === saved))) return selectionIssue(group, saved)
    if (chosenId(group)) return ''
    if (!group.hits.length) return 'На процесс не назначено решений.'
    return 'Нет подтверждённого решения с известным количеством и ценой. ' + (group.hits[0]?.economic_reasons?.[0]?.message || '')
  }

  const remainingHit = (group: MatchGroup) => group.hits.find((hit) => hit.product_id === chosenId(group)) ?? null

  const picksFor = (groups: MatchGroup[]) => {
    const picks: Record<string, string> = {}
    for (const group of groups) {
      const hit = remainingHit(group)
      if (hit) picks[group.process_code] = hit.product_id
      else if (store.value.chosen[group.process_code] && !eligibleForEconomy(group.hits.find((h) => h.product_id === store.value.chosen[group.process_code]))) picks[group.process_code] = store.value.chosen[group.process_code]!
    }
    return picks
  }

  const skippedOf = (groups: MatchGroup[]) => groups.flatMap((group) => {
    const reason = skipReason(group)
    return reason ? [{ code: group.process_code, name: group.process_name, reason }] : []
  })

  const choose = (process: string, productId: string) => {
    store.value = {
      ...store.value,
      chosen: { ...store.value.chosen, [process]: productId },
      confirmed: { ...store.value.confirmed, [process]: true },
    }
  }

  const isConfirmed = (process: string) => Boolean(store.value.confirmed[process])

  const choices = computed(() => ({ ...store.value.chosen }))

  return { inCompare, toggleCompare, includedHits, chosenId, remainingHit, skipReason, picksFor, skippedOf, choose, isConfirmed, choices, storageError }
}

/** «!» у шага «Подбор» со списком процессов без робота: вместо плашки на странице. */
export const skippedAlerts = (rows: { name: string }[]) => (rows.length
  ? {
      match: {
        title: 'Не выбраны роботы для процессов:',
        items: rows.map((row) => row.name),
        note: 'Экономический парк неполный. Технически подходящим решениям могут недоставать количества, комплектации или цены. Причины указаны в подборе.',
      },
    }
  : undefined)
