<script setup lang="ts">
import { PhPaperclip } from '@phosphor-icons/vue'
import type { ThreadCard } from '~/data/integrator'
import { statusLabel } from '~/data/integrator'
import { fetchErrorMessage } from '~/utils/errors'
import { platformGet, usePlatformBase } from '~/composables/usePlatform'

const props = defineProps<{ threads: ThreadCard[]; empty: string }>()

interface ChatFile { name: string; title: string; url: string }
interface ChatMessage { id: string; author: 'me' | 'peer'; body: string; files: ChatFile[]; created_at: string }

const route = useRoute()
const selected = ref('')
const messages = ref<ChatMessage[]>([])
const text = ref('')
const error = ref('')
const busy = ref(false)
    const file = ref<File | null>(null)
    const fileKey = ref(0)

const current = computed(() => props.threads.find((item) => item.id === selected.value) ?? null)
const pill = (status: string) => status === 'answered' ? 'ok' : status === 'declined' ? 'danger' : 'warn'

watch(() => props.threads, (list) => {
  const query = typeof route.query.request === 'string' ? route.query.request : ''
  if (query && list.some((item) => item.id === query)) selected.value = query
  else if (!list.some((item) => item.id === selected.value)) selected.value = list[0]?.id ?? ''
}, { immediate: true })

const load = async (id: string) => {
  error.value = ''
  messages.value = []
  if (!id) return
  try {
    messages.value = await platformGet<ChatMessage[]>(`/integration/${id}/messages`)
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Переписка не открылась')
  }
}

watch(selected, (id) => { void load(id) })

const onFile = (event: Event) => {
  file.value = (event.target as HTMLInputElement).files?.[0] ?? null
}

const send = async () => {
  if (!selected.value) return
  error.value = ''
  busy.value = true
  try {
    const body = new FormData()
    body.set('text', text.value)
    if (file.value) body.set('file', file.value)
    const saved = await $fetch<ChatMessage>(`${usePlatformBase()}/integration/${selected.value}/messages`, {
      method: 'POST',
      body,
      credentials: 'include',
    })
    messages.value = [...messages.value, saved]
    text.value = ''
    file.value = null
    fileKey.value += 1
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Сообщение не ушло')
  } finally {
    busy.value = false
  }
}

const when = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="split">
    <aside class="glass a-panel list">
      <p v-if="!threads.length" class="body-sm muted">{{ empty }}</p>
      <button v-for="item in threads" :key="item.id" type="button" class="thread" :class="{ on: item.id === selected }" @click="selected = item.id">
        <span class="h4">{{ item.title }}</span>
        <span class="caption">{{ item.subtitle }}</span>
        <span class="a-pill" :class="pill(item.status)">{{ statusLabel[item.status] || item.status }}</span>
      </button>
    </aside>
    <section class="glass a-panel talk">
      <template v-if="current">
        <div class="a-head">
          <div>
            <div class="h3">{{ current.title }}</div>
            <p class="caption">{{ current.subtitle }}</p>
          </div>
          <NuxtLink v-if="current.project_id" :to="`/projects/${current.project_id}`" class="text-link">Открыть проект</NuxtLink>
        </div>
        <UiCallout v-if="error" tone="danger">{{ error }}</UiCallout>
        <div class="log">
          <p v-if="!messages.length && !error" class="body-sm muted">Сообщений пока нет. Напишите первое.</p>
          <article v-for="item in messages" :key="item.id" class="bubble" :class="{ me: item.author === 'me' }">
            <p v-if="item.body">{{ item.body }}</p>
            <a v-for="doc in item.files" :key="doc.name" :href="doc.url" class="file" target="_blank" rel="noopener">
              <PhPaperclip :size="14" /> {{ doc.title || 'Файл' }}
            </a>
            <span class="caption">{{ when(item.created_at) }}</span>
          </article>
        </div>
        <form class="composer" @submit.prevent="send">
          <textarea v-model="text" class="textarea" rows="3" placeholder="Сообщение по проекту" />
          <label class="a-fld">
            <span class="caption">Файл, если нужно</span>
            <input :key="fileKey" class="input" type="file" accept="image/png,image/jpeg,image/webp,application/pdf,text/plain,text/csv" @change="onFile">
            <span class="caption">{{ file ? file.name : 'PNG, JPG, PDF, TXT или CSV, до 8 МБ' }}</span>
          </label>
          <UiButton type="submit" :disabled="busy">Отправить</UiButton>
        </form>
      </template>
      <p v-else class="body-sm muted">Выберите переписку слева.</p>
    </section>
  </div>
</template>

<style scoped>
.split { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: var(--space-5); align-items: start; }
.list, .talk { padding: var(--space-4); display: grid; gap: 10px; align-content: start; }
.list > *, .talk > * { position: relative; z-index: 1; }
.thread { display: grid; gap: 4px; text-align: left; padding: 12px; border-radius: 12px; }
.thread.on { background: rgba(15, 20, 19, 0.06); }
.log { display: grid; gap: 8px; max-height: 420px; overflow: auto; }
.bubble { display: grid; gap: 4px; padding: 10px 12px; border-radius: 12px; background: rgba(15, 20, 19, 0.05); }
.bubble.me { background: var(--surface-brand-tint); }
.file { display: inline-flex; align-items: center; gap: 6px; font-weight: 700; }
.composer { display: grid; gap: 10px; }
.text-link { font-weight: 700; }
.a-pill { display: inline-flex; width: fit-content; padding: 3px 9px; border-radius: 999px; font-size: 12.5px; font-weight: 600; background: rgba(15, 20, 19, 0.06); }
.a-pill.warn { background: var(--state-warn-tint); color: var(--state-warn); }
.a-pill.ok { background: var(--surface-brand-tint); color: var(--brand-ink); }
.a-pill.danger { background: var(--state-danger-tint); color: var(--state-danger); }
@media (max-width: 800px) {
  .split { grid-template-columns: 1fr; }
}
</style>
