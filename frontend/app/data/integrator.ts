export const specializations = ['Склад', 'Производство', 'Медицина', 'Аэропорт', 'Сварка', 'Паллетирование']

export const docKinds = [
  { id: 'charter', label: 'Карточка компании' },
  { id: 'permit', label: 'Разрешение' },
  { id: 'certificate', label: 'Сертификат' },
  { id: 'partner', label: 'Партнёрство с производителем' },
  { id: 'other', label: 'Другой документ' },
]

export const statusLabel: Record<string, string> = {
  sent: 'Ждёт ответа',
  answered: 'Есть отзыв',
  declined: 'Отклонён',
}

export interface ThreadCard {
  id: string
  title: string
  subtitle: string
  status: string
  project_id?: string
}

export interface IntegrationDoc {
  kind: string
  title: string
  filename?: string
  url?: string
}
