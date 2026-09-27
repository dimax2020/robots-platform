<script setup lang="ts">
import { PhX, PhPlus } from '@phosphor-icons/vue'
import { attrGroups, availabilityLabel, availabilityTone, formatRub, type Availability } from '~/data/catalog'
import { formatAttributeValue } from '~/data/attributeValue'
import { photoFor } from '~/data/placeholders'
import { platformGet } from '~/composables/usePlatform'

useHead({ title: 'Сравнение решений' })
const { picks, toggle } = useCompare()

interface CardAttr {
  approximate?: boolean
  condition?: string | null
  unit?: string | null
  key: string
  label: string
  group: string
  status: string
  value: string | number | null
  source: { kind: string; publisher: string; url: string | null } | null
}
interface Card {
  slug: string
  name: string
  manufacturer: string | null
  availability: string | null
  trl: number | null
  price_rub: number | null
  image_url: string | null
  solution_type: { code: string; name: string } | null
  attrs: CardAttr[]
}

const items = ref<Card[]>([])
const loading = ref(false)
const loadError = ref('')

const load = async () => {
  loading.value = true
  loadError.value = ''
  try {
    const cards = await Promise.all(picks.value.map(async (pick) => {
      try {
        return await platformGet<Card>(`/catalog/products/${pick.slug}`)
      } catch {
        return null
      }
    }))
    items.value = cards.filter((card): card is Card => card !== null)
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : 'Не удалось открыть карточки'
  } finally {
    loading.value = false
  }
}
watch(() => picks.value.map((item) => item.slug).join('|'), () => { void load() }, { immediate: true })

const groupLabel = (code: string) => attrGroups.find((group) => group.code === code)?.label ?? (code || 'Характеристики')
const rows = computed(() => {
  const groups = new Map<string, Map<string, string>>()
  for (const card of items.value) {
    for (const attr of card.attrs) {
      if (!attr.group || attr.group === 'identification' || attr.group === 'data_quality') continue
      const bucket = groups.get(attr.group) ?? new Map<string, string>()
      bucket.set(attr.key, attr.label || attr.key)
      groups.set(attr.group, bucket)
    }
  }
  return [...groups.entries()].map(([code, keys]) => ({ code, label: groupLabel(code), keys: [...keys.entries()] }))
})
const cell = (card: Card, key: string) => {
  const attr = card.attrs.find((item) => item.key === key)
  if (!attr || attr.status !== 'known' || attr.value == null || attr.value === '') return 'нет данных'
  return formatAttributeValue(attr.value, attr.unit, attr.approximate, attr.condition)
}
const toneOf = (raw: string | null): Availability => {
  if (raw === 'operation' || raw === 'piloting' || raw === 'rnd') return raw
  return 'piloting'
}

const adding = ref(false)
const pool = ref<{ slug: string; name: string; manufacturer: string | null; trl: number | null; image_url: string | null; solution_type: { name: string } | null }[]>([])
const openAdd = async () => {
  adding.value = !adding.value
  if (!adding.value || pool.value.length) return
  const page = await platformGet<{ items: typeof pool.value }>('/catalog/products?limit=48')
  pool.value = page.items
}
const candidates = computed(() => pool.value.filter((item) => !picks.value.some((pick) => pick.slug === item.slug)))
const add = (item: (typeof pool.value)[number]) => {
  toggle(item.slug, {
    name: item.name,
    image: photoFor(item.image_url, item.name),
    solutionType: item.solution_type?.name ?? '',
    manufacturer: item.manufacturer ?? '',
  })
}
</script>

<template>
  <section class="container compare">
    <div class="between head" v-reveal>
      <div>
        <div class="label">Сравнение</div>
        <h1 class="hero-2">Рядом по одним и тем же полям</h1>
        <p class="body muted">Строки берутся из характеристик каталога платформы, того же набора, что и карточка продукта. Пустые значения показаны явно.</p>
      </div>
      <div class="row">
        <UiButton variant="secondary" @click="openAdd"><template #icon><PhPlus :size="16" weight="bold" /></template>Добавить продукт</UiButton>
      </div>
    </div>

    <p v-if="loadError" class="caption">{{ loadError }}</p>

    <Transition name="fade">
      <div v-if="adding" class="picker glass">
        <div class="picker-head between">
          <span class="h4">Добавить в сравнение</span>
          <span class="caption">Первые карточки каталога платформы.</span>
        </div>
        <div class="picker-grid">
          <button v-for="p in candidates" :key="p.slug" type="button" class="pick" @click="add(p)">
            <img :src="photoFor(p.image_url, p.name)" alt="">
            <span class="pick-text"><span class="body-sm strong">{{ p.name }}</span><span class="caption">{{ p.solution_type?.name || 'без типа' }} · УГТ {{ p.trl ?? '—' }}</span></span>
          </button>
        </div>
      </div>
    </Transition>

    <div v-if="loading && !items.length" class="empty glass"><UiSkeleton h="240px" /></div>
    <div v-else-if="items.length" class="table-wrap glass glass-xl" v-reveal="1">
      <table class="cmp">
        <thead>
          <tr>
            <th class="param-h"><span class="label">Характеристика</span></th>
            <th v-for="p in items" :key="p.slug" class="prod">
              <div class="prod-card">
                <button type="button" class="rm" :aria-label="`Убрать ${p.name}`" @click="toggle(p.slug)"><PhX :size="12" weight="bold" /></button>
                <img :src="photoFor(p.image_url, p.name)" :alt="p.name">
                <NuxtLink :to="`/catalog/card/${p.slug}`" class="h4">{{ p.name }}</NuxtLink>
                <span class="caption">{{ p.manufacturer || 'Производитель не указан' }}</span>
                <span class="prod-badges">
                  <UiBadge v-if="p.availability" :tone="availabilityTone[toneOf(p.availability)]" size="sm">{{ availabilityLabel[toneOf(p.availability)] }}</UiBadge>
                  <UiBadge v-if="p.trl" tone="neutral" mono size="sm">УГТ {{ p.trl }}</UiBadge>
                </span>
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr class="sec"><td :colspan="items.length + 1"><span class="label">Цена</span></td></tr>
          <tr>
            <td class="param">Стоимость единицы</td>
            <td v-for="p in items" :key="p.slug" class="val"><span class="mono-md strong">{{ formatRub(p.price_rub ?? undefined) }}</span></td>
          </tr>
          <template v-for="g in rows" :key="g.code">
            <tr class="sec"><td :colspan="items.length + 1"><span class="label">{{ g.label }}</span></td></tr>
            <tr v-for="[key, label] in g.keys" :key="key">
              <td class="param">{{ label }}</td>
              <td v-for="p in items" :key="p.slug" class="val">{{ cell(p, key) }}</td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
    <div v-else class="empty glass">
      <div class="h3">В сравнении пока пусто</div>
      <p class="body muted">Отметьте модели в каталоге кнопкой «Сравнить» или добавьте продукт здесь.</p>
      <UiButton to="/catalog" variant="secondary">Открыть каталог</UiButton>
    </div>
  </section>
</template>

<style scoped>
.compare { padding-top: var(--space-12); padding-bottom: var(--space-16); display: grid; gap: var(--space-6); }
.head { align-items: flex-end; }
.head > div:first-child { display: grid; gap: 10px; max-width: 64ch; }
.picker { padding: var(--space-5); display: grid; gap: var(--space-4); }
.picker > * { position: relative; z-index: 1; }
.picker-head .caption { max-width: 60ch; text-align: right; }
.picker-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
.pick { display: grid; grid-template-columns: 48px 1fr auto; gap: 12px; align-items: center; padding: 8px 10px; border-radius: 12px; background: rgba(255, 255, 255, 0.6); text-align: left; transition: background var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease); }
.pick:hover { background: #fff; box-shadow: inset 0 0 0 1px var(--border-hairline); }
.pick img { width: 48px; height: 48px; object-fit: cover; border-radius: 10px; }
.pick-text { display: grid; }
.table-wrap { padding: var(--space-3); overflow-x: auto; }
.cmp { position: relative; z-index: 1; min-width: 100%; }
.cmp th, .cmp td { padding: 12px 16px; vertical-align: top; }
.param-h { text-align: left; vertical-align: bottom; width: 240px; }
.prod { text-align: left; min-width: 220px; }
.prod-card { position: relative; display: grid; gap: 4px; padding: 12px; border-radius: 16px; background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.prod-card img { width: 100%; aspect-ratio: 4 / 3; object-fit: cover; border-radius: 12px; margin-bottom: 6px; }
.prod-card .h4 { color: var(--ink-strong); }
.prod-badges { display: flex; gap: 6px; margin-top: 4px; }
.rm { position: absolute; top: 18px; right: 18px; z-index: 2; width: 24px; height: 24px; border-radius: 50%; background: var(--surface-graphite); color: #fff; display: inline-flex; align-items: center; justify-content: center; }
.sec td { padding-top: 22px; padding-bottom: 6px; border-bottom: 1px solid rgba(15, 20, 19, 0.08); }
.param { font-size: 14px; color: var(--ink-body); border-bottom: 1px solid rgba(15, 20, 19, 0.05); }
.val { text-align: right; border-bottom: 1px solid rgba(15, 20, 19, 0.05); }
tbody tr:nth-child(odd):not(.sec) td { background: rgba(15, 20, 19, 0.018); }
.empty { padding: var(--space-12); text-align: center; display: grid; gap: var(--space-3); justify-items: center; }
.empty > * { position: relative; z-index: 1; }
.fade-enter-active, .fade-leave-active { transition: opacity var(--dur-mid) var(--ease), transform var(--dur-mid) var(--ease); }
.fade-enter-from, .fade-leave-to { opacity: 0; transform: translateY(-6px); }
</style>
