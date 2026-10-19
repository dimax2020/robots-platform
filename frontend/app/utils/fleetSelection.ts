/** Тот же confirmed_economic_ready_v1, что и серверный assessment.select_hit. */
export interface EligibilityHit {
  product_id: string
  verdict: string
  count?: number | null
  economic_ready?: boolean
  economic_reasons?: { code: string; message: string }[]
}
export interface EligibilityGroup {
  best_product_id?: string | null
  hits: EligibilityHit[]
}
/** Технически подходящее решение можно сравнивать до определения количества и цены. */
export const includedInTechnicalComparison = (hit: EligibilityHit): boolean => hit.verdict === 'pass'
export const eligibleForEconomy = (hit: EligibilityHit | undefined): boolean => Boolean(
  hit && hit.verdict === 'pass' && hit.economic_ready === true
  && typeof hit.count === 'number' && Number.isFinite(hit.count) && Number.isInteger(hit.count) && hit.count > 0,
)
export function automaticChoice(group: EligibilityGroup): string {
  const hit = group.hits.find((h) => h.product_id === group.best_product_id)
  return eligibleForEconomy(hit) ? hit!.product_id : ''
}
export function selectionIssue(group: EligibilityGroup, chosenId: string): string {
  if (!chosenId) return 'Нет подтверждённого решения с известным количеством и ценой.'
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
