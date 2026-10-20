export default defineNuxtRouteMiddleware(async () => {
  if (import.meta.server) return
  const user = await useAuth().ensure()
  if (!user) return navigateTo('/login')
  // Чужой роли в кабинете интегратора делать нечего.
  if (user.role !== 'integrator') {
    if (user.role === 'admin') return navigateTo('/admin')
    if (user.role === 'vendor') return navigateTo('/vendor')
    return navigateTo('/projects')
  }
})
