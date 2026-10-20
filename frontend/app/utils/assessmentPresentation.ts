import type { MatchHit } from '../composables/usePlatformCompare'

export const assessmentLabel = (hit: MatchHit): string => {
  if (hit.verdict === 'pass' && (hit.applicability === 'conditional' || hit.assumptions?.length || hit.uses_demo_synthetic)) return 'Подходит при допущениях'
  return ({ pass: 'Подходит', unknown: 'Требуется уточнение', fail: 'Несовместим', conditional: 'Требуется уточнение' } as Record<string, string>)[hit.verdict] || 'Требуется уточнение'
}
export const assessmentTone = (hit: MatchHit): 'ok' | 'warn' | 'info' | 'danger' => {
  if (hit.verdict === 'fail') return 'danger'
  if (hit.verdict !== 'pass') return 'info'
  return assessmentLabel(hit) === 'Подходит' ? 'ok' : 'warn'
}
export const significantReasons = (hit: MatchHit) => (hit.significant_reasons ?? hit.reasons ?? [])
  .filter(r => r.severity === 'fail' || r.severity === 'unknown')

export const countExplanation = (hit: MatchHit): string => {
  if (hit.count != null) return `${hit.count.toLocaleString('ru-RU')} шт.`
  const reasons = hit.sizing?.reasons ?? []
  if (reasons.length > 2) return 'Уточните параметры нагрузки и рабочего режима — список ниже.'
  return reasons.map(r => r.message).join(' · ') || 'Уточните производительность и рабочий режим решения.'
}

export const clarificationMessages = (hit: MatchHit): string[] => [...new Set([
  ...(hit.clarifications ?? hit.reasons ?? []).map(r => r.message),
  ...(hit.economic_reasons ?? []).map(r => r.message),
])]
