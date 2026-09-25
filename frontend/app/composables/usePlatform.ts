export function usePlatformBase() {
  const config = useRuntimeConfig()
  return config.public.platformApiBase as string
}

export interface PlatformCard {
  id: string
  slug: string
  name: string
  manufacturer: string | null
  availability: string | null
  trl: number | null
  price_rub: number | null
  image_url: string | null
  highlights?: string[]
}

export interface PlatformPage {
  items: PlatformCard[]
  next_cursor: string | null
  total: number
}

export async function platformGet<T>(path: string) {
  return await $fetch<T>(`${usePlatformBase()}${path}`)
}

export async function platformSend<T>(path: string, method: 'POST' | 'PUT' | 'PATCH', body?: unknown) {
  return await $fetch<T>(`${usePlatformBase()}${path}`, { method, body })
}
