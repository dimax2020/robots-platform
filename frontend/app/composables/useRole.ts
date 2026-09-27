import { useAuth } from '~/composables/useAuth'

export type Role = 'guest' | 'user' | 'admin'

export const roleLabel: Record<Role, string> = {
  guest: 'Гость',
  user: 'Пользователь',
  admin: 'Администратор',
}

export const useRole = () => {
  const { user } = useAuth()
  const role = computed<Role>(() => user.value?.role ?? 'guest')
  return { role }
}

export interface ComparePick {
  slug: string
  name: string
  image: string
  solutionType: string
  manufacturer: string
}

export const useCompare = () => {
  const picks = useState<ComparePick[]>('compare-picks', () => [])
  const ids = computed(() => picks.value.map((item) => item.slug))
  const toggle = (slug: string, card?: Omit<ComparePick, 'slug'>) => {
    if (picks.value.some((item) => item.slug === slug)) {
      picks.value = picks.value.filter((item) => item.slug !== slug)
      return
    }
    picks.value = [...picks.value, { slug, name: card?.name || slug, image: card?.image || '', solutionType: card?.solutionType || '', manufacturer: card?.manufacturer || '' }]
  }
  const has = (slug: string) => picks.value.some((item) => item.slug === slug)
  const clear = () => { picks.value = [] }
  return { ids, picks, toggle, has, clear }
}
