<script setup lang="ts">
import { PhUploadSimple, PhFileCsv } from '@phosphor-icons/vue'
import { platformGet, usePlatformBase } from '~/composables/usePlatform'
import { fetchErrorMessage } from '~/utils/errors'

definePageMeta({ layout: 'admin', middleware: 'admin', pageTransition: false })
useHead({ title: 'Админка · Таблицы' })

interface Job { id: string; kind: string; status: string; error: string | null; counters: Record<string, number>; created_at: string | null; finished_at: string | null }

const kinds = [
  { code: 'catalog', file: 'catalog_export_v4.csv', title: 'Каталог организатора', hint: 'Все колонки строки сохраняются в карточке. Тип решения ставится по колонкам «Тип» и «Подтип».' },
  { code: 'manual', file: 'ttx_manual.csv', title: 'Ручная таблица характеристик', hint: 'Дописывает пустые характеристики существующих карточек. Источник берётся из строки таблицы, заполненное не затирается.' },
]
const kind = ref<'catalog' | 'manual'>('catalog')
const file = ref<File | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
const drag = ref(false)
const notice = ref<{ tone: 'info' | 'ok' | 'danger'; text: string } | null>(null)
const jobs = ref<Job[]>([])
const busy = ref(false)

const statusLabel: Record<string, string> = { pending: 'ожидает', running: 'выполняется', success: 'готово', error: 'ошибка' }
const statusTone: Record<string, 'warn' | 'info' | 'ok' | 'danger'> = { pending: 'warn', running: 'info', success: 'ok', error: 'danger' }
const kindTitle = (value: string) => kinds.find((item) => `import_${item.code}` === value)?.title ?? value
const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString('ru-RU', { timeZone: 'Europe/Moscow' }) : '—')
const counterText = (counters: Record<string, number>) => {
  const parts = []
  if (counters.rows != null) parts.push(`${counters.rows} строк`)
  if (counters.created != null) parts.push(`${counters.created} новых`)
  if (counters.updated != null) parts.push(`${counters.updated} обновлено`)
  if (counters.skipped) parts.push(`${counters.skipped} пропущено`)
  if (counters.typed) parts.push(`${counters.typed} получили тип`)
  if (counters.untyped != null) parts.push(`${counters.untyped} без типа в каталоге`)
  return parts.join(' · ') || '—'
}

const loadJobs = async () => { jobs.value = await platformGet<Job[]>('/admin/jobs?kind=import&limit=15') }
onMounted(() => { void loadJobs().catch(() => {}) })

const onFile = (event: Event) => { file.value = (event.target as HTMLInputElement).files?.[0] ?? null }
const onDrop = (event: DragEvent) => { drag.value = false; file.value = event.dataTransfer?.files?.[0] ?? file.value }

const watchJob = async (id: string) => {
  for (let i = 0; i < 60; i += 1) {
    const job = await platformGet<Job>(`/admin/jobs/${id}`)
    notice.value = { tone: job.status === 'error' ? 'danger' : job.status === 'success' ? 'ok' : 'info', text: job.error || `${statusLabel[job.status] ?? job.status}: ${counterText(job.counters)}` }
    if (job.status === 'success' || job.status === 'error') { await loadJobs(); return }
    await new Promise((resolve) => setTimeout(resolve, 2000))
  }
}

const upload = async () => {
  if (!file.value || busy.value) return
  busy.value = true
  const body = new FormData()
  body.set('kind', kind.value)
  body.set('file', file.value)
  try {
    const job = await $fetch<{ job_id: string }>(`${usePlatformBase()}/admin/imports`, { method: 'POST', body })
    notice.value = { tone: 'info', text: 'Файл в очереди. Статус обновится сам.' }
    file.value = null
    await loadJobs()
    await watchJob(job.job_id)
  } catch (err) {
    notice.value = { tone: 'danger', text: fetchErrorMessage(err, 'Файл не принят') }
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Импорт данных" title="Таблицы" lead="Загрузка файлов в каталог (ТЗ 3.3.2). Файл уходит в очередь, импорт выполняет фоновый обработчик. Ручные правки в карточках импорт не затирает." />
    <UiCallout v-if="notice" :tone="notice.tone">{{ notice.text }}</UiCallout>
    <p class="caption">Сайты обходят парсеры: <NuxtLink to="/admin/parsers" class="link">расписание и ручной запуск</NuxtLink>. Продукты без типа после импорта разбираются в <NuxtLink to="/admin/catalog/types?tab=untyped" class="link">Каталог → Типы решений</NuxtLink>.</p>

    <div class="kinds">
      <button v-for="item in kinds" :key="item.code" type="button" class="glass kind" :class="{ on: kind === item.code }" @click="kind = item.code as 'catalog' | 'manual'">
        <span class="k-in">
          <span class="h4">{{ item.title }}</span>
          <span class="mono-sm">{{ item.file }}</span>
          <span class="caption">{{ item.hint }}</span>
        </span>
      </button>
    </div>

    <div class="drop glass" :class="{ drag }" @dragover.prevent="drag = true" @dragleave="drag = false" @drop.prevent="onDrop">
      <div class="d-in">
        <div class="d-ic"><PhFileCsv :size="28" weight="duotone" /></div>
        <div class="h3">{{ file ? file.name : 'Перетащите CSV сюда' }}</div>
        <div class="body-sm muted">{{ kinds.find((k) => k.code === kind)?.title }}. Кодировка UTF-8, разделитель как в исходном файле.</div>
        <div class="d-row">
          <UiButton size="sm" variant="secondary" @click="fileInput?.click()"><template #icon><PhUploadSimple :size="14" weight="bold" /></template>Выбрать файл</UiButton>
          <UiButton size="sm" :disabled="!file || busy" @click="upload">Поставить в очередь</UiButton>
        </div>
        <input ref="fileInput" class="sr" type="file" accept=".csv,text/csv" @change="onFile">
      </div>
    </div>

    <section class="glass glass-xl a-panel">
      <div class="h4">Последние импорты</div>
      <p v-if="!jobs.length" class="body-sm muted">Импортов ещё не было.</p>
      <table v-else class="table">
        <thead><tr><th>Когда</th><th>Файл</th><th>Статус</th><th>Итог</th></tr></thead>
        <tbody>
          <tr v-for="job in jobs" :key="job.id">
            <td class="mono-sm">{{ when(job.finished_at || job.created_at) }}</td>
            <td class="body-sm">{{ kindTitle(job.kind) }}</td>
            <td><UiBadge :tone="statusTone[job.status] || 'neutral'" size="sm">{{ statusLabel[job.status] || job.status }}</UiBadge></td>
            <td class="body-sm">{{ job.error || counterText(job.counters) }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.kinds { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.kind { text-align: left; border-radius: var(--radius-lg); }
.kind.on { box-shadow: inset 0 0 0 2px var(--brand-400); }
.k-in { position: relative; z-index: 1; display: grid; gap: 6px; padding: var(--space-4) var(--space-5); }
.drop { border: 1.5px dashed var(--border-strong); }
.drop.drag { border-color: var(--brand-500); }
.d-in { position: relative; z-index: 1; padding: var(--space-6); display: grid; gap: 6px; justify-items: center; text-align: center; }
.d-ic { width: 56px; height: 56px; border-radius: 16px; background: var(--surface-brand-tint); color: var(--brand-700); display: grid; place-items: center; margin-bottom: 6px; }
.d-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; justify-content: center; margin-top: 8px; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
@media (max-width: 1100px) { .kinds { grid-template-columns: 1fr; } }
</style>
