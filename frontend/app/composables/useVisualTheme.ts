/** Ключ и класс должны совпадать со скриптом в nuxt.config (он ставит класс до первой отрисовки). */
export const VISUAL_KEY = 'visual-rich'
export const VISUAL_LITE_CLASS = 'visual-lite'

const SOFTWARE_GPU = /swiftshader|llvmpipe|softpipe|software|basic render/i

export function detectGpu(): boolean {
  try {
    const canvas = document.createElement('canvas')
    const gl = canvas.getContext('webgl', { failIfMajorPerformanceCaveat: true })
    if (!gl) return false
    let ok = true
    const info = gl.getExtension('WEBGL_debug_renderer_info')
    if (info) {
      const renderer = String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL) || '')
      if (SOFTWARE_GPU.test(renderer)) ok = false
    }
    gl.getExtension('WEBGL_lose_context')?.loseContext()
    return ok
  } catch {
    return false
  }
}

/** true — красивая тема. Если выбора ещё нет, смотрим видеокарту и записываем его. */
export function readRich(): boolean {
  try {
    const stored = localStorage.getItem(VISUAL_KEY)
    if (stored === '1' || stored === '0') return stored === '1'
    const rich = detectGpu()
    localStorage.setItem(VISUAL_KEY, rich ? '1' : '0')
    return rich
  } catch {
    return true
  }
}

export function applyRich(rich: boolean) {
  document.documentElement.classList.toggle(VISUAL_LITE_CLASS, !rich)
}

export function useVisualTheme() {
  const rich = useState(VISUAL_KEY, () => true)

  onMounted(() => {
    rich.value = readRich()
    applyRich(rich.value)
  })

  const toggleRich = () => {
    rich.value = !rich.value
    try { localStorage.setItem(VISUAL_KEY, rich.value ? '1' : '0') } catch { /* приватный режим */ }
    applyRich(rich.value)
  }

  return { rich, toggleRich }
}
