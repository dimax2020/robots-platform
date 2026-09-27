<script setup lang="ts">
import { PhArrowLeft } from '@phosphor-icons/vue'
import { platformGet } from '~/composables/usePlatform'
import { formatRub, availabilityLabel, type Availability } from '~/data/catalog'
import { formatAttributeValue } from '~/data/attributeValue'
import { photoFor } from '~/data/placeholders'

const route = useRoute()
const slug = computed(() => route.params.slug as string)
interface Attr { approximate?: boolean; condition?: string | null; unit?: string | null; key: string; label?: string; status: string; value: string | number | null; quote: string | null; source: { kind: string; publisher: string; url: string | null; parser_code: string | null } | null }
interface Card {
  name: string
  manufacturer: string | null
  availability: string | null
  trl: number | null
  price_rub: number | null
  summary: string | null
  image_url: string | null
  highlights?: string[]
  attrs: Attr[]
}
const product = ref<Card | null>(null)
const error = ref('')
useHead({ title: () => product.value ? `${product.value.name} · Каталог` : 'Карточка' })

const known = computed(() => product.value?.attrs.filter((attr) => attr.status === 'known' && attr.value != null) ?? [])
const photo = computed(() => photoFor(product.value?.image_url, product.value?.name ?? ''))
const statusText = computed(() => {
  const raw = product.value?.availability
  if (!raw) return ''
  if (raw === 'operation' || raw === 'piloting' || raw === 'rnd') return availabilityLabel[raw as Availability]
  return raw
})
const sourceOf = (attr: Attr) => {
  if (!attr.source) return 'источник не указан'
  const parser = attr.source.parser_code ? ` · ${attr.source.parser_code}` : ''
  return `${attr.source.publisher}${parser}`
}

onMounted(async () => {
  try {
    product.value = await platformGet<Card>(`/catalog/products/${slug.value}`)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Карточка не найдена'
  }
})
</script>

<template>
  <section class="container product">
    <NuxtLink to="/catalog" class="back body-sm"><PhArrowLeft :size="14" weight="bold" /> Каталог</NuxtLink>
    <UiCallout v-if="error" tone="danger" title="Карточка не открылась">{{ error }}</UiCallout>

    <template v-else-if="product">
      <div class="head">
        <div class="media glass glass-xl">
          <img :src="photo" :alt="product.name">
        </div>
        <div class="info">
          <h1 class="hero-2">{{ product.name }}</h1>
          <div class="vendor body">
            <span class="strong">{{ product.manufacturer || 'Производитель не указан' }}</span>
            <span v-if="product.trl" class="muted">УГТ {{ product.trl }}</span>
            <span v-if="statusText" class="muted">{{ statusText }}</span>
          </div>
          <p v-if="product.summary" class="body-lg muted">{{ product.summary }}</p>
          <div v-if="product.highlights?.length" class="hl">
            <div v-for="item in product.highlights" :key="item" class="hl-item">
              <span class="mono-lg">{{ item }}</span>
            </div>
          </div>
          <div class="price-row glass">
            <div>
              <div class="caption">Стоимость единицы</div>
              <div class="display-4">{{ formatRub(product.price_rub ?? undefined) }}</div>
            </div>
          </div>
        </div>
      </div>

      <section class="group glass">
        <div class="g-head">
          <div class="mono-sm num">1</div>
          <div>
            <h2 class="h3">Характеристики</h2>
            <div class="caption">У каждого значения указан источник. Пустых полей справочника здесь нет: показаны только те, что уже записаны.</div>
          </div>
        </div>
        <div v-if="known.length" class="rows">
          <div v-for="attr in known" :key="attr.key" class="rowl">
            <span class="body-sm k">{{ attr.label || attr.key }}</span>
            <span class="body-sm strong val">{{ formatAttributeValue(attr.value, attr.unit, attr.approximate, attr.condition) }}</span>
            <span class="caption">{{ sourceOf(attr) }}</span>
          </div>
        </div>
        <p v-else class="body-sm muted">Характеристики для этой карточки ещё не записаны.</p>
      </section>
    </template>
  </section>
</template>

<style scoped>
.product { padding-top: var(--space-8); padding-bottom: var(--space-16); display: grid; gap: var(--space-8); }
.back { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-muted); font-weight: 600; }
.back:hover { color: var(--ink-strong); }
.head { display: grid; grid-template-columns: minmax(0, 6fr) minmax(0, 6fr); gap: var(--space-10); align-items: start; }
.head:has(.wide) { grid-template-columns: minmax(0, 1fr); }
.media { position: relative; padding: 10px; }
.media img { width: 100%; aspect-ratio: 4 / 3; object-fit: contain; background: #e9eeec; border-radius: 18px; position: relative; z-index: 1; }
.info { display: grid; gap: var(--space-4); align-content: start; }
.vendor { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
.vendor .muted { display: inline-flex; align-items: center; gap: 4px; }
.hl { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-4); padding: var(--space-4) 0; border-top: 1px solid var(--border-hairline); border-bottom: 1px solid var(--border-hairline); }
.hl-item { display: grid; gap: 4px; }
.hl-item .mono-lg { color: var(--ink-strong); font-size: 18px; }
.price-row { display: flex; justify-content: space-between; align-items: center; gap: var(--space-4); padding: var(--space-5) var(--space-6); }
.price-row > * { position: relative; z-index: 1; }
.group { padding: var(--space-6); }
.group > * { position: relative; z-index: 1; }
.g-head { display: flex; gap: 14px; align-items: flex-start; margin-bottom: var(--space-5); }
.num { width: 28px; height: 28px; border-radius: 8px; background: var(--surface-graphite); color: var(--brand-300); display: inline-flex; align-items: center; justify-content: center; flex: none; }
.rows { display: grid; }
.rowl { display: grid; grid-template-columns: minmax(160px, 240px) minmax(0, 1fr) minmax(160px, 280px); gap: var(--space-4); align-items: center; padding: 10px 0; border-top: 1px solid rgba(15, 20, 19, 0.06); }
.rowl:first-child { border-top: 0; }
.k { color: var(--ink-body); }
.val { color: var(--ink-strong); }
@media (max-width: 1100px) {
  .head, .hl { grid-template-columns: 1fr; }
  .rowl { grid-template-columns: 1fr; gap: 4px; }
}
</style>
