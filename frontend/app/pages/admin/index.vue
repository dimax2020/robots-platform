<script setup lang="ts">
import { PhArrowRight, PhWarningCircle, PhCheckCircle } from '@phosphor-icons/vue'
import { platformGet } from '~/composables/usePlatform'
import { fetchErrorMessage } from '~/utils/errors'
import { adminNav } from '~/data/adminNav'
import { pluralRu } from '~/data/adminLabels'

definePageMeta({ layout: 'admin', middleware: 'admin', pageTransition: false })
useHead({ title: 'Админка · Обзор' })

interface Ref { code: string; name: string }
interface Job { id: string; kind: string; parser_code: string | null; status: string; error: string | null; counters: Record<string, number>; created_at: string | null; finished_at: string | null }
interface Overview {
  products: { total: number; untyped: number; without_process: number; without_price: number }
  processes: {
    total: number
    without_robots: Ref[]
    without_filters: Ref[]
    without_count: Ref[]
    without_objects: Ref[]
    readiness: { code: string; name: string; ready: number; robots: number; complete: number }[]
    average_ready: number
  }
  objects: { code: string; name: string; unbound: number }[]
  norms: { last_change: string | null; without_source: string[]; total: number }
  sources: { total: number; without_url: number }
  jobs: Job[]
}

const data = ref<Overview | null>(null)
const failure = ref('')
onMounted(async () => {
  try {
    data.value = await platformGet<Overview>('/admin/overview')
  } catch (err) {
    failure.value = fetchErrorMessage(err, 'Сводка не загрузилась: проверьте, что платформа запущена')
  }
})

const tasks = computed(() => {
  const d = data.value
  if (!d) return []
  const list: { tone: 'warn' | 'ok'; title: string; note: string; to: string; action: string }[] = []
  if (d.products.untyped) list.push({ tone: 'warn', title: `${d.products.untyped} ${pluralRu(d.products.untyped, 'продукт', 'продукта', 'продуктов')} без типа решения`, note: 'Без типа продукт выпадает из уровня дерева ТЗ 3.3.1 и из нормативов по типам. Тип назначается сразу всей категории сайта.', to: '/admin/catalog/types?tab=untyped', action: 'Разобрать' })
  if (d.products.without_process) list.push({ tone: 'warn', title: `${d.products.without_process} ${pluralRu(d.products.without_process, 'продукт', 'продукта', 'продуктов')} не привязаны к процессу`, note: 'В подбор робот попадает только через процесс.', to: '/admin/products?process=-', action: 'Открыть' })
  if (d.processes.without_objects.length) list.push({ tone: 'warn', title: `Процессы без объекта: ${d.processes.without_objects.map((p) => p.name).join(', ')}`, note: 'Проект их не видит.', to: `/admin/processes?code=${d.processes.without_objects[0]!.code}`, action: 'Настроить' })
  if (d.processes.without_robots.length) list.push({ tone: 'warn', title: `Процессы без роботов: ${d.processes.without_robots.map((p) => p.name).join(', ')}`, note: 'Подбор по ним будет пустым.', to: `/admin/coverage?process=${d.processes.without_robots[0]!.code}`, action: 'Добавить роботов' })
  if (d.processes.without_filters.length) list.push({ tone: 'warn', title: `Процессы без условий: ${d.processes.without_filters.map((p) => p.name).join(', ')}`, note: 'В подбор проходят все роботы процесса.', to: `/admin/processes?code=${d.processes.without_filters[0]!.code}`, action: 'Задать условия' })
  if (d.processes.without_count.length) list.push({ tone: 'warn', title: `Процессы без формулы количества: ${d.processes.without_count.map((p) => p.name).join(', ')}`, note: 'Количество роботов и экономика по ним не посчитаются.', to: `/admin/processes?code=${d.processes.without_count[0]!.code}`, action: 'Задать формулу' })
  for (const obj of d.objects) list.push({ tone: 'warn', title: `${obj.name}: ${obj.unbound} ${pluralRu(obj.unbound, 'величина', 'величины', 'величин')} процессов без поля объекта`, note: 'Условие не проверяется, робот получает «уточнить».', to: `/admin/objects?code=${obj.code}`, action: 'Привязать' })
  if (d.norms.without_source.length) list.push({ tone: 'warn', title: `Нормативы без источника: ${d.norms.without_source.join(', ')}`, note: 'ТЗ 3.5.1 запрещает недокументированные коэффициенты.', to: '/admin/norms', action: 'Указать источник' })
  if (!list.length) list.push({ tone: 'ok', title: 'Модель подбора и каталог настроены', note: 'Срочных задач нет.', to: '/admin/catalog', action: 'Дерево каталога' })
  return list
})

const pct = (value: number) => `${Math.round(value * 100)}%`
const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString('ru-RU', { timeZone: 'Europe/Moscow', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : 'не было')
const jobTitle = (job: Job) => (job.kind === 'parser' ? `Парсер ${job.parser_code}` : job.kind === 'import_catalog' ? 'Импорт каталога' : job.kind === 'import_manual' ? 'Импорт ручной таблицы' : job.kind)
const statusLabel: Record<string, string> = { pending: 'ожидает', running: 'выполняется', success: 'готово', error: 'ошибка' }
const statusTone: Record<string, 'warn' | 'info' | 'ok' | 'danger'> = { pending: 'warn', running: 'info', success: 'ok', error: 'danger' }
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Обзор" title="Что требует внимания" lead="Сводка по каталогу, модели подбора и нормативам на живых данных платформы. Каждая строка ведёт туда, где это исправляется." />
    <UiCallout v-if="failure" tone="danger">{{ failure }}</UiCallout>

    <template v-if="data">
      <div class="tiles">
        <NuxtLink to="/admin/products" class="glass tile"><span class="t-in"><span class="display-3">{{ data.products.total }}</span><span class="h4">Продуктов</span><span class="caption">{{ data.products.without_price }} без цены</span></span></NuxtLink>
        <NuxtLink to="/admin/processes" class="glass tile"><span class="t-in"><span class="display-3">{{ data.processes.total }}</span><span class="h4">Процессов</span><span class="caption">готовность данных к расчёту {{ pct(data.processes.average_ready) }}</span></span></NuxtLink>
        <NuxtLink to="/admin/catalog/types?tab=untyped" class="glass tile" :class="{ warn: data.products.untyped }"><span class="t-in"><span class="display-3">{{ data.products.untyped }}</span><span class="h4">Без типа решения</span><span class="caption">из {{ data.products.total }} продуктов</span></span></NuxtLink>
        <NuxtLink to="/admin/sources" class="glass tile"><span class="t-in"><span class="display-3">{{ data.sources.total }}</span><span class="h4">Источников</span><span class="caption">{{ data.sources.without_url }} без ссылки</span></span></NuxtLink>
      </div>

      <section class="glass glass-xl a-panel">
        <div class="h3">Задачи</div>
        <div v-for="task in tasks" :key="task.title" class="task">
          <component :is="task.tone === 'ok' ? PhCheckCircle : PhWarningCircle" :size="20" weight="fill" :class="task.tone" />
          <div><div class="body-sm strong">{{ task.title }}</div><div class="caption">{{ task.note }}</div></div>
          <UiButton size="sm" variant="secondary" :to="task.to">{{ task.action }}<template #after><PhArrowRight :size="14" weight="bold" /></template></UiButton>
        </div>
      </section>

      <div class="two">
        <section class="glass glass-xl a-panel">
          <div class="a-head">
            <div class="h4">Готовность данных по процессам</div>
            <NuxtLink to="/admin/coverage" class="link body-sm">Список продуктов</NuxtLink>
          </div>
          <p class="caption">Доля характеристик, нужных для расчёта, в среднем по роботам процесса. Сначала самые слабые.</p>
          <NuxtLink v-for="item in data.processes.readiness.slice(0, 8)" :key="item.code" :to="`/admin/coverage?process=${item.code}`" class="ready">
            <span class="body-sm">{{ item.name }}</span>
            <span class="bar"><i :style="{ width: pct(item.ready) }" /></span>
            <span class="mono-sm">{{ pct(item.ready) }}</span>
            <span class="caption">{{ item.complete }}/{{ item.robots }} полных</span>
          </NuxtLink>
        </section>

        <section class="glass glass-xl a-panel">
          <div class="a-head">
            <div class="h4">Последние импорты и парсеры</div>
            <NuxtLink to="/admin/tables" class="link body-sm">Таблицы</NuxtLink>
          </div>
          <p v-if="!data.jobs.length" class="body-sm muted">Прогонов ещё не было.</p>
          <div v-for="job in data.jobs" :key="job.id" class="job">
            <span class="body-sm strong">{{ jobTitle(job) }}</span>
            <UiBadge :tone="statusTone[job.status] || 'neutral'" size="sm">{{ statusLabel[job.status] || job.status }}</UiBadge>
            <span class="caption">{{ when(job.finished_at || job.created_at) }}</span>
            <span v-if="job.error" class="caption err">{{ job.error }}</span>
            <span v-else-if="job.counters.created != null || job.counters.updated != null" class="caption">{{ job.counters.created ?? 0 }} новых, {{ job.counters.updated ?? 0 }} обновлено</span>
          </div>
          <div class="a-block">
            <div class="h4">Нормативы</div>
            <p class="caption">Последнее изменение: {{ when(data.norms.last_change) }}. {{ data.norms.without_source.length ? `Без источника: ${data.norms.without_source.length}.` : `Все ${data.norms.total} с обоснованием и источником.` }}</p>
            <NuxtLink to="/admin/norms" class="link body-sm">К нормативам</NuxtLink>
          </div>
        </section>
      </div>

      <section class="glass glass-xl a-panel">
        <div class="h4">Разделы</div>
        <div class="sections">
          <div v-for="group in adminNav" :key="group.label" class="sec">
            <div class="a-sub">{{ group.label }}</div>
            <NuxtLink v-for="item in group.items" :key="item.to" :to="item.to" class="sec-item">
              <component :is="item.icon" :size="18" weight="duotone" />
              <span><span class="body-sm strong">{{ item.label }}</span><span class="caption block">{{ item.note }}</span></span>
            </NuxtLink>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.tiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-4); }
.tile { border-radius: var(--radius-xl); transition: transform var(--dur-mid) var(--ease); }
.tile:hover { transform: translateY(-2px); }
.tile.warn .display-3 { color: var(--state-warn); }
.t-in { position: relative; z-index: 1; display: grid; gap: 4px; padding: var(--space-5); }
.task { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 10px 0; border-top: 1px solid var(--border-hairline); }
.task .warn { color: var(--state-warn); }
.task .ok { color: var(--brand-600); }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-5); align-items: start; }
.ready { display: grid; grid-template-columns: minmax(0, 1fr) 90px 44px 90px; gap: 10px; align-items: center; padding: 6px 8px; border-radius: 10px; }
.ready:hover { background: rgba(15, 20, 19, 0.04); }
.bar { height: 6px; border-radius: 3px; background: rgba(15, 20, 19, 0.08); overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--state-warn); }
.job { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 4px 10px; align-items: center; padding: 8px 0; border-top: 1px solid var(--border-hairline); }
.job .caption:last-child:not(:nth-child(3)) { grid-column: 1 / -1; }
.err { color: var(--state-danger); }
.sections { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4); }
.sec { display: grid; gap: 4px; align-content: start; }
.sec-item { display: grid; grid-template-columns: auto 1fr; gap: 10px; align-items: start; padding: 8px; border-radius: 10px; color: var(--brand-700); }
.sec-item:hover { background: rgba(15, 20, 19, 0.04); }
.block { display: block; }
@media (max-width: 1100px) {
  .tiles { grid-template-columns: 1fr 1fr; }
  .two, .sections { grid-template-columns: 1fr; }
}
</style>
