<script setup lang="ts">
import { PhCopy, PhInfo, PhX } from '@phosphor-icons/vue'
import { fetchErrorMessage } from '~/utils/errors'
import { platformSend } from '~/composables/usePlatform'

/** Плашка опубликованного демо над шагами проекта. «Скрыть» запоминается в браузере для этого демо на всех шагах. */
const props = defineProps<{ projectKey: string }>()

const { role } = useRole()
const router = useRouter()
const storageKey = computed(() => `demo-banner-hidden:${props.projectKey}`)
const hidden = useState<Record<string, boolean>>('demo-banner-hidden', () => ({}))

onMounted(() => {
  try {
    if (localStorage.getItem(storageKey.value) === '1') hidden.value = { ...hidden.value, [props.projectKey]: true }
  } catch { /* хранилище недоступно: плашка просто показывается */ }
})

const hide = () => {
  hidden.value = { ...hidden.value, [props.projectKey]: true }
  try { localStorage.setItem(storageKey.value, '1') } catch { /* без хранилища скрытие живёт до перезагрузки */ }
}

const copying = ref(false)
const error = ref('')
const copy = async () => {
  if (copying.value) return
  copying.value = true
  error.value = ''
  try {
    const result = await platformSend<{ id: string }>(`/projects/${props.projectKey}/copy`, 'POST')
    await router.push(`/projects/${result.id}/params`)
  } catch (e: unknown) {
    error.value = fetchErrorMessage(e, 'Не удалось скопировать демо')
  } finally {
    copying.value = false
  }
}
</script>

<template>
  <section v-if="!hidden[projectKey]" class="demo" role="note">
    <PhInfo :size="20" weight="duotone" class="ic" />
    <div class="copy">
      <div class="title">Демо-объект · только просмотр</div>
      <p>Параметры и допущения задал администратор. Пройдите по шагам, чтобы посмотреть подбор, сравнение, экономику и визуализацию. Менять значения можно в своей копии проекта.</p>
      <p v-if="error" class="err">{{ error }}</p>
      <div class="actions">
        <UiButton v-if="role !== 'guest'" size="sm" :disabled="copying" @click="copy"><template #icon><PhCopy :size="14" weight="bold" /></template>{{ copying ? 'Копируем…' : 'Скопировать в мои проекты' }}</UiButton>
        <UiButton v-else to="/login" size="sm">Войти, чтобы скопировать и править</UiButton>
        <UiButton variant="ghost" size="sm" @click="hide">Скрыть</UiButton>
      </div>
    </div>
    <button type="button" class="close" aria-label="Скрыть плашку демо-объекта" @click="hide"><PhX :size="16" weight="bold" /></button>
  </section>
</template>

<style scoped>
.demo { position: relative; display: grid; grid-template-columns: auto 1fr; gap: 12px; padding: 16px 48px 16px 18px; border-radius: 16px; background: var(--state-info-tint); color: var(--state-info); }
.ic { margin-top: 2px; }
.copy { display: grid; gap: 4px; }
.title { font-weight: 700; }
p { margin: 0; font-size: 15px; line-height: 1.45; }
.err { color: var(--state-danger); }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }
.close { position: absolute; top: 12px; right: 12px; width: 28px; height: 28px; border-radius: 8px; display: inline-flex; align-items: center; justify-content: center; color: inherit; opacity: 0.7; }
.close:hover { opacity: 1; background: rgba(15, 20, 19, 0.06); }
</style>
