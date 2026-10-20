import type { MatchHit } from '../composables/usePlatformCompare'

/* Статус робота для пользователя — три слова. Допущения демо-расчёта пользователю не показываем: подходящий робот просто «Подходит». */
export const assessmentLabel = (hit: MatchHit): string =>
  ({ pass: 'Подходит', fail: 'Не подходит' } as Record<string, string>)[hit.verdict] || 'Уточнить'
export const assessmentTone = (hit: MatchHit): 'ok' | 'warn' | 'info' | 'danger' => {
  if (hit.verdict === 'fail') return 'danger'
  return hit.verdict === 'pass' ? 'ok' : 'info'
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
