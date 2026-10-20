import type { Ref } from 'vue'

/**
 * Первый проход шага: процесс за процессом и в конце итог. Когда пользователь дошёл до итога, шаг считается
 * пройденным, и дальше он открывается сразу с итога — там все процессы видны разом.
 * Хранится в браузере: это удобство навигации, не данные проекта.
 */
export const STEP_SUMMARY = 'all'

/** Строка итога шага: процесс, его робот и статус. */
export interface SummaryRow {
  code: string
  name: string
  to: string
  tone: 'ok' | 'warn' | 'todo'
  image?: string | null
  robot?: string
  detail?: string
  aside?: string
}

export function useStepPass(projectId: Ref<string>, step: 'match' | 'compare' | 'economics') {
  const done = ref(false)
  /* Первый проход идёт по порядку: дальше последнего открытого процесса не прыгаем. -1 — ещё ни один не открыт. */
  const reached = ref(-1)
  const key = computed(() => `step-pass:${projectId.value}:${step}`)
  const reachKey = computed(() => `step-reach:${projectId.value}:${step}`)
  const read = () => {
    if (!import.meta.client || !projectId.value) return
    try {
      done.value = localStorage.getItem(key.value) === '1'
      reached.value = Number(localStorage.getItem(reachKey.value) ?? -1)
    } catch {
      done.value = false
    }
  }
  const progress = useProjectProgress(projectId)
  const markDone = () => {
    progress.complete(step)
    if (done.value) return
    done.value = true
    if (!import.meta.client) return
    try {
      localStorage.setItem(key.value, '1')
    } catch {
      /* хранилище недоступно — первый проход просто повторится */
    }
  }
  const reach = (index: number) => {
    if (index <= reached.value) return
    reached.value = index
    try { localStorage.setItem(reachKey.value, String(index)) } catch { /* хранилище недоступно */ }
  }
  read()
  watch(key, read)
  return { done, markDone, reached, reach }
}

/**
 * Первый проход проекта по шагам: следующий шаг открывается, когда пройден предыдущий. Дальше — свободно.
 * Демо и проекты только для просмотра не блокируются. Хранится в браузере: это порядок прохождения, не данные проекта.
 */
export const STEP_ORDER = ['params', 'match', 'compare', 'economics', 'what-if', 'plan', 'report'] as const
export function useProjectProgress(projectId: Ref<string>) {
  const state = useState<Record<string, number>>('project-progress', () => ({}))
  const key = computed(() => `project-progress:${projectId.value}`)
  /* Сколько шагов открыто: 1 — только параметры. Уже пройденные раньше подбор, сравнение и экономика тоже засчитываются. */
  const read = () => {
    if (!import.meta.client || !projectId.value || state.value[projectId.value] != null) return
    let open = 1
    try {
      open = Math.max(1, Number(localStorage.getItem(key.value) ?? 1) || 1)
      for (const [index, step] of (['match', 'compare', 'economics'] as const).entries()) {
        if (localStorage.getItem(`step-pass:${projectId.value}:${step}`) === '1') open = Math.max(open, index + 3)
      }
    } catch { /* без хранилища — с начала */ }
    state.value = { ...state.value, [projectId.value]: open }
  }
  read()
  watch(key, read)
  const open = computed(() => state.value[projectId.value] ?? 1)
  const save = (value: number) => {
    const next = Math.min(STEP_ORDER.length, Math.max(open.value, value))
    if (next === open.value) return
    state.value = { ...state.value, [projectId.value]: next }
    try { localStorage.setItem(key.value, String(next)) } catch { /* хранилище недоступно */ }
  }
  /** Шаг пройден — открываем следующий. */
  const complete = (code: (typeof STEP_ORDER)[number]) => save(STEP_ORDER.indexOf(code) + 2)
  const isOpen = (code: string) => STEP_ORDER.indexOf(code as (typeof STEP_ORDER)[number]) + 1 <= open.value
  return { open, complete, isOpen }
}

/**
 * Процесс, на котором пользователь сейчас, — общий для подбора, сравнения и экономики. Перешёл со «Перевозки паллет»
 * в подборе на шаг сравнения — там откроется та же «Перевозка паллет». Итог шага хранится как STEP_SUMMARY.
 */
export function useProcessFocus(projectId: Ref<string>) {
  const focus = useState<Record<string, string>>('process-focus', () => ({}))
  const key = computed(() => `process-focus:${projectId.value}`)
  if (import.meta.client && projectId.value && focus.value[projectId.value] == null) {
    try { focus.value = { ...focus.value, [projectId.value]: sessionStorage.getItem(key.value) ?? '' } } catch { /* без хранилища — только в пределах вкладки */ }
  }
  const current = computed(() => focus.value[projectId.value] ?? '')
  const set = (code: string) => {
    if (!projectId.value || focus.value[projectId.value] === code) return
    focus.value = { ...focus.value, [projectId.value]: code }
    try { sessionStorage.setItem(key.value, code) } catch { /* хранилище недоступно */ }
  }
  /**
   * Что открыть, если в адресе процесса нет: запомненный процесс, если он есть на этом шаге;
   * итог — только если шаг уже пройден; иначе первый процесс (первый проход идёт по порядку).
   */
  const pick = (codes: string[], done: boolean, summary: string) => {
    const remembered = current.value
    if (remembered && remembered !== STEP_SUMMARY && codes.includes(remembered)) return remembered
    if (done) return summary
    return codes[0] ?? summary
  }
  return { current, set, pick }
}
