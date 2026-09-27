<script setup lang="ts">
import { PhMagnifyingGlass } from '@phosphor-icons/vue'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { fetchErrorMessage } from '~/utils/errors'
import { attrGroupLabel, attrGroupOrder } from '~/data/adminLabels'

definePageMeta({ layout: 'admin', middleware: 'admin', pageTransition: false })
useHead({ title: 'Админка · Характеристики' })

interface Item { key: string; label: string; unit: string | null; usage: string; group: string; datatype: string; sort: number; products: number }

const items = ref<Item[]>([])
const q = ref('')
const group = ref('all')
const usage = ref('')
const notice = ref<{ ok: boolean; text: string } | null>(null)
const usageLabel: Record<string, string> = { active: 'В условиях', unused: 'Не используется', pending: 'Новая' }
const usageTone: Record<string, 'ok' | 'neutral' | 'warn'> = { active: 'ok', unused: 'neutral', pending: 'warn' }
const datatypes: Record<string, string> = { number: 'Число', text: 'Текст', bool: 'Да / нет', enum: 'Список' }

const load = async () => {
  try {
    items.value = await platformGet<Item[]>('/admin/attribute-dictionary')
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось загрузить справочник') }
  }
}
onMounted(load)

const shown = computed(() => {
  const text = q.value.trim().toLowerCase()
  return items.value.filter((item) =>
    (group.value === 'all' || item.group === group.value)
    && (!usage.value || item.usage === usage.value)
    && (!text || `${item.label} ${item.key}`.toLowerCase().includes(text)))
})
const counts = computed(() => {
  const out: Record<string, number> = {}
  for (const item of items.value) out[item.group] = (out[item.group] ?? 0) + 1
  return out
})

const saveItem = async (item: Item) => {
  try {
    await platformSend(`/admin/attribute-dictionary/${encodeURIComponent(item.key)}`, 'PATCH', { label: item.label, unit: item.unit ?? '', group: item.group, datatype: item.datatype })
    notice.value = { ok: true, text: `«${item.label}» сохранена` }
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось сохранить') }
  }
}
const toggleUnused = async (item: Item) => {
  try {
    await platformSend(`/admin/attributes/${encodeURIComponent(item.key)}/usage`, 'POST', { unused: item.usage !== 'unused' })
    await load()
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось изменить состояние') }
  }
}
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Продукты" title="Справочник характеристик" lead="Подписи, единицы и группы ТЗ для всех характеристик роботов. По группе характеристика попадает в раздел карточки, по типу — в форму правки. «В условиях» значит, что её уже читает условие подбора." />
    <UiCallout v-if="notice" :tone="notice.ok ? 'ok' : 'danger'">{{ notice.text }}</UiCallout>

    <section class="glass a-panel filters">
      <label class="search"><PhMagnifyingGlass :size="16" weight="bold" /><input v-model="q" class="s-in" placeholder="Подпись или ключ"></label>
      <select v-model="group" class="select" aria-label="Группа">
        <option value="all">все группы · {{ items.length }}</option>
        <option v-for="code in attrGroupOrder" :key="code" :value="code">{{ attrGroupLabel[code] }} · {{ counts[code] ?? 0 }}</option>
      </select>
      <select v-model="usage" class="select" aria-label="Состояние">
        <option value="">любое состояние</option>
        <option v-for="(label, key) in usageLabel" :key="key" :value="key">{{ label }}</option>
      </select>
    </section>

    <section class="glass glass-xl a-panel">
      <p class="caption">Изменения сохраняются, когда поле теряет фокус. У «Прочих» характеристик нет группы ТЗ: чаще всего это поля с сайтов, которые пришли от парсеров.</p>
      <div class="a-tbl">
        <table class="table">
          <thead><tr><th>Подпись</th><th>Единица</th><th>Группа ТЗ</th><th>Тип</th><th class="num">У продуктов</th><th>Состояние</th><th /></tr></thead>
          <tbody>
            <tr v-for="item in shown" :key="item.key">
              <td><input v-model="item.label" class="input" @change="saveItem(item)"><span class="caption mono-sm block">{{ item.key }}</span></td>
              <td><input :value="item.unit ?? ''" class="input unit" @change="item.unit = ($event.target as HTMLInputElement).value; saveItem(item)"></td>
              <td>
                <select v-model="item.group" class="select" @change="saveItem(item)">
                  <option v-for="code in attrGroupOrder" :key="code" :value="code">{{ attrGroupLabel[code] }}</option>
                </select>
              </td>
              <td>
                <select v-model="item.datatype" class="select" @change="saveItem(item)">
                  <option v-for="(label, key) in datatypes" :key="key" :value="key">{{ label }}</option>
                </select>
              </td>
              <td class="num mono-sm">{{ item.products }}</td>
              <td><UiBadge :tone="usageTone[item.usage] || 'neutral'" size="sm">{{ usageLabel[item.usage] || item.usage }}</UiBadge></td>
              <td class="num"><UiButton size="sm" variant="secondary" :disabled="item.usage === 'active'" @click="toggleUnused(item)">{{ item.usage === 'unused' ? 'Вернуть' : 'Не использовать' }}</UiButton></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.filters { display: grid; grid-template-columns: minmax(240px, 1.5fr) 1fr 1fr; gap: 10px; padding: 10px; }
.search { display: flex; align-items: center; gap: 10px; padding: 0 14px; border-radius: var(--radius-sm); background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); color: var(--ink-muted); }
.s-in { flex: 1; background: none; border: 0; outline: none; min-height: 42px; font-weight: 600; color: var(--ink-strong); }
.block { display: block; }
.unit { width: 110px; }
</style>
