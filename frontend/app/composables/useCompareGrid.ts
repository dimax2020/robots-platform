import type { Confidence, Product } from '~/data/catalog'
import { labelProcess } from '~/data/siteFields'
import type { CalcCandidate, CalcOption, CalcRun, CalcTrace } from '~/composables/useCalc'
import type {
  ApiCompareBetter,
  ApiCompareGroup,
  ApiCompareOrigin,
  ApiCompareParam,
  ApiProject,
} from '~/types/api'

// ---------------------------------------------------------------------------
// Публичные типы сетки сравнения (вход для страницы шага 4)
// ---------------------------------------------------------------------------

export type CompareValueOrigin = 'catalog' | 'engine' | 'derived'

/** Происхождение числа: источник каталога или отметка движка (§0). */
export interface CompareProvenance {
  kind: CompareValueOrigin
  /** Id источника характеристики, если значение из attrs. */
  sourceId?: string
  quote?: string
  /** Формула из options / трассировки. */
  formula?: string
  note?: string
}

export interface CompareParamValue {
  known: boolean
  /** Число для дельты; для диапазона — середина. */
  numeric?: number
  /** Нечисловое значение (reliability A–D и т.п.). */
  text?: string
  display: string
  /** Диапазон сравнивался по середине. */
  approximate?: boolean
  unit?: string | null
  provenance?: CompareProvenance
}

export type CompareDeltaTone = 'better' | 'worse' | 'neutral'
export type CompareDeltaKind = 'baseline' | 'numeric' | 'ordinal' | 'no_data'

export interface CompareDeltaRow {
  key: string
  label: string
  unit?: string | null
  group: ApiCompareGroup
  origin: ApiCompareOrigin
  better: ApiCompareBetter
  rationale: string
  active: CompareParamValue
  baseline: CompareParamValue
  kind: CompareDeltaKind
  /** «это эталон» / «нет данных у …» / словесная дельта reliability. */
  message: string
  tone: CompareDeltaTone | null
  absDelta?: number
  /** Проценты от значения эталона; null если эталон 0. */
  relDeltaPct?: number | null
  approximate?: boolean
}

export interface CompareDeltaGroup {
  group: ApiCompareGroup
  label: string
  rows: CompareDeltaRow[]
}

export interface CompareDeltaPanel {
  /** Активная карточка совпадает с эталоном. */
  isBaseline: boolean
  message: string | null
  groups: CompareDeltaGroup[]
}

export interface CompareCarouselItem {
  productId: string
  processCode: string
  score: number | null
  verdict: CalcCandidate['verdict']
  product?: Product
  count?: number
  formula?: string
}

export interface CompareSubrow {
  processCode: string
  solutionTypeCode: string
  solutionTypeLabel: string
  /** Лучший score среди pass-кандидатов подстроки. */
  bestScore: number
  carousel: CompareCarouselItem[]
  /** Вердикт unknown: в сравнение не входят. */
  needsReview: CompareCarouselItem[]
  baselineProductId: string | null
  activeProductId: string | null
  isPinned: boolean
  panel: CompareDeltaPanel
}

export type CompareEmptyReason = 'no_solutions' | 'all_pending_or_excluded'

export interface CompareGroup {
  processCode: string
  label: string
  /** Нет pass-кандидатов — группа остаётся с честной причиной. */
  emptyReason: CompareEmptyReason | null
  emptyMessage: string | null
  subrows: CompareSubrow[]
}

export interface CompareParkSlice {
  processCode: string
  label: string
  count: number
}

export interface CompareSummary {
  closedCount: number
  openCount: number
  openLabels: string[]
  totalPark: number
  parkByProcess: CompareParkSlice[]
  /** Сумма стоимости оборудования по эталонам; null если ни у одной позиции нет цены. */
  equipmentCost: number | null
  /** Цена известна не у всех эталонов — сумма неполная. */
  equipmentCostPartial: boolean
  priceKnown: number
  priceTotal: number
  worstReliability: Confidence | null
  worstReliabilityProductId: string | null
  worstReliabilityLabel: string | null
  /** Сколько полей ждут ответа вендора (корзина «требует проверки» шага 3). */
  vendorFieldsWaiting: number
  /** Честная строка про шаг 5. */
  economicsStub: string
}

export interface ComparePin {
  processCode: string
  solutionTypeCode: string
  productId: string
}

export interface UseCompareGridInput {
  detail: MaybeRefOrGetter<ApiProject | null | undefined>
  run: MaybeRefOrGetter<CalcRun | null | undefined>
  products: MaybeRefOrGetter<Product[]>
  compareSpec: MaybeRefOrGetter<ApiCompareParam[]>
  /** Для подписи достоверности из kind источника, если в size-трассе буквы нет. */
  confidenceOf?: (sourceId?: string) => Confidence | undefined
}

const GROUP_LABEL: Record<ApiCompareGroup, string> = {
  technical: 'Технические',
  operational: 'Эксплуатационные',
  economic: 'Экономические',
}

const REL_RANK: Record<string, number> = { A: 4, B: 3, C: 2, D: 1 }

const ECONOMICS_STUB =
  'Окупаемость, TCO и годовой эффект — шаг 5 (экономика); сейчас это заглушка.'

const subrowKey = (processCode: string, solutionTypeCode: string) =>
  `${processCode}:${solutionTypeCode}`

const pinToken = (p: ComparePin) =>
  `${p.processCode}:${p.solutionTypeCode}:${p.productId}`

export const parseComparePins = (raw: unknown): ComparePin[] => {
  const list = Array.isArray(raw) ? raw : raw != null && raw !== '' ? [raw] : []
  const out: ComparePin[] = []
  for (const item of list) {
    if (typeof item !== 'string') continue
    const parts = item.split(':')
    if (parts.length < 3) continue
    const [processCode, solutionTypeCode, ...rest] = parts
    const productId = rest.join(':')
    if (!processCode || !solutionTypeCode || !productId) continue
    out.push({ processCode, solutionTypeCode, productId })
  }
  return out
}

export const serializeComparePins = (pins: ComparePin[]): string[] => pins.map(pinToken)

const formatNumber = (n: number): string => {
  if (Number.isInteger(n)) return n.toLocaleString('ru-RU')
  return n.toLocaleString('ru-RU', { maximumFractionDigits: 4 })
}

const unknownValue = (): CompareParamValue => ({
  known: false,
  display: 'нет данных',
})

const optionOf = (run: CalcRun | null | undefined, c: CalcCandidate): CalcOption | undefined =>
  (run?.options ?? []).find((o) => o.productId === c.productId && o.processCode === c.processCode)

const letterFromSource = (source?: string): Confidence | null => {
  if (!source) return null
  const m = source.match(/^\[([A-D])\]/i)
  return m ? (m[1]!.toUpperCase() as Confidence) : null
}

const worstLetter = (letters: Confidence[]): Confidence | null => {
  if (!letters.length) return null
  return letters.reduce((a, b) => ((REL_RANK[a] ?? 0) <= (REL_RANK[b] ?? 0) ? a : b))
}

/** Достоверность из size-трассы продукта; иначе — по источникам его attrs (§3). */
const reliabilityOf = (
  productId: string,
  run: CalcRun | null | undefined,
  product: Product | undefined,
  confidenceOf?: (sourceId?: string) => Confidence | undefined,
): Confidence | null => {
  const sizeLetters = (run?.trace ?? [])
    .filter((t: CalcTrace) => t.step === 'size' && t.productId === productId)
    .map((t) => letterFromSource(t.source))
    .filter((x): x is Confidence => Boolean(x))
  const fromTrace = worstLetter(sizeLetters)
  if (fromTrace) return fromTrace

  if (!product) return null
  const fromAttrs = product.attrs
    .map((a) => {
      if (a.sourceId && confidenceOf) return confidenceOf(a.sourceId)
      return undefined
    })
    .filter((x): x is Confidence => Boolean(x))
  return worstLetter(fromAttrs)
}

const resolveCompareParam = (
  param: ApiCompareParam,
  candidate: CalcCandidate,
  product: Product | undefined,
  run: CalcRun | null | undefined,
  confidenceOf?: (sourceId?: string) => Confidence | undefined,
): CompareParamValue => {
  const opt = optionOf(run, candidate)

  if (param.origin === 'engine') {
    if (param.key === 'count') {
      if (opt?.count == null) return unknownValue()
      return {
        known: true,
        numeric: opt.count,
        display: formatNumber(opt.count),
        unit: param.unit,
        provenance: { kind: 'engine', formula: opt.formula, note: 'options.count' },
      }
    }
    if (param.key === 'score') {
      if (candidate.score == null) return unknownValue()
      return {
        known: true,
        numeric: candidate.score,
        display: formatNumber(candidate.score),
        unit: param.unit,
        provenance: { kind: 'engine', note: 'candidate.score' },
      }
    }
    if (param.key === 'reliability') {
      const letter = reliabilityOf(candidate.productId, run, product, confidenceOf)
      if (!letter) return unknownValue()
      return {
        known: true,
        text: letter,
        display: letter,
        provenance: { kind: 'engine', note: 'size trace / источники характеристик' },
      }
    }
    if (param.key === 'data_completeness') {
      if (!product) return unknownValue()
      return {
        known: true,
        numeric: product.completeness,
        display: `${Math.round(product.completeness * 100)} %`,
        unit: param.unit,
        provenance: { kind: 'engine', note: 'completeness_filled / completeness_total' },
      }
    }
    return unknownValue()
  }

  if (param.origin === 'attr') {
    if (param.key === 'price_rub') {
      if (product?.priceRub == null) return unknownValue()
      return {
        known: true,
        numeric: product.priceRub,
        display: formatNumber(product.priceRub),
        unit: param.unit ?? '₽',
        provenance: {
          kind: 'catalog',
          note: product.priceNote ?? 'product.price_rub',
        },
      }
    }
    const attr = product?.attrs.find((a) => a.key === param.key)
    if (!attr || attr.status !== 'known') return unknownValue()
    if (attr.range) {
      const mid = (attr.range[0] + attr.range[1]) / 2
      return {
        known: true,
        numeric: mid,
        approximate: true,
        display: `${formatNumber(attr.range[0])}–${formatNumber(attr.range[1])}`,
        unit: attr.unit ?? param.unit,
        provenance: {
          kind: 'catalog',
          sourceId: attr.sourceId,
          quote: attr.quote,
          note: attr.note,
        },
      }
    }
    if (typeof attr.value === 'number') {
      return {
        known: true,
        numeric: attr.value,
        display: formatNumber(attr.value),
        unit: attr.unit ?? param.unit,
        provenance: {
          kind: 'catalog',
          sourceId: attr.sourceId,
          quote: attr.quote,
          note: attr.note,
        },
      }
    }
    if (attr.value != null) {
      return {
        known: true,
        text: String(attr.value),
        display: String(attr.value),
        unit: attr.unit ?? param.unit,
        provenance: {
          kind: 'catalog',
          sourceId: attr.sourceId,
          quote: attr.quote,
          note: attr.note,
        },
      }
    }
    return unknownValue()
  }

  if (param.origin === 'derived' && param.key === 'park_price_rub') {
    const count = opt?.count
    const price = product?.priceRub
    if (count == null || price == null) return unknownValue()
    const value = count * price
    return {
      known: true,
      numeric: value,
      display: formatNumber(value),
      unit: param.unit ?? '₽',
      provenance: {
        kind: 'derived',
        formula: `${count} × ${price}`,
        note: 'count * price_rub; только оборудование, без внедрения и сервиса',
      },
    }
  }

  return unknownValue()
}

const noDataWho = (activeKnown: boolean, baselineKnown: boolean): string => {
  if (!activeKnown && !baselineKnown) return 'нет данных у активной карточки и у эталона'
  if (!activeKnown) return 'нет данных у активной карточки'
  return 'нет данных у эталона'
}

const stepWord = (n: number): string => {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return 'ступень'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return 'ступени'
  return 'ступеней'
}

const ordinalDeltaMessage = (
  active: string,
  baseline: string,
  better: ApiCompareBetter,
): { message: string; tone: CompareDeltaTone | null } => {
  const a = REL_RANK[active] ?? 0
  const b = REL_RANK[baseline] ?? 0
  const diff = a - b
  if (diff === 0) {
    return { message: 'одинаковая достоверность', tone: better === 'none' ? null : 'neutral' }
  }
  const steps = Math.abs(diff)
  const higher = diff > 0
  const message = higher
    ? `достоверность выше на ${steps === 1 ? 'одну' : String(steps)} ${steps === 1 ? 'ступень' : stepWord(steps)}`
    : `достоверность ниже на ${steps === 1 ? 'одну' : String(steps)} ${steps === 1 ? 'ступень' : stepWord(steps)}`
  if (better === 'none') return { message, tone: null }
  const activeBetter = better === 'max' ? higher : !higher
  return { message, tone: activeBetter ? 'better' : 'worse' }
}

const buildDeltaRow = (
  param: ApiCompareParam,
  active: CompareParamValue,
  baseline: CompareParamValue,
  isSameProduct: boolean,
): CompareDeltaRow => {
  const base = {
    key: param.key,
    label: param.label,
    unit: param.unit,
    group: param.group,
    origin: param.origin,
    better: param.better,
    rationale: param.rationale,
    active,
    baseline,
  }

  if (isSameProduct) {
    return {
      ...base,
      kind: 'baseline',
      message: 'это эталон',
      tone: null,
    }
  }

  if (!active.known || !baseline.known) {
    return {
      ...base,
      kind: 'no_data',
      message: noDataWho(active.known, baseline.known),
      tone: null,
    }
  }

  if (active.text != null || baseline.text != null) {
    const a = active.text ?? ''
    const b = baseline.text ?? ''
    const { message, tone } = ordinalDeltaMessage(a, b, param.better)
    return {
      ...base,
      kind: 'ordinal',
      message,
      tone,
    }
  }

  if (active.numeric == null || baseline.numeric == null) {
    return {
      ...base,
      kind: 'no_data',
      message: noDataWho(false, false),
      tone: null,
    }
  }

  const absDelta = active.numeric - baseline.numeric
  const relDeltaPct = baseline.numeric === 0 ? null : (absDelta / baseline.numeric) * 100
  const approximate = Boolean(active.approximate || baseline.approximate)

  let tone: CompareDeltaTone | null = null
  if (param.better === 'none') {
    tone = null
  } else if (absDelta === 0) {
    tone = 'neutral'
  } else if (param.better === 'max') {
    tone = absDelta > 0 ? 'better' : 'worse'
  } else {
    tone = absDelta < 0 ? 'better' : 'worse'
  }

  const approxNote = approximate ? ' (приблизительно, по середине диапазона)' : ''
  const relNote =
    relDeltaPct == null
      ? ''
      : `, ${relDeltaPct > 0 ? '+' : ''}${relDeltaPct.toLocaleString('ru-RU', { maximumFractionDigits: 1 })} %`
  const message = `${absDelta > 0 ? '+' : ''}${formatNumber(absDelta)}${param.unit ? ` ${param.unit}` : ''}${relNote}${approxNote}`

  return {
    ...base,
    kind: 'numeric',
    message,
    tone,
    absDelta,
    relDeltaPct,
    approximate,
  }
}

const buildPanel = (
  spec: ApiCompareParam[],
  activeCand: CalcCandidate | undefined,
  baselineCand: CalcCandidate | undefined,
  productOf: (id: string) => Product | undefined,
  run: CalcRun | null | undefined,
  confidenceOf?: (sourceId?: string) => Confidence | undefined,
): CompareDeltaPanel => {
  if (!activeCand || !baselineCand) {
    return {
      isBaseline: false,
      message: 'Сравнивать нечего: ни один кандидат не прошёл жёсткие условия.',
      groups: [],
    }
  }
  const isBaseline = activeCand.productId === baselineCand.productId
  if (isBaseline) {
    return { isBaseline: true, message: 'это эталон', groups: [] }
  }

  const activeProduct = productOf(activeCand.productId)
  const baselineProduct = productOf(baselineCand.productId)
  const rows = spec.map((param) =>
    buildDeltaRow(
      param,
      resolveCompareParam(param, activeCand, activeProduct, run, confidenceOf),
      resolveCompareParam(param, baselineCand, baselineProduct, run, confidenceOf),
      false,
    ),
  )

  const order: ApiCompareGroup[] = ['technical', 'operational', 'economic']
  const groups: CompareDeltaGroup[] = order
    .map((group) => ({
      group,
      label: GROUP_LABEL[group],
      rows: rows.filter((r) => r.group === group),
    }))
    .filter((g) => g.rows.length)

  return { isBaseline: false, message: null, groups }
}

const toCarouselItem = (
  c: CalcCandidate,
  run: CalcRun | null | undefined,
  productOf: (id: string) => Product | undefined,
): CompareCarouselItem => {
  const opt = optionOf(run, c)
  return {
    productId: c.productId,
    processCode: c.processCode,
    score: c.score,
    verdict: c.verdict,
    product: productOf(c.productId),
    count: opt?.count,
    formula: opt?.formula,
  }
}

/**
 * Сетка шага 4: группы → подстроки → карусель / эталон / дельты / сводка.
 * Закрепления эталона живут в query `pin` (разбор и сборка здесь).
 */
export const useCompareGrid = (input: UseCompareGridInput) => {
  const route = useRoute()
  const router = useRouter()
  const confidenceOf = input.confidenceOf ?? (() => undefined)

  const detail = computed(() => toValue(input.detail) ?? null)
  const run = computed(() => toValue(input.run) ?? null)
  const products = computed(() => toValue(input.products) ?? [])
  const compareSpec = computed(() => toValue(input.compareSpec) ?? [])

  const productOf = (id: string) => products.value.find((p) => p.id === id)

  const pins = computed(() => parseComparePins(route.query.pin))
  const pinMap = computed(() => {
    const map = new Map<string, string>()
    for (const p of pins.value) map.set(subrowKey(p.processCode, p.solutionTypeCode), p.productId)
    return map
  })

  /** Активная позиция карусели по подстроке; по умолчанию — эталон. */
  const activeMap = useState<Record<string, string>>('compare-grid-active', () => ({}))

  const setPinsInQuery = (next: ComparePin[]) => {
    const query = { ...route.query } as Record<string, string | string[] | undefined>
    const tokens = serializeComparePins(next)
    if (tokens.length === 0) delete query.pin
    else if (tokens.length === 1) query.pin = tokens[0]
    else query.pin = tokens
    return router.replace({ query })
  }

  const pinBaseline = (processCode: string, solutionTypeCode: string, productId: string) => {
    const key = subrowKey(processCode, solutionTypeCode)
    const rest = pins.value.filter((p) => subrowKey(p.processCode, p.solutionTypeCode) !== key)
    return setPinsInQuery([...rest, { processCode, solutionTypeCode, productId }])
  }

  const clearPin = (processCode: string, solutionTypeCode: string) => {
    const key = subrowKey(processCode, solutionTypeCode)
    return setPinsInQuery(pins.value.filter((p) => subrowKey(p.processCode, p.solutionTypeCode) !== key))
  }

  const setActive = (processCode: string, solutionTypeCode: string, productId: string) => {
    activeMap.value = {
      ...activeMap.value,
      [subrowKey(processCode, solutionTypeCode)]: productId,
    }
  }

  const groups = computed<CompareGroup[]>(() => {
    const tasks = detail.value?.tasks ?? []
    const candidates = run.value?.candidates ?? []
    const spec = compareSpec.value

    return tasks.map((task) => {
      const processCode = task.process_code
      const label = labelProcess(processCode, task.name)
      const taskCands = candidates.filter((c) => c.processCode === processCode)
      const pass = taskCands.filter((c) => c.verdict === 'pass')

      let emptyReason: CompareEmptyReason | null = null
      let emptyMessage: string | null = null
      if (!pass.length) {
        if (!taskCands.length) {
          emptyReason = 'no_solutions'
          emptyMessage = 'Нет типов решений на этот процесс: подбор не нашёл кандидатов.'
        } else {
          emptyReason = 'all_pending_or_excluded'
          emptyMessage =
            'Все кандидаты в корзинах «требует проверки» и «исключён» — сравнивать нечего.'
        }
      }

      const byType = new Map<string, CalcCandidate[]>()
      for (const c of taskCands) {
        const product = productOf(c.productId)
        const code = product?.solutionTypeCode
        if (!code) continue
        const list = byType.get(code) ?? []
        list.push(c)
        byType.set(code, list)
      }

      const subrows: CompareSubrow[] = Array.from(byType.entries())
        .map(([solutionTypeCode, list]) => {
          const passList = list
            .filter((c) => c.verdict === 'pass')
            .slice()
            .sort((a, b) => (b.score ?? -1) - (a.score ?? -1))
          const reviewList = list.filter((c) => c.verdict === 'unknown')
          const bestScore = passList[0]?.score ?? -1
          const labelType =
            productOf(passList[0]?.productId ?? reviewList[0]?.productId ?? '')?.solutionType ??
            solutionTypeCode

          const key = subrowKey(processCode, solutionTypeCode)
          const pinnedId = pinMap.value.get(key)
          const defaultId = passList[0]?.productId ?? null
          const baselineProductId =
            (pinnedId && passList.some((c) => c.productId === pinnedId) ? pinnedId : null) ??
            defaultId
          const activeStored = activeMap.value[key]
          const activeProductId =
            (activeStored && passList.some((c) => c.productId === activeStored)
              ? activeStored
              : null) ?? baselineProductId

          const activeCand = passList.find((c) => c.productId === activeProductId)
          const baselineCand = passList.find((c) => c.productId === baselineProductId)

          return {
            processCode,
            solutionTypeCode,
            solutionTypeLabel: labelType,
            bestScore,
            carousel: passList.map((c) => toCarouselItem(c, run.value, productOf)),
            needsReview: reviewList.map((c) => toCarouselItem(c, run.value, productOf)),
            baselineProductId,
            activeProductId,
            isPinned: Boolean(pinnedId && pinnedId === baselineProductId),
            panel: buildPanel(spec, activeCand, baselineCand, productOf, run.value, confidenceOf),
          }
        })
        .filter((s) => s.carousel.length || s.needsReview.length)
        .sort((a, b) => b.bestScore - a.bestScore)

      return {
        processCode,
        label,
        emptyReason,
        emptyMessage,
        subrows,
      }
    })
  })

  const summary = computed<CompareSummary>(() => {
    const taskGroups = groups.value
    const closed = taskGroups.filter((g) => g.subrows.some((s) => s.carousel.length > 0))
    const open = taskGroups.filter((g) => !g.subrows.some((s) => s.carousel.length > 0))

    const baselines: { processCode: string; label: string; item: CompareCarouselItem }[] = []
    for (const g of taskGroups) {
      for (const s of g.subrows) {
        if (!s.baselineProductId) continue
        const item = s.carousel.find((c) => c.productId === s.baselineProductId)
        if (item) baselines.push({ processCode: g.processCode, label: g.label, item })
      }
    }

    const parkByProcessMap = new Map<string, CompareParkSlice>()
    let totalPark = 0
    for (const b of baselines) {
      const count = b.item.count ?? 0
      totalPark += count
      const prev = parkByProcessMap.get(b.processCode)
      if (prev) prev.count += count
      else parkByProcessMap.set(b.processCode, { processCode: b.processCode, label: b.label, count })
    }

    let equipmentCost = 0
    let priceKnown = 0
    const priceTotal = baselines.length
    let anyPrice = false
    for (const b of baselines) {
      const price = b.item.product?.priceRub
      const count = b.item.count
      if (price != null && count != null) {
        equipmentCost += count * price
        priceKnown += 1
        anyPrice = true
      }
    }

    let worstReliability: Confidence | null = null
    let worstReliabilityProductId: string | null = null
    let worstReliabilityLabel: string | null = null
    for (const b of baselines) {
      const letter = reliabilityOf(b.item.productId, run.value, b.item.product, confidenceOf)
      if (!letter) continue
      if (!worstReliability || (REL_RANK[letter] ?? 99) < (REL_RANK[worstReliability] ?? 99)) {
        worstReliability = letter
        worstReliabilityProductId = b.item.productId
        worstReliabilityLabel = b.item.product?.name ?? b.item.productId
      }
    }

    const vendorFieldsWaiting = (run.value?.vendorQueries ?? []).length

    return {
      closedCount: closed.length,
      openCount: open.length,
      openLabels: open.map((g) => g.label),
      totalPark,
      parkByProcess: Array.from(parkByProcessMap.values()),
      equipmentCost: anyPrice ? equipmentCost : null,
      equipmentCostPartial: priceTotal > 0 && priceKnown < priceTotal,
      priceKnown,
      priceTotal,
      worstReliability,
      worstReliabilityProductId,
      worstReliabilityLabel,
      vendorFieldsWaiting,
      economicsStub: ECONOMICS_STUB,
    }
  })

  return {
    groups,
    summary,
    pins,
    parsePins: parseComparePins,
    serializePins: serializeComparePins,
    pinBaseline,
    clearPin,
    setActive,
    resolveParam: (
      param: ApiCompareParam,
      candidate: CalcCandidate,
      product?: Product,
    ) =>
      resolveCompareParam(
        param,
        candidate,
        product ?? productOf(candidate.productId),
        run.value,
        confidenceOf,
      ),
  }
}
