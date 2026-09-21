import {
  attrGroups,
  confidenceByKind,
  highlightsFor,
  imageFor,
  type AttrValue,
  type Product,
  type ProductCase,
  type Source,
  type TreeNode,
} from '~/data/catalog'
import type {
  ApiAttrValue,
  ApiAttributeDef,
  ApiCatalogTree,
  ApiProductCard,
  ApiProductDetail,
  ApiProductList,
  ApiSource,
  ApiTreeNode,
} from '~/types/api'

/** Один и тот же путь для браузера и для SSR: внутри compose SSR ходит к контейнеру api напрямую. */
export const useApiBase = () => {
  const config = useRuntimeConfig()
  return import.meta.server ? config.apiBaseServer : config.public.apiBase
}

const GROUPS = new Set(attrGroups.map((g) => g.code))

export const mapSource = (s: ApiSource): Source => ({
  id: String(s.id),
  kind: s.kind,
  publisher: s.publisher || s.title || 'источник без названия',
  url: s.url || '',
  fetchedAt: s.captured_at,
  checkedAt: s.last_checked_at?.slice(0, 10) || s.captured_at,
  usageCount: s.usage_count,
})

/** Значение атрибута само подписей не знает — метка и группа берутся из справочника. */
const mapAttr = (key: string, v: ApiAttrValue, defs: Map<string, ApiAttributeDef>): AttrValue => {
  const def = defs.get(key)
  const group = def && GROUPS.has(def.group_code) ? def.group_code : 'technical'
  return {
    key,
    label: def?.label ?? key,
    unit: v.unit ?? def?.unit ?? undefined,
    group,
    status: v.status,
    value: typeof v.value === 'boolean' ? (v.value ? 'да' : 'нет') : (v.value ?? undefined),
    sourceId: v.source_id != null ? String(v.source_id) : undefined,
    quote: v.quote ?? undefined,
    note: v.note ?? undefined,
  }
}

const mapCard = (c: ApiProductCard, attrs: AttrValue[], cases: ProductCase[]): Product => {
  const base = {
    id: c.id,
    slug: c.slug,
    name: c.name,
    manufacturer: c.manufacturer,
    legalEntity: c.legal_entity ?? '',
    country: c.country ?? '',
    city: c.region ?? '',
    availability: c.availability,
    trl: c.trl ?? 0,
    marketPotential: c.market_potential ?? 0,
    autoMatch: c.auto_match,
    solutionType: c.solution_type.name,
    solutionTypeCode: c.solution_type.code,
    family: c.family,
    processes: c.processes.map((p) => p.name),
    objects: c.object_types.map((o) => o.name),
    industries: c.industries.map((i) => i.name),
    image: imageFor(c.solution_type.code, c.family),
    summary: '',
    priceRub: c.price_rub ?? undefined,
    priceNote: c.price_note ?? undefined,
    attrs,
    cases,
    // Заполненность считается бэкендом по справочнику характеристик (§6.3)
    completeness: c.completeness_total ? c.completeness_filled / c.completeness_total : 0,
  }
  return { ...base, highlights: highlightsFor(base) }
}

const mapTree = (n: ApiTreeNode): TreeNode => ({
  label: n.label,
  children: n.children.length ? n.children.map(mapTree) : undefined,
  productIds: n.children.length ? undefined : n.product_ids,
})

/**
 * Каталог тянется один раз за SSR-проход и кладётся в payload: фильтры на странице
 * каталога работают по готовому массиву, без запросов на каждое нажатие.
 */
export const useCatalog = () => {
  const base = useApiBase()

  const attributes = useAsyncData<ApiAttributeDef[]>(
    'catalog-attributes',
    () => $fetch(`${base}/catalog/attributes`),
    { default: () => [] },
  )
  const list = useAsyncData<ApiProductList>(
    'catalog-products',
    () => $fetch(`${base}/catalog/products`),
    { default: () => ({ catalog_version_id: 0, total: 0, products: [] }) },
  )
  const treeData = useAsyncData<ApiCatalogTree>(
    'catalog-tree',
    () => $fetch(`${base}/catalog/tree`),
    { default: () => ({ catalog_version_id: 0, nodes: [] }) },
  )
  const sourceList = useAsyncData<ApiSource[]>(
    'catalog-sources',
    () => $fetch(`${base}/catalog/sources`),
    { default: () => [] },
  )

  const defs = computed(() => new Map(attributes.data.value.map((d) => [d.key, d])))

  return {
    attributeDefs: computed(() => attributes.data.value),
    products: computed(() => list.data.value.products.map((c) => mapCard(c, [], []))),
    catalogTree: computed(() => treeData.data.value.nodes.map(mapTree)),
    sources: computed(() => sourceList.data.value.map(mapSource)),
    catalogVersionId: computed(() => list.data.value.catalog_version_id),
    pending: computed(() => list.pending.value || attributes.pending.value),
    error: computed(() => list.error.value || attributes.error.value || treeData.error.value),
    sourceById: (id?: string) => sourceList.data.value.map(mapSource).find((s) => s.id === id),
    confidenceOf: (id?: string) => {
      const src = sourceList.data.value.find((s) => String(s.id) === id)
      return src ? confidenceByKind[src.kind] : undefined
    },
    refresh: async () => {
      await Promise.all([attributes.refresh(), list.refresh(), treeData.refresh(), sourceList.refresh()])
    },
    defs,
  }
}

/** Полная карточка: описание, ТТХ с источниками и кейсы грузятся отдельным запросом. */
export const useProduct = (key: MaybeRefOrGetter<string>) => {
  const base = useApiBase()
  const { attributeDefs } = useCatalog()

  const { data, pending, error, refresh } = useAsyncData<ApiProductDetail | null>(
    () => `product-${toValue(key)}`,
    () => $fetch(`${base}/catalog/products/${toValue(key)}`).catch(() => null),
    { watch: [computed(() => toValue(key))] },
  )

  const defs = computed(() => new Map(attributeDefs.value.map((d) => [d.key, d])))

  const product = computed<Product | undefined>(() => {
    const d = data.value
    if (!d) return undefined
    const attrs = Object.entries(d.attrs).map(([key, v]) => mapAttr(key, v, defs.value))
    const cases: ProductCase[] = d.cases.map((c) => ({
      id: String(c.id),
      summary: c.summary ?? '',
      customer: c.customer ?? undefined,
      process: c.process?.name,
      sourceId: c.source_id != null ? String(c.source_id) : undefined,
    }))
    return { ...mapCard(d, attrs, cases), summary: d.summary ?? '' }
  })

  return {
    product,
    sources: computed(() => (data.value?.sources ?? []).map(mapSource)),
    attributeDefs,
    pending,
    error,
    refresh,
  }
}
