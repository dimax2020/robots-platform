// v-reveal: появление блока при попадании в вьюпорт.
// SSR отдаёт data-reveal (атрибут не участвует в проверке гидрации, в отличие от class/style),
// клиент навешивает наблюдатель и добавляет .is-in.
const stepOf = (v: unknown) => (typeof v === 'number' ? Math.max(0, Math.min(Math.round(v), 5)) : 0)

export default defineNuxtPlugin((nuxtApp) => {
  let io: IntersectionObserver | null = null
  const get = () => {
    if (io) return io
    io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting) {
            e.target.classList.add('is-in')
            io?.unobserve(e.target)
          }
        }
      },
      { rootMargin: '0px 0px -8% 0px', threshold: 0.08 },
    )
    return io
  }

  nuxtApp.vueApp.directive('reveal', {
    getSSRProps(binding) {
      return { 'data-reveal': String(stepOf(binding.value)) }
    },
    mounted(el: HTMLElement, binding) {
      el.dataset.reveal = String(stepOf(binding.value))
      if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        el.classList.add('is-in')
        return
      }
      get().observe(el)
    },
    unmounted(el: HTMLElement) {
      io?.unobserve(el)
    },
  })
})
