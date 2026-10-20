/* Запросы «сообщить, когда вендор пополнит данные о роботе». Общие для подбора и сравнения: отмеченный на одном шаге
   робот отмечен и на другом. Хранятся в браузере; если хранилище недоступно — работают до перезагрузки страницы. */
const KEY = 'platform-vendor-clarifications'

export function useVendorNotify() {
  const requested = useState<string[]>('vendor-notify', () => [])
  onMounted(() => {
    try {
      const saved: unknown = JSON.parse(localStorage.getItem(KEY) || '[]')
      if (Array.isArray(saved)) requested.value = [...new Set([...requested.value, ...saved.filter((id): id is string => typeof id === 'string')])]
    } catch { /* хранилище недоступно */ }
  })
  const isRequested = (productId: string) => requested.value.includes(productId)
  const request = (productId: string) => {
    requested.value = [...new Set([...requested.value, productId])]
    try { localStorage.setItem(KEY, JSON.stringify(requested.value)) } catch { /* отметка живёт до перезагрузки */ }
  }
  return { isRequested, request }
}
