// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  css: ['katex/dist/katex.min.css', '~/assets/css/main.css'],
  runtimeConfig: {
    // Куда server/routes/platform отправляет /platform/**, уже без префикса. Меняется при запуске
    // переменной NUXT_PLATFORM_API_UPSTREAM: в контейнере — http://platform-api:8000,
    // в `npm run dev` — traefik из compose, который сам снимает /platform.
    platformApiUpstream: `${process.env.NUXT_DEV_API_ORIGIN || 'http://localhost'}/platform`,
    public: {
      // Браузер и SSR ходят на тот же origin, что и сайт.
      platformApiBase: process.env.NUXT_PUBLIC_PLATFORM_API_BASE || '/platform/api/v1',
    },
  },
  app: {
    head: {
      htmlAttrs: { lang: 'ru' },
      title: 'Платформа роботизации',
      meta: [
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'description', content: 'Каталог и подбор роботизированных решений для склада, аэропорта и медучреждения.' },
        { name: 'theme-color', content: '#EEF2F0' },
      ],
      link: [
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Unbounded:wght@600;700&family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500;700&display=swap',
        },
      ],
    },
    pageTransition: { name: 'page', mode: 'out-in' },
  },
})
