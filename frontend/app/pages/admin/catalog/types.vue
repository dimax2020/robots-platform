<script setup lang="ts">
import { PhPlus, PhTrash, PhCaretDown, PhCaretRight } from '@phosphor-icons/vue'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { fetchErrorMessage } from '~/utils/errors'
import { familyLabel, pluralRu } from '~/data/adminLabels'
import { replaceQuery } from '~/composables/useQuerySync'

definePageMeta({ layout: 'admin', middleware: 'admin', pageTransition: false })
useHead({ title: 'Админка · Типы решений' })

interface SolutionType { code: string; name: string; group: string; family: string; products: number }
interface Draft { code: string | null; name: string; group: string; family: string }
interface UntypedGroup { raw_key: string; label: string; count: number; products: { slug: string; name: string; manufacturer: string | null }[] }
interface Rule { raw_key: string; label: string; type_code: string; type_name: string }

const route = useRoute()
const tab = ref(route.query.tab === 'untyped' ? 'untyped' : route.query.tab === 'rules' ? 'rules' : 'types')
watch(tab, (value) => { replaceQuery({ tab: value }) })

const types = ref<SolutionType[]>([])
const untyped = ref<UntypedGroup[]>([])
const rules = ref<Rule[]>([])
const draft = ref<Draft | null>(null)
const query = ref('')
const notice = ref<{ ok: boolean; text: string } | null>(null)
const picks = reactive<Record<string, string>>({})
const remember = reactive<Record<string, boolean>>({})
const open = reactive(new Set<string>())
const busy = ref(false)

const untypedTotal = computed(() => untyped.value.reduce((sum, item) => sum + item.count, 0))
const tabs = computed(() => [
  { id: 'types', label: 'Типы', count: types.value.length },
  { id: 'untyped', label: 'Без типа', count: untypedTotal.value },
  { id: 'rules', label: 'Правила импорта', count: rules.value.length },
])

const grouped = computed(() => {
  const text = query.value.trim().toLowerCase()
  const shown = types.value.filter((item) => !text || `${item.name} ${item.code} ${item.group}`.toLowerCase().includes(text))
  const map = new Map<string, SolutionType[]>()
  for (const item of shown) {
    const key = item.group || 'Без группы'
    map.set(key, [...(map.get(key) ?? []), item])
  }
  return [...map.entries()].map(([group, items]) => ({ group, items }))
})
const groupNames = computed(() => [...new Set(types.value.map((item) => item.group).filter(Boolean))].sort())

const load = async () => {
  const [a, b, c] = await Promise.all([
    platformGet<SolutionType[]>('/admin/solution-types'),
    platformGet<UntypedGroup[]>('/admin/solution-types/untyped'),
    platformGet<Rule[]>('/admin/solution-types/rules'),
  ])
  types.value = a
  untyped.value = b
  rules.value = c
  for (const group of b) {
    if (remember[group.raw_key] === undefined) remember[group.raw_key] = true
    if (picks[group.raw_key] === undefined) picks[group.raw_key] = ''
  }
}
onMounted(() => { void load().catch((err) => { notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось загрузить типы') } }) })

const create = () => { draft.value = { code: null, name: '', group: '', family: 'flow_cycle' } }
const edit = (item: SolutionType) => { draft.value = { code: item.code, name: item.name, group: item.group, family: item.family } }

const save = async () => {
  if (!draft.value || busy.value) return
  busy.value = true
  try {
    await platformSend('/admin/solution-types', 'POST', draft.value)
    notice.value = { ok: true, text: `Тип «${draft.value.name}» сохранён` }
    draft.value = null
    await load()
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось сохранить') }
  } finally {
    busy.value = false
  }
}

const remove = async (item: SolutionType) => {
  const tail = item.products ? ` ${item.products} ${pluralRu(item.products, 'продукт останется', 'продукта останутся', 'продуктов останутся')} без типа.` : ''
  if (!confirm(`Удалить тип «${item.name}»?${tail}`)) return
  try {
    await platformSend(`/admin/solution-types/${item.code}`, 'DELETE')
    await load()
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось удалить') }
  }
}

const assignGroup = async (group: UntypedGroup) => {
  const code = picks[group.raw_key]
  if (!code || busy.value) return
  busy.value = true
  try {
    const result = await platformSend<{ changed: number }>('/admin/solution-types/assign', 'POST', {
      solution_type: code, raw_key: group.raw_key, remember: Boolean(remember[group.raw_key]),
    })
    notice.value = { ok: true, text: `Тип назначен: ${result.changed} ${pluralRu(result.changed, 'продукт', 'продукта', 'продуктов')}` }
    await load()
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось назначить тип') }
  } finally {
    busy.value = false
  }
}

const assignOne = async (slug: string, code: string) => {
  if (!code) return
  try {
    await platformSend('/admin/solution-types/assign', 'POST', { solution_type: code, slugs: [slug] })
    await load()
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось назначить тип') }
  }
}

const dropRule = async (rule: Rule) => {
  try {
    await platformSend(`/admin/solution-types/rules?raw_key=${encodeURIComponent(rule.raw_key)}`, 'DELETE')
    await load()
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось удалить правило') }
  }
}
const toggle = (key: string) => { if (open.has(key)) open.delete(key); else open.add(key) }
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Каталог" title="Типы решений" lead="Уровень дерева между процессом и продуктом (ТЗ 3.3.1). Типы взяты из пар «Тип / Подтип» каталога организатора. Семейство подсказывает, по какой логике считать количество.">
      <UiButton @click="create"><template #icon><PhPlus :size="16" weight="bold" /></template>Новый тип</UiButton>
    </AdminHead>
    <UiCallout v-if="notice" :tone="notice.ok ? 'ok' : 'danger'">{{ notice.text }}</UiCallout>

    <section v-if="draft" class="glass glass-xl a-panel">
      <div class="h3">{{ draft.code ? 'Изменить тип' : 'Новый тип решения' }}</div>
      <div class="a-row">
        <label class="a-fld"><span class="caption">Название</span><input v-model="draft.name" class="input" placeholder="Например, Робот-официант"></label>
        <label class="a-fld"><span class="caption">Группа</span><input v-model="draft.group" class="input" list="type-groups" placeholder="Мобильные роботы"></label>
        <label class="a-fld narrow"><span class="caption">Семейство расчёта</span>
          <select v-model="draft.family" class="select">
            <option v-for="(label, code) in familyLabel" :key="code" :value="code">{{ label }}</option>
          </select>
        </label>
      </div>
      <datalist id="type-groups"><option v-for="name in groupNames" :key="name" :value="name" /></datalist>
      <div class="a-row">
        <UiButton :disabled="busy || !draft.name.trim()" @click="save">{{ busy ? 'Сохраняем…' : 'Сохранить' }}</UiButton>
        <UiButton variant="secondary" @click="draft = null">Отмена</UiButton>
      </div>
    </section>

    <UiTabs v-model="tab" :tabs="tabs" />

    <template v-if="tab === 'types'">
      <input v-model="query" class="input" placeholder="Поиск по названию, коду или группе">
      <section v-for="block in grouped" :key="block.group" class="glass glass-xl a-panel">
        <div class="h4">{{ block.group }}</div>
        <div class="a-tbl">
          <table class="table">
            <thead><tr><th>Тип</th><th>Семейство</th><th class="num">Продуктов</th><th /></tr></thead>
            <tbody>
              <tr v-for="item in block.items" :key="item.code" :class="{ hl: route.query.code === item.code }">
                <td><button type="button" class="strong nm" @click="edit(item)">{{ item.name }}</button><span class="caption block mono-sm">{{ item.code }}</span></td>
                <td class="body-sm">{{ familyLabel[item.family] || item.family || '—' }}</td>
                <td class="num mono-sm"><NuxtLink v-if="item.products" :to="`/admin/products?type=${item.code}`" class="link">{{ item.products }}</NuxtLink><span v-else>0</span></td>
                <td class="num"><button type="button" class="a-x" :aria-label="`Удалить ${item.name}`" @click="remove(item)"><PhTrash :size="16" /></button></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <template v-else-if="tab === 'untyped'">
      <UiCallout tone="info" title="Как назначать">
        Продукты сгруппированы по категории с сайта или из каталога. Выберите тип и назначьте всей группе. Галка «запомнить» сохраняет правило: следующий импорт или прогон парсера поставит этот тип новым продуктам той же категории сам.
      </UiCallout>
      <p v-if="!untyped.length" class="body-sm muted">Все продукты с типом.</p>
      <section v-for="group in untyped" :key="group.raw_key" class="glass glass-xl a-panel">
        <div class="a-head">
          <button type="button" class="grp-t" @click="toggle(group.raw_key)">
            <component :is="open.has(group.raw_key) ? PhCaretDown : PhCaretRight" :size="14" weight="bold" />
            <span class="h4">{{ group.label }}</span>
            <span class="a-pill warn">{{ group.count }} {{ pluralRu(group.count, 'продукт', 'продукта', 'продуктов') }}</span>
          </button>
        </div>
        <div class="a-row">
          <label class="a-fld"><span class="caption">Тип решения для всей группы</span>
            <select v-model="picks[group.raw_key]" class="select">
              <option value="">выберите тип</option>
              <optgroup v-for="block in grouped" :key="block.group" :label="block.group">
                <option v-for="item in block.items" :key="item.code" :value="item.code">{{ item.name }}</option>
              </optgroup>
            </select>
          </label>
          <label class="rem"><input v-model="remember[group.raw_key]" type="checkbox"> <span class="body-sm">запомнить для следующих импортов</span></label>
          <UiButton :disabled="busy || !picks[group.raw_key]" @click="assignGroup(group)">Назначить всем</UiButton>
        </div>
        <div v-if="open.has(group.raw_key)" class="a-tbl">
          <table class="table">
            <thead><tr><th>Продукт</th><th>Производитель</th><th>Тип только этому продукту</th></tr></thead>
            <tbody>
              <tr v-for="product in group.products" :key="product.slug">
                <td><NuxtLink :to="`/admin/products/${product.slug}`" class="strong">{{ product.name }}</NuxtLink></td>
                <td class="body-sm">{{ product.manufacturer || '—' }}</td>
                <td>
                  <select class="select" @change="assignOne(product.slug, ($event.target as HTMLSelectElement).value)">
                    <option value="">выберите тип</option>
                    <optgroup v-for="block in grouped" :key="block.group" :label="block.group">
                      <option v-for="item in block.items" :key="item.code" :value="item.code">{{ item.name }}</option>
                    </optgroup>
                  </select>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <section v-else class="glass glass-xl a-panel">
      <p class="caption">Правило связывает категорию источника с типом. Удаление правила не меняет уже назначенные типы.</p>
      <p v-if="!rules.length" class="body-sm muted">Правил пока нет. Они появляются, когда тип назначают группе с галкой «запомнить».</p>
      <table v-else class="table">
        <thead><tr><th>Категория источника</th><th>Тип решения</th><th /></tr></thead>
        <tbody>
          <tr v-for="rule in rules" :key="rule.raw_key">
            <td class="body-sm">{{ rule.label || 'пустая категория' }}</td>
            <td class="body-sm strong">{{ rule.type_name }}</td>
            <td class="num"><button type="button" class="a-x" aria-label="Удалить правило" @click="dropRule(rule)"><PhTrash :size="16" /></button></td>
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
.hl td { background: var(--surface-brand-tint); }
.grp-t { display: inline-flex; gap: 10px; align-items: center; text-align: left; }
.rem { display: inline-flex; gap: 8px; align-items: center; min-height: 44px; }
</style>
