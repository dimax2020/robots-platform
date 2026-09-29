<script setup lang="ts">
import { platformGet, type PlatformCard, type PlatformPage } from '~/composables/usePlatform'
import type { Product } from '~/data/catalog'
import { photoFor } from '~/data/placeholders'

const props = defineProps<{ solutionType?: string; process?: string; objectCode?: string }>()
const pageSize = 24
const items = ref<Product[]>([])
const total = ref(0)
const cursor = ref<string | null>(null)
const done = ref(false)
const loading = ref(false)
const error = ref('')
const sentinel = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

const highlightOf = (raw: string) => {
  const prefixes = ['Грузоподъёмность', 'Скорость', 'Проход', 'Работа']
  const label = prefixes.find((item) => raw.startsWith(`${item} `))
  if (!label) return { label: raw, value: 'нет данных' }
  return { label, value: raw.slice(label.length).trim() }
}

const knownAvailability = (raw: string | null): Product['availability'] | null => {
  if (!raw) return null
  const value = raw.toLowerCase()
  if (value === 'operation' || value.includes('эксплуата')) return 'operation'
  if (value === 'rnd' || value.includes('разработ')) return 'rnd'
  if (value === 'piloting' || value.includes('пилот')) return 'piloting'
  return null
}

const toProduct = (card: PlatformCard): Product => {
  const availability = knownAvailability(card.availability)
  const product: Product & { statusKnown: boolean } = {
    id: card.id,
    slug: card.slug,
    name: card.name,
    manufacturer: card.manufacturer || 'Не указан',
    legalEntity: '',
    country: '',
    city: '',
    availability: availability ?? 'piloting',
    statusKnown: availability != null,
    trl: card.trl ?? 0,
    marketPotential: 0,
    autoMatch: (card.trl ?? 0) >= 5 && card.availability !== 'rnd' && card.availability != null,
    solutionType: card.solution_type?.name ?? '',
    solutionTypeCode: card.solution_type?.code ?? '',
    family: '',
    processes: [],
    objects: [],
    industries: [],
    image: photoFor(card.image_url, card.name),
    summary: '',
    priceRub: card.price_rub ?? undefined,
    highlights: (card.highlights ?? []).map(highlightOf),
    attrs: [],
    cases: [],
    completeness: 0,
  }
  return product
}

const loadMore = async () => {
  if (loading.value || done.value) return
  loading.value = true
  error.value = ''
  try {
    const query = new URLSearchParams({ limit: String(pageSize) })
    if (cursor.value) query.set('cursor', cursor.value)
    if (props.solutionType) query.set('solution_type', props.solutionType)
    if (props.process) query.set('process', props.process)
    if (props.objectCode) query.set('object_code', props.objectCode)
    const asked = `${props.solutionType ?? ''}|${props.process ?? ''}|${props.objectCode ?? ''}`
    const page = await platformGet<PlatformPage>(`/catalog/products?${query}`)
    if (asked !== `${props.solutionType ?? ''}|${props.process ?? ''}|${props.objectCode ?? ''}`) return
    items.value = items.value.concat(page.items.map(toProduct))
    total.value = page.total
    cursor.value = page.next_cursor
    done.value = !page.next_cursor
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Каталог платформы не ответил'
    done.value = true
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadMore()
  observer = new IntersectionObserver((entries) => {
    if (entries.some((entry) => entry.isIntersecting)) void loadMore()
  }, { rootMargin: '240px' })
  if (sentinel.value) observer.observe(sentinel.value)
})

watch([() => props.solutionType, () => props.process, () => props.objectCode], async () => {
  items.value = []
  total.value = 0
  cursor.value = null
  done.value = false
  loading.value = false
  await loadMore()
})

onBeforeUnmount(() => observer?.disconnect())

defineExpose({ items, total, loading, error, done })
</script>

<template>
  <div>
    <slot :items="items" :total="total" :loading="loading" :error="error" :done="done" />
    <div ref="sentinel" class="sentinel" />
  </div>
</template>

<style scoped>
.sentinel { height: 1px; }
</style>
