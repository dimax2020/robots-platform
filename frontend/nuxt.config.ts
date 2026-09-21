// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },
  css: ['~/assets/css/main.css'],
  runtimeConfig: {
    // Адрес для SSR. По умолчанию через traefik на :80 — единственный порт, опубликованный
    // на хост, поэтому `bun run dev` работает без правок. В compose переопределяется на
    // http://api:8000/api/v1, чтобы SSR шёл к контейнеру напрямую.
    apiBaseServer: process.env.NUXT_API_BASE_SERVER || 'http://localhost/api/v1',
    public: {
      // Браузер ходит на тот же origin: в compose путь /api отдаёт traefik,
      // в dev-режиме — прокси из routeRules ниже
      apiBase: process.env.NUXT_PUBLIC_API_BASE || '/api/v1',
    },
  },
  // В режиме `bun run dev` Nuxt слушает 3000, а API внутри compose: прокидываем /api через traefik
  routeRules: {
    '/api/**': { proxy: `${process.env.NUXT_DEV_API_ORIGIN || 'http://localhost'}/api/**` },
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
