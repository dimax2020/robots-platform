<script setup lang="ts">
import { PhMagnifyingGlass, PhPlus } from '@phosphor-icons/vue'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { fetchErrorMessage } from '~/utils/errors'
import { platformSourceKinds, pluralRu } from '~/data/adminLabels'
import { photoFor } from '~/data/placeholders'
import { replaceQuery } from '~/composables/useQuerySync'

definePageMeta({ layout: 'admin', middleware: 'admin', pageTransition: false })
useHead({ title: 'Админка · Продукты' })

interface Row {
  id: string
  slug: string
  name: string
  manufacturer: string | null
  availability: string | null
  trl: number | null
  price_rub: number | null
  image_url: string | null
  solution_type: { code: string; name: string } | null
  processes: { code: string; name: string }[]
  completeness: number
}

const route = useRoute()
const router = useRouter()
const items = ref<Row[]>([])
const types = ref<{ code: string; name: string; group: string }[]>([])
const processes = ref<{ code: string; name: string }[]>([])
const pending = ref(true)
const notice = ref<{ ok: boolean; text: string } | null>(null)
const q = ref(typeof route.query.q === 'string' ? route.query.q : '')
const type = ref(typeof route.query.type === 'string' ? route.query.type : '')
const process = ref(typeof route.query.process === 'string' ? route.query.process : '')
const fill = ref('')
const sort = ref<'name' | 'fill' | 'price'>('name')
const creating = ref<{ name: string; manufacturer: string; solution_type: string; kind: string; publisher: string; url: string } | null>(null)

const load = async () => {
  pending.value = true
  try {
    const params = new URLSearchParams()
    if (type.value) params.set('type', type.value)
    if (process.value) params.set('process', process.value)
    items.value = await platformGet<Row[]>(`/admin/products?${params}`)
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось загрузить продукты') }
  } finally {
    pending.value = false
  }
}
onMounted(async () => {
  const [typeList, processList] = await Promise.all([
    platformGet<{ code: string; name: string; group: string }[]>('/admin/solution-types'),
    platformGet<{ code: string; name: string }[]>('/admin/processes'),
  ])
  types.value = typeList
  processes.value = processList
  await load()
})
watch([type, process], () => {
  replaceQuery({ type: type.value || undefined, process: process.value || undefined })
  void load()
})

const list = computed(() => {
  const text = q.value.trim().toLowerCase()
  let rows = items.value.filter((item) => !text || `${item.name} ${item.manufacturer ?? ''}`.toLowerCase().includes(text))
  if (fill.value === 'low') rows = rows.filter((item) => item.completeness < 0.3)
  if (fill.value === 'mid') rows = rows.filter((item) => item.completeness >= 0.3 && item.completeness < 0.7)
  if (fill.value === 'high') rows = rows.filter((item) => item.completeness >= 0.7)
  if (sort.value === 'fill') rows = [...rows].sort((a, b) => a.completeness - b.completeness)
  if (sort.value === 'price') rows = [...rows].sort((a, b) => (a.price_rub ?? 1e15) - (b.price_rub ?? 1e15))
  return rows
})
const typeGroups = computed(() => {
  const map = new Map<string, { code: string; name: string }[]>()
  for (const item of types.value) map.set(item.group || 'Без группы', [...(map.get(item.group || 'Без группы') ?? []), item])
  return [...map.entries()]
})
const pct = (value: number) => `${Math.round(value * 100)}%`
const rub = (value: number | null) => (value == null ? 'нет' : `${value.toLocaleString('ru-RU')} ₽`)

const create = async () => {
  if (!creating.value?.name.trim()) return
  try {
    const card = await platformSend<{ slug: string }>('/admin/products', 'POST', {
      name: creating.value.name,
      manufacturer: creating.value.manufacturer || null,
      solution_type: creating.value.solution_type || null,
      source: { kind: creating.value.kind, publisher: creating.value.publisher || creating.value.manufacturer, url: creating.value.url },
    })
    await router.push(`/admin/products/${card.slug}`)
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось создать продукт') }
  }
}
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Продукты" title="Карточки продуктов" lead="Каталог ФЦ БАС, ручная таблица и парсеры сайтов в одной базе. Ручная правка в карточке получает свой источник, и следующий импорт её не затирает (ТЗ 3.3.5).">
      <UiButton @click="creating = { name: '', manufacturer: '', solution_type: '', kind: 'vendor', publisher: '', url: '' }"><template #icon><PhPlus :size="16" weight="bold" /></template>Новый продукт</UiButton>
    </AdminHead>
    <UiCallout v-if="notice" :tone="notice.ok ? 'ok' : 'danger'">{{ notice.text }}</UiCallout>

    <section v-if="creating" class="glass glass-xl a-panel">
      <div class="h3">Новый продукт</div>
      <div class="a-row">
        <label class="a-fld"><span class="caption">Название</span><input v-model="creating.name" class="input" placeholder="Модель робота"></label>
        <label class="a-fld"><span class="caption">Производитель</span><input v-model="creating.manufacturer" class="input"></label>
        <label class="a-fld"><span class="caption">Тип решения</span>
          <select v-model="creating.solution_type" class="select">
            <option value="">не задан</option>
            <optgroup v-for="[group, rows] in typeGroups" :key="group" :label="group">
              <option v-for="item in rows" :key="item.code" :value="item.code">{{ item.name }}</option>
            </optgroup>
          </select>
        </label>
      </div>
      <div class="a-row">
        <label class="a-fld narrow"><span class="caption">Откуда данные</span>
          <select v-model="creating.kind" class="select">
            <option v-for="kind in platformSourceKinds.filter((k) => k.manual)" :key="kind.code" :value="kind.code">{{ kind.label }} · {{ kind.confidence }}</option>
          </select>
        </label>
        <label class="a-fld"><span class="caption">Кто опубликовал</span><input v-model="creating.publisher" class="input" :placeholder="creating.manufacturer || 'Производитель'"></label>
        <label class="a-fld"><span class="caption">Ссылка</span><input v-model="creating.url" class="input" placeholder="https://"></label>
      </div>
      <p class="caption">Характеристики, фото и процессы заполняются в карточке после создания. Новый продукт появится в каталоге и подборе, когда у него будет процесс.</p>
      <div class="a-row">
        <UiButton :disabled="!creating.name.trim()" @click="create">Создать и открыть карточку</UiButton>
        <UiButton variant="secondary" @click="creating = null">Отмена</UiButton>
      </div>
    </section>

    <section class="glass a-panel filters">
      <label class="search"><PhMagnifyingGlass :size="16" weight="bold" /><input v-model="q" class="s-in" placeholder="Название или производитель"></label>
      <select v-model="type" class="select" aria-label="Тип решения">
        <option value="">все типы</option>
        <option value="-">без типа</option>
        <optgroup v-for="[group, rows] in typeGroups" :key="group" :label="group">
          <option v-for="item in rows" :key="item.code" :value="item.code">{{ item.name }}</option>
        </optgroup>
      </select>
      <select v-model="process" class="select" aria-label="Процесс">
        <option value="">все процессы</option>
        <option value="-">без процесса</option>
        <option v-for="item in processes" :key="item.code" :value="item.code">{{ item.name }}</option>
      </select>
      <select v-model="fill" class="select" aria-label="Заполненность">
        <option value="">любая заполненность</option>
        <option value="low">меньше 30%</option>
        <option value="mid">30–70%</option>
        <option value="high">от 70%</option>
      </select>
      <select v-model="sort" class="select" aria-label="Сортировка">
        <option value="name">по названию</option>
        <option value="fill">сначала пустые</option>
        <option value="price">по цене</option>
      </select>
    </section>
    <div class="caption">{{ pending ? 'Загрузка…' : `Показано ${list.length} ${pluralRu(list.length, 'продукт', 'продукта', 'продуктов')}` }}</div>

    <section class="glass glass-xl a-panel">
      <div class="a-tbl">
        <table class="table">
          <thead><tr><th /><th>Продукт</th><th>Тип решения</th><th class="num">Процессов</th><th>Статус</th><th class="num">УГТ</th><th class="num">Цена</th><th>Поля ТЗ</th></tr></thead>
          <tbody>
            <tr v-for="p in list" :key="p.id">
              <td><img :src="photoFor(p.image_url, p.name)" :alt="p.name" class="thumb" loading="lazy"></td>
              <td><NuxtLink :to="`/admin/products/${p.slug}`" class="strong">{{ p.name }}</NuxtLink><span class="caption block">{{ p.manufacturer || 'производитель не указан' }}</span></td>
              <td class="body-sm"><span v-if="p.solution_type">{{ p.solution_type.name }}</span><span v-else class="a-pill warn">без типа</span></td>
              <td class="num mono-sm"><span :class="{ 'a-pill warn': !p.processes.length }">{{ p.processes.length }}</span></td>
              <td class="caption">{{ p.availability || 'не указан' }}</td>
              <td class="num mono-sm">{{ p.trl ?? '—' }}</td>
              <td class="num mono-sm">{{ rub(p.price_rub) }}</td>
              <td><span class="bar"><i :style="{ width: pct(p.completeness) }" /></span><span class="mono-sm">{{ pct(p.completeness) }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.filters { grid-template-columns: minmax(240px, 1.4fr) repeat(4, minmax(150px, 1fr)); display: grid; gap: 10px; padding: 10px; }
.search { display: flex; align-items: center; gap: 10px; padding: 0 14px; border-radius: var(--radius-sm); background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); color: var(--ink-muted); }
.s-in { flex: 1; background: none; border: 0; outline: none; min-height: 42px; font-weight: 600; color: var(--ink-strong); }
.thumb { width: 44px; height: 44px; border-radius: 10px; object-fit: cover; background: #fff; }
.block { display: block; }
.bar { display: inline-block; width: 64px; height: 6px; border-radius: 3px; background: rgba(15, 20, 19, 0.08); vertical-align: middle; margin-right: 8px; overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--brand-500); }
@media (max-width: 1100px) { .filters { grid-template-columns: 1fr 1fr; } }
</style>
