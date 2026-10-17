export default defineNuxtRouteMiddleware(async () => {
  if (import.meta.server) return
  const user = await useAuth().ensure()
  if (!user) return navigateTo('/login')
  // Чужую роль не пускаем в кабинет: там только заявки своего производителя.
  if (user.role !== 'vendor') return navigateTo(user.role === 'admin' ? '/admin' : '/projects')
})