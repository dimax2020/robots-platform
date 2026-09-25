<script setup lang="ts">
import { PhUploadSimple, PhFileCsv } from '@phosphor-icons/vue'
import { platformGet, platformSend } from '~/composables/usePlatform'

definePageMeta({ layout: 'admin' })
useHead({ title: 'Импорт таблиц' })

interface Tree {
  industries: { code: string; name: string }[]
  objects: { code: string; name: string; industries: string[]; processes: string[] }[]
  processes: { code: string; name: string; product_count: number; filters: Filter[] }[]
}
interface Filter { id?: number; name: string; object_keys: string[]; robot_keys: string[]; op: string; mode: string }
interface Attr { key: string; label: string; usage: string }

const tree = ref<Tree | null>(null)
const attrs = ref<Attr[]>([])
const notice = ref('')
const kind = ref<'catalog' | 'manual'>('catalog')
const file = ref<File | null>(null)
const slug = ref('')
const processCodes = ref('')
const objectCode = ref('warehouse')
const objectName = ref('Склад')
const objectIndustries = ref('logistics')
const objectProcesses = ref('')

const usageLabel: Record<string, string> = { active: 'В фильтрах', unused: 'Не используется', pending: 'Новая' }
const usageTone: Record<string, 'ok' | 'neutral' | 'warn'> = { active: 'ok', unused: 'neutral', pending: 'warn' }
const fileInput = ref<HTMLInputElement | null>(null)
const drag = ref(false)

const onFile = (event: Event) => {
  file.value = (event.target as HTMLInputElement).files?.[0] ?? null
}

const onDrop = (event: DragEvent) => {
  drag.value = false
  file.value = event.dataTransfer?.files?.[0] ?? file.value
}

const load = async () => {
  tree.value = await platformGet<Tree>('/catalog/tree')
  attrs.value = await platformGet<Attr[]>('/admin/attributes')
  const warehouse = tree.value.objects.find((item) => item.code === 'warehouse')
  if (warehouse) objectProcesses.value = warehouse.processes.join(', ')
}

const upload = async () => {
  if (!file.value) return
  const body = new FormData()
  body.set('kind', kind.value)
  body.set('file', file.value)
  const job = await $fetch<{ job_id: string }>(`${useRuntimeConfig().public.platformApiBase}/admin/imports`, { method: 'POST', body })
  notice.value = `Прогон ${job.job_id} поставлен. Статус обновится сам.`
  await watchJob(job.job_id)
}

const watchJob = async (id: string) => {
  for (let i = 0; i < 30; i += 1) {
    const job = await platformGet<{ status: string; error: string | null; counters: Record<string, number> }>(`/admin/jobs/${id}`)
    const created = job.counters.created
    const updated = job.counters.updated
    const bits = [
      created != null ? `${created} новых` : '',
      updated != null ? `${updated} обновлено` : '',
    ].filter(Boolean)
    notice.value = job.error || [job.status === 'success' ? 'Готово' : job.status, bits.join(', ')].filter(Boolean).join(': ')
    if (job.status === 'success' || job.status === 'error') {
      await load()
      return
    }
    await new Promise((resolve) => setTimeout(resolve, 2000))
  }
}

const saveObject = async () => {
  await platformSend('/admin/objects', 'POST', {
    code: objectCode.value.trim(),
    name: objectName.value.trim(),
    industries: objectIndustries.value.split(',').map((item) => item.trim()).filter(Boolean),
    processes: objectProcesses.value.split(',').map((item) => item.trim()).filter(Boolean),
  })
  notice.value = 'Объект сохранён'
  await load()
}

const assign = async () => {
  await platformSend(`/admin/products/${slug.value.trim()}/processes`, 'PUT', {
    processes: processCodes.value.split(',').map((item) => item.trim()).filter(Boolean),
  })
  notice.value = 'Процессы назначены роботу'
  await load()
}

const toggleUnused = async (key: string, unused: boolean) => {
  await platformSend(`/admin/attributes/${key}/usage`, 'POST', { unused })
  await load()
}

onMounted(() => { void load().catch((err) => { notice.value = String(err) }) })
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Импорт" title="Таблицы каталога" lead="Сюда загружаются только файлы: исходный каталог ФЦ БАС и ручная таблица характеристик. Парсеры сайтов запускаются отдельно, по расписанию." />

    <UiCallout v-if="notice" tone="info">{{ notice }}</UiCallout>
    <p class="caption">Парсеры сайтов: <NuxtLink to="/admin/parsers">расписание и ручной запуск</NuxtLink>.</p>

    <div class="drop glass" :class="{ drag }" @dragover.prevent="drag = true" @dragleave="drag = false" @drop.prevent="onDrop">
      <div class="d-in">
        <div class="d-ic"><PhFileCsv :size="28" weight="duotone" /></div>
        <div class="h3">{{ file ? file.name : 'Выберите CSV' }}</div>
        <div class="body-sm muted">Исходный каталог или ручная таблица характеристик. Файл уходит в очередь, в каталог сразу не пишется.</div>
        <div class="d-row">
          <select v-model="kind" class="select">
            <option value="catalog">catalog_export_v4.csv</option>
            <option value="manual">ttx_manual.csv</option>
          </select>
          <UiButton size="sm" variant="secondary" @click="fileInput?.click()"><template #icon><PhUploadSimple :size="14" weight="bold" /></template>Выбрать файл</UiButton>
          <UiButton size="sm" :disabled="!file" @click="upload">Поставить в очередь</UiButton>
        </div>
        <input ref="fileInput" class="sr" type="file" accept=".csv,text/csv" @change="onFile">
      </div>
    </div>

    <section class="glass glass-xl panel">
      <div class="in">
        <div class="h3">Объекты</div>
        <div class="caption">Отрасли и процессы объекта. Один объект может относиться к нескольким отраслям.</div>
        <div class="tbl">
          <table class="table">
            <thead><tr><th>Объект</th><th>Отрасли</th><th>Процессы</th></tr></thead>
            <tbody>
              <tr v-for="item in tree?.objects ?? []" :key="item.code">
                <td><span class="strong">{{ item.name }}</span><span class="caption block mono-sm">{{ item.code }}</span></td>
                <td class="body-sm">{{ item.industries.join(', ') || 'нет' }}</td>
                <td class="body-sm">{{ item.processes.join(', ') || 'нет' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="fields">
          <label class="fld"><span class="caption">Код</span><input v-model="objectCode" class="input"></label>
          <label class="fld"><span class="caption">Название</span><input v-model="objectName" class="input"></label>
          <label class="fld"><span class="caption">Отрасли через запятую</span><input v-model="objectIndustries" class="input"></label>
          <label class="fld"><span class="caption">Процессы через запятую</span><input v-model="objectProcesses" class="input"></label>
        </div>
        <div class="actions"><UiButton size="sm" variant="secondary" @click="saveObject">Сохранить объект</UiButton></div>
      </div>
    </section>

    <section class="glass glass-xl panel">
      <div class="in">
        <div class="h3">Процессы</div>
        <div class="caption">Сколько роботов назначено на процесс. Фильтры пока пустые: в подбор проходят все назначенные роботы.</div>
        <div class="tbl">
          <table class="table">
            <thead><tr><th>Процесс</th><th class="num">Роботов</th><th class="num">Фильтров</th></tr></thead>
            <tbody>
              <tr v-for="process in tree?.processes ?? []" :key="process.code">
                <td><span class="strong">{{ process.name }}</span><span class="caption block mono-sm">{{ process.code }}</span></td>
                <td class="num mono-sm">{{ process.product_count }}</td>
                <td class="num mono-sm">{{ process.filters.length }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <section class="glass glass-xl panel">
      <div class="in">
        <div class="h3">Процессы робота</div>
        <div class="caption">Коды процессов через запятую. Назначение заменяет прежний список у этой карточки.</div>
        <div class="fields">
          <label class="fld"><span class="caption">Slug</span><input v-model="slug" class="input"></label>
          <label class="fld"><span class="caption">Процессы</span><input v-model="processCodes" class="input" placeholder="floor_cleaning, pallet_transport"></label>
        </div>
        <div class="actions"><UiButton size="sm" :disabled="!slug.trim()" @click="assign">Назначить</UiButton></div>
      </div>
    </section>

    <section class="glass glass-xl panel">
      <div class="in">
        <div class="h3">Характеристики</div>
        <div class="caption">В фильтрах — ключ уже читает правило. Не используется — отложена. Новая — пришла из импорта и ещё не разобрана.</div>
        <div class="tbl">
          <table class="table">
            <thead><tr><th>Характеристика</th><th>Состояние</th><th></th></tr></thead>
            <tbody>
              <tr v-for="attr in attrs" :key="attr.key">
                <td><span class="strong">{{ attr.label }}</span><span class="caption block mono-sm">{{ attr.key }}</span></td>
                <td><UiBadge :tone="usageTone[attr.usage] || 'neutral'" size="sm">{{ usageLabel[attr.usage] || attr.usage }}</UiBadge></td>
                <td class="num"><UiButton size="sm" variant="secondary" @click="toggleUnused(attr.key, attr.usage !== 'unused')">{{ attr.usage === 'unused' ? 'Вернуть' : 'Не использовать' }}</UiButton></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.drop { border: 1.5px dashed var(--border-strong); }
.drop.drag { border-color: var(--brand-500); }
.d-in { position: relative; z-index: 1; padding: var(--space-6); display: grid; gap: 6px; justify-items: center; text-align: center; }
.d-ic { width: 56px; height: 56px; border-radius: 16px; background: var(--surface-brand-tint); color: var(--brand-700); display: grid; place-items: center; margin-bottom: 6px; }
.d-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; justify-content: center; margin-top: 8px; }
.d-row .select { width: 240px; }
.sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
.panel { overflow: hidden; }
.in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: var(--space-4); }
.tbl { overflow: auto; }
.block { display: block; }
.fields { display: grid; grid-template-columns: 1fr 1fr; gap: 16px 24px; }
.fld { display: grid; gap: 6px; }
.actions { display: flex; }
.num { text-align: right; }
@media (max-width: 1100px) { .fields { grid-template-columns: 1fr; } }
</style>
