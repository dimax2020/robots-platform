import { placeholderFor } from '~/data/placeholders'

/* Битая картинка (сайт вендора не отвечает, ссылка устарела) подменяется локальной заглушкой по названию робота.
   Слушаем ошибки загрузки на всём документе: так не нужно помнить про обработчик в каждом месте с фото. */
export default defineNuxtPlugin(() => {
  document.addEventListener('error', (event) => {
    const img = event.target
    if (!(img instanceof HTMLImageElement) || img.dataset.fallback) return
    img.dataset.fallback = '1'
    img.src = placeholderFor(img.alt || '')
  }, true)
})
