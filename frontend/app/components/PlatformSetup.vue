<script setup lang="ts">
import { platformGet, platformSend } from '~/composables/usePlatform'

interface ProcessItem {
  code: string
  name: string
  enabled: boolean
}
interface Project {
  id: string
  processes: ProcessItem[]
}

/** Только просмотр: опубликованное демо у гостя и пользователя. Переключатели не нажимаются, сохранение не идёт. */
const props = defineProps<{ objectCode?: string; readonly?: boolean }>()

const route = useRoute()
const projectId = computed(() => String(route.params.id || ''))
const project = ref<Project | null>(null)
const notice = ref('')
const noticeTone = ref<'ok' | 'danger'>('ok')

const load = async () => {
  if (!projectId.value) return
  project.value = await platformGet<Project>(`/projects/${projectId.value}`)
}

const save = async () => {
  if (!project.value || props.readonly) return
  const enabled: Record<string, boolean> = {}
  for (const process of project.value.processes) enabled[process.code] = process.enabled
  project.value = await platformSend<Project>(`/projects/${projectId.value}`, 'PATCH', { enabled })
}

defineExpose({ save })

onMounted(() => { void load().catch((err) => { notice.value = String(err); noticeTone.value = 'danger' }) })
</script>

<template>
  <section class="group glass">
    <div class="sec-head">
      <div>
        <div class="h3">Процессы объекта</div>
        <div class="caption">{{ readonly ? 'Какие процессы администратор включил в подбор этого демо.' : 'Снимите процесс, если его не нужно включать в подбор. Пока фильтры пустые, проходят все роботы процесса.' }}</div>
      </div>
    </div>

    <UiCallout v-if="notice" :tone="noticeTone">{{ notice }}</UiCallout>

    <div class="procs">
      <button
        v-for="(process, index) in project?.processes ?? []"
        :key="process.code"
        type="button"
        class="proc"
        :class="{ on: process.enabled, still: readonly }"
        :aria-pressed="process.enabled"
        :disabled="readonly"
        @click="process.enabled = !process.enabled"
      >
        <span class="mono-sm tn">{{ index + 1 }}</span>
        <span class="proc-copy">
          <span class="body-sm strong">{{ process.name }}</span>
          <span class="caption">{{ process.enabled ? 'в подборе' : 'выключен' }}</span>
        </span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.group { padding: var(--space-6); display: grid; gap: var(--space-5); }
.group > * { position: relative; z-index: 1; }
.sec-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-4); }
.procs { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.proc { display: grid; grid-template-columns: auto 1fr; gap: 10px; align-items: center; text-align: left; padding: 10px 12px; border-radius: 14px; background: rgba(255, 255, 255, 0.55); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.proc.on { background: #fff; box-shadow: inset 0 0 0 1px var(--brand-400); }
.proc.still { cursor: default; }
.proc-copy { display: grid; gap: 2px; min-width: 0; }
.proc-copy .body-sm { color: var(--ink-strong); font-weight: 650; }
.tn { width: 28px; height: 28px; border-radius: 8px; background: var(--surface-graphite); color: var(--brand-300); display: inline-flex; align-items: center; justify-content: center; flex: none; }
@media (max-width: 1100px) {
  .procs { grid-template-columns: 1fr; }
}
</style>
