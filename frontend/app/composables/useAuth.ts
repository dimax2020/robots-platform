import { platformGet, platformSend } from '~/composables/usePlatform'

export interface AuthUser {
  login: string
  role: 'guest' | 'user' | 'admin'
}

export function useAuth() {
  const user = useState<AuthUser | null>('auth-user', () => null)
  const ready = useState('auth-ready', () => false)

  const ensure = async () => {
    if (import.meta.server) return user.value
    if (ready.value) return user.value
    try {
      user.value = await platformGet<AuthUser>('/auth/me')
    } catch {
      user.value = null
    }
    ready.value = true
    return user.value
  }

  const login = async (loginName: string, password: string) => {
    user.value = await platformSend<AuthUser>('/auth/login', 'POST', { login: loginName, password })
    ready.value = true
    return user.value
  }

  const logout = async () => {
    try {
      await platformSend('/auth/logout', 'POST')
    } catch {
      /* cookie всё равно сбрасываем на клиенте */
    }
    user.value = null
    ready.value = true
  }

  return { user, ready, ensure, login, logout }
}
