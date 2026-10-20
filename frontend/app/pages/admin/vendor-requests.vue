<script setup lang="ts">
import { fetchErrorMessage } from '~/utils/errors'
import { platformGet, platformSend } from '~/composables/usePlatform'

definePageMeta({ layout: 'admin', middleware: 'admin', pageTransition: false })
useHead({ title: 'Заявки производителей' })

interface RobotPayload { name?: string; summary?: string; price_rub?: number | null; processes?: string[] }
interface RequestRow {
  id: string
  company: string
  kind: string
  title: string
  summary: string
  status: string
  admin_comment: string
  catalog_applied: boolean
  facts: { label: string; value: string }[]
  created_at: string | null
  payload: {
    company_name?: string
    about?: string
    website?: string
    email?: string
    phone?: string
    city?: string
    robot?: RobotPayload
    robots?: RobotPayload[]
  }
}
interface ProfileDraft { company_name: string; city: string; website: string; email: string; phone: string; about: string }
interface RobotDraft { name: string; summary: string; price: string; processes: string[] }

const rows = ref<RequestRow[]>([])
const comments = reactive<Record<string, string>>({})
const error = ref('')
const notice = ref('')
const busy = ref('')
const rowError = ref('')
/* Карточка короткая, пока администратор её не открыл. Черновик правки живёт до кнопки «Внести в каталог». */
const openId = ref('')
const processes = ref<{ code: string; name: string }[]>([])
const drafts = reactive<Record<string, { profile?: ProfileDraft; robots?: RobotDraft[] }>>({})

const statusLabel: Record<string, string> = {
  pending: 'На проверке',
  approved: 'Принято',
  rejected: 'Отклонено',
  revision: 'На доработке',
  withdraw_pending: 'Просит отозвать',
  withdrawn: 'Отозвана',
}
const kindLabel: Record<string, string> = {
  profile: 'Профиль',
  product_create: 'Новый робот',
  product_update: 'Характеристики',
  import_batch: 'Список роботов',
  parse: 'Поиск на сайте',
}
const waiting = computed(() => rows.value.filter((item) => item.status === 'pending' || item.status === 'withdraw_pending'))
const closed = computed(() => rows.value.filter((item) => item.status !== 'pending' && item.status !== 'withdraw_pending'))

const load = async () => {
  rows.value = await platformGet<RequestRow[]>('/admin/vendor-requests')
}

const decide = async (row: RequestRow, status: 'approved' | 'rejected' | 'revision') => {
  error.value = ''
  notice.value = ''
  const comment = (comments[row.id] || '').trim()
  rowError.value = ''
  if (status !== 'approved' && !comment) {
    rowError.value = row.id
    error.value = 'Напишите комментарий рядом с заявкой. Без него производитель не поймёт, что исправить.'
    return
  }
  busy.value = row.id
  try {
    await platformSend(`/admin/vendor-requests/${row.id}`, 'POST', { status, comment })
    if (row.status === 'withdraw_pending') {
      notice.value = status === 'approved' ? 'Отзыв подтверждён. В каталог заявка не попала.' : 'Отзыв не принят, заявка осталась.'
    } else if (status === 'approved') {
      notice.value = 'Заявка принята. Каталог пока прежний: поправьте поля и нажмите «Внести в каталог».'
    } else {
      notice.value = 'Решение отправлено производителю. Каталог не менялся.'
    }
    await load()
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Решение не сохранилось')
  } finally {
    busy.value = ''
  }
}

const when = (iso: string | null) => iso ? new Date(iso).toLocaleString('ru-RU', { timeZone: 'Europe/Moscow' }) : ''

const robotsOf = (row: RequestRow) => {
  const payload = row.payload || {}
  if (payload.robots?.length) return payload.robots
  if (payload.robot) return [payload.robot]
  return []
}

const openCard = (row: RequestRow) => {
  if (openId.value === row.id) {
    openId.value = ''
    return
  }
  openId.value = row.id
  if (drafts[row.id] || row.status !== 'approved' || row.catalog_applied || row.kind === 'parse') return
  if (row.kind === 'profile') {
    const payload = row.payload || {}
    drafts[row.id] = {
      profile: {
        company_name: payload.company_name || '',
        city: payload.city || '',
        website: payload.website || '',
        email: payload.email || '',
        phone: payload.phone || '',
        about: payload.about || '',
      },
    }
    return
  }
  drafts[row.id] = {
    robots: robotsOf(row).map((robot) => ({
      name: robot.name || '',
      summary: robot.summary || '',
      price: robot.price_rub == null ? '' : String(robot.price_rub),
      processes: [...(robot.processes || [])],
    })),
  }
}

const publish = async (row: RequestRow) => {
  error.value = ''
  notice.value = ''
  rowError.value = ''
  const draft = drafts[row.id]
  const body = row.kind === 'profile'
    ? draft?.profile
    : {
        robots: (draft?.robots || []).map((robot) => ({
          name: robot.name,
          summary: robot.summary,
          price_rub: robot.price.trim() ? Number(robot.price.replace(/\s/g, '').replace(',', '.')) : null,
          processes: robot.processes,
        })),
      }
  busy.value = row.id
  try {
    await platformSend(`/admin/vendor-requests/${row.id}/apply`, 'POST', { ...(body || {}) })
    notice.value = 'Записано в каталог. До этой кнопки карточки не менялись.'
    await load()
  } catch (err) {
    rowError.value = row.id
    error.value = fetchErrorMessage(err, 'В каталог не записалось')
  } finally {
    busy.value = ''
  }
}

const hideRow = async (row: RequestRow) => {
  error.value = ''
  notice.value = ''
  busy.value = row.id
  try {
    await platformSend(`/admin/vendor-requests/${row.id}/hide`, 'POST')
    notice.value = 'Заявка убрана из вашего списка. У производителя она остаётся.'
    await load()
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Не удалось убрать заявку')
  } finally {
    busy.value = ''
  }
}

onMounted(async () => {
  const tree = await platformGet<{ processes: { code: string; name: string }[] }>('/catalog/tree').catch(() => null)
  processes.value = tree?.processes || []
  await load().catch((err) => { error.value = fetchErrorMessage(err, 'Очередь не открылась') })
})
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Производители" title="Заявки на изменения" lead="Производитель сам ничего не публикует. Принятие заявки каталог не меняет. Когда всё проверено, поправьте поля и нажмите «Внести в каталог»." />
    <UiCallout v-if="notice" tone="ok">{{ notice }}</UiCallout>
    <p v-if="!rows.length" class="body-sm muted">Заявок нет.</p>

    <h2 v-if="waiting.length" class="h3">Ждут решения</h2>
    <div v-if="waiting.length" class="cards">
      <article v-for="row in waiting" :key="row.id" class="glass card" :class="{ open: openId === row.id }">
        <button type="button" class="card-hit" :aria-expanded="openId === row.id" @click="openCard(row)">
          <span class="a-head">
            <span class="card-main">
              <span class="caption">{{ row.company }} · {{ kindLabel[row.kind] || row.kind }} · {{ when(row.created_at) }}</span>
              <span class="card-title">{{ row.title }}</span>
              <span v-if="row.summary" class="card-sum">{{ row.summary }}</span>
            </span>
            <UiBadge :tone="row.status === 'withdraw_pending' ? 'warn' : 'info'">{{ statusLabel[row.status] }}</UiBadge>
          </span>
        </button>
        <div v-if="openId === row.id" class="card-body">
          <p v-if="row.status === 'withdraw_pending'" class="body-sm">Производитель просит отозвать заявку. Подтверждение ничего не записывает в каталог.</p>
          <VendorRequestFacts :facts="row.facts || []" />
          <label class="comment">
            <span class="field-label">Комментарий</span>
            <textarea v-model="comments[row.id]" class="textarea" rows="3" placeholder="Нужен, если заявку возвращаете, отклоняете или не даёте отозвать" />
          </label>
          <p v-if="rowError === row.id" class="field-error">{{ error }}</p>
          <div class="a-row">
            <UiButton :disabled="busy === row.id" @click="decide(row, 'approved')">{{ row.status === 'withdraw_pending' ? 'Подтвердить отзыв' : 'Подтвердить' }}</UiButton>
            <UiButton v-if="row.status === 'pending'" variant="secondary" :disabled="busy === row.id" @click="decide(row, 'revision')">Вернуть на правку</UiButton>
            <UiButton variant="ghost" :disabled="busy === row.id" @click="decide(row, 'rejected')">{{ row.status === 'withdraw_pending' ? 'Не отзывать' : 'Отклонить' }}</UiButton>
          </div>
        </div>
      </article>
    </div>

    <h2 v-if="closed.length" class="h3">Уже решено</h2>
    <div v-if="closed.length" class="cards">
      <article v-for="row in closed" :key="row.id" class="glass card" :class="{ open: openId === row.id }">
        <button type="button" class="card-hit" :aria-expanded="openId === row.id" @click="openCard(row)">
          <span class="a-head">
            <span class="card-main">
              <span class="caption">{{ row.company }} · {{ kindLabel[row.kind] || row.kind }} · {{ when(row.created_at) }}</span>
              <span class="card-title">{{ row.title }}</span>
              <span v-if="row.summary" class="card-sum">{{ row.summary }}</span>
            </span>
            <UiBadge :tone="row.status === 'approved' ? 'ok' : row.status === 'rejected' ? 'danger' : 'warn'">{{ statusLabel[row.status] || row.status }}</UiBadge>
          </span>
        </button>
        <div v-if="openId === row.id" class="card-body">
          <VendorRequestFacts :facts="row.facts || []" />
          <p v-if="row.admin_comment" class="caption">Комментарий производителю: {{ row.admin_comment }}</p>
          <template v-if="row.status === 'approved' && !row.catalog_applied">
            <p class="caption">Каталог ещё прежний. Поправьте то, что попадёт в карточку, и нажмите кнопку.</p>
            <div v-if="drafts[row.id]?.profile" class="edit">
              <label class="field field-line"><span class="field-label">Компания</span><input v-model="drafts[row.id]!.profile!.company_name" class="input"></label>
              <label class="field field-line"><span class="field-label">Город</span><input v-model="drafts[row.id]!.profile!.city" class="input"></label>
              <label class="field field-line"><span class="field-label">Сайт</span><input v-model="drafts[row.id]!.profile!.website" class="input"></label>
              <label class="field field-line"><span class="field-label">Почта</span><input v-model="drafts[row.id]!.profile!.email" class="input"></label>
              <label class="field field-line"><span class="field-label">Телефон</span><input v-model="drafts[row.id]!.profile!.phone" class="input"></label>
              <label class="field field-line"><span class="field-label">О компании</span><textarea v-model="drafts[row.id]!.profile!.about" class="textarea" rows="3" /></label>
            </div>
            <div v-for="(robot, index) in drafts[row.id]?.robots || []" :key="index" class="edit">
              <label class="field field-line"><span class="field-label">Модель</span><input v-model="robot.name" class="input"></label>
              <label class="field field-line"><span class="field-label">Коротко</span><textarea v-model="robot.summary" class="textarea" rows="2" /></label>
              <label class="field field-line"><span class="field-label">Цена, руб.</span><input v-model="robot.price" class="input" inputmode="decimal"></label>
              <label class="field field-line"><span class="field-label">Что умеет</span><ProcessPicker v-model="robot.processes" :processes="processes" /></label>
            </div>
            <p v-if="row.kind === 'parse'" class="caption">Поиск на сайте начнётся после кнопки. В каталог попадут только роботы этой компании.</p>
            <p v-if="rowError === row.id" class="field-error">{{ error }}</p>
            <UiButton :disabled="busy === row.id" @click="publish(row)">Внести в каталог</UiButton>
          </template>
          <p v-else-if="row.status === 'approved'" class="caption">Уже в каталоге.</p>
          <UiButton size="sm" variant="ghost" :disabled="busy === row.id" @click="hideRow(row)">Удалить из списка</UiButton>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 12px; }
.card { min-width: 0; padding: 12px 14px; display: grid; gap: 10px; align-content: start; overflow: hidden; }
.card.open { grid-column: 1 / -1; }
.card-hit { display: block; width: 100%; min-width: 0; text-align: left; }
.card-main { min-width: 0; display: grid; gap: 4px; }
.card-title { display: block; min-width: 0; font-size: 16px; font-weight: 700; line-height: 1.35; overflow-wrap: anywhere; }
.card-sum { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; color: var(--ink-muted); font-size: 13px; line-height: 1.4; overflow-wrap: anywhere; }
.card-body { display: grid; gap: 10px; min-width: 0; }
.comment { display: grid; gap: 8px; margin-top: 8px; max-width: 640px; }
.comment .textarea { width: 100%; min-width: 0; }
.edit { display: grid; gap: 10px; padding-top: 8px; min-width: 0; }
</style>
