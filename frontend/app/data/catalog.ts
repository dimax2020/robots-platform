// Заглушка каталога. Данные демонстрационные (mock): имена и числа
// подобраны правдоподобно по структуре «Информация о роботах.md».

export type Availability = 'operation' | 'piloting' | 'rnd'
export type SourceKind = 'manufacturer' | 'dealer' | 'media' | 'catalog' | 'analog' | 'assumption'
export type Confidence = 'A' | 'B' | 'C' | 'D'
export type ValueStatus = 'known' | 'unknown' | 'not_applicable'

export interface Source {
  id: string
  kind: SourceKind
  publisher: string
  url: string
  fetchedAt: string
  checkedAt: string
  quote?: string
}

export interface AttrValue {
  key: string
  label: string
  unit?: string
  group: 'identification' | 'technical' | 'infrastructure' | 'economics' | 'applicability' | 'data_quality'
  status: ValueStatus
  value?: string | number
  range?: [number, number]
  sourceId?: string
  quote?: string
}

export interface Product {
  id: string
  slug: string
  name: string
  manufacturer: string
  legalEntity: string
  country: string
  city: string
  availability: Availability
  trl: number
  marketPotential: number
  autoMatch: boolean
  solutionType: string
  solutionTypeCode: string
  processes: string[]
  objects: string[]
  image: string
  summary: string
  priceRub?: number
  priceNote?: string
  highlights: { label: string; value: string }[]
  attrs: AttrValue[]
  completeness: number
}

export const sourceKindLabel: Record<SourceKind, string> = {
  manufacturer: 'Производитель',
  dealer: 'Дилер',
  media: 'СМИ',
  catalog: 'Каталог организатора',
  analog: 'Оценка по аналогу',
  assumption: 'Допущение команды',
}

export const confidenceByKind: Record<SourceKind, Confidence> = {
  manufacturer: 'A',
  dealer: 'B',
  catalog: 'B',
  media: 'C',
  analog: 'C',
  assumption: 'D',
}

export const availabilityLabel: Record<Availability, string> = {
  operation: 'В эксплуатации',
  piloting: 'Пилот',
  rnd: 'Разработка',
}

export const availabilityTone: Record<Availability, 'ok' | 'warn' | 'neutral'> = {
  operation: 'ok',
  piloting: 'warn',
  rnd: 'neutral',
}

export const sources: Source[] = [
  { id: 's-ronavi', kind: 'manufacturer', publisher: 'Ronavi Robotics', url: 'https://ronavi.example/h1500', fetchedAt: '2026-08-14', checkedAt: '2026-09-12', quote: 'Грузоподъёмность до 1 500 кг, скорость до 1,5 м/с' },
  { id: 's-catalog', kind: 'catalog', publisher: 'Каталог ФЦ БАС, категории 1–2', url: 'file://catalog/amr-1-2.xlsx', fetchedAt: '2026-09-02', checkedAt: '2026-09-02' },
  { id: 's-catalog-79', kind: 'catalog', publisher: 'Каталог ФЦ БАС, категории 7–9 v2', url: 'file://catalog/7-9-v2.xlsx', fetchedAt: '2026-09-02', checkedAt: '2026-09-18' },
  { id: 's-avtomakon', kind: 'manufacturer', publisher: 'ГК «Автомакон»', url: 'https://avtomakon.example/g2p', fetchedAt: '2026-08-21', checkedAt: '2026-09-15', quote: 'Пропускная способность до 160 тар в час на робота' },
  { id: 's-dikom', kind: 'dealer', publisher: 'ООО «Диком-Сервис»', url: 'https://dikom.example/dmr300', fetchedAt: '2026-08-30', checkedAt: '2026-08-30' },
  { id: 's-media', kind: 'media', publisher: 'CNews', url: 'https://cnews.example/robots-2026', fetchedAt: '2026-07-11', checkedAt: '2026-07-11' },
  { id: 's-analog', kind: 'analog', publisher: 'Оценка по аналогу: класс AMR 300 кг', url: '', fetchedAt: '2026-09-05', checkedAt: '2026-09-05', quote: 'Медиана по 6 позициям класса' },
  { id: 's-team', kind: 'assumption', publisher: 'Допущение команды', url: '', fetchedAt: '2026-09-06', checkedAt: '2026-09-06' },
  { id: 's-niias', kind: 'manufacturer', publisher: 'АО «НИИАС»', url: 'https://niias.example/rover', fetchedAt: '2026-08-02', checkedAt: '2026-09-01' },
  { id: 's-mai', kind: 'manufacturer', publisher: 'МАИ', url: 'https://mai.example/patrol', fetchedAt: '2026-08-04', checkedAt: '2026-08-04' },
]

export const sourceById = (id?: string) => sources.find((s) => s.id === id)
export const confidenceOf = (id?: string): Confidence | undefined => {
  const s = sourceById(id)
  return s ? confidenceByKind[s.kind] : undefined
}

const a = (
  group: AttrValue['group'],
  key: string,
  label: string,
  value: string | number | undefined,
  unit?: string,
  sourceId?: string,
  status: ValueStatus = 'known',
  quote?: string,
): AttrValue => ({ group, key, label, value, unit, sourceId, status, quote })

export const products: Product[] = [
  {
    id: 'p-01', slug: 'ronavi-h1500', name: 'Ronavi H1500', manufacturer: 'Ronavi Robotics', legalEntity: 'ООО «Ронави Роботикс»', country: 'Россия', city: 'Москва',
    availability: 'operation', trl: 9, marketPotential: 5, autoMatch: true,
    solutionType: 'AMR палетный', solutionTypeCode: 'amr_pallet', processes: ['Внутрискладское перемещение', 'Подача на линию'], objects: ['Склад', 'Цех'],
    image: '/img/robot-amr-pallet.png', summary: 'Палетный AMR с подъёмной платформой для перемещения грузов между зонами склада.',
    priceRub: 4_200_000, priceNote: 'без пусконаладки',
    highlights: [{ label: 'Нагрузка', value: '1 500 кг' }, { label: 'Скорость', value: '1,5 м/с' }, { label: 'Автономность', value: '8 ч' }, { label: 'Навигация', value: 'Лидар SLAM' }],
    completeness: 0.92,
    attrs: [
      a('technical', 'payload_kg', 'Грузоподъёмность', 1500, 'кг', 's-ronavi', 'known', 'Грузоподъёмность до 1 500 кг'),
      a('technical', 'speed_ms', 'Скорость', '1,5', 'м/с', 's-ronavi'),
      a('technical', 'autonomy_h', 'Автономность', 8, 'ч', 's-ronavi'),
      a('technical', 'charge_min', 'Зарядка', 45, 'мин', 's-dikom'),
      a('technical', 'nav', 'Навигация', 'Лидар SLAM', undefined, 's-ronavi'),
      a('technical', 'accuracy_mm', 'Точность позиционирования', '±10', 'мм', 's-ronavi'),
      a('technical', 'dims', 'Габариты', '1 620 × 1 080 × 320', 'мм', 's-catalog'),
      a('technical', 'throughput', 'Производительность', 42, 'палет/ч', 's-analog'),
      a('infrastructure', 'wifi', 'Связь', 'Wi-Fi 5 ГГц, роуминг', undefined, 's-ronavi'),
      a('infrastructure', 'floor', 'Требования к полу', 'Ровность ≤ 5 мм на 2 м', undefined, 's-ronavi'),
      a('infrastructure', 'temp', 'Температурный режим', 'от +5 до +40', '°C', 's-catalog'),
      a('infrastructure', 'ip', 'Класс защиты', undefined, undefined, undefined, 'unknown'),
      a('economics', 'price', 'Стоимость единицы', 4_200_000, '₽', 's-dikom'),
      a('economics', 'software', 'Стоимость ПО (флот)', 1_100_000, '₽/год', 's-dikom'),
      a('economics', 'integration', 'Внедрение и интеграция', '15–20', '% от CAPEX', 's-team'),
      a('economics', 'service', 'Сервис', 8, '% от цены в год', 's-analog'),
      a('applicability', 'cases', 'Кейсы', 'Склад Wildberries Коледино; ПВЗ-хаб', undefined, 's-media'),
      a('applicability', 'risks', 'Риски', 'Узкие проезды < 1,4 м; уклон > 3%', undefined, 's-team'),
    ],
  },
  {
    id: 'p-02', slug: 'weibot-g2p-600', name: 'Weibot G2P-600', manufacturer: 'ГК «Автомакон»', legalEntity: 'ООО «Вейбот Автомакон Роботикс»', country: 'Россия', city: 'Москва',
    availability: 'operation', trl: 9, marketPotential: 5, autoMatch: true,
    solutionType: 'Goods-to-person AMR', solutionTypeCode: 'amr_g2p', processes: ['Комплектация заказов', 'Внутрискладское перемещение'], objects: ['Склад'],
    image: '/img/robot-g2p.png', summary: 'Робот подвозит стеллаж с тарой к станции комплектовщика. Кубическая схема goods-to-person.',
    priceRub: 2_900_000, priceNote: 'без стеллажей',
    highlights: [{ label: 'Нагрузка', value: '600 кг' }, { label: 'Скорость', value: '2,0 м/с' }, { label: 'Тар в час', value: '160' }, { label: 'Навигация', value: 'QR-метки' }],
    completeness: 0.88,
    attrs: [
      a('technical', 'payload_kg', 'Грузоподъёмность', 600, 'кг', 's-avtomakon'),
      a('technical', 'speed_ms', 'Скорость', '2,0', 'м/с', 's-avtomakon'),
      a('technical', 'autonomy_h', 'Автономность', 6, 'ч', 's-avtomakon'),
      a('technical', 'charge_min', 'Зарядка', 60, 'мин', 's-avtomakon'),
      a('technical', 'nav', 'Навигация', 'QR-метки на полу', undefined, 's-avtomakon'),
      a('technical', 'accuracy_mm', 'Точность позиционирования', '±5', 'мм', 's-avtomakon'),
      a('technical', 'dims', 'Габариты', '1 040 × 780 × 300', 'мм', 's-catalog'),
      a('technical', 'throughput', 'Производительность', 160, 'тар/ч', 's-avtomakon', 'known', 'Пропускная способность до 160 тар в час на робота'),
      a('infrastructure', 'wifi', 'Связь', 'Wi-Fi 5 ГГц', undefined, 's-avtomakon'),
      a('infrastructure', 'floor', 'Требования к полу', 'Ровность ≤ 3 мм на 2 м, QR-сетка 1 м', undefined, 's-avtomakon'),
      a('infrastructure', 'temp', 'Температурный режим', 'от 0 до +40', '°C', 's-avtomakon'),
      a('infrastructure', 'ip', 'Класс защиты', 'IP20', undefined, 's-avtomakon'),
      a('economics', 'price', 'Стоимость единицы', 2_900_000, '₽', 's-avtomakon'),
      a('economics', 'software', 'Стоимость ПО (флот)', 2_400_000, '₽/год', 's-avtomakon'),
      a('economics', 'integration', 'Внедрение и интеграция', '25–35', '% от CAPEX', 's-team'),
      a('economics', 'service', 'Сервис', 10, '% от цены в год', 's-analog'),
      a('applicability', 'cases', 'Кейсы', 'Фулфилмент-центр Ozon Хоругвино', undefined, 's-media'),
      a('applicability', 'risks', 'Риски', 'Перекладка QR-сетки при перепланировке', undefined, 's-team'),
    ],
  },
  {
    id: 'p-03', slug: 'dmr-300-carrier-b', name: 'DMR 300 Carrier B', manufacturer: 'ООО «Диком-Сервис»', legalEntity: 'ООО «Диком-Сервис»', country: 'Россия', city: 'Москва',
    availability: 'operation', trl: 8, marketPotential: 3, autoMatch: true,
    solutionType: 'AMR транспортный', solutionTypeCode: 'amr_transport', processes: ['Внутрискладское перемещение'], objects: ['Склад', 'Цех'],
    image: '/img/robot-amr-pallet.png', summary: 'Транспортный AMR лёгкого класса для перемещения тары и коробов между зонами.',
    priceRub: 10_800_000, priceNote: 'цена требует проверки',
    highlights: [{ label: 'Нагрузка', value: '300 кг' }, { label: 'Скорость', value: '1,2 м/с' }, { label: 'Автономность', value: 'нет данных' }, { label: 'Навигация', value: 'Лидар' }],
    completeness: 0.54,
    attrs: [
      a('technical', 'payload_kg', 'Грузоподъёмность', 300, 'кг', 's-dikom'),
      a('technical', 'speed_ms', 'Скорость', '1,2', 'м/с', 's-dikom'),
      a('technical', 'autonomy_h', 'Автономность', undefined, 'ч', undefined, 'unknown'),
      a('technical', 'charge_min', 'Зарядка', undefined, 'мин', undefined, 'unknown'),
      a('technical', 'nav', 'Навигация', 'Лидар', undefined, 's-dikom'),
      a('technical', 'accuracy_mm', 'Точность позиционирования', undefined, 'мм', undefined, 'unknown'),
      a('technical', 'dims', 'Габариты', '980 × 640 × 280', 'мм', 's-catalog'),
      a('technical', 'throughput', 'Производительность', 28, 'тар/ч', 's-analog', 'known', 'Медиана по 6 позициям класса'),
      a('infrastructure', 'wifi', 'Связь', 'Wi-Fi', undefined, 's-dikom'),
      a('infrastructure', 'floor', 'Требования к полу', undefined, undefined, undefined, 'unknown'),
      a('infrastructure', 'temp', 'Температурный режим', undefined, '°C', undefined, 'unknown'),
      a('infrastructure', 'ip', 'Класс защиты', undefined, undefined, undefined, 'unknown'),
      a('economics', 'price', 'Стоимость единицы', 10_800_000, '₽', 's-catalog'),
      a('economics', 'software', 'Стоимость ПО (флот)', undefined, '₽/год', undefined, 'unknown'),
      a('economics', 'integration', 'Внедрение и интеграция', '15–20', '% от CAPEX', 's-team'),
      a('economics', 'service', 'Сервис', 8, '% от цены в год', 's-analog'),
      a('applicability', 'cases', 'Кейсы', undefined, undefined, undefined, 'unknown'),
      a('applicability', 'risks', 'Риски', 'Цена выше соседей по классу в 7–10 раз: уточнить состав комплекса', undefined, 's-team'),
    ],
  },
  {
    id: 'p-04', slug: 'arktika-6', name: 'Арктика-6', manufacturer: 'Эйдос-Робототехника', legalEntity: 'ООО «Эйдос-Робототехника»', country: 'Россия', city: 'Казань',
    availability: 'operation', trl: 9, marketPotential: 4, autoMatch: true,
    solutionType: 'Промышленный манипулятор', solutionTypeCode: 'arm_industrial', processes: ['Паллетирование', 'Подача на линию'], objects: ['Склад', 'Цех'],
    image: '/img/robot-arm.png', summary: 'Шестиосевой манипулятор для паллетирования и обслуживания станков.',
    priceRub: 6_400_000, priceNote: 'с контроллером, без оснастки',
    highlights: [{ label: 'Нагрузка', value: '12 кг' }, { label: 'Вылет', value: '1 420 мм' }, { label: 'Повторяемость', value: '±0,03 мм' }, { label: 'Осей', value: '6' }],
    completeness: 0.9,
    attrs: [
      a('technical', 'payload_kg', 'Полезная нагрузка', 12, 'кг', 's-catalog-79'),
      a('technical', 'reach_mm', 'Вылет', 1420, 'мм', 's-catalog-79'),
      a('technical', 'repeat_mm', 'Повторяемость', '±0,03', 'мм', 's-catalog-79'),
      a('technical', 'axes', 'Осей', 6, undefined, 's-catalog-79'),
      a('technical', 'speed_ms', 'Скорость', undefined, 'м/с', undefined, 'not_applicable'),
      a('technical', 'autonomy_h', 'Автономность', undefined, 'ч', undefined, 'not_applicable'),
      a('technical', 'throughput', 'Производительность', 14, 'циклов/мин', 's-catalog-79'),
      a('infrastructure', 'power', 'Питание', '3 × 380 В, 4 кВт', undefined, 's-catalog-79'),
      a('infrastructure', 'ip', 'Класс защиты', 'IP54', undefined, 's-catalog-79'),
      a('infrastructure', 'wifi', 'Связь', 'Ethernet, PROFINET', undefined, 's-catalog-79'),
      a('economics', 'price', 'Стоимость единицы', 6_400_000, '₽', 's-catalog-79'),
      a('economics', 'software', 'Стоимость ПО', 0, '₽/год', 's-catalog-79'),
      a('economics', 'integration', 'Внедрение и интеграция', '40–60', '% от CAPEX', 's-team'),
      a('economics', 'service', 'Сервис', 6, '% от цены в год', 's-catalog-79'),
      a('applicability', 'cases', 'Кейсы', 'Паллетирование мешков 25 кг, КАМАЗ', undefined, 's-media'),
      a('applicability', 'risks', 'Риски', 'Требует ограждения и проекта безопасности', undefined, 's-team'),
    ],
  },
  {
    id: 'p-05', slug: 'kobot-kr-10', name: 'Кобот КР-10', manufacturer: 'Rozum Robotics', legalEntity: 'ООО «Розум Роботикс»', country: 'Россия', city: 'Санкт-Петербург',
    availability: 'operation', trl: 9, marketPotential: 4, autoMatch: true,
    solutionType: 'Коллаборативный робот', solutionTypeCode: 'arm_cobot', processes: ['Комплектация заказов', 'Упаковка'], objects: ['Склад', 'Цех', 'Медучреждение'],
    image: '/img/robot-cobot.png', summary: 'Коллаборативный манипулятор для упаковки и сортировки рядом с людьми без ограждения.',
    priceRub: 3_100_000, priceNote: 'с захватом',
    highlights: [{ label: 'Нагрузка', value: '10 кг' }, { label: 'Вылет', value: '1 300 мм' }, { label: 'Повторяемость', value: '±0,05 мм' }, { label: 'Осей', value: '6' }],
    completeness: 0.86,
    attrs: [
      a('technical', 'payload_kg', 'Полезная нагрузка', 10, 'кг', 's-catalog-79'),
      a('technical', 'reach_mm', 'Вылет', 1300, 'мм', 's-catalog-79'),
      a('technical', 'repeat_mm', 'Повторяемость', '±0,05', 'мм', 's-catalog-79'),
      a('technical', 'axes', 'Осей', 6, undefined, 's-catalog-79'),
      a('technical', 'throughput', 'Производительность', 9, 'циклов/мин', 's-catalog-79'),
      a('infrastructure', 'power', 'Питание', '220 В, 0,6 кВт', undefined, 's-catalog-79'),
      a('infrastructure', 'ip', 'Класс защиты', 'IP54', undefined, 's-catalog-79'),
      a('economics', 'price', 'Стоимость единицы', 3_100_000, '₽', 's-catalog-79'),
      a('economics', 'integration', 'Внедрение и интеграция', '20–30', '% от CAPEX', 's-team'),
      a('economics', 'service', 'Сервис', 5, '% от цены в год', 's-catalog-79'),
      a('applicability', 'cases', 'Кейсы', 'Упаковка косметики, «Фаберлик»', undefined, 's-media'),
      a('applicability', 'risks', 'Риски', 'Скорость ограничена нормами коллаборации', undefined, 's-team'),
    ],
  },
  {
    id: 'p-06', slug: 'avtomakon-af-1600', name: 'Автомакон AF-1600', manufacturer: 'ГК «Автомакон»', legalEntity: 'ООО «Вейбот Автомакон Роботикс»', country: 'Россия', city: 'Москва',
    availability: 'piloting', trl: 7, marketPotential: 4, autoMatch: true,
    solutionType: 'Автономный погрузчик', solutionTypeCode: 'agv_forklift', processes: ['Приёмка и отгрузка', 'Внутрискладское перемещение'], objects: ['Склад'],
    image: '/img/robot-forklift.png', summary: 'Беспилотный ричтрак для стеллажного хранения до 6 м с лидарной навигацией.',
    priceRub: 9_800_000, priceNote: 'без зарядной станции',
    highlights: [{ label: 'Нагрузка', value: '1 600 кг' }, { label: 'Высота подъёма', value: '6 000 мм' }, { label: 'Скорость', value: '1,8 м/с' }, { label: 'Навигация', value: 'Лидар 3D' }],
    completeness: 0.78,
    attrs: [
      a('technical', 'payload_kg', 'Грузоподъёмность', 1600, 'кг', 's-avtomakon'),
      a('technical', 'lift_mm', 'Высота подъёма', 6000, 'мм', 's-avtomakon'),
      a('technical', 'speed_ms', 'Скорость', '1,8', 'м/с', 's-avtomakon'),
      a('technical', 'autonomy_h', 'Автономность', 7, 'ч', 's-avtomakon'),
      a('technical', 'throughput', 'Производительность', 22, 'палет/ч', 's-analog'),
      a('infrastructure', 'floor', 'Требования к полу', 'Проезд ≥ 2,9 м', undefined, 's-avtomakon'),
      a('infrastructure', 'wifi', 'Связь', 'Wi-Fi 5 ГГц', undefined, 's-avtomakon'),
      a('infrastructure', 'ip', 'Класс защиты', undefined, undefined, undefined, 'unknown'),
      a('economics', 'price', 'Стоимость единицы', 9_800_000, '₽', 's-avtomakon'),
      a('economics', 'integration', 'Внедрение и интеграция', '20–30', '% от CAPEX', 's-team'),
      a('applicability', 'cases', 'Кейсы', 'Пилот на РЦ «Магнит», 2026', undefined, 's-media'),
      a('applicability', 'risks', 'Риски', 'Пилотная стадия: гарантии производительности нет', undefined, 's-team'),
    ],
  },
  {
    id: 'p-07', slug: 'yacheyka-q', name: 'Ячейка Q', manufacturer: 'Комитас', legalEntity: 'ООО «Комитас»', country: 'Россия', city: 'Москва',
    availability: 'operation', trl: 8, marketPotential: 4, autoMatch: true,
    solutionType: 'Кубическое хранение', solutionTypeCode: 'cube_storage', processes: ['Хранение', 'Комплектация заказов'], objects: ['Склад'],
    image: '/img/robot-cube.png', summary: 'Шаттлы по сетке над кубом контейнеров. Плотность хранения выше стеллажной в 3–4 раза.',
    priceRub: 1_450_000, priceNote: 'за шаттл, без сетки',
    highlights: [{ label: 'Нагрузка', value: '30 кг' }, { label: 'Скорость', value: '3,1 м/с' }, { label: 'Тар в час', value: '30' }, { label: 'Высота куба', value: '5 м' }],
    completeness: 0.82,
    attrs: [
      a('technical', 'payload_kg', 'Грузоподъёмность', 30, 'кг', 's-catalog'),
      a('technical', 'speed_ms', 'Скорость', '3,1', 'м/с', 's-catalog'),
      a('technical', 'throughput', 'Производительность', 30, 'тар/ч', 's-catalog'),
      a('technical', 'autonomy_h', 'Автономность', undefined, 'ч', undefined, 'not_applicable'),
      a('infrastructure', 'floor', 'Требования к полу', 'Нагрузка ≥ 4 т/м²', undefined, 's-catalog'),
      a('economics', 'price', 'Стоимость шаттла', 1_450_000, '₽', 's-catalog'),
      a('economics', 'integration', 'Внедрение и интеграция', '50–70', '% от CAPEX', 's-team'),
      a('applicability', 'risks', 'Риски', 'Долгий монтаж сетки: 10–14 недель', undefined, 's-team'),
    ],
  },
  {
    id: 'p-08', slug: 'legat-patrol', name: 'Легат Патрол', manufacturer: 'МАИ', legalEntity: 'ФГБОУ ВО «МАИ»', country: 'Россия', city: 'Москва',
    availability: 'piloting', trl: 7, marketPotential: 3, autoMatch: true,
    solutionType: 'Патрульный робот', solutionTypeCode: 'patrol', processes: ['Охрана периметра', 'Инспекция'], objects: ['Склад', 'Аэропорт'],
    image: '/img/robot-patrol.png', summary: 'Колёсный патрульный робот с сенсорной мачтой для периметра и открытых площадок.',
    priceRub: 3_600_000, priceNote: 'комплектация «Безопасность»',
    highlights: [{ label: 'Автономность', value: '10 ч' }, { label: 'Скорость', value: '1,4 м/с' }, { label: 'Температура', value: '−25…+40 °C' }, { label: 'Нагрузка', value: 'не применимо' }],
    completeness: 0.46,
    attrs: [
      a('technical', 'autonomy_h', 'Автономность', 10, 'ч', 's-mai'),
      a('technical', 'speed_ms', 'Скорость', '1,4', 'м/с', 's-mai'),
      a('technical', 'payload_kg', 'Грузоподъёмность', undefined, 'кг', undefined, 'not_applicable'),
      a('technical', 'throughput', 'Производительность', undefined, undefined, undefined, 'unknown'),
      a('infrastructure', 'temp', 'Температурный режим', 'от −25 до +40', '°C', 's-mai'),
      a('infrastructure', 'ip', 'Класс защиты', undefined, undefined, undefined, 'unknown'),
      a('economics', 'price', 'Стоимость единицы', 3_600_000, '₽', 's-catalog'),
      a('applicability', 'risks', 'Риски', 'Две комплектации в каталоге занесены как две позиции', undefined, 's-team'),
    ],
  },
  {
    id: 'p-09', slug: 'sanitar-uv-2', name: 'Санитар UV-2', manufacturer: 'Промобот', legalEntity: 'ООО «Промобот»', country: 'Россия', city: 'Пермь',
    availability: 'piloting', trl: 7, marketPotential: 3, autoMatch: true,
    solutionType: 'Робот дезинфекции', solutionTypeCode: 'uv_disinfection', processes: ['Дезинфекция помещений', 'Доставка внутри корпуса'], objects: ['Медучреждение', 'Аэропорт'],
    image: '/img/robot-uv.png', summary: 'Автономная УФ-дезинфекция палат и коридоров по расписанию.',
    priceRub: 2_200_000,
    highlights: [{ label: 'Автономность', value: '5 ч' }, { label: 'Скорость', value: '0,8 м/с' }, { label: 'Площадь за цикл', value: '120 м²' }, { label: 'Навигация', value: 'Лидар' }],
    completeness: 0.7,
    attrs: [
      a('technical', 'autonomy_h', 'Автономность', 5, 'ч', 's-catalog'),
      a('technical', 'speed_ms', 'Скорость', '0,8', 'м/с', 's-catalog'),
      a('technical', 'throughput', 'Площадь за цикл', 120, 'м²', 's-catalog'),
      a('economics', 'price', 'Стоимость единицы', 2_200_000, '₽', 's-catalog'),
      a('applicability', 'risks', 'Риски', 'Требуется вывод людей из зоны обработки', undefined, 's-team'),
    ],
  },
  {
    id: 'p-10', slug: 'strizh-i', name: 'Стриж-И', manufacturer: 'ФЦ БАС', legalEntity: 'АНО «ФЦ БАС»', country: 'Россия', city: 'Москва',
    availability: 'piloting', trl: 7, marketPotential: 4, autoMatch: true,
    solutionType: 'БАС инспекционный', solutionTypeCode: 'uav_inspection', processes: ['Инвентаризация', 'Инспекция'], objects: ['Склад', 'Аэропорт'],
    image: '/img/robot-drone.png', summary: 'Коптер для инвентаризации стеллажей по штрихкодам и осмотра кровли.',
    priceRub: 1_900_000, priceNote: 'с док-станцией',
    highlights: [{ label: 'Полёт', value: '32 мин' }, { label: 'Скорость', value: '4 м/с' }, { label: 'Ячеек в час', value: '900' }, { label: 'Навигация', value: 'Визуальная' }],
    completeness: 0.74,
    attrs: [
      a('technical', 'autonomy_h', 'Время полёта', '0,53', 'ч', 's-catalog-79'),
      a('technical', 'speed_ms', 'Скорость', 4, 'м/с', 's-catalog-79'),
      a('technical', 'throughput', 'Производительность', 900, 'ячеек/ч', 's-catalog-79'),
      a('economics', 'price', 'Стоимость комплекта', 1_900_000, '₽', 's-catalog-79'),
      a('applicability', 'risks', 'Риски', 'Полёты внутри помещений: регламент оператора', undefined, 's-team'),
    ],
  },
  {
    id: 'p-11', slug: 'rover-niias', name: 'Ровер для грузовых вагонов', manufacturer: 'АО «НИИАС»', legalEntity: 'АО «НИИАС»', country: 'Россия', city: 'Москва',
    availability: 'rnd', trl: 6, marketPotential: 2, autoMatch: false,
    solutionType: 'Ровер сервисный', solutionTypeCode: 'rover_rail', processes: ['Инспекция'], objects: ['Цех'],
    image: '/img/robot-patrol.png', summary: 'Наземный ровер для осмотра подвижного состава. Стадия разработки.',
    highlights: [{ label: 'УГТ', value: '6' }, { label: 'Стадия', value: 'Разработка' }, { label: 'Нагрузка', value: 'нет данных' }, { label: 'Скорость', value: 'нет данных' }],
    completeness: 0.22,
    attrs: [
      a('technical', 'payload_kg', 'Грузоподъёмность', undefined, 'кг', undefined, 'unknown'),
      a('technical', 'speed_ms', 'Скорость', undefined, 'м/с', undefined, 'unknown'),
      a('economics', 'price', 'Стоимость единицы', undefined, '₽', undefined, 'unknown'),
      a('applicability', 'risks', 'Риски', 'Дубль в категориях 5 и 10 каталога', undefined, 's-team'),
    ],
  },
  {
    id: 'p-12', slug: 'terminal-t', name: 'Терминал-Т', manufacturer: 'Аэромакс', legalEntity: 'ООО «Аэромакс»', country: 'Россия', city: 'Москва',
    availability: 'piloting', trl: 7, marketPotential: 4, autoMatch: true,
    solutionType: 'Багажный тягач', solutionTypeCode: 'baggage_tug', processes: ['Перемещение багажа', 'Доставка на перрон'], objects: ['Аэропорт'],
    image: '/img/site-airport.png', summary: 'Беспилотный электротягач для багажных тележек между терминалом и перроном.',
    priceRub: 12_500_000,
    highlights: [{ label: 'Тяга', value: '3 000 кг' }, { label: 'Скорость', value: '4,2 м/с' }, { label: 'Автономность', value: '9 ч' }, { label: 'Навигация', value: 'RTK GNSS + лидар' }],
    completeness: 0.66,
    attrs: [
      a('technical', 'payload_kg', 'Масса прицепа', 3000, 'кг', 's-catalog'),
      a('technical', 'speed_ms', 'Скорость', '4,2', 'м/с', 's-catalog'),
      a('technical', 'autonomy_h', 'Автономность', 9, 'ч', 's-catalog'),
      a('economics', 'price', 'Стоимость единицы', 12_500_000, '₽', 's-catalog'),
      a('applicability', 'risks', 'Риски', 'Допуск на перрон: согласование с АБ аэропорта', undefined, 's-team'),
    ],
  },
]

export const productBySlug = (slug: string) => products.find((p) => p.slug === slug || p.id === slug)

export interface TreeNode {
  label: string
  count?: number
  children?: TreeNode[]
  productIds?: string[]
}

export const catalogTree: TreeNode[] = [
  {
    label: 'Логистика и торговля',
    children: [
      {
        label: 'Склад',
        children: [
          { label: 'Внутрискладское перемещение', children: [
            { label: 'AMR палетный', productIds: ['p-01'] },
            { label: 'AMR транспортный', productIds: ['p-03'] },
            { label: 'Автономный погрузчик', productIds: ['p-06'] },
          ] },
          { label: 'Комплектация заказов', children: [
            { label: 'Goods-to-person AMR', productIds: ['p-02'] },
            { label: 'Кубическое хранение', productIds: ['p-07'] },
            { label: 'Коллаборативный робот', productIds: ['p-05'] },
          ] },
          { label: 'Паллетирование', children: [{ label: 'Промышленный манипулятор', productIds: ['p-04'] }] },
          { label: 'Инвентаризация', children: [{ label: 'БАС инспекционный', productIds: ['p-10'] }] },
          { label: 'Охрана периметра', children: [{ label: 'Патрульный робот', productIds: ['p-08'] }] },
        ],
      },
    ],
  },
  {
    label: 'Транспорт',
    children: [
      {
        label: 'Аэропорт',
        children: [
          { label: 'Перемещение багажа', children: [{ label: 'Багажный тягач', productIds: ['p-12'] }] },
          { label: 'Охрана периметра', children: [{ label: 'Патрульный робот', productIds: ['p-08'] }] },
          { label: 'Дезинфекция помещений', children: [{ label: 'Робот дезинфекции', productIds: ['p-09'] }] },
        ],
      },
    ],
  },
  {
    label: 'Здравоохранение',
    children: [
      {
        label: 'Медучреждение',
        children: [
          { label: 'Дезинфекция помещений', children: [{ label: 'Робот дезинфекции', productIds: ['p-09'] }] },
          { label: 'Доставка внутри корпуса', children: [{ label: 'Коллаборативный робот', productIds: ['p-05'] }] },
        ],
      },
    ],
  },
  {
    label: 'Промышленность',
    children: [
      {
        label: 'Цех',
        children: [
          { label: 'Подача на линию', children: [{ label: 'AMR палетный', productIds: ['p-01'] }, { label: 'Промышленный манипулятор', productIds: ['p-04'] }] },
          { label: 'Инспекция', children: [{ label: 'Ровер сервисный', productIds: ['p-11'] }] },
        ],
      },
    ],
  },
]

// Число уникальных продуктов в поддереве
export const countNode = (n: TreeNode): number => {
  const ids = new Set<string>()
  const walk = (x: TreeNode) => { x.productIds?.forEach((id) => ids.add(id)); x.children?.forEach(walk) }
  walk(n)
  return ids.size
}

export const attrGroups: { code: AttrValue['group']; label: string; hint: string }[] = [
  { code: 'identification', label: 'Идентификация', hint: 'Название, производитель, юрлицо, страна, статус, УГТ, рыночный потенциал' },
  { code: 'technical', label: 'Технические характеристики', hint: 'Нагрузка, скорость, автономность, точность, производительность' },
  { code: 'infrastructure', label: 'Инфраструктура', hint: 'Связь, пол, питание, температурный режим' },
  { code: 'economics', label: 'Экономика', hint: 'Стоимость единицы, ПО, внедрение, сервис' },
  { code: 'applicability', label: 'Применимость', hint: 'Объекты, процессы, кейсы, риски' },
  { code: 'data_quality', label: 'Качество данных', hint: 'Источники, даты, выведенная достоверность, готовность к автоподбору' },
]

export const formatRub = (n?: number) => {
  if (n == null) return 'нет данных'
  if (n >= 1_000_000) return `${(n / 1_000_000).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} млн ₽`
  return `${n.toLocaleString('ru-RU')} ₽`
}

export const formatNum = (n: number, digits = 0) => n.toLocaleString('ru-RU', { maximumFractionDigits: digits, minimumFractionDigits: digits })
