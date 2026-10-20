<script setup lang="ts">
import { fetchErrorMessage } from '~/utils/errors'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { statusLabel } from '~/data/integrator'

definePageMeta({ layout: 'integrator', middleware: 'integrator', pageTransition: false })
useHead({ title: 'Кабинет интегратора · Запросы' })

interface Profile { nda_accepted: boolean; nda_text: string }
interface RequestCard {
  id: string
  project_id: string
  project_name: string
  object_name: string
  status: string
  user_note: string
  feedback: string
  decline_comment: string
  created_at: string
}

const profile = ref<Profile | null>(null)
const rows = ref<RequestCard[]>([])
const comments = reactive<Record<string, string>>({})
const error = ref('')
const notice = ref('')
const busy = ref('')

const pill = (status: string) => status === 'answered' ? 'ok' : status === 'declined' ? 'danger' : 'warn'
const when = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })
}

const load = async () => {
  profile.value = await platformGet<Profile>('/integrator/me')
  if (!profile.value.nda_accepted) return
  rows.value = await platformGet<RequestCard[]>('/integrator/requests')
}

const accept = async () => {
  error.value = ''
  busy.value = 'nda'
  try {
    profile.value = await platformSend<Profile>('/integrator/nda', 'POST')
    rows.value = await platformGet<RequestCard[]>('/integrator/requests')
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Не получилось принять уведомление')
  } finally {
    busy.value = ''
  }
}

const act = async (id: string, kind: 'feedback' | 'decline') => {
  const comment = (comments[id] || '').trim()
  if (!comment) {
    error.value = kind === 'decline' ? 'Напишите, почему не берёте проект.' : 'Напишите отзыв по проекту.'
    return
  }
  error.value = ''
  notice.value = ''
  busy.value = id + kind
  try {
    const saved = await platformSend<RequestCard>(`/integrator/requests/${id}/${kind}`, 'POST', { comment })
    rows.value = rows.value.map((item) => item.id === id ? saved : item)
    comments[id] = ''
    notice.value = kind === 'decline' ? 'Проект отклонён. Заказчик увидит комментарий.' : 'Отзыв отправлен заказчику.'
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Не получилось сохранить')
  } finally {
    busy.value = ''
  }
}

onMounted(() => { void load().catch((err) => { error.value = fetchErrorMessage(err, 'Запросы не открылись') }) })
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Кабинет интегратора" title="Запросы" lead="Проекты, которые заказчики отправили вам после подбора." />
    <UiCallout v-if="error" tone="danger">{{ error }}</UiCallout>
    <UiCallout v-else-if="notice" tone="ok">{{ notice }}</UiCallout>

    <section v-if="profile && !profile.nda_accepted" class="glass glass-xl a-panel">
      <div class="h3">Неразглашение деталей проекта</div>
      <p class="body">{{ profile.nda_text }}</p>
      <UiButton :disabled="busy === 'nda'" @click="accept">Принимаю и открываю запросы</UiButton>
    </section>

    <p v-else-if="profile && !rows.length" class="body-sm muted">Пока никто не отправил проект. Когда заказчик нажмёт «Отправить интегратору» в отчёте, карточка появится здесь.</p>

    <article v-for="row in rows" :key="row.id" class="glass a-panel">
      <div class="a-head">
        <div>
          <div class="h3">{{ row.project_name }}</div>
          <p class="caption">{{ row.object_name }}<span v-if="when(row.created_at)"> · {{ when(row.created_at) }}</span></p>
        </div>
        <span class="a-pill" :class="pill(row.status)">{{ statusLabel[row.status] || row.status }}</span>
      </div>
      <p v-if="row.user_note" class="body-sm">Заказчик написал: {{ row.user_note }}</p>
      <p v-if="row.feedback" class="body-sm">Ваш отзыв: {{ row.feedback }}</p>
      <p v-if="row.decline_comment" class="body-sm">Причина отказа: {{ row.decline_comment }}</p>
      <div class="a-row">
        <UiButton :to="`/projects/${row.project_id}`" variant="secondary" size="sm">Открыть проект</UiButton>
        <UiButton :to="`/projects/${row.project_id}/report`" variant="secondary" size="sm">Отчёт</UiButton>
        <UiButton :to="`/integrator/chat?request=${row.id}`" variant="secondary" size="sm">Написать в чат</UiButton>
      </div>
      <label class="a-fld">
        <span class="caption">Комментарий</span>
        <textarea v-model="comments[row.id]" class="textarea" rows="3" placeholder="Что скажете заказчику" />
      </label>
      <div class="a-row">
        <UiButton v-if="row.status !== 'declined'" :disabled="busy === row.id + 'feedback'" @click="act(row.id, 'feedback')">Оставить отзыв</UiButton>
        <UiButton variant="secondary" :disabled="busy === row.id + 'decline'" @click="act(row.id, 'decline')">Отклонить</UiButton>
      </div>
    </article>
  </div>
</template>
