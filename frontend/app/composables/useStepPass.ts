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
