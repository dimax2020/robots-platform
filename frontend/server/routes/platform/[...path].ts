// /platform/** уходит в API по внутренней сети. Префикс снимается: API отвечает на /api/v1/...,
// а cookie и адреса в браузере остаются на одном origin с сайтом.
export default defineEventHandler((event) => {
  const upstream = String(useRuntimeConfig(event).platformApiUpstream || '').replace(/\/$/, '')
  const rest = event.path.replace(/^\/platform/, '') || '/'
  return proxyRequest(event, `${upstream}${rest}`)
})
