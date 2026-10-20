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
  const key = computed(() => `step-pass:${projectId.value}:${step}`)
  const read = () => {
    if (!import.meta.client || !projectId.value) return
    try {
      done.value = localStorage.getItem(key.value) === '1'
    } catch {
      done.value = false
    }
  }
  const markDone = () => {
    done.value = true
    if (!import.meta.client) return
    try {
      localStorage.setItem(key.value, '1')
    } catch {
      /* хранилище недоступно — первый проход просто повторится */
    }
  }
  read()
  watch(key, read)
  return { done, markDone }
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
