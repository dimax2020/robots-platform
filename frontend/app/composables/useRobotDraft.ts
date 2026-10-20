import { reactive, ref } from 'vue'
import type { Gap } from '~/data/analytics'
import { fetchErrorMessage } from '~/utils/errors'
import { platformSend } from '~/composables/usePlatform'

export interface RobotProduct {
  slug: string
  name: string
  summary: string | null
  price_rub: number | null
  processes: string[]
  attrs: { key: string; label: string; value: unknown }[]
}

/* Черновик одной открытой карточки. Пустые поля из аналитики добавляем, чтобы их было куда вписать. */
export function useRobotDraft(reload: () => Promise<void>) {
  const openSlug = ref('')
  const editName = ref('')
  const editSummary = ref('')
  const editPrice = ref('')
  const editProcesses = ref<string[]>([])
  const editAttrs = ref<{ key: string; label: string; value: string }[]>([])
  const busy = ref(false)
  const notice = ref('')
  const error = ref('')

  const fill = (robot: RobotProduct, gaps: Gap[]) => {
    openSlug.value = robot.slug
    editName.value = robot.name
    editSummary.value = robot.summary || ''
    editPrice.value = robot.price_rub == null ? '' : String(robot.price_rub)
    editProcesses.value = [...robot.processes]
    const attrs = robot.attrs.map((item) => ({
      key: item.key,
      label: item.label,
      value: item.value == null ? '' : String(item.value),
    }))
    for (const gap of gaps) {
      if (gap.key === 'price_rub' || attrs.some((item) => item.key === gap.key)) continue
      attrs.push({ key: gap.key, label: gap.label, value: '' })
    }
    editAttrs.value = attrs
  }

  const toggle = (robot: RobotProduct | undefined, gaps: Gap[] = []) => {
    if (!robot) return
    if (openSlug.value === robot.slug) {
      openSlug.value = ''
      return
    }
    fill(robot, gaps)
  }

  const open = (robot: RobotProduct | undefined, gaps: Gap[] = []) => {
    if (!robot) return
    fill(robot, gaps)
  }

  const send = async () => {
    error.value = ''
    notice.value = ''
    const raw = editPrice.value.trim()
    const price = raw === '' ? null : Number(raw.replace(',', '.'))
    if (price !== null && Number.isNaN(price)) {
      error.value = 'Цена должна быть числом. Если цены нет, оставьте поле пустым.'
      return
    }
    busy.value = true
    try {
      await platformSend('/vendor/requests', 'POST', {
        kind: 'product_update',
        payload: {
          slug: openSlug.value,
          name: editName.value,
          summary: editSummary.value,
          price_rub: price,
          processes: editProcesses.value,
          attrs: editAttrs.value
            .filter((item) => item.value.trim() !== '')
            .map((item) => ({ key: item.key, label: item.label, value: item.value.trim() })),
        },
      })
      notice.value = 'Правка отправлена на проверку. Заказчик увидит её после подтверждения. Статус лежит в заявках.'
      await reload()
    } catch (err) {
      error.value = fetchErrorMessage(err, 'Не получилось отправить')
    } finally {
      busy.value = false
    }
  }

  return reactive({ openSlug, editName, editSummary, editPrice, editProcesses, editAttrs, busy, notice, error, toggle, open, send })
}
