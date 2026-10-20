<script setup lang="ts">
import type { VendorBoard } from '~/data/analytics'
import { fetchErrorMessage } from '~/utils/errors'
import { platformGet, platformSend, usePlatformBase } from '~/composables/usePlatform'

definePageMeta({ layout: 'vendor', middleware: 'vendor', pageTransition: false })
useHead({ title: 'Кабинет вендора · Компания' })

interface Profile {
  manufacturer: string
  company_name: string
  about: string
  website: string
  email: string
  phone: string
  city: string
  logo_url: string | null
  documents: { kind: string; title: string; filename?: string; url?: string; note?: string }[]
}

const route = useRoute()
const jump: Record<string, string> = {
  robots: '/vendor/robots',
  stats: '/vendor/analytics',
  analytics: '/vendor/analytics',
  requests: '/vendor/requests',
}
if (typeof route.query.tab === 'string' && jump[route.query.tab]) {
  await navigateTo(jump[route.query.tab], { replace: true })
}

const profile = ref<Profile | null>(null)
const board = ref<VendorBoard | null>(null)
const revision = ref(false)
const notice = ref('')
const error = ref('')
const busy = ref(false)
const form = reactive({
  company_name: '',
  about: '',
  website: '',
  email: '',
  phone: '',
  city: '',
  logo: '',
  documents: [] as { kind: string; title: string; filename: string; note: string }[],
})
const docKind = ref('card')
const docTitle = ref('')
const docKinds = [
  { id: 'card', label: 'Карточка предприятия' },
  { id: 'permit', label: 'Разрешительный документ' },
  { id: 'certificate', label: 'Сертификат' },
  { id: 'other', label: 'Другой документ' },
]

const fillProfile = (row: Profile) => {
  form.company_name = row.company_name
  form.about = row.about
  form.website = row.website
  form.email = row.email
  form.phone = row.phone
  form.city = row.city
  form.logo = ''
  form.documents = row.documents.map((item) => ({
    kind: item.kind,
    title: item.title,
    filename: item.filename || '',
    note: item.note || '',
  }))
}

const statsLead = computed(() => {
  if (!board.value) return ''
  return `Роботов: ${board.value.robots.length}. Участвуют в подборе: ${board.value.pie.in}.`
})

const load = async () => {
  const [me, queue, summary] = await Promise.all([
    platformGet<{ profile: Profile }>('/vendor/me'),
    platformGet<{ status: string }[]>('/vendor/requests'),
    platformGet<VendorBoard>('/vendor/analytics').catch(() => null),
  ])
  profile.value = me.profile
  board.value = summary
  fillProfile(me.profile)
  revision.value = queue.some((item) => item.status === 'revision')
}

const upload = async (file: File, kind: 'logo' | 'doc') => {
  const body = new FormData()
  body.append('file', file)
  body.append('kind', kind)
  return await $fetch<{ filename: string }>(`${usePlatformBase()}/vendor/files`, { method: 'POST', body, credentials: 'include' })
}

const onLogo = async (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  error.value = ''
  notice.value = ''
  busy.value = true
  try {
    const saved = await upload(file, 'logo')
    form.logo = saved.filename
    notice.value = 'Логотип прикреплён. Нажмите «Отправить на проверку», чтобы его увидел администратор.'
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Логотип не загрузился')
  } finally {
    busy.value = false
  }
}

const onDoc = async (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  error.value = ''
  notice.value = ''
  busy.value = true
  try {
    const saved = await upload(file, 'doc')
    form.documents.push({
      kind: docKind.value,
      title: docTitle.value.trim() || file.name,
      filename: saved.filename,
      note: '',
    })
    docTitle.value = ''
    notice.value = 'Документ прикреплён. Отправьте карточку на проверку, чтобы его увидел администратор.'
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Документ не загрузился')
  } finally {
    busy.value = false
  }
}

const sendProfile = async () => {
  error.value = ''
  notice.value = ''
  busy.value = true
  try {
    await platformSend('/vendor/requests', 'POST', { kind: 'profile', payload: { ...form, documents: form.documents } })
    notice.value = 'Карточка компании отправлена. Пока её не подтвердят, заказчик видит прежнюю.'
    await load()
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Не получилось отправить')
  } finally {
    busy.value = false
  }
}

onMounted(() => { void load().catch((err) => { error.value = fetchErrorMessage(err, 'Кабинет не открылся') }) })
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Кабинет производителя" :title="profile?.company_name || 'Компания'" :lead="statsLead" />
    <UiCallout v-if="revision" tone="warn">
      Администратор просит внести правки. Комментарий лежит в заявках.
      <NuxtLink to="/vendor/requests" class="jump">Открыть заявки</NuxtLink>
    </UiCallout>
    <UiCallout v-if="error" tone="danger">{{ error }}</UiCallout>
    <UiCallout v-else-if="notice" tone="ok">
      {{ notice }}
      <NuxtLink to="/vendor/requests" class="jump">Смотреть статус</NuxtLink>
    </UiCallout>

    <form v-if="profile" class="glass glass-xl a-panel" @submit.prevent="sendProfile">
      <div class="h3">Как вас увидит заказчик</div>
      <p class="body-sm muted">В каталоге роботы подписаны так: {{ profile.manufacturer }}. Это название не меняется, иначе уже загруженные модели оторвутся от компании.</p>
      <div class="grid-2">
        <label class="a-fld"><span class="caption">Название компании</span><input v-model="form.company_name" class="input" required></label>
        <label class="a-fld"><span class="caption">Город</span><input v-model="form.city" class="input"></label>
        <label class="a-fld"><span class="caption">Сайт</span><input v-model="form.website" class="input" placeholder="https://"></label>
        <label class="a-fld"><span class="caption">Почта</span><input v-model="form.email" class="input" type="email"></label>
        <label class="a-fld"><span class="caption">Телефон</span><input v-model="form.phone" class="input"></label>
        <label class="a-fld">
          <span class="caption">Логотип</span>
          <input class="input" type="file" accept="image/png,image/jpeg,image/webp" @change="onLogo">
          <span class="caption">{{ form.logo ? 'Новая картинка прикреплена' : (profile.logo_url ? 'Логотип уже есть, можно заменить' : 'Картинка до 2 МБ') }}</span>
        </label>
      </div>
      <label class="a-fld"><span class="caption">О компании</span><textarea v-model="form.about" class="textarea" rows="3" placeholder="Чем занимаетесь и каких роботов выпускаете" /></label>
      <div class="a-block">
        <div class="h4">Документы</div>
        <p class="body-sm muted">Карточка предприятия, разрешение или сертификат. Их видит администратор, когда проверяет заявку.</p>
        <ul v-if="form.documents.length" class="docs">
          <li v-for="(doc, index) in form.documents" :key="doc.filename || doc.title">
            <span>{{ docKinds.find((item) => item.id === doc.kind)?.label }}: {{ doc.title }}</span>
            <button type="button" class="text-btn" @click="form.documents.splice(index, 1)">Убрать</button>
          </li>
        </ul>
        <div class="grid-2">
          <label class="a-fld">
            <span class="caption">Тип документа</span>
            <select v-model="docKind" class="select">
              <option v-for="item in docKinds" :key="item.id" :value="item.id">{{ item.label }}</option>
            </select>
          </label>
          <label class="a-fld"><span class="caption">Название</span><input v-model="docTitle" class="input" placeholder="Например, декларация соответствия"></label>
        </div>
        <label class="a-fld"><span class="caption">Файл</span><input class="input" type="file" accept="application/pdf,image/png,image/jpeg,image/webp" @change="onDoc"></label>
      </div>
      <UiButton type="submit" size="lg" :disabled="busy">Отправить на проверку</UiButton>
    </form>
  </div>
</template>

<style scoped>
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.docs { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.docs li { display: flex; justify-content: space-between; gap: 12px; }
.text-btn { color: var(--state-danger); font-weight: 700; }
.jump { margin-left: 8px; font-weight: 700; text-decoration: underline; text-underline-offset: 3px; }
@media (max-width: 800px) {
  .grid-2 { grid-template-columns: 1fr; }
}
</style>
