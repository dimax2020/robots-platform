<script setup lang="ts">
import { PhPlus, PhTrash, PhMagnifyingGlass, PhArrowSquareOut } from '@phosphor-icons/vue'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { fetchErrorMessage } from '~/utils/errors'
import { pluralRu } from '~/data/adminLabels'
import { replaceQuery } from '~/composables/useQuerySync'

definePageMeta({ layout: 'admin', middleware: 'admin', pageTransition: false })
useHead({ title: 'Админка · Список продуктов' })

interface ProcItem { code: string; name: string; product_count: number; objects: { code: string; name: string }[] }
interface Key { key: string; label: string; used_in: string; missing: number }
interface Robot { slug: string; name: string; manufacturer: string | null; image_url: string | null; solution_type: string | null; ready: number; completeness: number; missing: string[] }
interface Coverage { code: string; name: string; keys: Key[]; robots: Robot[]; total: number; ready: number }
interface Found { slug: string; name: string; manufacturer: string | null; processes: { code: string }[]; solution_type: { name: string } | null }

const route = useRoute()
const processes = ref<ProcItem[]>([])
const selected = ref(typeof route.query.process === 'string' ? route.query.process : '')
const data = ref<Coverage | null>(null)
const loading = ref(false)
const notice = ref<{ ok: boolean; text: string } | null>(null)
const onlyKey = ref('')
const query = ref('')
const addQuery = ref('')
const found = ref<Found[]>([])

const usedLabel: Record<string, string> = { 'условие': 'условие подбора', 'количество': 'формула количества', 'лучший': 'выбор лучшего', 'экономика': 'экономика' }
const keyLabel = (key: string) => data.value?.keys.find((item) => item.key === key)?.label ?? key
const averageReady = computed(() => {
  const rows = data.value?.robots ?? []
  return rows.length ? Math.round((rows.reduce((sum, item) => sum + item.ready, 0) / rows.length) * 100) : 0
})
const worst = computed(() => [...(data.value?.keys ?? [])].filter((item) => item.missing).sort((a, b) => b.missing - a.missing))
const shown = computed(() => {
  const text = query.value.trim().toLowerCase()
  return (data.value?.robots ?? []).filter((item) => (!onlyKey.value || item.missing.includes(onlyKey.value)) && (!text || `${item.name} ${item.manufacturer ?? ''}`.toLowerCase().includes(text)))
})
const grouped = computed(() => {
  const map = new Map<string, ProcItem[]>()
  for (const item of processes.value) {
    const name = item.objects.map((obj) => obj.name).join(', ') || 'Без объекта'
    map.set(name, [...(map.get(name) ?? []), item])
  }
  return [...map.entries()]
})

const load = async () => {
  if (!selected.value) { data.value = null; return }
  loading.value = true
  try {
    data.value = await platformGet<Coverage>(`/admin/processes/${selected.value}/coverage`)
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось загрузить роботов процесса') }
  } finally {
    loading.value = false
  }
}
const choose = (code: string) => {
  selected.value = code
  onlyKey.value = ''
  replaceQuery({ process: code || undefined })
  void load()
}
onMounted(async () => {
  try {
    processes.value = await platformGet<ProcItem[]>('/admin/processes')
    if (!selected.value && processes.value[0]) choose(processes.value[0].code)
    else await load()
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось загрузить процессы') }
  }
})

let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(addQuery, (text) => {
  clearTimeout(searchTimer)
  if (text.trim().length < 2) { found.value = []; return }
  searchTimer = setTimeout(async () => {
    found.value = await platformGet<Found[]>(`/admin/products?q=${encodeURIComponent(text.trim())}&limit=12`)
  }, 300)
})
const inProcess = (item: Found) => item.processes.some((proc) => proc.code === selected.value)

const change = async (add: string[], remove: string[]) => {
  try {
    await platformSend(`/admin/processes/${selected.value}/products`, 'PUT', { add, remove })
    notice.value = { ok: true, text: add.length ? 'Робот добавлен в процесс' : 'Робот убран из процесса' }
    await load()
    if (addQuery.value.trim().length >= 2) found.value = await platformGet<Found[]>(`/admin/products?q=${encodeURIComponent(addQuery.value.trim())}&limit=12`)
    processes.value = await platformGet<ProcItem[]>('/admin/processes')
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось изменить состав процесса') }
  }
}
const pct = (value: number) => `${Math.round(value * 100)}%`
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Модель подбора" title="Список продуктов" lead="Выберите процесс: видно, сколько роботов к нему относится, насколько они заполнены и каких данных не хватает для расчёта подбора, количества и экономики." />
    <UiCallout v-if="notice" :tone="notice.ok ? 'ok' : 'danger'">{{ notice.text }}</UiCallout>

    <section class="glass glass-xl a-panel">
      <div class="a-row">
        <label class="a-fld"><span class="caption">Процесс</span>
          <select :value="selected" class="select" @change="choose(($event.target as HTMLSelectElement).value)">
            <optgroup v-for="[group, items] in grouped" :key="group" :label="group">
              <option v-for="item in items" :key="item.code" :value="item.code">{{ item.name }} · {{ item.product_count }}</option>
            </optgroup>
          </select>
        </label>
        <UiButton v-if="selected" variant="secondary" :to="`/admin/processes?code=${selected}`">Настроить процесс</UiButton>
      </div>
    </section>

    <template v-if="data">
      <div class="stats">
        <div class="glass st"><span class="st-in"><span class="display-4">{{ data.total }}</span><span class="caption">{{ pluralRu(data.total, 'робот', 'робота', 'роботов') }} в процессе</span></span></div>
        <div class="glass st"><span class="st-in"><span class="display-4">{{ data.ready }}</span><span class="caption">с полными данными для расчёта</span></span></div>
        <div class="glass st"><span class="st-in"><span class="display-4">{{ averageReady }}%</span><span class="caption">средняя готовность к расчёту</span></span></div>
      </div>

      <section class="glass glass-xl a-panel">
        <div>
          <div class="h4">Что нужно для расчёта</div>
          <p class="caption">Список собран из настройки процесса: условия подбора, формула количества, выбор лучшего и поля экономики. Нажмите, чтобы оставить только роботов без этой характеристики.</p>
        </div>
        <div class="keys">
          <button v-for="item in data.keys" :key="item.key" type="button" class="key" :class="{ on: onlyKey === item.key, bad: item.missing }" @click="onlyKey = onlyKey === item.key ? '' : item.key">
            <span class="body-sm strong">{{ item.label }}</span>
            <span class="caption">{{ usedLabel[item.used_in] ?? item.used_in }}</span>
            <span class="mono-sm">{{ item.missing ? `нет у ${item.missing}` : 'есть у всех' }}</span>
          </button>
        </div>
        <p v-if="worst.length" class="caption">Чаще всего не хватает: {{ worst.slice(0, 3).map((item) => `${item.label} (${item.missing})`).join(', ') }}.</p>
      </section>

      <section class="glass glass-xl a-panel">
        <div class="a-head">
          <div class="h4">Роботы процесса{{ onlyKey ? ` без «${keyLabel(onlyKey)}»` : '' }} · {{ shown.length }}</div>
          <label class="search"><PhMagnifyingGlass :size="16" /><input v-model="query" class="input" placeholder="Название или производитель"></label>
        </div>
        <div class="a-tbl">
          <table class="table">
            <thead><tr><th>Робот</th><th>Тип решения</th><th>Готов к расчёту</th><th class="num">Поля ТЗ</th><th>Не хватает</th><th /></tr></thead>
            <tbody>
              <tr v-for="robot in shown" :key="robot.slug">
                <td>
                  <NuxtLink :to="`/admin/products/${robot.slug}`" class="strong">{{ robot.name }}</NuxtLink>
                  <span class="caption block">{{ robot.manufacturer || 'производитель не указан' }}</span>
                </td>
                <td class="body-sm"><span v-if="robot.solution_type">{{ robot.solution_type }}</span><span v-else class="a-pill warn">без типа</span></td>
                <td>
                  <span class="bar"><i :style="{ width: pct(robot.ready) }" :class="{ full: robot.ready >= 1 }" /></span>
                  <span class="mono-sm">{{ pct(robot.ready) }}</span>
                </td>
                <td class="num mono-sm">{{ pct(robot.completeness) }}</td>
                <td>
                  <div class="a-chips">
                    <span v-for="key in robot.missing" :key="key" class="a-pill warn">{{ keyLabel(key) }}</span>
                    <span v-if="!robot.missing.length" class="a-pill ok">всё есть</span>
                  </div>
                </td>
                <td class="num">
                  <span class="acts">
                    <NuxtLink :to="`/admin/products/${robot.slug}`" class="a-x" title="Заполнить в карточке"><PhArrowSquareOut :size="16" /></NuxtLink>
                    <button type="button" class="a-x" :aria-label="`Убрать ${robot.name} из процесса`" @click="change([], [robot.slug])"><PhTrash :size="16" /></button>
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
          <p v-if="!shown.length" class="body-sm muted">{{ data.total ? 'Под фильтр никто не подошёл.' : 'У процесса нет роботов: добавьте их ниже.' }}</p>
        </div>
      </section>

      <section class="glass glass-xl a-panel">
        <div class="h4">Добавить робота в процесс</div>
        <label class="search"><PhMagnifyingGlass :size="16" /><input v-model="addQuery" class="input" placeholder="Начните вводить название или производителя"></label>
        <div v-for="item in found" :key="item.slug" class="found">
          <div>
            <NuxtLink :to="`/admin/products/${item.slug}`" class="body-sm strong">{{ item.name }}</NuxtLink>
            <span class="caption block">{{ item.manufacturer || '—' }} · {{ item.solution_type?.name || 'без типа' }} · {{ item.processes.length }} {{ pluralRu(item.processes.length, 'процесс', 'процесса', 'процессов') }}</span>
          </div>
          <span v-if="inProcess(item)" class="a-pill ok">уже в процессе</span>
          <UiButton v-else size="sm" variant="secondary" @click="change([item.slug], [])"><template #icon><PhPlus :size="14" weight="bold" /></template>Добавить</UiButton>
        </div>
      </section>
    </template>
    <p v-else-if="loading" class="body-sm muted">Загружаем…</p>
  </div>
</template>

<style scoped>
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4); }
.st { border-radius: var(--radius-lg); }
.st-in { position: relative; z-index: 1; display: grid; gap: 4px; padding: var(--space-4) var(--space-5); }
.keys { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 8px; }
.key { display: grid; gap: 2px; text-align: left; padding: 10px 12px; border-radius: 12px; background: var(--surface-brand-tint); }
.key.bad { background: var(--state-warn-tint); }
.key.on { box-shadow: inset 0 0 0 2px var(--ink-strong); }
.search { display: flex; gap: 8px; align-items: center; color: var(--ink-muted); min-width: 280px; }
.block { display: block; }
.bar { display: inline-block; width: 80px; height: 6px; border-radius: 3px; background: rgba(15, 20, 19, 0.08); vertical-align: middle; margin-right: 8px; overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--state-warn); }
.bar i.full { background: var(--brand-500); }
.acts { display: inline-flex; gap: 4px; }
.found { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 12px; align-items: center; padding: 8px 0; border-top: 1px solid var(--border-hairline); }
@media (max-width: 1100px) { .stats { grid-template-columns: 1fr; } }
</style>
