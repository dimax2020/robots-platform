export const fetchErrorMessage = (e: unknown, fallback: string) => {
  const err = e as { data?: { detail?: unknown }; message?: string }
  const detail = err?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail)) {
    return detail.map((item) => (item as { msg?: string }).msg ?? String(item)).join('; ')
  }
  return err?.message || fallback
}
