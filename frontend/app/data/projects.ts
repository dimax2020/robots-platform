// Заглушка проектов и расчётов. Все числа демонстрационные (mock).

export type ObjectType = 'warehouse' | 'airport' | 'hospital'

export const objectTypeLabel: Record<ObjectType, string> = {
  warehouse: 'Склад',
  airport: 'Аэропорт',
  hospital: 'Медучреждение',
}

export const objectTypeImage: Record<ObjectType, string> = {
  warehouse: '/img/site-warehouse.png',
  airport: '/img/site-airport.png',
  hospital: '/img/site-hospital.png',
}

export interface Project {
  id: string
  name: string
  objectType: ObjectType
  industry: string
  updatedAt: string
  catalogVersion: string
  modelVersion: string
  step: number
  /** Демо-объект платформы: ведёт администратор, опубликованный видят все. */
  isDemo?: boolean
  published?: boolean
  /** Открыт только для просмотра: гость или пользователь смотрит опубликованное демо. */
  readonly?: boolean
  area?: number
  shifts?: number
  tasks: number
}

export const steps = [
  { code: 'params', label: 'Параметры', path: 'params' },
  { code: 'match', label: 'Подбор', path: 'match' },
  { code: 'compare', label: 'Сравнение', path: 'compare' },
  { code: 'economics', label: 'Экономика', path: 'economics' },
  { code: 'what-if', label: 'What-if', path: 'what-if' },
  { code: 'plan', label: 'Визуализация', path: 'plan' },
  { code: 'report', label: 'Отчёт', path: 'report' },
] as const

export const fullPathSteps = 7
export const shortPathSteps = 3

/** Демо-объекты и проекты живут на платформе (`/projects`, `/projects/demo`); здесь только справочник шагов. */
export const projects: Project[] = []

export const isFullPath = (p: Project) => p.objectType === 'warehouse'

export interface Task {
  id: string
  process: string
  flow: string
  route: number
  container: string
  peak: number
  load: number
  unload: number
}

export const demoTasks: Task[] = [
  { id: 't1', process: 'Внутрискладское перемещение', flow: '240 палет/смена', route: 85, container: 'Европалета 1 200 × 800', peak: 1.6, load: 40, unload: 35 },
  { id: 't2', process: 'Комплектация заказов', flow: '1 850 строк/смена', route: 32, container: 'Тара 600 × 400', peak: 1.4, load: 12, unload: 18 },
  { id: 't3', process: 'Паллетирование', flow: '96 палет/смена', route: 0, container: 'Короб 600 × 400 × 300', peak: 1.2, load: 0, unload: 0 },
  { id: 't4', process: 'Инвентаризация', flow: '14 000 ячеек/неделя', route: 0, container: 'Не применимо', peak: 1.0, load: 0, unload: 0 },
]

export interface Scenario {
  id: string
  title: string
  subtitle: string
  fleet: { productId: string; count: number }[]
  capex: [number, number, number]
  opex: [number, number, number]
  effect: [number, number, number]
  payback: [number, number, number]
  raas?: boolean
  note?: string
}

export const scenarios: Scenario[] = [
  { id: 's0', title: 'Без роботизации', subtitle: 'Текущие ручные операции', fleet: [], capex: [0, 0, 0], opex: [186, 194, 203], effect: [0, 0, 0], payback: [0, 0, 0], note: '38 сотрудников склада в две смены, 9 электропогрузчиков, ФОТ 148 млн ₽ в год.' },
  { id: 's1', title: 'Подбор по задачам', subtitle: 'Каждый процесс закрыт своим лучшим решением', fleet: [{ productId: 'p-01', count: 7 }, { productId: 'p-02', count: 12 }, { productId: 'p-04', count: 2 }, { productId: 'p-10', count: 1 }], capex: [112, 128, 149], opex: [58, 64, 73], effect: [92, 108, 121], payback: [2.6, 3.4, 4.9], note: 'Четыре вендора, четыре контракта сервиса.' },
  { id: 's2', title: 'Оптимальный состав парка', subtitle: 'Один набор машин на общий бюджет и площадь', fleet: [{ productId: 'p-01', count: 9 }, { productId: 'p-02', count: 10 }, { productId: 'p-10', count: 1 }], capex: [96, 108, 124], opex: [51, 56, 63], effect: [84, 97, 109], payback: [2.4, 3.0, 4.2], raas: true, note: 'Паллетирование остаётся ручным: два манипулятора не окупаются на 96 палет в смену.' },
]

export interface CostLine { label: string; value: number; sourceId?: string; note?: string }

export const capexLines: CostLine[] = [
  { label: 'Оборудование', value: 71.4, sourceId: 's-ronavi', note: '9 × Ronavi H1500, 10 × Weibot G2P-600, 1 × Стриж-И' },
  { label: 'Инфраструктура', value: 8.2, sourceId: 's-team', note: 'Зарядные станции, разметка, Wi-Fi' },
  { label: 'ПО и лицензии', value: 6.5, sourceId: 's-avtomakon' },
  { label: 'Интеграция с WMS', value: 9.8, sourceId: 's-team', note: 'Текстовое описание связей, без интеграции в MVP' },
  { label: 'Пусконаладка', value: 4.6, sourceId: 's-dikom' },
  { label: 'Обучение', value: 1.2, sourceId: 's-team' },
  { label: 'Резерв', value: 6.3, sourceId: 's-team', note: '6% от суммы' },
]

export const opexLines: CostLine[] = [
  { label: 'Сервис', value: 9.6, sourceId: 's-analog', note: '8–10% от стоимости оборудования' },
  { label: 'Лицензии', value: 3.5, sourceId: 's-avtomakon' },
  { label: 'Энергия', value: 2.1, sourceId: 's-team', note: '0,9 кВт·ч на машину в час, 7,2 ₽/кВт·ч' },
  { label: 'Связь', value: 0.4, sourceId: 's-team' },
  { label: 'Расходники', value: 1.8, sourceId: 's-analog', note: 'Аккумуляторы: замена раз в 4 года' },
  { label: 'Ремонт', value: 2.9, sourceId: 's-analog' },
  { label: 'Персонал эксплуатации', value: 35.7, sourceId: 's-team', note: '14 сотрудников вместо 38' },
]

export const effectLines: CostLine[] = [
  { label: 'Экономия ФОТ', value: 93.6, sourceId: 's-team', note: '24 ставки × 3,9 млн ₽' },
  { label: 'Дополнительный доход', value: 0, sourceId: 's-team', note: 'Интервал 0–9,4 млн ₽: рост пропускной способности' },
  { label: 'Предотвращённые потери', value: 3.8, sourceId: 's-analog', note: 'Бой и пересорт по бенчмарку класса' },
]
