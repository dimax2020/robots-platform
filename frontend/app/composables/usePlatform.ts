import type { Product } from '~/data/catalog'
import { photoFor } from '~/data/placeholders'

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
  solution_type?: { code: string; name: string } | null
}

export function cardToProduct(card: PlatformCard): Product {
  const raw = (card.availability || '').toLowerCase()
  const availability = raw === 'operation' || raw.includes('эксплуата')
    ? 'operation'
    : raw === 'rnd' || raw.includes('разработ')
      ? 'rnd'
      : 'piloting'
  const known = Boolean(card.availability) && (raw === 'operation' || raw === 'rnd' || raw === 'piloting' || raw.includes('эксплуата') || raw.includes('разработ') || raw.includes('пилот'))
  return {
    id: card.id,
    slug: card.slug,
    name: card.name,
    manufacturer: card.manufacturer || 'Не указан',
    legalEntity: '',
    country: '',
    city: '',
    availability: known ? availability : 'piloting',
    trl: card.trl ?? 0,
    marketPotential: 0,
    autoMatch: (card.trl ?? 0) >= 5 && availability !== 'rnd' && known,
    solutionType: card.solution_type?.name ?? '',
    solutionTypeCode: card.solution_type?.code ?? '',
    family: '',
    processes: [],
    objects: [],
    industries: [],
    image: photoFor(card.image_url, card.name),
    summary: '',
    priceRub: card.price_rub ?? undefined,
    highlights: (card.highlights ?? []).map((rawLine) => {
      const prefixes = ['Грузоподъёмность', 'Скорость', 'Проход', 'Работа']
      const label = prefixes.find((item) => rawLine.startsWith(`${item} `))
      if (!label) return { label: rawLine, value: 'нет данных' }
      return { label, value: rawLine.slice(label.length).trim() }
    }),
    attrs: [],
    cases: [],
    completeness: card.trl ?? 0,
  }
}

export interface PlatformPage {
  items: PlatformCard[]
  next_cursor: string | null
  total: number
}

export async function platformGet<T>(path: string) {
  return await $fetch<T>(`${usePlatformBase()}${path}`, { credentials: 'include' })
}

export async function platformSend<T>(path: string, method: 'POST' | 'PUT' | 'PATCH' | 'DELETE', body?: Record<string, unknown>) {
  return await $fetch<T>(`${usePlatformBase()}${path}`, { method, body, credentials: 'include' })
}
