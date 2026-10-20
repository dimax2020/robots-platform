import type { Component } from 'vue'
import { PhIdentificationCard, PhRobot, PhChartPie, PhListChecks } from '@phosphor-icons/vue'

export interface VendorNavItem { to: string; label: string; icon: Component; note: string }

export const vendorNav: VendorNavItem[] = [
  { to: '/vendor', label: 'Компания', icon: PhIdentificationCard, note: 'Название, контакты и документы' },
  { to: '/vendor/robots', label: 'Роботы', icon: PhRobot, note: 'Карточки моделей и отправка на проверку' },
  { to: '/vendor/analytics', label: 'Аналитика', icon: PhChartPie, note: 'Кто участвует в подборе и чего не хватает' },
  { to: '/vendor/requests', label: 'Заявки', icon: PhListChecks, note: 'Что на проверке и что просят исправить' },
]

/** «Компания» горит только на корне кабинета, а не на вложенных страницах. */
export const activeVendorPath = (path: string) => {
  if (path === '/vendor') return '/vendor'
  let best = ''
  for (const item of vendorNav) {
    if (item.to === '/vendor') continue
    if ((path === item.to || path.startsWith(`${item.to}/`)) && item.to.length > best.length) best = item.to
  }
  return best
}
