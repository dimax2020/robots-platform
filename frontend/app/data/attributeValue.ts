/** Числа показываются с единицей; приближение и условия остаются видимыми. */
export function formatAttributeValue(value: unknown, unit?: string | null, approximate = false, condition?: string | null): string {
  if (value == null) return 'нет данных'
  if (typeof value === 'boolean') return value ? 'да' : 'нет'
  const text = String(value)
  const bare = /^[+−\-\d.,\s×xх]+$/.test(text)
  const quantity = unit && bare ? `${text} ${unit}` : text
  return `${approximate ? '≈ ' : ''}${quantity}${condition ? ` (${condition})` : ''}`
}
