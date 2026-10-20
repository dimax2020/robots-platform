<script setup lang="ts">
import { fetchErrorMessage } from '~/utils/errors'
import { platformGet } from '~/composables/usePlatform'
import { docKinds } from '~/data/integrator'

useHead({ title: 'Интеграторы' })

interface Card {
  id: string
  company_name: string
  brand: string
  about: string
  website: string
  email: string
  phone: string
  city: string
  regions: string
  contact_name: string
  experience_years: number | null
  specializations: string[]
  logo_url: string | null
  documents: { kind: string; title: string }[]
}

interface Mine { id: string; integrator_id: string; status: string }

const { role } = useRole()
const cards = ref<Card[]>([])
const mine = ref<Mine[]>([])
const error = ref('')

const threadOf = (id: string) => mine.value.find((item) => item.integrator_id === id)
const kindLabel = (kind: string) => docKinds.find((item) => item.id === kind)?.label || 'Документ'

onMounted(async () => {
  if (role.value === 'guest') return
  try {
    cards.value = await platformGet<Card[]>('/integrators')
    if (role.value === 'user' || role.value === 'admin') mine.value = await platformGet<Mine[]>('/integration/mine')
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Список не открылся')
  }
})
</script>

<template>
  <section class="container page">
    <AdminHead
      label="Интеграторы"
      title="Кому отправить проект"
      lead="После подбора откройте отчёт и нажмите «Отправить интегратору». Здесь можно посмотреть компанию и переписку."
    />
    <UiCallout v-if="role === 'guest'" tone="info">Войдите как пользователь, чтобы отправить свой проект и писать интегратору.</UiCallout>
    <UiCallout v-if="error" tone="danger">{{ error }}</UiCallout>
    <p v-else-if="role !== 'guest' && !cards.length" class="body-sm muted">Пока нет карточек интеграторов.</p>
    <div class="grid">
      <article v-for="card in cards" :key="card.id" class="glass card">
        <div class="top">
          <img v-if="card.logo_url" :src="card.logo_url" :alt="card.company_name" class="logo">
          <div>
            <div class="h3">{{ card.company_name }}</div>
            <p class="caption">{{ card.city }}<span v-if="card.experience_years != null"> · {{ card.experience_years }} лет на рынке</span></p>
          </div>
        </div>
        <p v-if="card.about" class="body-sm">{{ card.about }}</p>
        <div v-if="card.specializations.length" class="specs">
          <span v-for="name in card.specializations" :key="name" class="pill">{{ name }}</span>
        </div>
        <p v-if="card.regions" class="caption">Регионы: {{ card.regions }}</p>
        <p v-if="card.contact_name" class="caption">Контакт: {{ card.contact_name }}</p>
        <p class="caption">
          <a v-if="card.website" :href="card.website" target="_blank" rel="noopener">{{ card.website }}</a>
          <span v-if="card.email"> · {{ card.email }}</span>
          <span v-if="card.phone"> · {{ card.phone }}</span>
        </p>
        <ul v-if="card.documents.length" class="docs">
          <li v-for="doc in card.documents" :key="doc.title">{{ kindLabel(doc.kind) }}: {{ doc.title }}</li>
        </ul>
        <UiButton
          v-if="threadOf(card.id)"
          :to="`/integrators/chat?request=${threadOf(card.id)?.id}`"
          size="sm"
        >Открыть чат</UiButton>
        <p v-else class="caption">Чтобы начать разговор, отправьте проект с шага «Отчёт».</p>
      </article>
    </div>
  </section>
</template>

<style scoped>
.page { display: grid; gap: var(--space-6); padding-top: var(--space-8); padding-bottom: var(--space-16); }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--space-4); }
.card { display: grid; gap: 10px; padding: var(--space-5); align-content: start; }
.card > * { position: relative; z-index: 1; }
.top { display: flex; gap: 12px; align-items: center; }
.logo { width: 56px; height: 56px; object-fit: contain; border-radius: 12px; background: white; }
.specs { display: flex; flex-wrap: wrap; gap: 6px; }
.pill { padding: 3px 9px; border-radius: 999px; font-size: 12.5px; font-weight: 600; background: rgba(15, 20, 19, 0.06); }
.docs { margin: 0; padding-left: 18px; }
</style>
