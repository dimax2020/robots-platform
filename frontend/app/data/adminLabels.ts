import type { Confidence } from '~/data/catalog'

export const familyLabel: Record<string, string> = {
  flow_cycle: 'Поток и рейсы',
  station_robots: 'Станции и ячейки',
  area_window: 'Площадь за окно времени',
  perimeter_rounds: 'Обход маршрута',
  count_window: 'Счёт мест за окно',
}

/** Виды источников Platform: у парсеров свой вид, в прежнем каталоге его не было. */
export const platformSourceKinds: { code: string; label: string; confidence: Confidence; manual: boolean }[] = [
  { code: 'vendor', label: 'Производитель', confidence: 'A', manual: true },
  { code: 'dealer', label: 'Дилер или интегратор', confidence: 'B', manual: true },
  { code: 'catalog', label: 'Каталог организатора', confidence: 'B', manual: true },
  { code: 'parser', label: 'Парсер сайта', confidence: 'B', manual: false },
  { code: 'media', label: 'СМИ, обзор', confidence: 'C', manual: true },
  { code: 'analogue', label: 'Оценка по аналогу', confidence: 'C', manual: true },
  { code: 'assumption', label: 'Допущение команды', confidence: 'D', manual: true },
]

export const sourceKindName = (code: string) => platformSourceKinds.find((item) => item.code === code)?.label ?? code
export const confidenceOf = (code: string): Confidence => platformSourceKinds.find((item) => item.code === code)?.confidence ?? 'D'
export const needsRationale = (code: string) => code === 'analogue' || code === 'assumption'

export const attrGroupLabel: Record<string, string> = {
  identification: 'Идентификация',
  technical: 'Технические характеристики',
  infrastructure: 'Инфраструктура',
  economics: 'Экономика',
  applicability: 'Применимость',
  data_quality: 'Качество данных',
  '': 'Прочие характеристики',
}
export const attrGroupOrder = ['identification', 'technical', 'infrastructure', 'economics', 'applicability', 'data_quality', '']

export const fieldKindLabel: Record<string, string> = { number: 'Число', int: 'Целое', bool: 'Да / нет', text: 'Текст' }

export const pluralRu = (n: number, one: string, few: string, many: string) => {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few
  return many
}
