<script setup lang="ts">
import { formatRub } from '~/data/catalog'
import { photoFor } from '~/data/placeholders'
import { fetchErrorMessage } from '~/utils/errors'
import { platformGet, platformSend } from '~/composables/usePlatform'

definePageMeta({ layout: 'vendor', middleware: 'vendor', pageTransition: false })
useHead({ title: 'Кабинет вендора · Заявки' })

interface RequestRow {
  id: string
  kind: string
  title: string
  summary: string
  status: string
  catalog_applied: boolean
  admin_comment: string
  created_at: string | null
  subject_slug: string
  image_url: string | null
  price_rub: number | null
  facts: { label: string; value: string }[]
}

const requests = ref<RequestRow[]>([])
const notice = ref('')
const error = ref('')
const busy = ref(false)
const openRequest = ref('')
const statusLabel: Record<string, string> = {
  pending: 'На проверке',
  approved: 'Принято',
  rejected: 'Отклонено',
  revision: 'Нужна доработка',
  withdraw_pending: 'Отзыв на проверке',
  withdrawn: 'Отозвана',
}
const statusHint: Record<string, string> = {
  pending: 'Администратор ещё не ответил. В каталоге пока прежние данные.',
  approved: 'Администратор принял заявку. В каталог она попадёт, когда он нажмёт «Внести в каталог».',
  rejected: 'В каталог это не попало.',
  revision: 'Поправьте по комментарию и отправьте ещё раз.',
  withdraw_pending: 'Просьба отозвать ушла администратору. Пока он не подтвердит, заявка ещё жива.',
  withdrawn: 'Заявку отозвали. В каталог она не попала.',
}
const hintFor = (item: RequestRow) => {
  if (item.status === 'approved' && item.catalog_applied) return 'Изменение уже видно в каталоге.'
  if (item.status === 'approved') return 'Администратор принял заявку. В каталог она попадёт, когда он нажмёт «Внести в каталог».'
  return statusHint[item.status] || ''
}
const requestGroups = computed(() => {
  const order = [
    { id: 'revision', title: 'Нужно исправить', statuses: ['revision'] },
    { id: 'pending', title: 'Ждут ответа', statuses: ['pending', 'withdraw_pending'] },
    { id: 'done', title: 'Уже решено', statuses: ['approved', 'rejected', 'withdrawn'] },
  ]
  return order
    .map((group) => ({ ...group, items: requests.value.filter((item) => group.statuses.includes(item.status)) }))
    .filter((group) => group.items.length)
})
const when = (iso: string | null) => iso
  ? new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })
  : ''

const load = async () => {
  requests.value = await platformGet<RequestRow[]>('/vendor/requests')
}
const run = async (action: () => Promise<void>, ok: string) => {
  error.value = ''
  notice.value = ''
  busy.value = true
  try {
    await action()
    notice.value = ok
    await load()
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Не получилось отправить')
  } finally {
    busy.value = false
  }
}
const withdrawRequest = (id: string) => run(async () => {
  await platformSend(`/vendor/requests/${id}/withdraw`, 'POST')
}, 'Просьба отозвать отправлена. Пока администратор её не подтвердит, заявка остаётся.')
const hideRequest = (id: string) => run(async () => {
  await platformSend(`/vendor/requests/${id}/hide`, 'POST')
}, 'Заявка убрана из вашего списка. В каталоге из-за этого ничего не меняется.')

onMounted(() => { void load().catch((err) => { error.value = fetchErrorMessage(err, 'Заявки не открылись') }) })
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Заявки" title="Что уже отправлено" lead="Пока администратор не подтвердит заявку, заказчик видит прежние данные." />
    <UiCallout v-if="error" tone="danger">{{ error }}</UiCallout>
    <UiCallout v-else-if="notice" tone="ok">{{ notice }}</UiCallout>
    <p v-if="!requests.length" class="body-sm muted">Пока пусто. Измените компанию или робота, и здесь появится ответ администратора.</p>

    <template v-for="group in requestGroups" :key="group.id">
      <div class="h3">{{ group.title }}</div>
      <div class="grid grid-cards">
        <article v-for="item in group.items" :key="item.id" class="card-r glass" :class="{ open: openRequest === item.id }">
          <button type="button" class="media" :aria-expanded="openRequest === item.id" :aria-label="item.title" @click="openRequest = openRequest === item.id ? '' : item.id">
            <img :src="photoFor(item.image_url, item.title)" :alt="item.title">
            <span class="badges">
              <UiBadge :tone="item.status === 'approved' ? 'ok' : item.status === 'rejected' ? 'danger' : item.status === 'revision' ? 'warn' : 'info'">{{ statusLabel[item.status] || item.status }}</UiBadge>
            </span>
          </button>
          <div class="body">
            <button type="button" class="h3 name" @click="openRequest = openRequest === item.id ? '' : item.id">{{ item.title }}</button>
            <p v-if="item.summary" class="headline">{{ item.summary }}</p>
            <p class="caption">{{ hintFor(item) }}</p>
            <div class="foot">
              <div class="price">
                <span v-if="item.price_rub != null" class="mono-lg">{{ formatRub(item.price_rub) }}</span>
                <span class="caption">{{ when(item.created_at) }}</span>
              </div>
            </div>
            <div v-if="openRequest === item.id" class="editor">
              <VendorRequestFacts :facts="item.facts || []" />
              <p v-if="item.admin_comment" class="note">{{ item.admin_comment }}</p>
              <div class="a-row">
                <UiButton v-if="item.status === 'revision' && item.subject_slug" size="sm" variant="secondary" :to="`/vendor/robots?slug=${item.subject_slug}`">Исправить эту модель</UiButton>
                <UiButton v-if="item.status === 'pending' || item.status === 'revision'" size="sm" variant="ghost" :disabled="busy" @click="withdrawRequest(item.id)">Отозвать</UiButton>
                <UiButton v-if="item.status === 'approved' || item.status === 'rejected' || item.status === 'withdrawn'" size="sm" variant="ghost" :disabled="busy" @click="hideRequest(item.id)">Удалить из списка</UiButton>
              </div>
            </div>
          </div>
        </article>
      </div>
    </template>
  </div>
</template>

<style scoped>
.card-r { display: grid; grid-template-rows: auto 1fr; border-radius: var(--radius-xl); overflow: hidden; height: 100%; }
.card-r.open { grid-column: 1 / -1; height: auto; }
.media { position: relative; display: grid; place-items: center; aspect-ratio: 4 / 3; margin: 8px; border: 0; border-radius: 18px; overflow: hidden; background: #e9eeec; cursor: pointer; }
.media img { width: 100%; height: 100%; object-fit: cover; }
.letter { font-size: 48px; font-weight: 700; color: var(--ink-muted); }
.badges { position: absolute; left: 10px; top: 10px; display: flex; gap: 6px; flex-wrap: wrap; }
.body { display: grid; gap: 8px; padding: 8px 16px 16px; align-content: start; text-align: left; }
.name { color: var(--ink-strong); text-align: left; background: none; border: 0; padding: 0; cursor: pointer; }
.headline { margin: 0; font-size: 13px; line-height: 1.45; color: var(--ink-body); display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.foot { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; }
.price { display: grid; }
.price .mono-lg { color: var(--ink-strong); }
.editor { display: grid; gap: 10px; padding-top: 12px; border-top: 1px solid var(--border-hairline); }
.note { margin: 0; padding: 8px 12px; border-radius: 10px; background: var(--state-warn-tint); color: var(--state-warn); font-size: 12px; line-height: 1.4; font-weight: 500; }
</style>
