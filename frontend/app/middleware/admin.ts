export default defineNuxtRouteMiddleware(async () => {
  if (import.meta.server) return
  const user = await useAuth().ensure()
  if (!user) return navigateTo('/login')
  if (user.role !== 'admin') return navigateTo('/projects')
})
