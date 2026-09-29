import type { Component } from 'vue'
import {
  PhSquaresFour, PhBuildings, PhSlidersHorizontal, PhListChecks, PhCalculator, PhStack,
  PhPackage, PhTag, PhRocketLaunch, PhUploadSimple, PhLinkSimple, PhTreeStructure, PhFactory, PhShapes, PhPlay, PhFunnel,
} from '@phosphor-icons/vue'

export interface AdminNavItem { to: string; label: string; icon: Component; note: string }
export interface AdminNavGroup { label: string; items: AdminNavItem[] }

export const adminOverview: AdminNavItem = { to: '/admin', label: 'Обзор', icon: PhSquaresFour, note: 'Что требует внимания' }

export const adminNav: AdminNavGroup[] = [
  {
    label: 'Проекты',
    items: [
      { to: '/admin/demo', label: 'Демо-объекты', icon: PhPlay, note: 'Собрать как проект и опубликовать для просмотра' },
    ],
  },
  {
    label: 'Модель подбора',
    items: [
      { to: '/admin/objects', label: 'Объекты', icon: PhBuildings, note: 'Поля расчёта и процессы объекта' },
      { to: '/admin/processes', label: 'Процессы', icon: PhSlidersHorizontal, note: 'Условия подбора, количество, схема' },
      { to: '/admin/filters', label: 'Общие фильтры', icon: PhFunnel, note: 'Правила для всех процессов: готовность робота' },
      { to: '/admin/coverage', label: 'Список продуктов', icon: PhListChecks, note: 'Роботы процесса и недостающие данные' },
    ],
  },
  {
    label: 'Экономика',
    items: [
      { to: '/admin/norms', label: 'Нормативы', icon: PhCalculator, note: 'Коэффициенты и их источники' },
      { to: '/admin/norms/types', label: 'По типам решений', icon: PhStack, note: 'Переопределения для типа робота' },
    ],
  },
  {
    label: 'Продукты',
    items: [
      { to: '/admin/products', label: 'Карточки', icon: PhPackage, note: 'Фото, характеристики, источники' },
      { to: '/admin/products/attributes', label: 'Характеристики', icon: PhTag, note: 'Справочник: подписи, группы, единицы' },
    ],
  },
  {
    label: 'Импорт данных',
    items: [
      { to: '/admin/parsers', label: 'Парсеры', icon: PhRocketLaunch, note: 'Расписание обхода сайтов' },
      { to: '/admin/tables', label: 'Таблицы', icon: PhUploadSimple, note: 'CSV каталога и ручных характеристик' },
      { to: '/admin/sources', label: 'Источники', icon: PhLinkSimple, note: 'Реестр и достоверность A–D' },
    ],
  },
  {
    label: 'Каталог',
    items: [
      { to: '/admin/catalog', label: 'Дерево', icon: PhTreeStructure, note: 'Отрасль → объект → процесс → тип → продукт' },
      { to: '/admin/catalog/industries', label: 'Отрасли', icon: PhFactory, note: 'Отрасли и их объекты' },
      { to: '/admin/catalog/types', label: 'Типы решений', icon: PhShapes, note: 'Типы и продукты без типа' },
    ],
  },
]

const allItems = [adminOverview, ...adminNav.flatMap((group) => group.items)]

/** Активен пункт с самым длинным совпадающим префиксом: «Нормативы» не горят на странице «По типам». */
export const activeAdminPath = (path: string) => {
  if (path === '/admin') return '/admin'
  let best = ''
  for (const item of allItems) {
    if (item.to === '/admin') continue
    if ((path === item.to || path.startsWith(`${item.to}/`)) && item.to.length > best.length) best = item.to
  }
  return best
}
