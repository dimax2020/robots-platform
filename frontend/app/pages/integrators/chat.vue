<script setup lang="ts">
import { fetchErrorMessage } from '~/utils/errors'
import { platformGet } from '~/composables/usePlatform'
import type { ThreadCard } from '~/data/integrator'

useHead({ title: 'Чаты с интеграторами' })

interface Mine {
  id: string
  project_id: string
  project_name: string
  integrator_name: string
  status: string
  feedback: string
  decline_comment: string
}

const { role } = useRole()
const threads = ref<ThreadCard[]>([])
const notes = ref<Mine[]>([])
const error = ref('')

const currentNote = computed(() => notes.value)

onMounted(async () => {
  if (role.value === 'guest') return
  try {
    const rows = await platformGet<Mine[]>('/integration/mine')
    notes.value = rows
    threads.value = rows.map((row) => ({
      id: row.id,
      title: row.integrator_name || 'Интегратор',
      subtitle: row.project_name,
      status: row.status,
      project_id: row.project_id,
    }))
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Чаты не открылись')
  }
})
</script>

<template>
  <section class="container page">
    <AdminHead label="Интеграторы" title="Переписка" lead="Сообщения и файлы остаются здесь. Интегратор видит ту же историю." />
    <UiCallout v-if="role === 'guest'" tone="info">Войдите как пользователь, чтобы писать интегратору.</UiCallout>
    <UiCallout v-if="error" tone="danger">{{ error }}</UiCallout>
    <div v-if="currentNote.some((item) => item.feedback || item.decline_comment)" class="notes">
      <UiCallout v-for="item in currentNote.filter((row) => row.feedback || row.decline_comment)" :key="item.id" :tone="item.decline_comment ? 'warn' : 'ok'">
        <strong>{{ item.integrator_name }}</strong> по проекту «{{ item.project_name }}».
        {{ item.decline_comment ? `Не берёт проект: ${item.decline_comment}` : item.feedback }}
      </UiCallout>
    </div>
    <IntegrationChat v-if="role !== 'guest'" :threads="threads" empty="Отправьте проект с шага «Отчёт», и чат появится здесь." />
  </section>
</template>

<style scoped>
.page { display: grid; gap: var(--space-6); padding-top: var(--space-8); padding-bottom: var(--space-16); }
.notes { display: grid; gap: 8px; }
</style>
