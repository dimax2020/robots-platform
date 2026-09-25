<script setup lang="ts">
import { PhMagnifyingGlass } from '@phosphor-icons/vue'
import { platformGet, type PlatformCard, type PlatformPage } from '~/composables/usePlatform'

definePageMeta({ layout: 'admin' })
useHead({ title: 'Админка · Продукты' })

const q = ref('')
const items = ref<PlatformCard[]>([])
const total = ref(0)
const pending = ref(true)
const error = ref('')

const list = computed(() => {
  const query = q.value.trim().toLowerCase()
  if (!query) return items.value
  return items.value.filter((item) => `${item.name} ${item.manufacturer ?? ''}`.toLowerCase().includes(query))
})

const load = async () => {
  pending.value = true
  error.value = ''
  const all: PlatformCard[] = []
  let cursor: string | null = null
  try {
    do {
      const query = new URLSearchParams({ limit: '100' })
      if (cursor) query.set('cursor', cursor)
      const page: PlatformPage = await platformGet<PlatformPage>(`/catalog/products?${query}`)
      all.push(...page.items)
      total.value = page.total ?? all.length
      cursor = page.next_cursor
    } while (cursor)
    items.value = all
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Новый каталог не ответил'
  } finally {
    pending.value = false
  }
}

onMounted(() => { void load() })
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Продукты" title="Список продуктов" lead="Это новая база: каталог ФЦ БАС и карточки, которые добавили парсеры. Прежний список на 241 карточку остаётся в старом API и сюда не входит." />

    <div class="filters glass">
      <label class="f search"><PhMagnifyingGlass :size="16" weight="bold" /><input v-model="q" class="s-in" placeholder="Название или производитель"></label>
    </div>

    <p v-if="error" class="caption">{{ error }}</p>
    <div class="count caption">
      {{ pending ? 'Загрузка…' : `Показано ${list.length} из ${total}` }}
    </div>

    <div class="tbl glass glass-xl">
      <table class="table">
        <thead><tr><th>Продукт</th><th>Производитель</th><th>Статус</th><th>УГТ</th><th class="num">Цена</th></tr></thead>
        <tbody>
          <tr v-for="p in list" :key="p.id">
            <td><NuxtLink :to="`/catalog/card/${p.slug}`" class="strong">{{ p.name }}</NuxtLink></td>
            <td class="body-sm">{{ p.manufacturer || 'не указан' }}</td>
            <td class="caption">{{ p.availability || 'не указан' }}</td>
            <td class="mono-sm">{{ p.trl ?? 'нет' }}</td>
            <td class="num mono-sm">{{ p.price_rub ? `${p.price_rub.toLocaleString('ru-RU')} ₽` : 'нет' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.filters { display: grid; grid-template-columns: minmax(240px, 1fr); gap: 10px; padding: 10px; }
.filters > * { position: relative; z-index: 1; }
.search { display: flex; align-items: center; gap: 10px; padding: 0 14px; border-radius: var(--radius-sm); background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); color: var(--ink-muted); }
.s-in { flex: 1; background: none; border: 0; outline: none; min-height: 42px; font-weight: 600; color: var(--ink-strong); }
.count { padding: 0 10px; }
.tbl { padding: var(--space-3); }
.tbl table { position: relative; z-index: 1; }
</style>
