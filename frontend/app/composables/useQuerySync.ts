/**
 * Меняет query в адресе без навигации роутера. router.replace с одним только query
 * оставляет анимацию перехода страниц (mode: out-in) недоигранной, и следующая страница не открывается.
 */
export function replaceQuery(patch: Record<string, string | undefined>) {
  if (!import.meta.client) return
  const url = new URL(window.location.href)
  for (const [key, value] of Object.entries(patch)) {
    if (value) url.searchParams.set(key, value)
    else url.searchParams.delete(key)
  }
  const next = `${url.pathname}${url.search}${url.hash}`
  window.history.replaceState({ ...window.history.state, current: next }, '', next)
}
