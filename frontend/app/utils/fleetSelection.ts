/** Тот же confirmed_economic_ready_v1, что и серверный assessment.select_hit. */
export interface EligibilityHit {
  product_id: string
  verdict: string
  count?: number | null
  economic_ready?: boolean
  demo_economic_ready?: boolean
  calculation_mode?: string
  economic_reasons?: { code: string; message: string }[]
}
export interface EligibilityGroup {
  best_product_id?: string | null
  demo_best_product_id?: string | null
  calculation_mode?: string
  hits: EligibilityHit[]
}
/** Подходящие и неопределённые решения доступны для технического сравнения. */
export const includedInTechnicalComparison = (hit: EligibilityHit): boolean => ['pass', 'unknown', 'conditional'].includes(hit.verdict)
export const eligibleForEconomy = (hit: EligibilityHit | undefined): boolean => Boolean(
  hit && hit.verdict === 'pass' && (hit.economic_ready === true || hit.calculation_mode === 'demo' && hit.demo_economic_ready === true)
  && typeof hit.count === 'number' && Number.isFinite(hit.count) && Number.isInteger(hit.count) && hit.count > 0,
)
export function automaticChoice(group: EligibilityGroup): string {
  const id = group.calculation_mode === 'demo' ? group.demo_best_product_id : group.best_product_id
  const hit = group.hits.find((h) => h.product_id === id)
  return eligibleForEconomy(hit) ? hit!.product_id : ''
}
export function selectionIssue(group: EligibilityGroup, chosenId: string): string {
  if (!chosenId) return 'Нет подходящего решения с рассчитанным количеством и известной ценой.'
  const hit = group.hits.find((h) => h.product_id === chosenId)
  if (!hit) return 'Сохранённое решение отсутствует в текущем подборе. Выберите его заново.'
  if (!eligibleForEconomy(hit)) return hit.economic_reasons?.map((r) => r.message).join('; ')
    || 'Решение не допущено к экономике. Нужны подтверждённая применимость, количество и цена.'
  return ''
}

export function normalizeCompareStore(value: unknown) {
  const record = (v: unknown): Record<string, unknown> => v !== null && typeof v === 'object' && !Array.isArray(v) ? v as Record<string, unknown> : {}
  const raw = record(value)
  const lists = (v: unknown): Record<string, string[]> => Object.fromEntries(Object.entries(record(v))
    .filter(([, entry]) => Array.isArray(entry)).map(([key, entry]) => [key, (entry as unknown[]).filter((id): id is string => typeof id === 'string')]))
  return {
    extra: lists(raw.extra), excluded: lists(raw.excluded),
    chosen: Object.fromEntries(Object.entries(record(raw.chosen)).filter(([, v]) => typeof v === 'string')) as Record<string, string>,
    confirmed: Object.fromEntries(Object.entries(record(raw.confirmed)).filter(([, v]) => typeof v === 'boolean')) as Record<string, boolean>,
  }
}
