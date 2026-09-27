export default defineNuxtPlugin(async () => {
  await useAuth().ensure()
})
