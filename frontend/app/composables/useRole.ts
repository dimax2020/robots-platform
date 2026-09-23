export type Role = 'guest' | 'user' | 'admin'

export const roleLabel: Record<Role, string> = {
  guest: 'Гость',
  user: 'Пользователь',
  admin: 'Администратор',
}

export const useRole = () => {
  const role = useState<Role>('role', () => 'guest')
  const setRole = (r: Role) => { role.value = r }
  return { role, setRole }
}

// Список моделей для сравнения (заглушка на клиенте)
export const useCompare = () => {
  // Пусто: мок-идентификаторы давали счётчик «3» при пустой странице сравнения
  const ids = useState<string[]>('compare', () => [])
  const toggle = (id: string) => {
    ids.value = ids.value.includes(id) ? ids.value.filter((x) => x !== id) : [...ids.value, id]
  }
  const has = (id: string) => ids.value.includes(id)
  const clear = () => { ids.value = [] }
  return { ids, toggle, has, clear }
}
