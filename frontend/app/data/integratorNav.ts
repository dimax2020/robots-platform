import type { Component } from 'vue'
import { PhIdentificationCard, PhListChecks, PhChatCircle } from '@phosphor-icons/vue'

export interface IntegratorNavItem { to: string; label: string; icon: Component; note: string }

export const integratorNav: IntegratorNavItem[] = [
  { to: '/integrator', label: 'Профиль', icon: PhIdentificationCard, note: 'Компания, логотип и документы' },
  { to: '/integrator/requests', label: 'Запросы', icon: PhListChecks, note: 'Проекты, которые прислали заказчики' },
  { to: '/integrator/chat', label: 'Чат', icon: PhChatCircle, note: 'Переписка по проекту' },
]

/** «Профиль» горит только на корне кабинета. */
export const activeIntegratorPath = (path: string) => {
  if (path === '/integrator') return '/integrator'
  let best = ''
  for (const item of integratorNav) {
    if (item.to === '/integrator') continue
    if ((path === item.to || path.startsWith(`${item.to}/`)) && item.to.length > best.length) best = item.to
  }
  return best
}
