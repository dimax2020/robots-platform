<script setup lang="ts">
import { PhPlus, PhTrash } from '@phosphor-icons/vue'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { fetchErrorMessage } from '~/utils/errors'
import { pluralRu } from '~/data/adminLabels'

definePageMeta({ layout: 'admin', middleware: 'admin', pageTransition: false })
useHead({ title: 'Админка · Нормативы по типам решений' })

interface Norm { key: string; label: string; unit: string; group: string; standard: number; min: number; max: number; step: number }
interface Override { type_code: string; type_name: string; type_group: string; products: number; key: string; label: string; unit: string; value: number; standard: number; rationale: string; origin: string; updated_at: string | null }
interface TypeItem { code: string; name: string; group: string; products: number }
interface Draft { type_code: string; key: string; value: number | null; rationale: string; origin: string }

const norms = ref<Norm[]>([])
const overrides = ref<Override[]>([])
const types = ref<TypeItem[]>([])
const draft = ref<Draft | null>(null)
const notice = ref<{ ok: boolean; text: string } | null>(null)
const busy = ref(false)

const apply = (data: { norms: Norm[]; overrides: Override[] }) => {
  norms.value = data.norms
  overrides.value = data.overrides
}
const load = async () => {
  try {
    const [data, typeList] = await Promise.all([
      platformGet<{ norms: Norm[]; overrides: Override[] }>('/admin/economy/type-norms'),
      platformGet<TypeItem[]>('/admin/solution-types'),
    ])
    apply(data)
    types.value = typeList.filter((item) => item.products > 0)
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось загрузить нормативы по типам') }
  }
}
onMounted(load)

const byType = computed(() => {
  const map = new Map<string, Override[]>()
  for (const item of overrides.value) map.set(item.type_code, [...(map.get(item.type_code) ?? []), item])
  return [...map.entries()].map(([code, rows]) => ({ code, name: rows[0]!.type_name, group: rows[0]!.type_group, products: rows[0]!.products, rows }))
})
const normOf = (key: string) => norms.value.find((item) => item.key === key)
const num = (value: number) => value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })
const typeGroups = computed(() => {
  const map = new Map<string, TypeItem[]>()
  for (const item of types.value) map.set(item.group || 'Без группы', [...(map.get(item.group || 'Без группы') ?? []), item])
  return [...map.entries()]
})

const create = (typeCode = '') => { draft.value = { type_code: typeCode, key: norms.value[0]?.key ?? '', value: null, rationale: '', origin: '' } }
const edit = (item: Override) => { draft.value = { type_code: item.type_code, key: item.key, value: item.value, rationale: item.rationale, origin: item.origin } }

const save = async () => {
  if (!draft.value || draft.value.value === null || busy.value) return
  busy.value = true
  try {
    apply(await platformSend<{ norms: Norm[]; overrides: Override[] }>('/admin/economy/type-norms', 'PUT', draft.value))
    notice.value = { ok: true, text: 'Норматив типа сохранён. Проекты с роботами этого типа пересчитаются при следующем открытии экономики.' }
    draft.value = null
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось сохранить') }
  } finally {
    busy.value = false
  }
}
const remove = async (item: Override) => {
  try {
    apply(await platformSend<{ norms: Norm[]; overrides: Override[] }>(`/admin/economy/type-norms?type_code=${item.type_code}&key=${item.key}`, 'DELETE'))
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось удалить') }
  }
}
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Экономика" title="Нормативы по типам решений" lead="Там, где типы роботов реально различаются: у AMR и манипулятора разная стоимость сервиса и лицензий. Порядок в расчёте: своё значение проекта → норматив типа → стандарт.">
      <UiButton @click="create()"><template #icon><PhPlus :size="16" weight="bold" /></template>Переопределить норматив</UiButton>
    </AdminHead>
    <UiCallout v-if="notice" :tone="notice.ok ? 'ok' : 'danger'">{{ notice.text }}</UiCallout>
    <UiCallout tone="info" title="Какие нормативы можно переопределять">
      Только доли от стоимости оборудования: статьи CAPEX, сервис, лицензии, связь, расходники, ремонт и ставка аренды. Для них норматив, взвешенный по стоимости парка, даёт ту же сумму, что расчёт по каждому роботу отдельно. В отчёте экономики у такого норматива видно, какие типы его поправили.
    </UiCallout>

    <section v-if="draft" class="glass glass-xl a-panel">
      <div class="h3">Норматив для типа решения</div>
      <div class="a-row">
        <label class="a-fld"><span class="caption">Тип решения</span>
          <select v-model="draft.type_code" class="select">
            <option value="">выберите тип</option>
            <optgroup v-for="[group, list] in typeGroups" :key="group" :label="group">
              <option v-for="item in list" :key="item.code" :value="item.code">{{ item.name }} · {{ item.products }}</option>
            </optgroup>
          </select>
        </label>
        <label class="a-fld"><span class="caption">Норматив</span>
          <select v-model="draft.key" class="select">
            <option v-for="item in norms" :key="item.key" :value="item.key">{{ item.label }} · стандарт {{ num(item.standard) }} {{ item.unit }}</option>
          </select>
        </label>
        <label class="a-fld narrow"><span class="caption">Значение, {{ normOf(draft.key)?.unit }}</span>
          <input v-model.number="draft.value" class="input input-mono" type="number" :step="normOf(draft.key)?.step" :min="normOf(draft.key)?.min" :max="normOf(draft.key)?.max">
        </label>
      </div>
      <div class="a-row">
        <label class="a-fld"><span class="caption">Обоснование</span><input v-model="draft.rationale" class="input" placeholder="Почему у этого типа своё значение"></label>
        <label class="a-fld"><span class="caption">Источник</span><input v-model="draft.origin" class="input" placeholder="Договор, прайс вендора, кейс внедрения"></label>
      </div>
      <div class="a-row">
        <UiButton :disabled="busy || !draft.type_code || draft.value === null || !draft.rationale.trim()" @click="save">Сохранить</UiButton>
        <UiButton variant="secondary" @click="draft = null">Отмена</UiButton>
      </div>
    </section>

    <p v-if="!byType.length && !draft" class="body-sm muted">Переопределений пока нет: все типы считаются по стандарту со страницы «Нормативы».</p>

    <section v-for="block in byType" :key="block.code" class="glass glass-xl a-panel">
      <div class="a-head">
        <div>
          <div class="h4">{{ block.name }}</div>
          <span class="caption">{{ block.group || 'Без группы' }} · {{ block.products }} {{ pluralRu(block.products, 'продукт', 'продукта', 'продуктов') }}</span>
        </div>
        <UiButton size="sm" variant="secondary" @click="create(block.code)"><template #icon><PhPlus :size="14" weight="bold" /></template>Ещё норматив</UiButton>
      </div>
      <table class="table">
        <thead><tr><th>Норматив</th><th class="num">Стандарт</th><th class="num">У типа</th><th>Обоснование</th><th /></tr></thead>
        <tbody>
          <tr v-for="item in block.rows" :key="item.key">
            <td><button type="button" class="strong nm" @click="edit(item)">{{ item.label }}</button><span class="caption block">{{ item.unit }}</span></td>
            <td class="num mono-sm">{{ num(item.standard) }}</td>
            <td class="num mono-sm strong">{{ num(item.value) }}</td>
            <td class="body-sm">{{ item.rationale }}<span v-if="item.origin" class="caption block">Источник: {{ item.origin }}</span></td>
            <td class="num"><button type="button" class="a-x" aria-label="Убрать переопределение" @click="remove(item)"><PhTrash :size="16" /></button></td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.nm { text-align: left; }
.nm:hover { color: var(--link); }
.block { display: block; }
</style>
