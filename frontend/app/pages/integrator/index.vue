<script setup lang="ts">
import { fetchErrorMessage } from '~/utils/errors'
import { platformGet, platformSend, usePlatformBase } from '~/composables/usePlatform'
import { docKinds, specializations, type IntegrationDoc } from '~/data/integrator'

definePageMeta({ layout: 'integrator', middleware: 'integrator', pageTransition: false })
useHead({ title: 'Кабинет интегратора · Профиль' })

interface Profile {
  company_name: string
  brand: string
  about: string
  website: string
  email: string
  phone: string
  city: string
  address: string
  inn: string
  ogrn: string
  regions: string
  contact_name: string
  experience_years: number | null
  specializations: string[]
  logo_url: string | null
  documents: IntegrationDoc[]
  nda_accepted: boolean
  nda_text: string
}

const profile = ref<Profile | null>(null)
const error = ref('')
const notice = ref('')
const busy = ref(false)
const docKind = ref('charter')
const docTitle = ref('')
const form = reactive({
  company_name: '',
  brand: '',
  about: '',
  website: '',
  email: '',
  phone: '',
  city: '',
  address: '',
  inn: '',
  ogrn: '',
  regions: '',
  contact_name: '',
  experience_years: '' as string | number,
  specializations: [] as string[],
  documents: [] as IntegrationDoc[],
  logo: '',
})

const fill = (row: Profile) => {
  profile.value = row
  form.company_name = row.company_name
  form.brand = row.brand
  form.about = row.about
  form.website = row.website
  form.email = row.email
  form.phone = row.phone
  form.city = row.city
  form.address = row.address
  form.inn = row.inn
  form.ogrn = row.ogrn
  form.regions = row.regions
  form.contact_name = row.contact_name
  form.experience_years = row.experience_years ?? ''
  form.specializations = [...row.specializations]
  form.documents = row.documents.map((item) => ({ ...item }))
  form.logo = ''
}

const load = async () => {
  fill(await platformGet<Profile>('/integrator/me'))
}

const upload = async (file: File, kind: string) => {
  const body = new FormData()
  body.set('file', file)
  body.set('kind', kind)
  return await $fetch<{ filename: string }>(`${usePlatformBase()}/integrator/files`, { method: 'POST', body, credentials: 'include' })
}

const onLogo = async (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  error.value = ''
  busy.value = true
  try {
    const saved = await upload(file, 'logo')
    form.logo = saved.filename
    notice.value = 'Логотип прикреплён. Сохраните карточку, чтобы заказчик его увидел.'
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
  busy.value = true
  try {
    const saved = await upload(file, 'doc')
    form.documents.push({
      kind: docKind.value,
      title: docTitle.value.trim() || file.name,
      filename: saved.filename,
    })
    docTitle.value = ''
    notice.value = 'Документ прикреплён. Сохраните карточку.'
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Документ не загрузился')
  } finally {
    busy.value = false
  }
}

const toggleSpec = (name: string) => {
  form.specializations = form.specializations.includes(name)
    ? form.specializations.filter((item) => item !== name)
    : [...form.specializations, name]
}

const save = async () => {
  error.value = ''
  notice.value = ''
  busy.value = true
  try {
    const years = String(form.experience_years).trim()
    const saved = await platformSend<Profile>('/integrator/profile', 'PUT', {
      company_name: form.company_name,
      brand: form.brand,
      about: form.about,
      website: form.website,
      email: form.email,
      phone: form.phone,
      city: form.city,
      address: form.address,
      inn: form.inn,
      ogrn: form.ogrn,
      regions: form.regions,
      contact_name: form.contact_name,
      experience_years: years === '' ? null : Number(years),
      specializations: form.specializations,
      documents: form.documents,
      logo: form.logo || null,
    })
    fill(saved)
    notice.value = 'Карточка сохранена. Заказчик видит её в разделе «Интеграторы».'
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Не получилось сохранить')
  } finally {
    busy.value = false
  }
}

onMounted(() => { void load().catch((err) => { error.value = fetchErrorMessage(err, 'Кабинет не открылся') }) })
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Кабинет интегратора" :title="profile?.company_name || 'Профиль'" lead="Так вас видит заказчик, когда выбирает, кому отправить проект." />
    <UiCallout v-if="profile && !profile.nda_accepted" tone="warn">
      Перед запросами и чатом примите уведомление о неразглашении.
      <NuxtLink to="/integrator/requests" class="jump">Открыть уведомление</NuxtLink>
    </UiCallout>
    <UiCallout v-if="error" tone="danger">{{ error }}</UiCallout>
    <UiCallout v-else-if="notice" tone="ok">{{ notice }}</UiCallout>

    <form v-if="profile" class="glass glass-xl a-panel" @submit.prevent="save">
      <div class="h3">Компания</div>
      <div class="grid-2">
        <label class="a-fld"><span class="caption">Название компании</span><input v-model="form.company_name" class="input" required></label>
        <label class="a-fld"><span class="caption">Короткое имя</span><input v-model="form.brand" class="input" placeholder="Как вас называть в разговоре"></label>
        <label class="a-fld"><span class="caption">Город</span><input v-model="form.city" class="input"></label>
        <label class="a-fld"><span class="caption">Адрес</span><input v-model="form.address" class="input"></label>
        <label class="a-fld"><span class="caption">ИНН</span><input v-model="form.inn" class="input" inputmode="numeric"></label>
        <label class="a-fld"><span class="caption">ОГРН</span><input v-model="form.ogrn" class="input" inputmode="numeric"></label>
        <label class="a-fld"><span class="caption">Сайт</span><input v-model="form.website" class="input" placeholder="https://"></label>
        <label class="a-fld"><span class="caption">Почта</span><input v-model="form.email" class="input" type="email"></label>
        <label class="a-fld"><span class="caption">Телефон</span><input v-model="form.phone" class="input"></label>
        <label class="a-fld"><span class="caption">Контактное лицо</span><input v-model="form.contact_name" class="input"></label>
        <label class="a-fld"><span class="caption">Регионы работы</span><input v-model="form.regions" class="input" placeholder="Например, Москва и область"></label>
        <label class="a-fld"><span class="caption">Лет на рынке</span><input v-model="form.experience_years" class="input" inputmode="numeric"></label>
        <label class="a-fld">
          <span class="caption">Логотип</span>
          <input class="input" type="file" accept="image/png,image/jpeg,image/webp" @change="onLogo">
          <span class="caption">{{ form.logo ? 'Новая картинка прикреплена' : (profile.logo_url ? 'Логотип уже есть, можно заменить' : 'Картинка до 2 МБ') }}</span>
        </label>
      </div>
      <label class="a-fld"><span class="caption">О компании</span><textarea v-model="form.about" class="textarea" rows="3" placeholder="Какие площадки внедряете и с какими роботами работаете" /></label>
      <div class="a-block">
        <div class="h4">Чем занимаетесь</div>
        <div class="specs">
          <label v-for="name in specializations" :key="name" class="spec">
            <input type="checkbox" :checked="form.specializations.includes(name)" @change="toggleSpec(name)">
            <span>{{ name }}</span>
          </label>
        </div>
      </div>
      <div class="a-block">
        <div class="h4">Документы</div>
        <p class="body-sm muted">Карточка компании, разрешение, сертификат или письмо производителя о партнёрстве. Заказчик видит названия.</p>
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
          <label class="a-fld"><span class="caption">Название</span><input v-model="docTitle" class="input" placeholder="Например, допуск СРО"></label>
        </div>
        <label class="a-fld"><span class="caption">Файл</span><input class="input" type="file" accept="application/pdf,image/png,image/jpeg,image/webp" @change="onDoc"></label>
      </div>
      <UiButton type="submit" size="lg" :disabled="busy">Сохранить карточку</UiButton>
    </form>
  </div>
</template>

<style scoped>
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.docs { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.docs li { display: flex; justify-content: space-between; gap: 12px; }
.text-btn { color: var(--state-danger); font-weight: 700; }
.jump { margin-left: 8px; font-weight: 700; text-decoration: underline; text-underline-offset: 3px; }
.specs { display: flex; flex-wrap: wrap; gap: 8px; }
.spec { display: inline-flex; align-items: center; gap: 6px; padding: 6px 10px; border-radius: 999px; background: rgba(15, 20, 19, 0.05); font-weight: 600; }
@media (max-width: 800px) {
  .grid-2 { grid-template-columns: 1fr; }
}
</style>
