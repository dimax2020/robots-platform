<script setup lang="ts">
import { fetchErrorMessage } from '~/utils/errors'
import { platformGet, platformSend } from '~/composables/usePlatform'
import type { ThreadCard } from '~/data/integrator'

definePageMeta({ layout: 'integrator', middleware: 'integrator', pageTransition: false })
useHead({ title: 'Кабинет интегратора · Чат' })

interface Profile { nda_accepted: boolean; nda_text: string }
interface RequestCard {
  id: string
  project_id: string
  project_name: string
  object_name: string
  status: string
}

const profile = ref<Profile | null>(null)
const threads = ref<ThreadCard[]>([])
const error = ref('')
const busy = ref(false)

const load = async () => {
  profile.value = await platformGet<Profile>('/integrator/me')
  if (!profile.value.nda_accepted) return
  const rows = await platformGet<RequestCard[]>('/integrator/requests')
  threads.value = rows.map((row) => ({
    id: row.id,
    title: row.project_name,
    subtitle: row.object_name,
    status: row.status,
    project_id: row.project_id,
  }))
}

const accept = async () => {
  error.value = ''
  busy.value = true
  try {
    profile.value = await platformSend<Profile>('/integrator/nda', 'POST')
    await load()
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Не получилось принять уведомление')
  } finally {
    busy.value = false
  }
}

onMounted(() => { void load().catch((err) => { error.value = fetchErrorMessage(err, 'Чат не открылся') }) })
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Кабинет интегратора" title="Чат" lead="Переписка с заказчиком по его проекту. История сохраняется." />
    <UiCallout v-if="error" tone="danger">{{ error }}</UiCallout>
    <section v-if="profile && !profile.nda_accepted" class="glass glass-xl a-panel">
      <div class="h3">Неразглашение деталей проекта</div>
      <p class="body">{{ profile.nda_text }}</p>
      <UiButton :disabled="busy" @click="accept">Принимаю и открываю чат</UiButton>
    </section>
    <IntegrationChat v-else-if="profile" :threads="threads" empty="Когда появится запрос, переписка откроется здесь." />
  </div>
</template>
