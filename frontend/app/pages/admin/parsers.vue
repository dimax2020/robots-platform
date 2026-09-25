<script setup lang="ts">
import { PhCheckSquare, PhSquare } from '@phosphor-icons/vue'
import { platformGet, platformSend } from '~/composables/usePlatform'

definePageMeta({ layout: 'admin' })
useHead({ title: 'Парсеры' })

interface Job {
  id: string
  status: string
  error: string | null
  counters: Record<string, number>
  created_at: string | null
  finished_at: string | null
}
interface Parser {
  code: string
  title: string
  summary: string
  enabled: boolean
  hour: number
  minute: number
  next_run: string
  last_job: Job | null
}

const parsers = ref<Parser[]>([])
const notice = ref('')
const times = reactive<Record<string, string>>({})
const statusLabel: Record<string, string> = {
  pending: 'ожидает',
  running: 'выполняется',
  success: 'успех',
  error: 'ошибка',
}
const jobTone: Record<string, 'ok' | 'warn' | 'info' | 'danger' | 'neutral'> = {
  pending: 'warn',
  running: 'info',
  success: 'ok',
  error: 'danger',
}

const clock = (parser: Parser) =>
  `${String(parser.hour).padStart(2, '0')}:${String(parser.minute).padStart(2, '0')}`

const formatWhen = (iso: string | null) => {
  if (!iso) return 'ещё не запускался'
  return new Date(iso).toLocaleString('ru-RU', { timeZone: 'Europe/Moscow' })
}

const load = async () => {
  parsers.value = await platformGet<Parser[]>('/admin/parsers')
  for (const parser of parsers.value) {
    if (!times[parser.code]) times[parser.code] = clock(parser)
  }
}

const saveTime = async (parser: Parser) => {
  const [hour, minute] = (times[parser.code] || clock(parser)).split(':').map((part) => Number(part))
  await platformSend(`/admin/parsers/${parser.code}`, 'PATCH', { hour, minute, enabled: parser.enabled })
  notice.value = `${parser.title}: расписание ${times[parser.code]}, время московское`
  await load()
}

const toggle = async (parser: Parser) => {
  await platformSend(`/admin/parsers/${parser.code}`, 'PATCH', { enabled: !parser.enabled })
  await load()
}

const runNow = async (parser: Parser) => {
  const job = await platformSend<{ job_id: string }>(`/admin/parsers/${parser.code}/runs`, 'POST')
  notice.value = `${parser.title} поставлен в очередь`
  await watch(job.job_id)
}

const watch = async (id: string) => {
  for (let i = 0; i < 90; i += 1) {
    const job = await platformGet<Job>(`/admin/jobs/${id}`)
    notice.value = `${statusLabel[job.status] || job.status}${job.error ? `: ${job.error}` : ''}`
    if (job.status === 'success' || job.status === 'error') {
      await load()
      return
    }
    await new Promise((resolve) => setTimeout(resolve, 2000))
  }
  await load()
}

let timer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  void load().catch((err) => { notice.value = String(err) })
  timer = setInterval(() => {
    if (parsers.value.some((parser) => parser.last_job && (parser.last_job.status === 'pending' || parser.last_job.status === 'running'))) {
      void load()
    }
  }, 4000)
})
onBeforeUnmount(() => clearInterval(timer))
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Парсеры" title="Расписание обхода сайтов" lead="Каждый парсер запускается сам раз в сутки в выбранное московское время. Окно — два часа: если воркер был выключен в эту минуту, запуск всё ещё произойдёт в течение двух часов. Ручной запуск не ждёт расписания." />

    <UiCallout v-if="notice" tone="info">{{ notice }}</UiCallout>
    <p class="caption">Таблицы загружаются отдельно: <NuxtLink to="/admin/platform">импорт каталога и ручных характеристик</NuxtLink>.</p>

    <section v-for="parser in parsers" :key="parser.code" class="glass glass-xl card">
      <div class="in">
        <div class="head">
          <div>
            <div class="h3">{{ parser.title }}</div>
            <p class="caption">{{ parser.summary }}</p>
          </div>
          <UiButton size="sm" @click="runNow(parser)">Запустить сейчас</UiButton>
        </div>

        <div class="row">
          <button type="button" class="check" :class="{ on: parser.enabled }" @click="toggle(parser)">
            <PhCheckSquare v-if="parser.enabled" :size="18" weight="fill" /><PhSquare v-else :size="18" />
            <span class="body-sm strong">{{ parser.enabled ? 'Расписание включено' : 'Расписание выключено' }}</span>
          </button>
          <UiBadge :tone="parser.enabled ? 'ok' : 'neutral'" size="sm">{{ parser.enabled ? 'по расписанию' : 'выключен' }}</UiBadge>
        </div>

        <div class="row">
          <label class="time">
            <span class="caption">Каждый день в</span>
            <input v-model="times[parser.code]" type="time" class="input">
          </label>
          <UiButton size="sm" variant="secondary" @click="saveTime(parser)">Сохранить время</UiButton>
        </div>

        <div class="meta">
          <div>
            <div class="caption">Следующий запуск</div>
            <div class="body-sm strong">{{ formatWhen(parser.next_run) }}</div>
          </div>
          <div>
            <div class="caption">Последний прогон</div>
            <div class="body-sm strong">
              <template v-if="parser.last_job">
                <UiBadge :tone="jobTone[parser.last_job.status] || 'neutral'" size="sm">{{ statusLabel[parser.last_job.status] || parser.last_job.status }}</UiBadge>
                {{ formatWhen(parser.last_job.finished_at || parser.last_job.created_at) }}
              </template>
              <template v-else>ещё не было</template>
            </div>
          </div>
          <div v-if="parser.last_job && Object.keys(parser.last_job.counters).length">
            <div class="caption">Результат</div>
            <div class="body-sm strong">{{ parser.last_job.counters.created ?? 0 }} новых, {{ parser.last_job.counters.updated ?? 0 }} обновлено</div>
          </div>
        </div>
        <p v-if="parser.last_job?.error" class="caption err">{{ parser.last_job.error }}</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.card { overflow: hidden; }
.in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: var(--space-4); }
.head, .row { display: flex; gap: 12px; align-items: center; justify-content: space-between; flex-wrap: wrap; }
.check { display: inline-flex; align-items: center; gap: 10px; min-height: 36px; padding: 0 6px; border-radius: 8px; text-align: left; color: var(--ink-body); }
.check:hover { background: rgba(15, 20, 19, 0.05); }
.check svg { color: var(--ink-faint); }
.check.on svg { color: var(--brand-600); }
.time { display: flex; align-items: center; gap: 10px; }
.time .input { width: 140px; }
.meta { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); padding-top: var(--space-3); border-top: 1px solid var(--border-hairline); }
.err { color: var(--state-danger); }
@media (max-width: 1100px) { .meta { grid-template-columns: 1fr; } }
</style>
