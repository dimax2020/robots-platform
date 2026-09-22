import { objectTypeLabel, type ObjectType, type Project } from '~/data/projects'
import type {
  ApiCalcResponse,
  ApiCandidate,
  ApiProject,
  ApiProjectCreate,
  ApiProjectPatch,
  ApiScenario,
  ApiSiteProfileRef,
  ApiSizedOption,
  ApiTraceStep,
  ApiVendorQuery,
} from '~/types/api'

const industryByObject: Record<ObjectType, string> = {
  warehouse: 'Логистика и торговля',
  airport: 'Транспорт',
  hospital: 'Здравоохранение',
}

export const asObjectType = (code: string): ObjectType =>
  code === 'airport' || code === 'hospital' ? code : 'warehouse'

export const isNotFound = (e: unknown) => {
  const err = e as { statusCode?: number; status?: number }
  return err?.statusCode === 404 || err?.status === 404
}

export const fetchErrorMessage = (e: unknown, fallback: string) => {
  const err = e as { data?: { detail?: unknown }; message?: string }
  const detail = err?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail)) {
    return detail.map((item) => (item as { msg?: string }).msg ?? String(item)).join('; ')
  }
  return err?.message || fallback
}

export interface CalcCandidate {
  productId: string
  processCode: string
  verdict: ApiCandidate['verdict']
  failed: string[]
  unknown: string[]
  score: number | null
}

export interface CalcOption {
  productId: string
  processCode: string
  count: number
  formula: string
  family: string
}

export interface CalcTrace {
  step: string
  productId?: string
  verdict?: ApiTraceStep['verdict']
  formula?: string
  value?: number
  unit?: string
  source?: string
  message: string
}

export interface CalcVendorQuery {
  productId: string
  productName: string
  manufacturer: string
  field: string
  sourceUrl?: string
}

export interface CalcScenario {
  code: ApiScenario['code']
  name: string
  options: CalcOption[]
  raasAvailable: boolean
}

export interface CalcRun {
  runId: string
  engineVersion: string
  catalogVersionId: number
  candidates: CalcCandidate[]
  options: CalcOption[]
  scenarios: CalcScenario[]
  vendorQueries: CalcVendorQuery[]
  trace: CalcTrace[]
}

const mapOption = (o: ApiSizedOption): CalcOption => ({
  productId: o.product_id,
  processCode: o.process_code,
  count: o.count,
  formula: o.formula,
  family: o.family,
})

const mapCandidate = (c: ApiCandidate): CalcCandidate => ({
  productId: c.product_id,
  processCode: c.process_code,
  verdict: c.verdict,
  failed: c.failed ?? [],
  unknown: c.unknown ?? [],
  score: c.score ?? null,
})

const mapTrace = (t: ApiTraceStep): CalcTrace => ({
  step: t.step,
  productId: t.product_id ?? undefined,
  verdict: t.verdict ?? undefined,
  formula: t.formula ?? undefined,
  value: t.value ?? undefined,
  unit: t.unit ?? undefined,
  source: t.source ?? undefined,
  message: t.message,
})

const mapVendor = (q: ApiVendorQuery): CalcVendorQuery => ({
  productId: q.product_id,
  productName: q.product_name,
  manufacturer: q.manufacturer,
  field: q.field,
  sourceUrl: q.source_url ?? undefined,
})

const mapScenario = (s: ApiScenario): CalcScenario => ({
  code: s.code,
  name: s.name,
  options: (s.options ?? []).map(mapOption),
  raasAvailable: s.raas_available,
})

export const mapCalcRun = (r: ApiCalcResponse): CalcRun => ({
  runId: String(r.run_id),
  engineVersion: r.engine_version,
  catalogVersionId: r.catalog_version_id,
  candidates: (r.candidates ?? []).map(mapCandidate),
  options: (r.options ?? []).map(mapOption),
  scenarios: (r.scenarios ?? []).map(mapScenario),
  vendorQueries: (r.vendor_queries ?? []).map(mapVendor),
  trace: (r.trace ?? []).map(mapTrace),
})

export const mapProject = (p: ApiProject, run?: CalcRun | null): Project => {
  const objectType = asObjectType(p.object_type_code)
  return {
    id: String(p.id),
    name: p.name,
    objectType,
    industry: industryByObject[objectType],
    updatedAt: p.updated_at ?? p.created_at ?? '',
    catalogVersion: run ? `каталог #${run.catalogVersionId}` : '—',
    modelVersion: run?.engineVersion ?? '—',
    step: run ? 2 : 1,
    area: p.site.area_m2 ?? undefined,
    shifts: p.site.shifts_per_day ?? undefined,
    tasks: p.tasks.length,
  }
}

const latestRun = async (base: string, id: string): Promise<ApiCalcResponse | null> => {
  try {
    return await $fetch<ApiCalcResponse>(`${base}/projects/${id}/runs/latest`)
  } catch (e: unknown) {
    if (isNotFound(e)) return null
    throw e
  }
}

const oneProject = async (base: string, id: string): Promise<ApiProject | null> => {
  try {
    return await $fetch<ApiProject>(`${base}/projects/${id}`)
  } catch (e: unknown) {
    if (isNotFound(e)) return null
    throw e
  }
}

/** Список сохранённых проектов текущего демо-пользователя. */
export const useProjects = () => {
  const base = useApiBase()

  const list = useAsyncData<ApiProject[]>(
    'calc-projects',
    () => $fetch(`${base}/projects`),
    { default: () => [] },
  )

  return {
    projects: computed(() => list.data.value.map((p) => mapProject(p))),
    details: computed(() => list.data.value),
    pending: computed(() => list.pending.value),
    error: computed(() => list.error.value),
    refresh: list.refresh,
    create: (body: ApiProjectCreate) =>
      $fetch<ApiProject>(`${base}/projects`, { method: 'POST', body }),
  }
}

/** Проект и последний прогон: 404 прогона — это пустота, не ошибка. */
export const useCalc = (id: MaybeRefOrGetter<string>) => {
  const base = useApiBase()
  const key = computed(() => toValue(id))

  const projectReq = useAsyncData<ApiProject | null>(
    () => `calc-project-${key.value}`,
    () => oneProject(base, key.value),
    { watch: [key] },
  )

  const runReq = useAsyncData<ApiCalcResponse | null>(
    () => `calc-run-${key.value}`,
    () => (key.value ? latestRun(base, key.value) : Promise.resolve(null)),
    { watch: [key] },
  )

  const run = computed(() => (runReq.data.value ? mapCalcRun(runReq.data.value) : null))
  const project = computed(() =>
    projectReq.data.value ? mapProject(projectReq.data.value, run.value) : undefined,
  )

  return {
    project,
    detail: computed(() => projectReq.data.value),
    run,
    pending: computed(() => projectReq.pending.value || runReq.pending.value),
    error: computed(() => projectReq.error.value || runReq.error.value),
    refresh: async () => {
      await Promise.all([projectReq.refresh(), runReq.refresh()])
    },
    update: (body: ApiProjectPatch) =>
      $fetch<ApiProject>(`${base}/projects/${key.value}`, { method: 'PATCH', body }),
    calculate: () =>
      $fetch<ApiCalcResponse>(`${base}/projects/${key.value}/calculate`, { method: 'POST' }),
  }
}

/** Справочник профиля объекта для подписей «откуда значение». */
export const useSiteProfile = (code: MaybeRefOrGetter<string>) => {
  const base = useApiBase()
  const key = computed(() => toValue(code))

  const req = useAsyncData<ApiSiteProfileRef | null>(
    () => `calc-site-profile-${key.value}`,
    async () => {
      if (!key.value) return null
      try {
        return await $fetch<ApiSiteProfileRef>(`${base}/refs/site-profiles/${key.value}`)
      } catch (e: unknown) {
        if (isNotFound(e)) return null
        throw e
      }
    },
    { watch: [key] },
  )

  return {
    profile: computed(() => req.data.value),
    pending: computed(() => req.pending.value),
    error: computed(() => req.error.value),
    refresh: req.refresh,
  }
}

export const objectTypeName = (code: string) => objectTypeLabel[asObjectType(code)] ?? code
