<script setup lang="ts">
import {
  PhArrowCounterClockwise, PhArrowRight, PhArrowsDownUp, PhArrowUUpLeft, PhArrowUUpRight, PhCaretDown, PhCheckCircle, PhCursor, PhDownloadSimple, PhElevator, PhEye, PhEyeClosed, PhEyeSlash,
  PhHand, PhImage, PhLineSegments, PhLockSimple, PhLockSimpleOpen, PhMagicWand, PhMagnet, PhMapPin, PhPause, PhPencilSimple, PhPlay, PhPlus, PhPolygon, PhRuler, PhSquare, PhStairs, PhTrash, PhUploadSimple, PhWarning, PhCheck, PhCursorClick, PhDotsSixVertical, PhX,
} from '@phosphor-icons/vue'
import type PlanEditor from '~/components/PlanEditor.vue'
import type { EditorMode, EditorTool, PlanSelection } from '~/components/PlanEditor.vue'
import { fetchErrorMessage } from '~/utils/errors'
import { platformGet, platformSend, usePlatformBase } from '~/composables/usePlatform'
import { usePlatformCompare, type MatchGroup } from '~/composables/usePlatformCompare'
import { PRELIMINARY, usePlatformEconomy } from '~/composables/usePlatformEconomy'
import { Simulation } from '~/sim/engine'
import { floorBounds } from '~/sim/grid'
import { autoCount, buildProcess, clearProcess, emptyLayout, fitFloorToOutline, newFloor, normalizeLayout, placedCount, placeProcess, placeShell, processReady, rectOutline, ROLE_KIND, uid } from '~/sim/templates'
import type { ItemRole, Layout, LayoutGuide, LayoutItem, LinkKind, LoadMode, ProcessSettings, RobotView, SimConfig, SimProcess, SimStats, StationKind, Visibility } from '~/sim/types'
import type { WorkerResponse } from '~/sim/worker'

const route = useRoute()
const id = computed(() => route.params.id as string)
const { project, isDemo, readonly, source, pending, error } = usePlatformEconomy(id)
const { remainingHit, skipReason } = usePlatformCompare(id)
useHead({ title: () => `Визуализация · ${project.value?.name ?? 'проект'}` })

const PALETTE = ['#1f7a5a', '#175fb0', '#b2582b', '#6b5bd6', '#c0417a', '#2f8f9d', '#8a6d1d', '#4f6b2a']
const SAMPLE_PLAN = '/plans/floor-sample.svg'
type GroupWithItems = MatchGroup & { layout_items?: LayoutItem[] }

const editor = ref<InstanceType<typeof PlanEditor> | null>(null)
const groups = ref<GroupWithItems[]>([])
const layout = ref<Layout | null>(null)
const platformId = ref('')
const loadError = ref('')
const loading = ref(false)
const floorId = ref('')
const tool = ref<EditorTool>('select')
const selection = ref<PlanSelection[]>([])
const focusRobot = ref<number | null>(null)
const toolProcess = ref('')
const stationKind = ref<StationKind>('load')
const stationItem = ref('')
const linkKind = ref<LinkKind>('elevator')
const pendingLink = ref('')
const calibrateMeters = ref(10)
const snapOn = ref(true)
const hint = ref('')
const zoomPct = ref(100)
const saveState = ref<'idle' | 'pending' | 'saving' | 'saved' | 'error'>('idle')
const panels = reactive({ nav: true, monitor: true, props: true })
/* Просмотр: схема спит, пока по ней не кликнут, чтобы колесо прокручивало страницу, а не карту. */
const awake = ref(false)
/* Меню «Добавить объект» в режиме роботов. */
const addOpen = ref(false)
/* Редактор открывается поверх страницы на весь экран; на странице остаётся просмотр, монитор и пуск. */
const editing = ref(false)
const openEditor = (phase?: LayoutGuide['phase']) => {
  pause()
  editing.value = true
  document.body.style.overflow = 'hidden'
  const target = phase ?? (guide.value.phase === 'process' || guide.value.phase === 'building' ? guide.value.phase : 'building')
  if (target === 'process' && guide.value.process) openStage('process', guide.value.process)
  else openStage(target === 'process' ? 'building' : target)
  panels.nav = true
  panels.props = true
  nextTick(() => editor.value?.fitContent())
}
const closeEditor = () => {
  editing.value = false
  addOpen.value = false
  awake.value = false
  document.body.style.overflow = ''
  selection.value = []
  pendingLink.value = ''
  tool.value = 'select'
  setGuide({ phase: 'ready', process: '' })
  panels.monitor = true
  nextTick(() => { editor.value?.fitContent(); resetSim(); scheduleCheck(50) })
}
const propsTitle = computed(() => {
  if (pickedArea.value) return 'Участок пола'
  if (pickedBg.value) return 'Чертёж'
  if (pickedStation.value) return 'Станция'
  if (pickedBlock.value) return 'Препятствие'
  if (pickedZone.value) return 'Зона'
  if (pickedWall.value) return 'Стена'
  if (pickedLink.value) return pickedLink.value.name
  if (selection.value.length > 1) return `Выбрано ${selection.value.length}`
  return mode.value === 'building' ? 'Здание' : 'Роботы'
})
const loadMode = ref<LoadMode>('normal')
const peak = ref(1.5)
const failurePct = ref(20)
const playing = ref(false)
const speed = ref(20)
const live = ref<SimStats | null>(null)
const check = ref<WorkerResponse | null>(null)
const checking = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)
interface TripRow { id: number; process: string; floor: string; from: string; to: string; leftM: number; totalM: number }
const trips = ref<TripRow[]>([])

const site = computed<Record<string, unknown>>(() => (source.value?.site ?? {}) as Record<string, unknown>)
const shiftHours = computed(() => Number(site.value.shift_hours) || 8)

/* Процессы: робот из сравнения, объекты на схеме из настройки процесса. */
const skipped = computed(() => groups.value.flatMap((group) => {
  const reason = skipReason(group)
  return reason ? [{ code: group.process_code, name: group.process_name, reason }] : []
}))
const processes = computed<SimProcess[]>(() => groups.value.filter((group) => !skipReason(group)).map((group) => {
  const hit = remainingHit(group)
  const robot = hit ? { name: hit.name, count: hit.count ?? null, specs: hit.specs ?? [] } : null
  return buildProcess(group.process_code, group.process_name, robot, site.value, group.layout_items ?? [])
}))
const byCode = computed(() => Object.fromEntries(processes.value.map((proc) => [proc.code, proc])))
const colors = computed(() => Object.fromEntries(processes.value.map((proc, index) => [proc.code, PALETTE[index % PALETTE.length]!])))
const floor = computed(() => layout.value?.floors.find((item) => item.id === floorId.value))
const floorSize = computed(() => floor.value ? floorBounds(floor.value) : null)
const stageProcesses = computed(() => processes.value.filter((proc) => proc.items.length))

const settingsOf = (code: string): ProcessSettings => layout.value?.processes?.[code] ?? { visibility: 'full', robots: true }
const visibility = computed(() => Object.fromEntries(processes.value.map((proc) => [proc.code, settingsOf(proc.code).visibility])) as Record<string, Visibility>)
const setSettings = (code: string, patch: Partial<ProcessSettings>) => {
  if (!layout.value) return
  layout.value.processes = { ...(layout.value.processes ?? {}), [code]: { ...settingsOf(code), ...patch } }
  commit('Настройка процесса')
}
const cycleVisibility = (code: string) => {
  const order: Visibility[] = ['full', 'dim', 'hidden']
  setSettings(code, { visibility: order[(order.indexOf(settingsOf(code).visibility) + 1) % 3]! })
}
const visIcon = (code: string) => ({ full: PhEye, dim: PhEyeClosed, hidden: PhEyeSlash }[settingsOf(code).visibility])
const active = computed(() => processes.value.filter((proc) => proc.kind !== 'none' && settingsOf(proc.code).robots && settingsOf(proc.code).visibility !== 'hidden' && layout.value && processReady(layout.value, proc)))

/* Стадии. Режим холста: «Здание» — пол, препятствия, лифты; «Роботы» — объекты процессов и смена. */
const guide = computed<LayoutGuide>(() => layout.value?.guide ?? { phase: 'intro', process: '' })
const mode = computed<EditorMode>(() => (guide.value.phase === 'building' ? 'building' : 'robots'))
const stageProc = computed(() => byCode.value[guide.value.process] ?? null)
const stageIndex = computed(() => stageProcesses.value.findIndex((proc) => proc.code === guide.value.process))
const stageReady = (proc: SimProcess) => Boolean(layout.value && processReady(layout.value, proc))
const readyCount = computed(() => stageProcesses.value.filter(stageReady).length)
const floorReady = computed(() => Boolean(floor.value && floor.value.areas.some((area) => area.points.length >= 6)))
const buildingTasks = computed(() => {
  const floors = layout.value?.floors ?? []
  const several = floors.length > 1
  const links = layout.value?.links ?? []
  const complete = links.every((link) => link.stops.length >= 2)
  return [
    { id: 'floor', done: floorReady.value, title: 'Пол', text: 'Растяните прямоугольник или обведите углы. Несколько участков с наложением дают проход между ними. Стены — по границе, сами.', tool: 'floor' as EditorTool },
    { id: 'plan', done: Boolean(bg.value), title: 'Чертёж под сетку', text: 'Необязательно. Пожарная схема или план БТИ с прозрачностью и масштабом.', tool: 'select' as EditorTool, optional: true },
    { id: 'blocks', done: floors.some((f) => f.blocks.length > 0), title: 'Препятствия', text: 'Стеллажи, колонны, оборудование. Робот их объезжает.', tool: 'block' as EditorTool },
    { id: 'links', done: !several || (links.length > 0 && complete), title: several ? 'Лифт или лестница' : 'Переходы', text: several ? (complete ? 'Поставьте на одном этаже, затем укажите выход на другом.' : 'У перехода не указан второй конец: переключите этаж и кликните, где он выходит.') : 'Этаж один, переход не нужен. Появится, когда добавите этаж.', tool: 'link' as EditorTool },
  ]
})
const buildingReady = computed(() => buildingTasks.value.filter((task) => !task.optional).every((task) => task.done))
interface ItemTask { item: LayoutItem; need: number; have: number; auto: number; done: boolean }
const itemTasks = computed<ItemTask[]>(() => {
  const proc = stageProc.value
  if (!proc || !layout.value) return []
  return proc.items.map((item) => {
    const need = Math.max(item.role === 'waypoint' ? 2 : 1, item.min_count)
    const have = placedCount(layout.value!, proc.code, item)
    return { item, need, have, auto: autoCount(item, proc), done: have >= need }
  })
})
const setGuide = (next: LayoutGuide) => {
  if (!layout.value) return
  layout.value.guide = next
  /* Снимок истории держим в актуальном состоянии, иначе следующая правка запишет устаревшую стадию. */
  snapshot = JSON.stringify(layout.value)
  void scheduleSave()
}
const openStage = (phase: LayoutGuide['phase'], process = '') => {
  setGuide({ phase, process })
  selection.value = []
  pendingLink.value = ''
  addOpen.value = false
  tool.value = phase === 'building' && !floorReady.value ? 'floor' : 'select'
  if (process) {
    toolProcess.value = process
    const first = byCode.value[process]?.items[0]
    if (first) stationItem.value = first.key
    tool.value = 'select'
  }
}
const openMode = (next: EditorMode) => {
  if (next === 'building') return openStage('building')
  if (guide.value.phase === 'process') return
  const first = stageProcesses.value.find((proc) => !stageReady(proc)) ?? stageProcesses.value[0]
  first ? openStage('process', first.code) : openStage('building')
}
const pickItem = (item: LayoutItem, process = guide.value.process || toolProcess.value) => {
  if (process) toolProcess.value = process
  stationItem.value = item.key
  addOpen.value = false
  selection.value = []
  if (item.role === 'work_zone') tool.value = 'zone'
  else if (item.role === 'obstacle') tool.value = 'block'
  else {
    stationKind.value = ROLE_KIND[item.role] ?? 'load'
    tool.value = 'station'
  }
}
/* Объект, который сейчас ставим кликом: показываем чипом под панелью инструментов. */
const armedItem = computed(() => {
  if (!['station', 'zone', 'block'].includes(tool.value) || mode.value !== 'robots') return null
  return byCode.value[toolProcess.value]?.items.find((row) => row.key === stationItem.value) ?? null
})
const menuItems = computed(() => {
  const proc = byCode.value[toolProcess.value]
  if (!proc || !layout.value) return []
  return proc.items.map((item) => {
    const need = Math.max(item.role === 'waypoint' ? 2 : 1, item.min_count)
    return { item, need, have: placedCount(layout.value!, proc.code, item) }
  })
})
const onDragItem = (event: DragEvent, item: LayoutItem) => {
  event.dataTransfer?.setData('text/plain', JSON.stringify({ process: toolProcess.value, key: item.key }))
  if (event.dataTransfer) event.dataTransfer.effectAllowed = 'copy'
  addOpen.value = false
}
const onCanvasPointer = (event: PointerEvent) => {
  if (!addOpen.value) return
  const target = event.target as HTMLElement | null
  if (target?.closest('.add-menu, .tb.add')) return
  addOpen.value = false
}
const onDropItem = (event: DragEvent) => {
  const raw = event.dataTransfer?.getData('text/plain')
  if (!raw) return
  let data: { process?: string; key?: string } = {}
  try { data = JSON.parse(raw) } catch { return }
  const item = data.process ? byCode.value[data.process]?.items.find((row) => row.key === data.key) : undefined
  if (!item || !data.process) return
  editor.value?.dropItem(event.clientX, event.clientY, { process: data.process, item })
}
const nextStage = () => {
  const next = stageProcesses.value[guide.value.phase === 'building' ? 0 : stageIndex.value + 1]
  if (next) openStage('process', next.code)
  else closeEditor()
}
const prevStage = () => {
  if (guide.value.phase === 'process') return stageIndex.value <= 0 ? openStage('building') : openStage('process', stageProcesses.value[stageIndex.value - 1]!.code)
  openStage('building')
}
const stageTitle = computed(() => ({ intro: '', building: 'Здание и этажи', process: stageProc.value?.name ?? '', ready: 'Просмотр' }[guide.value.phase]))
const stageNumber = computed(() => {
  if (guide.value.phase === 'building') return 'Стадия 0'
  if (guide.value.phase === 'process') return `Стадия ${stageIndex.value + 1} из ${stageProcesses.value.length}`
  return `${readyCount.value} из ${stageProcesses.value.length} процессов готовы`
})

/* Автоматика. */
const autoShell = () => { if (!layout.value) return; placeShell(layout.value); commit('Каркас автоматически'); editor.value?.fitContent() }
const autoStage = (proc = stageProc.value) => {
  if (!layout.value || !proc) return
  clearProcess(layout.value, proc.code)
  placeProcess(layout.value, floorId.value, proc, site.value)
  commit(`${proc.name}: автоматически`)
  editor.value?.fitContent()
}
const autoAll = () => {
  if (!layout.value) return
  if (!buildingReady.value) placeShell(layout.value)
  for (const proc of stageProcesses.value) {
    if (stageReady(proc)) continue
    clearProcess(layout.value, proc.code)
    placeProcess(layout.value, floorId.value, proc, site.value)
  }
  commit('Собрано автоматически')
  editor.value?.fitContent()
}
const useSamplePlan = () => {
  const f = floor.value
  if (!f) return
  const bounds = floorBounds(f)
  const mpp = bounds.width / 1200
  f.background = { url: SAMPLE_PLAN, x: bounds.minX, y: bounds.minY, mpp, opacity: 0.75, width: 1200, height: 760, locked: false }
  commit('Тестовый чертёж')
  selection.value = [{ kind: 'background', id: 'bg' }]
  editor.value?.fit()
}

/* История. */
const past = ref<string[]>([])
const future = ref<string[]>([])
const lastLabel = ref('')
let snapshot = ''
const plain = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T
const commit = (label: string) => {
  if (!layout.value) return
  if (snapshot) {
    past.value.push(snapshot)
    if (past.value.length > 100) past.value.shift()
  }
  future.value = []
  snapshot = JSON.stringify(layout.value)
  lastLabel.value = label
  editor.value?.render()
  afterChange()
}
const undo = () => {
  const prev = past.value.pop()
  if (!prev || !layout.value) return
  future.value.push(JSON.stringify(layout.value))
  /* Стадия не входит в историю: откат схемы не должен возвращать пользователя на вводный экран. */
  const guideNow = layout.value.guide
  layout.value = { ...(JSON.parse(prev) as Layout), guide: guideNow }
  snapshot = JSON.stringify(layout.value)
  lastLabel.value = ''
  selection.value = []
  ensureFloor()
  nextTick(() => editor.value?.render())
  afterChange()
}
const redo = () => {
  const next = future.value.pop()
  if (!next || !layout.value) return
  past.value.push(JSON.stringify(layout.value))
  const guideNow = layout.value.guide
  layout.value = { ...(JSON.parse(next) as Layout), guide: guideNow }
  snapshot = JSON.stringify(layout.value)
  selection.value = []
  ensureFloor()
  nextTick(() => editor.value?.render())
  afterChange()
}
const ensureFloor = () => {
  if (layout.value && !layout.value.floors.some((f) => f.id === floorId.value)) floorId.value = layout.value.floors[0]?.id ?? ''
}
const onKey = (event: KeyboardEvent) => {
  const target = event.target as HTMLElement | null
  if (target && ['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName)) return
  if (!editing.value) return
  const meta = event.metaKey || event.ctrlKey
  if (meta && event.key.toLowerCase() === 'z') { event.preventDefault(); event.shiftKey ? redo() : undo(); return }
  if (meta && event.key.toLowerCase() === 'y') { event.preventDefault(); redo(); return }
  if (meta && event.key.toLowerCase() === 'd') { event.preventDefault(); duplicate(); return }
  if ((event.key === 'Delete' || event.key === 'Backspace') && selection.value.length && tool.value === 'select') { event.preventDefault(); removeSelected(); return }
  if (event.key === 'Escape' && addOpen.value) { addOpen.value = false; return }
  if (event.key === 'Escape' && mode.value === 'robots' && tool.value !== 'select' && tool.value !== 'hand') { tool.value = 'select'; return }
  if (event.key === 'Escape' && !selection.value.length && tool.value === 'select' && !pendingLink.value) { closeEditor(); return }
  if (meta) return
  const keys: Record<string, EditorTool> = mode.value === 'building'
    ? { v: 'select', h: 'hand', f: 'floor', r: 'block', l: 'link' }
    : { v: 'select', h: 'hand', z: 'zone', s: 'station' }
  const picked = keys[event.key.toLowerCase()]
  if (picked) tool.value = picked
}
onMounted(() => window.addEventListener('keydown', onKey))
onBeforeUnmount(() => { window.removeEventListener('keydown', onKey); pause(); worker?.terminate(); document.body.style.overflow = '' })

/* Загрузка и сохранение. */
const loadAll = async () => {
  if (import.meta.server || !source.value) return
  loading.value = true
  loadError.value = ''
  try {
    platformId.value = id.value
    const [match, stored] = await Promise.all([
      platformSend<{ groups: GroupWithItems[] }>(`/projects/${platformId.value}/match`, 'POST', { site: source.value.site }),
      platformGet<{ layout: Partial<Layout> }>(`/projects/${platformId.value}/layout`),
    ])
    groups.value = match.groups
    layout.value = stored.layout?.floors?.length ? normalizeLayout(stored.layout as Partial<Layout> & Record<string, unknown>) : emptyLayout(site.value)
    if (layout.value.guide && layout.value.guide.phase !== 'intro') layout.value.guide = { phase: 'ready', process: layout.value.guide.process }
    floorId.value = layout.value.floors[0]?.id ?? ''
    toolProcess.value = guide.value.process || (stageProcesses.value[0]?.code ?? '')
    peak.value = Number(site.value.peak_factor) > 1 ? Number(site.value.peak_factor) : 1.5
    snapshot = JSON.stringify(layout.value)
    past.value = []
    future.value = []
    resetSim()
    scheduleCheck(50)
  } catch (err: unknown) {
    loadError.value = fetchErrorMessage(err, 'Не удалось открыть схему')
  } finally {
    loading.value = false
  }
}
onMounted(() => { void loadAll() })
watch(() => JSON.stringify(source.value ?? null), () => { void loadAll() })

let saveTimer: ReturnType<typeof setTimeout> | undefined
const save = async () => {
  if (!layout.value || !platformId.value) return
  saveState.value = 'saving'
  try {
    await platformSend(`/projects/${platformId.value}/layout`, 'PUT', { layout: plain(layout.value) })
    saveState.value = 'saved'
  } catch {
    saveState.value = 'error'
  }
}
const scheduleSave = () => {
  /* Опубликованное демо у гостя и пользователя не сохраняется: смотрим, но не пишем. */
  if (readonly.value) { saveState.value = 'idle'; return }
  if (saveTimer) clearTimeout(saveTimer)
  saveState.value = 'pending'
  saveTimer = setTimeout(() => { void save() }, 700)
}
const afterChange = () => {
  scheduleSave()
  resetSim()
  scheduleCheck()
}
/** Изменение из редактора: он уже поменял данные, нам остаётся записать историю. */
const onEditorChange = (label: string) => commit(label)

/* Симуляция. */
const config = (): SimConfig | null => {
  if (!layout.value || !active.value.length) return null
  return { layout: plain(layout.value), processes: plain(active.value), mode: loadMode.value, peak: peak.value, failureShare: failurePct.value / 100, durationS: shiftHours.value * 3600, seed: 20260926 }
}
let sim: Simulation | null = null
let timer: ReturnType<typeof setTimeout> | undefined
let last = 0
let lastStats = 0
const views: RobotView[] = []
const liveQueue = ref(0)

/* Живые параметры и графики смены. */
const liveLoad = ref(100)
const liveOffline = ref(0)
const SAMPLE_S = 20
interface Sample { t: number; rate: number; backlog: number; util: number; active: number; queued: number; rates: Record<string, number> }
const samples = ref<Sample[]>([])
let lastSample: { t: number; done: Record<string, number> } | null = null
const resetMonitor = () => {
  samples.value = []
  lastSample = null
  liveOffline.value = 0
  liveLoad.value = 100
}
const sampleStats = (stats: SimStats) => {
  const done: Record<string, number> = {}
  for (const row of stats.processes) done[row.code] = row.done
  if (!lastSample) { lastSample = { t: stats.timeS, done }; return }
  if (stats.timeS - lastSample.t < SAMPLE_S) return
  const hours = (stats.timeS - lastSample.t) / 3600
  const rates: Record<string, number> = {}
  let rate = 0
  for (const row of stats.processes) {
    const value = Math.max(0, (row.done - (lastSample.done[row.code] ?? 0)) / hours)
    rates[row.code] = value
    if (row.unit !== 'м²') rate += value
  }
  const activeRobots = stats.processes.reduce((acc, row) => acc + row.active, 0)
  const sample: Sample = {
    t: stats.timeS,
    rate,
    backlog: stats.processes.reduce((acc, row) => acc + row.backlog, 0),
    util: activeRobots ? stats.processes.reduce((acc, row) => acc + row.utilization * row.active, 0) / activeRobots * 100 : 0,
    active: activeRobots,
    queued: stats.processes.reduce((acc, row) => acc + row.queued, 0),
    rates,
  }
  samples.value = [...samples.value.slice(-179), sample]
  lastSample = { t: stats.timeS, done }
}
const setLiveLoad = (raw: number) => {
  liveLoad.value = raw
  sim?.setLoadFactor(raw / 100)
}
const setLiveOffline = (raw: number) => {
  const total = liveRobots.value
  liveOffline.value = Math.max(0, Math.min(total, raw))
  sim?.setOffline(liveOffline.value)
  editor.value?.drawRobots(sim?.views(views) ?? [])
  if (sim) live.value = sim.stats()
}
const breakRandom = () => {
  if (!sim) return
  const id = sim.breakOne()
  if (id != null) { liveOffline.value = sim.offline; focusRobot.value = id }
  editor.value?.drawRobots(sim.views(views))
  live.value = sim.stats()
}
const repairAll = () => setLiveOffline(0)
const requiredNow = computed(() => (live.value?.processes ?? []).filter((row) => row.unit !== 'м²').reduce((acc, row) => acc + row.requiredPerHour, 0))
const series = (key: keyof Omit<Sample, 't' | 'rates'>) => samples.value.map((sample) => sample[key])
const processSeries = computed(() => active.value.filter((proc) => proc.kind === 'transport' || proc.kind === 'patrol').map((proc) => ({ points: samples.value.map((sample) => sample.rates[proc.code] ?? 0), color: colors.value[proc.code], label: proc.name })))
const resetSim = () => {
  pause()
  sim = null
  live.value = null
  trips.value = []
  resetMonitor()
  editor.value?.clearRobots()
  const cfg = config()
  if (!cfg) return
  try {
    sim = new Simulation(cfg)
    if (!editing.value) editor.value?.drawRobots(sim.views(views))
    live.value = sim.stats()
  } catch {
    sim = null
  }
}
const frame = () => {
  if (!playing.value || !sim) return
  const now = performance.now()
  const dt = last ? Math.min(1, (now - last) / 1000) : 0
  last = now
  sim.advance(sim.time + dt * speed.value)
  editor.value?.drawRobots(sim.views(views))
  if (now - lastStats > 250 || sim.finished) {
    live.value = sim.stats()
    sampleStats(live.value)
    liveQueue.value = views.filter((view) => view.status === 'queue').length
    trips.value = views.flatMap((view) => view.trip ? [{ id: view.id, process: view.process, floor: view.floor, from: view.trip.from, to: view.trip.to, leftM: view.trip.leftM, totalM: view.trip.totalM }] : [])
    lastStats = now
  }
  if (sim.finished) { playing.value = false; return }
  timer = setTimeout(frame, 16)
}
const play = () => {
  if (!sim || sim.finished) resetSim()
  if (!sim) return
  playing.value = true
  last = 0
  panels.monitor = true
  timer = setTimeout(frame, 0)
}
function pause() {
  playing.value = false
  if (timer) clearTimeout(timer)
  timer = undefined
}
const restart = () => { resetSim(); play() }
watch([loadMode, peak, failurePct], () => { resetSim(); scheduleCheck() })
watch(floorId, () => { if (sim && !editing.value) editor.value?.drawRobots(sim.views(views)) })
const onEditorReady = () => { if (sim && !editing.value) editor.value?.drawRobots(sim.views(views)) }

let worker: Worker | null = null
let requestId = 0
let checkTimer: ReturnType<typeof setTimeout> | undefined
const scheduleCheck = (delay = 900) => {
  if (checkTimer) clearTimeout(checkTimer)
  checkTimer = setTimeout(runCheck, delay)
}
const runCheck = () => {
  const cfg = config()
  if (!cfg || import.meta.server) { check.value = null; return }
  worker ??= new Worker(new URL('../../../sim/worker.ts', import.meta.url), { type: 'module' })
  const mine = ++requestId
  checking.value = true
  worker.onmessage = (event: MessageEvent<WorkerResponse>) => {
    if (event.data.id !== requestId) return
    check.value = event.data
    checking.value = false
  }
  worker.postMessage({ id: mine, config: cfg })
}

/* Этажи. */
const addFloor = () => {
  if (!layout.value) return
  const base = floor.value ?? layout.value.floors[0]
  const created = newFloor(`${layout.value.floors.length + 1} этаж`, base?.width ?? 60, base?.height ?? 40, base ? base.areas.map((area) => ({ id: uid('ar'), points: [...area.points] })) : undefined)
  layout.value.floors.push(created)
  floorId.value = created.id
  commit('Новый этаж')
  if (guide.value.phase !== 'building') openStage('building')
  nextTick(() => editor.value?.fit())
}
const removeFloor = () => {
  if (!layout.value || layout.value.floors.length <= 1 || !floor.value) return
  if (!confirm(`Удалить «${floor.value.name}» со всем содержимым?`)) return
  const fid = floorId.value
  layout.value.floors = layout.value.floors.filter((item) => item.id !== fid)
  for (const link of layout.value.links) link.stops = link.stops.filter((stop) => stop.floor !== fid)
  layout.value.links = layout.value.links.filter((link) => link.stops.length > 0)
  floorId.value = layout.value.floors[0]!.id
  commit('Этаж удалён')
}
const renameFloor = (raw: string) => { if (floor.value && raw.trim()) { floor.value.name = raw.trim(); commit('Имя этажа') } }
const setRectFloor = (key: 'w' | 'h', raw: string) => {
  const f = floor.value
  const value = Math.round(Number(raw))
  if (!f || !Number.isFinite(value) || value < 4 || value > 600) return
  const b = floorBounds(f)
  const w = key === 'w' ? value : Math.round(b.width)
  const h = key === 'h' ? value : Math.round(b.height)
  f.areas = [{ id: f.areas[0]?.id ?? uid('ar'), points: rectOutline(w, h) }]
  fitFloorToOutline(f)
  commit('Размер пола')
  editor.value?.fit()
}
const isRectFloor = computed(() => floor.value?.areas.length === 1 && floor.value.areas[0]!.points.length === 8)
const pickedArea = computed(() => single.value?.kind === 'area' ? floor.value?.areas.find((i) => i.id === single.value?.id) ?? null : null)
const areaSize = computed(() => {
  const a = pickedArea.value
  if (!a) return null
  const xs = a.points.filter((_, i) => i % 2 === 0)
  const ys = a.points.filter((_, i) => i % 2 === 1)
  const w = Math.max(...xs) - Math.min(...xs)
  const h = Math.max(...ys) - Math.min(...ys)
  let area = 0
  for (let i = 0, j = a.points.length - 2; i < a.points.length; j = i, i += 2) area += a.points[j]! * a.points[i + 1]! - a.points[i]! * a.points[j + 1]!
  return { w, h, area: Math.abs(area) / 2 }
})

/* Чертёж. */
const uploadBackground = async (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0]
  const f = floor.value
  if (!file || !f || !platformId.value) return
  const body = new FormData()
  body.append('file', file)
  try {
    const result = await $fetch<{ name: string }>(`${usePlatformBase()}/projects/${platformId.value}/layout/background`, { method: 'POST', body, credentials: 'include' })
    const url = `${usePlatformBase()}/layout-files/${result.name}`
    const img = new window.Image()
    img.onload = () => {
      const b = floorBounds(f)
      f.background = { url, x: b.minX, y: b.minY, mpp: b.width / img.naturalWidth, opacity: 0.6, width: img.naturalWidth, height: img.naturalHeight, locked: false }
      commit('Чертёж загружен')
      selection.value = [{ kind: 'background', id: 'bg' }]
      tool.value = 'calibrate'
    }
    img.src = url
  } catch (err: unknown) {
    hint.value = fetchErrorMessage(err, 'Не удалось загрузить чертёж')
  } finally {
    if (fileInput.value) fileInput.value.value = ''
  }
}
const bg = computed(() => floor.value?.background ?? null)
const bgWidthM = computed(() => bg.value ? bg.value.width * bg.value.mpp : 0)
const setBgWidth = (raw: string) => {
  const value = Number(raw)
  if (!bg.value || !Number.isFinite(value) || value <= 0) return
  bg.value.mpp = value / bg.value.width
  commit('Масштаб чертежа')
}
const onCalibrated = (factor: number) => {
  hint.value = `Масштаб чертежа уточнён ×${factor.toLocaleString('ru-RU', { maximumFractionDigits: 3 })}: ${calibrateMeters.value} м на плане равны ${calibrateMeters.value} клеткам.`
}

/* Выделение и свойства. */
const single = computed(() => selection.value.length === 1 ? selection.value[0]! : null)
const pickedStation = computed(() => single.value?.kind === 'station' ? floor.value?.stations.find((i) => i.id === single.value?.id) ?? null : null)
const pickedBlock = computed(() => single.value?.kind === 'block' ? floor.value?.blocks.find((i) => i.id === single.value?.id) ?? null : null)
const pickedZone = computed(() => single.value?.kind === 'zone' ? floor.value?.zones.find((i) => i.id === single.value?.id) ?? null : null)
const pickedWall = computed(() => single.value?.kind === 'wall' ? floor.value?.walls.find((i) => i.id === single.value?.id) ?? null : null)
const pickedLink = computed(() => single.value?.kind === 'link' ? layout.value?.links.find((i) => i.id === single.value?.id) ?? null : null)
const pickedBg = computed(() => single.value?.kind === 'background' ? bg.value : null)
const edit = (label: string) => commit(label)
const num = (event: Event) => Number((event.target as HTMLInputElement).value)
const removeSelected = () => {
  const current = layout.value
  const f = floor.value
  if (!current || !f || !selection.value.length) return
  for (const sel of selection.value) {
    if (sel.kind === 'station') f.stations = f.stations.filter((i) => i.id !== sel.id)
    if (sel.kind === 'block') f.blocks = f.blocks.filter((i) => i.id !== sel.id)
    if (sel.kind === 'zone') f.zones = f.zones.filter((i) => i.id !== sel.id)
    if (sel.kind === 'wall') f.walls = f.walls.filter((i) => i.id !== sel.id)
    if (sel.kind === 'link') current.links = current.links.filter((i) => i.id !== sel.id)
    if (sel.kind === 'background') f.background = null
    if (sel.kind === 'area' && f.areas.length > 1) f.areas = f.areas.filter((i) => i.id !== sel.id)
  }
  if (pendingLink.value && !current.links.some((l) => l.id === pendingLink.value)) pendingLink.value = ''
  selection.value = []
  commit('Удаление')
}
const duplicate = () => {
  const f = floor.value
  if (!f || !selection.value.length) return
  const next: PlanSelection[] = []
  for (const sel of selection.value) {
    if (sel.kind === 'block') { const b = f.blocks.find((i) => i.id === sel.id); if (b) { const copy = { ...b, id: uid('bl'), x: b.x + 1, y: b.y + 1 }; f.blocks.push(copy); next.push({ kind: 'block', id: copy.id }) } }
    if (sel.kind === 'zone') { const z = f.zones.find((i) => i.id === sel.id); if (z) { const copy = { ...z, id: uid('zn'), x: z.x + 1, y: z.y + 1 }; f.zones.push(copy); next.push({ kind: 'zone', id: copy.id }) } }
    if (sel.kind === 'station') { const s = f.stations.find((i) => i.id === sel.id); if (s) { const copy = { ...s, id: uid('st'), x: s.x + 1, y: s.y + 1 }; f.stations.push(copy); next.push({ kind: 'station', id: copy.id }) } }
    if (sel.kind === 'wall') { const w = f.walls.find((i) => i.id === sel.id); if (w) { const copy = { id: uid('wl'), points: w.points.map((v) => v + 1) }; f.walls.push(copy); next.push({ kind: 'wall', id: copy.id }) } }
    if (sel.kind === 'area') { const a = f.areas.find((i) => i.id === sel.id); if (a) { const copy = { id: uid('ar'), points: a.points.map((v) => v + 2) }; f.areas.push(copy); next.push({ kind: 'area', id: copy.id }) } }
  }
  if (next.length) { selection.value = next; commit('Дубликат') }
}
const onLinkStop = (linkId: string) => {
  const link = layout.value?.links.find((item) => item.id === linkId)
  if (!link) return
  if (link.stops.length < 2) {
    pendingLink.value = linkId
    const other = layout.value?.floors.find((f) => f.id !== floorId.value)
    hint.value = other ? `Первый конец стоит. Переключитесь на «${other.name}» и кликните, где ${link.name.toLowerCase()} выходит там.` : 'Добавьте второй этаж, чтобы указать, куда ведёт переход.'
    if (other) floorId.value = other.id
    tool.value = 'link'
  } else {
    pendingLink.value = ''
    hint.value = `${link.name} связывает два этажа. Роботы поедут через него.`
  }
}
const continueLink = (linkId: string) => {
  const link = layout.value?.links.find((item) => item.id === linkId)
  if (!link || !layout.value) return
  pendingLink.value = linkId
  const other = layout.value.floors.find((f) => !link.stops.some((s) => s.floor === f.id))
  if (other) floorId.value = other.id
  tool.value = 'link'
}
const linkFloorName = (fid: string) => layout.value?.floors.find((f) => f.id === fid)?.name ?? fid
const goToLinkEnd = (fid: string) => { floorId.value = fid }
const stationItems = (code: string) => (byCode.value[code]?.items ?? []).filter((item) => ROLE_KIND[item.role])
const onStationItem = () => {
  const st = pickedStation.value
  const item = st ? byCode.value[st.process]?.items.find((row) => row.key === st.item) : undefined
  if (st && item) st.kind = ROLE_KIND[item.role] ?? st.kind
  edit('Объект станции')
}
const roleName: Record<ItemRole, string> = { pickup: 'откуда берут груз', dropoff: 'куда везут', charge: 'зарядка', waypoint: 'точка обхода', work_zone: 'зона работы', obstacle: 'препятствие' }
const stationKindLabel = (kind: StationKind) => ({ load: 'загрузка', unload: 'выгрузка', charge: 'зарядка', waypoint: 'точка обхода' }[kind])

const buildingTools: { id: EditorTool; label: string; key: string; icon: unknown }[] = [
  { id: 'select', label: 'Выбрать', key: 'V', icon: PhCursor },
  { id: 'hand', label: 'Рука', key: 'H', icon: PhHand },
  { id: 'floor', label: 'Пол', key: 'F', icon: PhPolygon },
  { id: 'block', label: 'Препятствие', key: 'R', icon: PhSquare },
  { id: 'link', label: 'Лифт', key: 'L', icon: PhArrowsDownUp },
]
const robotTools: { id: EditorTool; label: string; key: string; icon: unknown }[] = [
  { id: 'select', label: 'Выбрать', key: 'V', icon: PhCursor },
  { id: 'hand', label: 'Рука', key: 'H', icon: PhHand },
]
const roleSwatch: Record<ItemRole, string> = { pickup: 'load', dropoff: 'unload', charge: 'chg', waypoint: 'way', work_zone: 'zone', obstacle: 'obs' }
const tools = computed(() => (mode.value === 'building' ? buildingTools : robotTools))
const exportPlan = () => {
  const data = editor.value?.exportPng()
  if (!data) return
  const link = document.createElement('a')
  link.href = data
  link.download = `схема-${floor.value?.name ?? 'этаж'}.png`
  link.click()
}

/* Показатели. */
const clock = computed(() => {
  const total = Math.floor(live.value?.timeS ?? 0)
  const minutes = Math.floor(total / 60)
  return `${String((8 + Math.floor(minutes / 60)) % 24).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
})
const liveUtil = computed(() => {
  const rows = live.value?.processes ?? []
  const robots = rows.reduce((acc, row) => acc + row.active, 0)
  return robots ? Math.round((rows.reduce((acc, row) => acc + row.utilization * row.active, 0) / robots) * 100) : 0
})
const liveRobots = computed(() => (live.value?.processes ?? []).reduce((acc, row) => acc + row.robots, 0))
const modeLabel = computed(() => loadMode.value === 'peak' ? `Пик ×${peak.value}` : loadMode.value === 'failure' ? `Сбой: −${failurePct.value}% роботов` : liveLoad.value === 100 ? 'базовый поток' : `поток ${liveLoad.value} %`)
const statFor = (code: string) => check.value?.stats.processes.find((row) => row.code === code)
const fmt = (value: number, digits = 0) => value.toLocaleString('ru-RU', { maximumFractionDigits: digits, minimumFractionDigits: digits })
const meters = (value: number) => value.toLocaleString('ru-RU', { maximumFractionDigits: value >= 100 ? 0 : 1 })
const perHour = (value: number) => (value >= 100 ? fmt(value) : fmt(value, value >= 10 ? 1 : 2))
const focusTrip = (row: TripRow) => { focusRobot.value = row.id; floorId.value = row.floor }
</script>

<template>
  <ProjectShell
    v-if="project"
    :project="project"
    current="plan"
    title="Визуализация"
    lead="Сценарий работы предприятия по стадиям на одной схеме: пол и чертёж, здание, объекты каждого процесса. Когда стадии закрыты, роботы из сравнения проходят смену по кратчайшим маршрутам."
  >
    <template #actions>
      <UiButton variant="secondary" @click="exportPlan"><template #icon><PhDownloadSimple :size="16" weight="bold" /></template>Выгрузить план</UiButton>
      <UiButton :to="`/projects/${project.id}/report`" size="lg">К отчёту<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
    </template>

    <UiCallout tone="warn" title="Предварительная оценка">{{ PRELIMINARY }} Модель упрощает движение: роботы не объезжают друг друга, станция обслуживает одного робота за раз, лифт — фиксированное время.</UiCallout>
    <SkippedProcesses :rows="skipped" />

    <section v-if="(pending || loading) && !layout" class="waiting glass"><div class="h3">Собираем схему</div></section>
    <UiCallout v-else-if="loadError || error" tone="danger" title="Схема не открылась">{{ loadError || fetchErrorMessage(error, 'Сервер не ответил.') }}</UiCallout>

    <section v-else-if="layout && guide.phase === 'intro' && readonly" class="intro glass glass-xl">
      <div class="intro-in">
        <div class="label">Демо-объект</div>
        <h2 class="h2">Схема этого объекта ещё не собрана</h2>
        <p class="body">Администратор публикует демо после того, как соберёт здание и расставит объекты процессов. Пока схемы нет — визуализацию можно посмотреть на другом демо или в своём проекте.</p>
        <div class="intro-act">
          <UiButton size="lg" variant="secondary" to="/projects">К проектам<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
        </div>
      </div>
    </section>

    <section v-else-if="layout && guide.phase === 'intro'" class="intro glass glass-xl">
      <div class="intro-in">
        <div class="label">Сценарий работы предприятия</div>
        <h2 class="h2">Соберём, как объект работает с роботами</h2>
        <p class="body">Схема собирается по стадиям на одном холсте. Управление как в графическом редакторе: колесо сдвигает, Ctrl + колесо приближает, рамка выделяет несколько объектов, Ctrl+Z отменяет. Одна клетка — один метр. На каждой стадии есть кнопка «Расставить автоматически».</p>
        <ol class="steps">
          <li><span class="mono-sm n">0</span><span><span class="strong">Пол и чертёж.</span> Нарисуйте контур пола или растяните прямоугольник. Под сетку можно положить пожарную схему или план БТИ с прозрачностью и масштабом.</span></li>
          <li><span class="mono-sm n">0</span><span><span class="strong">Здание.</span> Препятствия, перегородки. Если этажей несколько — лифт: ставите на одном этаже, затем указываете выход на другом. Каждый лифт ведёт к своему выходу.</span></li>
          <li><span class="mono-sm n">{{ stageProcesses.length || '+' }}</span><span><span class="strong">По стадии на процесс.</span> Объекты каждого процесса заданы в его настройке. Процесс можно приглушить, скрыть или оставить без роботов.</span></li>
          <li><span class="mono-sm n">▶</span><span><span class="strong">Смена.</span> Роботы едут по маршрутам, у каждого видно откуда, куда и сколько метров осталось. Справа проверка, справляется ли расчётное количество.</span></li>
        </ol>
        <div class="intro-act">
          <UiButton size="lg" @click="openEditor('building')">Начать со здания<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
          <UiButton size="lg" variant="secondary" @click="autoAll(); setGuide({ phase: 'ready', process: '' }); nextTick(() => { editor?.fitContent(); resetSim(); scheduleCheck(50) })"><template #icon><PhMagicWand :size="16" weight="bold" /></template>Собрать всё автоматически</UiButton>
        </div>
      </div>
    </section>

    <div v-else-if="layout" class="studio">
      <!-- Страница: просмотр схемы, монитор и запуск смены. Редактирование — в полноэкранном редакторе. -->
      <div v-if="!editing" class="canvas-in viewer" :class="{ asleep: !awake }" @mouseleave="awake = false">
        <ClientOnly>
          <PlanEditor
            ref="editor" :layout="layout" :floor-id="floorId" mode="view" tool="hand" :process="toolProcess" :station-kind="stationKind" :station-item="stationItem" :link-kind="linkKind"
            pending-link="" :colors="colors" :processes="byCode" :visibility="visibility" highlight="" :calibrate-meters="calibrateMeters" :selection="[]" :focus-robot="focusRobot" :snap="snapOn"
            @ready="onEditorReady" @hint="hint = $event" @focus="focusRobot = $event" @zoom="zoomPct = Math.round($event * 10)"
          />
        </ClientOnly>
        <!-- Пока схема спит, колесо прокручивает страницу; клик включает управление картой. -->
        <button v-if="!awake" type="button" class="sleep" @click="awake = true">
          <span class="sleep-chip glass glass-strong"><PhCursorClick :size="18" weight="bold" /><span>Нажмите, чтобы управлять схемой</span><span class="caption">колесо сдвигает · Ctrl + колесо приближает</span></span>
        </button>

        <div class="topbar glass glass-strong">
          <div class="floors-row">
            <button v-for="f in layout.floors" :key="f.id" type="button" class="flr" :class="{ on: f.id === floorId }" @click="floorId = f.id">{{ f.name }}</button>
          </div>
          <span class="sep" />
          <span class="caption ready">{{ readyCount }} из {{ stageProcesses.length }} процессов готовы · {{ active.length }} в модели</span>
          <span class="sep" />
          <UiBadge v-if="readonly" tone="info" size="sm">Демо · только просмотр</UiBadge>
          <UiButton v-else size="sm" @click="openEditor()"><template #icon><PhPencilSimple :size="14" weight="bold" /></template>Редактировать</UiButton>
        </div>

        <!-- Монитор: слева сверху. -->
        <aside class="panel monitor glass glass-strong" :class="{ folded: !panels.monitor }">
          <button type="button" class="p-head" @click="panels.monitor = !panels.monitor">
            <span class="label">Монитор</span><span class="h4">{{ clock }} · {{ modeLabel }}</span>
            <PhCaretDown :size="14" weight="bold" class="caret" />
          </button>
          <div v-if="panels.monitor" class="p-body">
            <div class="m-top">
              <div class="ring">
                <svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="52" class="track" /><circle cx="60" cy="60" r="52" class="fill" :style="{ strokeDasharray: `${(liveUtil / 100) * 326.7} 326.7` }" /></svg>
                <div class="ring-num"><span class="display-4">{{ liveUtil }}%</span><span class="caption">загрузка</span></div>
              </div>
              <div class="m-rows">
                <div><span class="caption">В строю / сломано</span><span class="mono-md">{{ liveRobots - liveOffline }} / {{ liveOffline }}</span></div>
                <div><span class="caption">В очереди сейчас</span><span class="mono-md">{{ liveQueue }}</span></div>
                <div v-for="row in (live?.processes ?? []).slice(0, 3)" :key="row.code"><span class="caption"><i class="dot" :style="{ background: colors[row.code] }" /> {{ row.name }}</span><span class="mono-md">{{ fmt(row.done) }} {{ row.unit }}</span></div>
              </div>
            </div>
            <p v-if="!active.length" class="caption">{{ readonly ? 'Ни один процесс не готов к смене: администратор ещё не расставил объекты на этом демо.' : 'Ни один процесс не готов к смене. Откройте редактор и расставьте объекты процессов или нажмите «Дособрать».' }}</p>
            <template v-else>
              <div class="live-ctl">
                <label class="field">
                  <span class="caption">Поток заданий · {{ liveLoad }} % от базового</span>
                  <input class="range" type="range" min="30" max="250" step="10" :value="liveLoad" :disabled="!sim" @input="setLiveLoad(num($event))">
                </label>
                <div class="pair">
                  <button type="button" class="tb wide" :disabled="!sim" title="Случайный робот выходит из строя, груз возвращается в очередь" @click="breakRandom"><PhWarning :size="14" weight="bold" /><span>Сломать</span></button>
                  <button type="button" class="tb wide" :disabled="!liveOffline" @click="setLiveOffline(liveOffline - 1)">Починить</button>
                  <button type="button" class="tb wide" :disabled="!liveOffline" @click="repairAll">Все в строй</button>
                </div>
              </div>
              <div class="charts">
                <div class="chart wide"><div class="between"><span class="caption strong">Выполнено в час</span><span class="caption">точка / {{ SAMPLE_S }} с</span></div><UiSpark :series="[{ points: series('rate'), color: '#0d8455' }]" :target="requiredNow || null" unit="в час" :height="48" /></div>
                <div v-if="processSeries.length > 1" class="chart wide"><span class="caption strong">По процессам</span><UiSpark :series="processSeries" unit="в час" :height="48" /></div>
                <div class="chart"><span class="caption strong">Не взятых заданий</span><UiSpark :series="[{ points: series('backlog'), color: '#b2582b' }]" unit="шт." :height="40" /></div>
                <div class="chart"><span class="caption strong">Загрузка роботов</span><UiSpark :series="[{ points: series('util'), color: '#175fb0' }]" :max="100" unit="%" :height="40" /></div>
                <div class="chart"><span class="caption strong">В строю и в очереди</span><UiSpark :series="[{ points: series('active'), color: '#0f1413', label: 'в строю' }, { points: series('queued'), color: '#e6a23c', label: 'в очереди' }]" unit="шт." :height="40" /></div>
              </div>
            </template>
          </div>
        </aside>

        <aside v-if="trips.length" class="routes glass glass-strong">
          <div class="i-in">
            <div class="caption">Маршруты сейчас · {{ trips.length }}</div>
            <button v-for="row in trips.slice(0, 5)" :key="row.id" type="button" class="trip" :class="{ on: focusRobot === row.id }" @click="focusTrip(row)">
              <i class="dot" :style="{ background: colors[row.process] }" />
              <span><span class="body-sm">{{ row.from }} → {{ row.to }}</span><span class="caption">робот {{ row.id }} · {{ meters(row.leftM) }} м из {{ meters(row.totalM) }}</span></span>
            </button>
          </div>
        </aside>
        <div class="zoombar glass glass-strong">
          <button type="button" class="tb" aria-label="Отдалить" @click="editor?.zoomBy(0.8)">−</button>
          <button type="button" class="zoomval mono-sm" @click="editor?.zoomTo(10)">{{ zoomPct }} %</button>
          <button type="button" class="tb" aria-label="Приблизить" @click="editor?.zoomBy(1.25)">+</button>
          <span class="sep" />
          <button type="button" class="tb wide" title="Shift+1" @click="editor?.fit()">Этаж</button>
          <button type="button" class="tb wide" title="Shift+2" @click="editor?.fitContent()">Объекты</button>
        </div>
        <div class="controls glass glass-strong">
          <button type="button" class="ctl primary" :aria-label="playing ? 'Стоп' : 'Пуск'" :disabled="!active.length" @click="playing ? pause() : play()"><PhPause v-if="playing" :size="18" weight="fill" /><PhPlay v-else :size="18" weight="fill" /></button>
          <button type="button" class="ctl" aria-label="Перезапуск" :disabled="!active.length" @click="restart"><PhArrowCounterClockwise :size="18" weight="bold" /></button>
          <span class="sep" />
          <button v-for="value in [1, 5, 20, 60]" :key="value" type="button" class="spd" :class="{ on: speed === value }" @click="speed = value">×{{ value }}</button>
          <span class="sep" />
          <span class="clock"><span class="caption">смена {{ shiftHours }} ч</span><span class="mono-md">{{ clock }}</span></span>
        </div>
        <div class="statusline caption"><span>{{ hint }}</span></div>
      </div>

      <!-- Проверка за смену: под холстом. -->
      <section v-if="!editing" class="check glass">
        <div class="ch-in">
          <div class="between">
            <div><div class="h4">Проверка за смену</div><div class="caption">Смена {{ shiftHours }} ч прогоняется без анимации при базовом потоке заданий. Поток и поломки вживую меняются в мониторе.</div></div>
            <span class="caption">{{ checking ? 'считаем' : check ? `${fmt(check.ms)} мс` : '' }}</span>
          </div>
          <div v-if="active.length" class="ch-grid">
            <div v-for="proc in active" :key="proc.code" class="chk">
              <div class="c-head"><i class="dot" :style="{ background: colors[proc.code] }" /><span class="body-sm strong">{{ proc.name }}</span></div>
              <span class="caption">{{ proc.robot.name }} × {{ proc.robot.count }} по расчёту</span>
              <template v-if="statFor(proc.code)">
                <UiBadge :tone="statFor(proc.code)!.confirmed ? 'ok' : 'warn'" size="sm">{{ statFor(proc.code)!.confirmed ? 'Подтверждает расчёт' : 'Не подтверждает расчёт' }}</UiBadge>
                <dl class="c-rows">
                  <div><dt class="caption">Нужно в час</dt><dd class="mono-sm">{{ perHour(statFor(proc.code)!.requiredPerHour) }} {{ proc.unit }}</dd></div>
                  <div><dt class="caption">Выполнено в час</dt><dd class="mono-sm">{{ perHour(statFor(proc.code)!.donePerHour) }} {{ proc.unit }}</dd></div>
                  <div v-if="proc.kind === 'transport'"><dt class="caption">Не взято к концу смены</dt><dd class="mono-sm">{{ fmt(statFor(proc.code)!.backlog) }}</dd></div>
                  <div><dt class="caption">Загрузка роботов</dt><dd class="mono-sm">{{ fmt(statFor(proc.code)!.utilization * 100) }}%</dd></div>
                  <div v-if="statFor(proc.code)!.avgCycleS"><dt class="caption">Средний цикл</dt><dd class="mono-sm">{{ fmt(statFor(proc.code)!.avgCycleS!) }} с</dd></div>
                  <div><dt class="caption">На зарядке</dt><dd class="mono-sm">{{ fmt(statFor(proc.code)!.chargingShare * 100) }}%</dd></div>
                  <div><dt class="caption">Минимум по модели</dt><dd class="mono-sm">{{ check?.minimal[proc.code] != null ? `${check.minimal[proc.code]} шт.` : 'не найден' }}</dd></div>
                </dl>
                <ul v-if="statFor(proc.code)!.notes.length" class="notes"><li v-for="note in statFor(proc.code)!.notes" :key="note" class="caption">{{ note }}</li></ul>
              </template>
            </div>
          </div>
          <p v-else class="body-sm muted">{{ readonly ? 'Появится, когда администратор расставит объекты хотя бы одного процесса на этом демо.' : 'Появится, когда хотя бы один процесс готов: откройте редактор и расставьте объекты или нажмите «Дособрать».' }}</p>
          <div class="legend">
            <div class="lg"><i class="sw load" /> Откуда берут груз</div>
            <div class="lg"><i class="sw unload" /> Куда везут</div>
            <div class="lg"><i class="sw chg" /> Зарядка</div>
            <div class="lg"><i class="sw way" /> Точка обхода</div>
            <div class="lg"><i class="sw zone" /> Зона работы</div>
            <div class="lg"><i class="sw lift" /> Лифт «Л», лестница «С»</div>
            <div class="lg"><i class="sw robot" /> Робот, тёмный — с грузом, серый — сломан</div>
          </div>
        </div>
      </section>

      <!-- Полноэкранный редактор: здание и роботы. Без монитора и запуска. -->
      <Teleport to="body">
        <div v-if="editing" class="fullscreen">
          <header class="fs-bar">
            <div class="fs-title">
              <span class="label">Редактор схемы</span>
              <span class="h4">{{ project.name }}</span>
            </div>
            <div class="modes">
              <button type="button" class="mode" :class="{ on: mode === 'building' }" @click="openMode('building')"><PhPolygon :size="14" weight="bold" /><span>Здание</span></button>
              <button type="button" class="mode" :class="{ on: mode === 'robots' }" @click="openMode('robots')"><PhMapPin :size="14" weight="bold" /><span>Роботы</span></button>
            </div>
            <div class="floors-row">
              <button v-for="f in layout.floors" :key="f.id" type="button" class="flr" :class="{ on: f.id === floorId }" @click="floorId = f.id">{{ f.name }}</button>
              <button v-if="mode === 'building'" type="button" class="flr add" title="Добавить этаж" @click="addFloor"><PhPlus :size="13" weight="bold" /><span>Этаж</span></button>
            </div>
            <div class="fs-actions">
              <button type="button" class="tb" :disabled="!past.length" :title="`Отменить · Ctrl+Z${lastLabel ? ` · ${lastLabel}` : ''}`" @click="undo"><PhArrowUUpLeft :size="18" weight="bold" /></button>
              <button type="button" class="tb" :disabled="!future.length" title="Повторить · Ctrl+Shift+Z" @click="redo"><PhArrowUUpRight :size="18" weight="bold" /></button>
              <button type="button" class="tb" :class="{ on: snapOn }" title="Привязка к сетке 0,5 м" @click="snapOn = !snapOn"><PhMagnet :size="18" weight="bold" /></button>
              <span class="caption save">{{ saveState === 'saving' || saveState === 'pending' ? 'Сохраняем…' : saveState === 'saved' ? 'Сохранено' : saveState === 'error' ? 'Не сохранилось' : '' }}</span>
              <UiButton size="sm" @click="closeEditor"><template #icon><PhCheck :size="14" weight="bold" /></template>Готово</UiButton>
            </div>
          </header>

          <div class="canvas-in fs-canvas" @dragover.prevent @drop.prevent="onDropItem" @pointerdown.capture="onCanvasPointer">
            <ClientOnly>
              <PlanEditor
                ref="editor" :layout="layout" :floor-id="floorId" :mode="mode" :tool="tool" :process="toolProcess" :station-kind="stationKind" :station-item="stationItem" :link-kind="linkKind"
                :pending-link="pendingLink" :colors="colors" :processes="byCode" :visibility="visibility" :highlight="guide.phase === 'process' ? guide.process : ''"
                :calibrate-meters="calibrateMeters" :selection="selection" :focus-robot="null" :snap="snapOn"
                @change="onEditorChange" @calibrated="onCalibrated" @hint="hint = $event" @select="selection = $event"
                @tool="tool = $event" @link-stop="onLinkStop" @zoom="zoomPct = Math.round($event * 10)"
              />
            </ClientOnly>

            <div class="toolbar glass glass-strong">
              <button v-for="item in tools" :key="item.id" type="button" class="tb" :class="{ on: tool === item.id }" :title="`${item.label} · ${item.key}`" @click="tool = item.id; pendingLink = ''; addOpen = false">
                <component :is="item.icon" :size="18" weight="bold" /><kbd>{{ item.key }}</kbd>
              </button>
              <template v-if="mode === 'robots'">
                <span class="sep" />
                <button type="button" class="tb add" :class="{ on: addOpen || !!armedItem }" title="Объекты процесса: перетащите на схему или кликните" @click="addOpen = !addOpen">
                  <PhPlus :size="16" weight="bold" /><span>Добавить объект</span><PhCaretDown :size="12" weight="bold" class="caret" :class="{ open: addOpen }" />
                </button>
              </template>
            </div>

            <!-- Меню объектов процесса: тянуть на схему или кликнуть и указать место. -->
            <div v-if="mode === 'robots' && addOpen" class="add-menu glass glass-strong">
              <div class="am-in">
                <label class="field">
                  <span class="caption">Процесс</span>
                  <select v-model="toolProcess" class="select sm"><option v-for="proc in stageProcesses" :key="proc.code" :value="proc.code">{{ proc.name }}</option></select>
                </label>
                <p class="caption">Перетащите объект на схему или кликните по нему и укажите место на плане.</p>
                <div class="am-list">
                  <button
                    v-for="row in menuItems" :key="row.item.key" type="button" class="am-item" :class="{ done: row.have >= row.need }" draggable="true"
                    @dragstart="onDragItem($event, row.item)" @click="pickItem(row.item, toolProcess)"
                  >
                    <i class="sw" :class="roleSwatch[row.item.role]" :style="row.item.role !== 'charge' && row.item.role !== 'obstacle' ? { '--c': colors[toolProcess] } : {}" />
                    <span class="am-text"><span class="body-sm strong">{{ row.item.label }}</span><span class="caption">{{ roleName[row.item.role] }} · {{ row.item.shape === 'area' ? 'растянуть рамкой' : 'поставить точкой' }}</span></span>
                    <span class="mono-sm am-count" :class="{ ok: row.have >= row.need }">{{ row.have }} / {{ row.need }}</span>
                    <PhDotsSixVertical :size="16" weight="bold" class="grip" />
                  </button>
                </div>
              </div>
            </div>

            <div v-if="armedItem" class="subbar glass glass-strong armed">
              <i class="sw" :class="roleSwatch[armedItem.role]" :style="{ '--c': colors[toolProcess] }" />
              <span class="body-sm"><span class="strong">{{ armedItem.label }}</span> · {{ byCode[toolProcess]?.name }}</span>
              <span class="caption">{{ armedItem.shape === 'area' ? 'растяните рамку на схеме' : 'кликните место на схеме' }}</span>
              <button type="button" class="tb small" title="Отмена · Esc" @click="tool = 'select'"><PhX :size="14" weight="bold" /></button>
            </div>
            <div v-if="tool === 'link'" class="subbar glass glass-strong">
              <button type="button" class="tb wide" :class="{ on: linkKind === 'elevator' }" @click="linkKind = 'elevator'"><PhElevator :size="16" weight="bold" /><span>Лифт</span></button>
              <button type="button" class="tb wide" :class="{ on: linkKind === 'stairs' }" @click="linkKind = 'stairs'"><PhStairs :size="16" weight="bold" /><span>Лестница</span></button>
              <span v-if="pendingLink" class="caption pend">Укажите второй конец на этом этаже</span>
            </div>
            <div v-if="tool === 'calibrate'" class="subbar glass glass-strong">
              <PhRuler :size="16" weight="bold" /><label class="caption" for="cal-m">Длина отрезка, м</label>
              <input id="cal-m" v-model.number="calibrateMeters" class="input input-mono sm num" type="number" min="0.5" step="0.5">
            </div>

            <!-- Стадии и задачи: справа. -->
            <aside class="panel nav glass glass-strong" :class="{ folded: !panels.nav }">
              <button type="button" class="p-head" @click="panels.nav = !panels.nav">
                <span class="label">{{ stageNumber }}</span><span class="h4">{{ stageTitle }}</span>
                <PhCaretDown :size="14" weight="bold" class="caret" />
              </button>
              <div v-if="panels.nav" class="p-body">
                <template v-if="mode === 'building'">
                  <ul class="tasks">
                    <li v-for="task in buildingTasks" :key="task.id" :class="{ done: task.done }"><button type="button" class="task" @click="task.id === 'plan' ? fileInput?.click() : tool = task.tool"><PhCheckCircle :size="15" weight="fill" /><span><span class="strong">{{ task.title }}.</span> {{ task.text }}</span></button></li>
                  </ul>
                  <div class="stage-act">
                    <UiButton size="sm" variant="secondary" @click="fileInput?.click()"><template #icon><PhUploadSimple :size="14" weight="bold" /></template>Чертёж</UiButton>
                    <UiButton size="sm" variant="secondary" @click="useSamplePlan"><template #icon><PhImage :size="14" weight="bold" /></template>Тестовый</UiButton>
                    <UiButton size="sm" variant="secondary" @click="autoShell"><template #icon><PhMagicWand :size="14" weight="bold" /></template>Авто</UiButton>
                    <input ref="fileInput" type="file" accept="image/png,image/jpeg,image/webp" hidden @change="uploadBackground">
                  </div>
                  <div v-if="layout.links.length" class="links">
                    <button v-for="link in layout.links" :key="link.id" type="button" class="lnk" :class="{ on: selection.some((s) => s.kind === 'link' && s.id === link.id), warn: link.stops.length < 2 }" @click="selection = [{ kind: 'link', id: link.id }]; floorId = link.stops[0]?.floor ?? floorId">
                      <span class="body-sm strong">{{ link.name }}</span>
                      <span class="caption">{{ link.stops.length < 2 ? 'нет второго конца' : link.stops.map((s) => linkFloorName(s.floor)).join(' ↔ ') }}</span>
                    </button>
                  </div>
                  <UiButton size="sm" @click="nextStage">К роботам<template #after><PhArrowRight :size="14" weight="bold" /></template></UiButton>
                </template>

                <template v-else>
                  <!-- Блок 1: какой процесс расставляем. -->
                  <div class="sect">
                    <div class="sect-head"><span class="label">Процесс</span><span class="caption">{{ readyCount }} из {{ stageProcesses.length }} готовы</span></div>
                    <div class="stages">
                      <button
                        v-for="(proc, index) in stageProcesses" :key="proc.code" type="button" class="stg" :class="{ on: guide.phase === 'process' && guide.process === proc.code, done: stageReady(proc), muted: settingsOf(proc.code).visibility !== 'full' }"
                        @click="openStage('process', proc.code)"
                      >
                        <PhCheckCircle :size="15" weight="fill" />
                        <span><span class="body-sm strong"><i class="dot" :style="{ background: colors[proc.code] }" />{{ index + 1 }} · {{ proc.name }}</span><span class="caption">{{ proc.kind === 'none' ? 'робот не выбран' : `${proc.robot.name} × ${proc.robot.count}` }}{{ settingsOf(proc.code).robots ? '' : ' · без роботов' }}</span></span>
                        <span class="vis" :title="{ full: 'Показан', dim: 'Приглушён', hidden: 'Скрыт' }[settingsOf(proc.code).visibility]" @click.stop="cycleVisibility(proc.code)"><component :is="visIcon(proc.code)" :size="14" weight="bold" /></span>
                      </button>
                    </div>
                  </div>

                  <!-- Блок 2: что нужно поставить для выбранного процесса. -->
                  <div v-if="guide.phase === 'process' && stageProc" class="sect req">
                    <div class="sect-head"><span class="label">Требования стадии</span><span class="caption">{{ itemTasks.filter((t) => t.done).length }} из {{ itemTasks.length }}</span></div>
                    <ul class="tasks">
                      <li v-for="task in itemTasks" :key="task.item.key" :class="{ done: task.done, on: stationItem === task.item.key && !!armedItem }">
                        <div class="task">
                          <PhCheckCircle :size="15" weight="fill" />
                          <span class="task-text"><span class="strong">{{ task.item.label }}</span> · {{ roleName[task.item.role] }}<span class="caption block">{{ task.item.hint }}</span></span>
                          <span class="task-side"><span class="mono-sm" :class="{ ok: task.done }">{{ task.have }} / {{ task.need }}</span><button type="button" class="tb small" :title="`Поставить: ${task.item.label}`" @click="pickItem(task.item, stageProc.code)"><PhPlus :size="13" weight="bold" /></button></span>
                        </div>
                      </li>
                    </ul>
                    <label class="check"><input type="checkbox" :checked="settingsOf(stageProc.code).robots" @change="setSettings(stageProc.code, { robots: ($event.target as HTMLInputElement).checked })"> Роботы выходят на схему</label>
                    <span v-if="stageProc.kind === 'none'" class="caption">Робот не выбран в сравнении: модель по процессу не считается.</span>
                  </div>
                  <p v-else class="caption">Выберите процесс выше: у каждого свой набор объектов на схеме.</p>

                  <div class="stage-act">
                    <UiButton variant="ghost" size="sm" @click="prevStage">Назад</UiButton>
                    <UiButton v-if="guide.phase === 'process'" size="sm" variant="secondary" @click="autoStage()"><template #icon><PhMagicWand :size="14" weight="bold" /></template>Авто</UiButton>
                    <UiButton size="sm" variant="secondary" @click="autoAll"><template #icon><PhMagicWand :size="14" weight="bold" /></template>Дособрать</UiButton>
                    <UiButton v-if="guide.phase === 'process' && stageIndex < stageProcesses.length - 1" size="sm" @click="nextStage">Дальше<template #after><PhArrowRight :size="14" weight="bold" /></template></UiButton>
                    <UiButton v-else size="sm" @click="closeEditor"><template #icon><PhCheck :size="14" weight="bold" /></template>Готово</UiButton>
                  </div>
                </template>
              </div>
            </aside>

            <!-- Свойства: слева снизу. -->
            <aside class="panel props glass glass-strong" :class="{ folded: !panels.props }">
              <button type="button" class="p-head" @click="panels.props = !panels.props">
                <span class="label">{{ selection.length ? 'Свойства' : 'Справка' }}</span>
                <span class="h4">{{ propsTitle }}</span>
                <button v-if="selection.length && !(pickedArea && floor && floor.areas.length <= 1)" type="button" class="tb small" title="Удалить · Delete" @click.stop="removeSelected"><PhTrash :size="14" weight="bold" /></button>
                <PhCaretDown :size="14" weight="bold" class="caret" />
              </button>
              <div v-if="panels.props" class="p-body">
                <template v-if="pickedArea && floor">
                  <label class="field"><span class="caption">Этаж</span><input class="input sm" :value="floor.name" @change="renameFloor(($event.target as HTMLInputElement).value)"></label>
                  <div v-if="areaSize" class="pair">
                    <label class="field"><span class="caption">Ширина, м</span><input class="input input-mono sm" type="number" :value="Math.round(areaSize.w)" :disabled="!isRectFloor" @change="setRectFloor('w', ($event.target as HTMLInputElement).value)"></label>
                    <label class="field"><span class="caption">Длина, м</span><input class="input input-mono sm" type="number" :value="Math.round(areaSize.h)" :disabled="!isRectFloor" @change="setRectFloor('h', ($event.target as HTMLInputElement).value)"></label>
                  </div>
                  <p v-if="areaSize" class="caption">Площадь {{ fmt(areaSize.area) }} м² · {{ pickedArea.points.length / 2 }} углов, тяните их на схеме. Наложите новый участок — он сольётся с этим.</p>
                  <div class="pair">
                    <UiButton size="sm" variant="secondary" @click="tool = 'floor'"><template #icon><PhPolygon :size="14" weight="bold" /></template>Добавить участок</UiButton>
                    <UiButton v-if="layout.floors.length > 1" size="sm" variant="ghost" @click="removeFloor"><template #icon><PhTrash :size="14" weight="bold" /></template>Этаж</UiButton>
                  </div>
                </template>
                <template v-else-if="pickedBg && bg">
                  <label class="field"><span class="caption">Прозрачность · {{ Math.round(bg.opacity * 100) }} %</span><input class="range" type="range" min="0.1" max="1" step="0.05" :value="bg.opacity" @input="bg.opacity = num($event); editor?.render()" @change="edit('Прозрачность чертежа')"></label>
                  <div class="pair">
                    <label class="field"><span class="caption">Ширина чертежа, м</span><input class="input input-mono sm" type="number" step="0.5" :value="Math.round(bgWidthM * 10) / 10" @change="setBgWidth(($event.target as HTMLInputElement).value)"></label>
                    <label class="field"><span class="caption">X, м</span><input class="input input-mono sm" type="number" step="0.5" :value="bg.x" @change="bg.x = num($event); edit('Сдвиг чертежа')"></label>
                    <label class="field"><span class="caption">Y, м</span><input class="input input-mono sm" type="number" step="0.5" :value="bg.y" @change="bg.y = num($event); edit('Сдвиг чертежа')"></label>
                  </div>
                  <div class="pair">
                    <UiButton size="sm" variant="secondary" @click="tool = 'calibrate'"><template #icon><PhRuler :size="14" weight="bold" /></template>Линейка</UiButton>
                    <UiButton size="sm" variant="secondary" @click="bg.locked = !bg.locked; edit(bg.locked ? 'Чертёж закреплён' : 'Чертёж откреплён')"><template #icon><component :is="bg.locked ? PhLockSimple : PhLockSimpleOpen" :size="14" weight="bold" /></template>{{ bg.locked ? 'Закреплён' : 'Закрепить' }}</UiButton>
                  </div>
                </template>
                <template v-else-if="pickedStation">
                  <label class="field"><span class="caption">Процесс</span><select v-model="pickedStation.process" class="select sm" @change="pickedStation.item = undefined; edit('Процесс станции')"><option v-for="proc in stageProcesses" :key="proc.code" :value="proc.code">{{ proc.name }}</option></select></label>
                  <label class="field"><span class="caption">Объект · роль: {{ stationKindLabel(pickedStation.kind) }}</span>
                    <select v-model="pickedStation.item" class="select sm" @change="onStationItem"><option v-for="item in stationItems(pickedStation.process)" :key="item.key" :value="item.key">{{ item.label }} · {{ roleName[item.role] }}</option></select>
                  </label>
                  <div class="pair">
                    <label class="field"><span class="caption">X, м</span><input class="input input-mono sm" type="number" step="0.5" :value="pickedStation.x" @change="pickedStation.x = num($event); edit('Координаты')"></label>
                    <label class="field"><span class="caption">Y, м</span><input class="input input-mono sm" type="number" step="0.5" :value="pickedStation.y" @change="pickedStation.y = num($event); edit('Координаты')"></label>
                  </div>
                </template>
                <template v-else-if="pickedBlock">
                  <label class="field"><span class="caption">Название</span><input v-model="pickedBlock.label" class="input sm" @change="edit('Название')"></label>
                  <div class="pair"><label class="field"><span class="caption">X</span><input class="input input-mono sm" type="number" step="0.5" :value="pickedBlock.x" @change="pickedBlock.x = num($event); edit('Координаты')"></label><label class="field"><span class="caption">Y</span><input class="input input-mono sm" type="number" step="0.5" :value="pickedBlock.y" @change="pickedBlock.y = num($event); edit('Координаты')"></label><label class="field"><span class="caption">Ширина</span><input class="input input-mono sm" type="number" min="0.5" step="0.5" :value="pickedBlock.w" @change="pickedBlock.w = Math.max(0.5, num($event)); edit('Размер')"></label><label class="field"><span class="caption">Длина</span><input class="input input-mono sm" type="number" min="0.5" step="0.5" :value="pickedBlock.h" @change="pickedBlock.h = Math.max(0.5, num($event)); edit('Размер')"></label></div>
                </template>
                <template v-else-if="pickedZone">
                  <label class="field"><span class="caption">Процесс</span><select v-model="pickedZone.process" class="select sm" @change="edit('Процесс зоны')"><option v-for="proc in stageProcesses" :key="proc.code" :value="proc.code">{{ proc.name }}</option></select></label>
                  <div class="pair"><label class="field"><span class="caption">X</span><input class="input input-mono sm" type="number" step="0.5" :value="pickedZone.x" @change="pickedZone.x = num($event); edit('Координаты')"></label><label class="field"><span class="caption">Y</span><input class="input input-mono sm" type="number" step="0.5" :value="pickedZone.y" @change="pickedZone.y = num($event); edit('Координаты')"></label><label class="field"><span class="caption">Ширина</span><input class="input input-mono sm" type="number" min="1" step="0.5" :value="pickedZone.w" @change="pickedZone.w = Math.max(1, num($event)); edit('Размер')"></label><label class="field"><span class="caption">Длина</span><input class="input input-mono sm" type="number" min="1" step="0.5" :value="pickedZone.h" @change="pickedZone.h = Math.max(1, num($event)); edit('Размер')"></label></div>
                  <p class="caption">Площадь {{ fmt(pickedZone.w * pickedZone.h) }} м².</p>
                </template>
                <template v-else-if="pickedWall">
                  <p class="caption">{{ pickedWall.points.length / 2 }} точек. Тяните квадратики на схеме, чтобы поправить.</p>
                </template>
                <template v-else-if="pickedLink">
                  <div class="pair">
                    <label class="field"><span class="caption">Название</span><input v-model="pickedLink.name" class="input sm" @change="edit('Имя перехода')"></label>
                    <button type="button" class="tb wide" :class="{ on: pickedLink.kind === 'elevator' }" @click="pickedLink.kind = 'elevator'; edit('Тип перехода')"><PhElevator :size="14" weight="bold" /><span>Лифт</span></button>
                    <button type="button" class="tb wide" :class="{ on: pickedLink.kind === 'stairs' }" @click="pickedLink.kind = 'stairs'; edit('Тип перехода')"><PhStairs :size="14" weight="bold" /><span>Лестница</span></button>
                  </div>
                  <div class="ends">
                    <div v-for="stop in pickedLink.stops" :key="stop.floor" class="end">
                      <span class="body-sm strong">{{ linkFloorName(stop.floor) }}</span>
                      <span class="mono-sm">{{ stop.x }}, {{ stop.y }} м</span>
                      <button v-if="stop.floor !== floorId" type="button" class="link" @click="goToLinkEnd(stop.floor)">показать</button>
                    </div>
                    <UiButton v-if="pickedLink.stops.length < 2" size="sm" @click="continueLink(pickedLink.id)">Указать второй конец</UiButton>
                  </div>
                  <div class="pair">
                    <label class="field"><span class="caption">Ожидание, с</span><input class="input input-mono sm" type="number" min="0" :value="pickedLink.wait_s" @change="pickedLink.wait_s = num($event); edit('Время перехода')"></label>
                    <label class="field"><span class="caption">На этаж, с</span><input class="input input-mono sm" type="number" min="0" :value="pickedLink.per_floor_s" @change="pickedLink.per_floor_s = num($event); edit('Время перехода')"></label>
                  </div>
                  <p class="caption">{{ pickedLink.kind === 'stairs' ? 'По лестнице ходят только шагающие роботы.' : 'Лифт связывает ровно два этажа.' }}</p>
                </template>
                <template v-else-if="selection.length > 1">
                  <p class="caption">Тяните все вместе, стрелки двигают на 1 м, Shift + стрелки — на 5 м, Ctrl+D дублирует.</p>
                </template>
                <template v-else>
                  <p class="caption">{{ mode === 'building' ? 'Кликните участок пола, препятствие, лифт или чертёж.' : 'Объекты процесса — в меню «Добавить объект» сверху: перетащите на схему или кликните и укажите место. Кликните станцию или зону, чтобы поправить.' }}</p>
                  <div class="keys">
                    <div v-if="mode === 'building'"><kbd>V</kbd> выбрать · <kbd>H</kbd> рука · <kbd>F</kbd> пол · <kbd>R</kbd> препятствие · <kbd>L</kbd> лифт</div>
                    <div v-else><kbd>V</kbd> выбрать · <kbd>H</kbd> рука · <kbd>Esc</kbd> отменить постановку</div>
                    <div><kbd>Space</kbd> сдвиг · <kbd>Ctrl</kbd>+колесо зум · <kbd>Ctrl+Z</kbd> отмена · <kbd>Delete</kbd> удалить · <kbd>Ctrl+D</kbd> дубликат · <kbd>Esc</kbd> закрыть</div>
                  </div>
                </template>
              </div>
            </aside>

            <div class="zoombar glass glass-strong">
              <button type="button" class="tb" aria-label="Отдалить" @click="editor?.zoomBy(0.8)">−</button>
              <button type="button" class="zoomval mono-sm" title="Ctrl+0 — 100 %" @click="editor?.zoomTo(10)">{{ zoomPct }} %</button>
              <button type="button" class="tb" aria-label="Приблизить" @click="editor?.zoomBy(1.25)">+</button>
              <span class="sep" />
              <button type="button" class="tb wide" title="Shift+1" @click="editor?.fit()">Этаж</button>
              <button type="button" class="tb wide" title="Shift+2" @click="editor?.fitContent()">Объекты</button>
            </div>
            <div class="statusline caption"><span>{{ hint }}</span></div>
          </div>
        </div>
      </Teleport>
    </div>
  </ProjectShell>
  <section v-else class="container gone">
    <UiCallout tone="danger" title="Проект не найден">Нет сохранённого расчёта с таким адресом.</UiCallout>
  </section>
</template>

<style scoped>
.waiting { padding: var(--space-10); }
.waiting > * { position: relative; z-index: 1; }
.gone { padding-top: var(--space-12); }
.intro-in { position: relative; z-index: 1; padding: var(--space-8); display: grid; gap: var(--space-4); max-width: 820px; }
.intro .h2, .intro p { margin: 0; }
.steps { display: grid; gap: 12px; margin: 0; padding: 0; list-style: none; }
.steps li { display: grid; grid-template-columns: 36px minmax(0, 1fr); gap: 12px; align-items: start; }
.n { width: 36px; height: 36px; border-radius: 10px; background: var(--surface-graphite); color: var(--brand-300); display: inline-flex; align-items: center; justify-content: center; }
.intro-act, .stage-act { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }

.studio { display: grid; gap: var(--space-3); }
.canvas-in { position: relative; height: calc(100dvh - 210px); min-height: 620px; border-radius: 18px; overflow: hidden; box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.08); }
.topbar { position: absolute; z-index: 7; top: 12px; right: 12px; display: inline-flex; align-items: center; gap: 8px; padding: 6px 6px 6px 8px; border-radius: 14px; }
.topbar > * { position: relative; z-index: 1; }
.ready { white-space: nowrap; }

/* Полноэкранный редактор. */
.fullscreen { position: fixed; inset: 0; z-index: 1000; display: grid; grid-template-rows: auto minmax(0, 1fr); background: #e7ecea; }
.fs-bar { display: flex; align-items: center; gap: 14px; padding: 10px 16px; background: #fff; border-bottom: 1px solid rgba(15, 20, 19, 0.08); }
.fs-title { display: grid; line-height: 1.15; min-width: 0; }
.fs-title .h4 { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 320px; }
.fs-actions { margin-left: auto; display: inline-flex; align-items: center; gap: 6px; }
.fs-canvas { height: auto; min-height: 0; border-radius: 0; box-shadow: none; }

/* Плавающие панели. */
.panel { position: absolute; z-index: 6; width: 320px; max-height: calc(100% - 24px); display: flex; flex-direction: column; border-radius: 14px; }
.panel > * { position: relative; z-index: 1; }
.panel.nav { top: 12px; left: 12px; }
.panel.monitor { top: 12px; left: 12px; width: 420px; }
.panel.props { bottom: 68px; right: 12px; width: 300px; max-height: 46%; }
.panel.folded { width: auto; }
.p-head { display: flex; align-items: center; gap: 8px; padding: 8px 10px 8px 12px; text-align: left; width: 100%; }
.p-head .label { flex: none; }
.p-head .h4 { flex: 1; min-width: 0; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.p-head .caret { flex: none; color: var(--ink-faint); transition: transform var(--dur-fast) var(--ease); }
.folded .p-head .caret { transform: rotate(-90deg); }
.p-body { display: grid; gap: 8px; padding: 0 12px 12px; overflow: auto; }
.p-body p { margin: 0; }

.modes { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; padding: 3px; border-radius: 10px; background: rgba(15, 20, 19, 0.06); }
.mode { display: inline-flex; align-items: center; justify-content: center; gap: 6px; height: 30px; padding: 0 12px; border-radius: 8px; font-size: 12px; font-weight: 700; color: var(--ink-muted); transition: all var(--dur-fast) var(--ease); }
.mode.on { background: #fff; color: var(--ink-strong); box-shadow: 0 1px 3px rgba(15, 20, 19, 0.12); }
.fs-bar .mode.on { background: var(--surface-graphite); color: #fff; box-shadow: none; }
.floors-row { display: flex; flex-wrap: wrap; gap: 4px; }
.flr { height: 28px; padding: 0 10px; border-radius: 8px; font-size: 12px; font-weight: 700; color: var(--ink-body); background: rgba(255, 255, 255, 0.55); box-shadow: inset 0 0 0 1px var(--border-hairline); }
.flr.on { background: var(--surface-graphite); color: #fff; box-shadow: none; }
.flr.add { display: inline-flex; align-items: center; gap: 4px; padding: 0 8px; color: var(--ink-muted); background: transparent; }
.stages { display: grid; gap: 2px; max-height: 30vh; overflow: auto; }
.stg { display: grid; grid-template-columns: 15px minmax(0, 1fr) auto; gap: 8px; align-items: center; text-align: left; padding: 6px 8px; border-radius: 10px; color: var(--ink-muted); }
.stg > svg { color: var(--ink-faint); }
.stg.done > svg { color: var(--state-ok); }
.stg:hover { background: rgba(255, 255, 255, 0.6); }
.stg.on { background: var(--surface-graphite); color: var(--ink-on-graphite); }
.stg.on .caption { color: var(--ink-muted-graphite); }
.stg.muted .body-sm { opacity: 0.6; }
.stg > span { display: grid; gap: 0; min-width: 0; }
.stg .strong { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; }
.vis { display: inline-flex; padding: 4px; border-radius: 6px; opacity: 0.7; }
.vis:hover { opacity: 1; background: rgba(255, 255, 255, 0.15); }
.links { display: grid; gap: 4px; }
.lnk { display: flex; justify-content: space-between; gap: 8px; padding: 6px 8px; border-radius: 8px; text-align: left; background: rgba(255, 255, 255, 0.5); box-shadow: inset 0 0 0 1px var(--border-hairline); }
.lnk.on { box-shadow: inset 0 0 0 1.5px #0d99ff; }
.lnk.warn { box-shadow: inset 0 0 0 1.5px #b2582b; }
.dot { width: 9px; height: 9px; border-radius: 50%; flex: none; display: inline-block; }
.tasks { display: grid; gap: 2px; margin: 0; padding: 0; list-style: none; }
.tasks li { color: var(--ink-muted); border-radius: 8px; }
.tasks li.done { color: var(--ink-body); }
.tasks li.on { background: var(--surface-brand-tint); }
.task { display: flex; gap: 8px; align-items: flex-start; text-align: left; width: 100%; padding: 5px 6px; color: inherit; font-size: 12.5px; line-height: 1.35; }
.tasks li.on .task { color: var(--ink-strong); }
.sect.req .tasks li.on { background: rgba(255, 255, 255, 0.7); }
.task svg { flex: none; margin-top: 2px; color: var(--ink-faint); }
.done .task svg { color: var(--state-ok); }
.block { display: block; }
.check { display: inline-flex; align-items: center; gap: 8px; font-size: 13px; }

.m-top { display: grid; grid-template-columns: 96px minmax(0, 1fr); gap: 12px; align-items: center; }
.ring { position: relative; width: 96px; height: 96px; }
.ring svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.track { fill: none; stroke: rgba(15, 20, 19, 0.08); stroke-width: 10; }
.fill { fill: none; stroke: var(--brand-500); stroke-width: 10; stroke-linecap: round; transition: stroke-dasharray var(--dur-slow) var(--ease); }
.ring-num { position: absolute; inset: 0; display: grid; place-content: center; text-align: center; gap: 0; }
.ring-num .display-4 { font-size: 22px; }
.m-rows { display: grid; gap: 4px; }
.m-rows > div { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.m-rows .caption { display: inline-flex; align-items: center; gap: 5px; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.m-rows .mono-md { color: var(--ink-strong); white-space: nowrap; font-size: 13px; }
.live-ctl { display: grid; gap: 6px; padding: 8px; border-radius: 10px; background: rgba(15, 20, 19, 0.04); }
.charts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px 12px; }
.chart { display: grid; gap: 3px; min-width: 0; }
.chart.wide { grid-column: 1 / -1; }

.toolbar, .subbar, .zoombar, .controls { position: absolute; z-index: 7; display: inline-flex; align-items: center; gap: 4px; padding: 6px; border-radius: 14px; }
.toolbar > *, .subbar > *, .zoombar > *, .controls > * { position: relative; z-index: 1; }
.toolbar { top: 12px; left: 50%; transform: translateX(-50%); }
.subbar { top: 62px; left: 50%; transform: translateX(-50%); gap: 8px; padding: 6px 10px; }
.zoombar { right: 12px; bottom: 12px; }
.controls { left: 50%; transform: translateX(-50%); bottom: 12px; gap: 6px; }
.routes { position: absolute; z-index: 5; right: 12px; bottom: 68px; width: 270px; max-height: 34%; overflow: auto; }
.tb { display: inline-flex; align-items: center; justify-content: center; gap: 6px; min-width: 36px; height: 36px; padding: 0 8px; border-radius: 10px; color: var(--ink-body); font-size: 12px; font-weight: 700; transition: all var(--dur-fast) var(--ease); }
.tb:hover { background: rgba(15, 20, 19, 0.06); }
.tb.on { background: var(--surface-graphite); color: #fff; }
.tb:disabled { opacity: 0.35; }
.tb kbd { font-family: var(--font-mono); font-size: 9px; color: inherit; opacity: 0.55; position: absolute; right: 4px; bottom: 3px; }
.tb.wide { padding: 0 12px; height: 32px; }
.tb.small { min-width: 28px; height: 28px; }
.sep { width: 1px; height: 22px; background: rgba(15, 20, 19, 0.12); margin: 0 4px; }
.zoomval { min-width: 56px; height: 36px; border-radius: 10px; color: var(--ink-strong); }
.zoomval:hover { background: rgba(15, 20, 19, 0.06); }
.pend { color: #b2582b; font-weight: 700; }
.select.sm, .input.sm { min-height: 32px; height: 32px; font-size: 12px; }
.num { width: 72px; }
.sc-sel { width: 150px; }
.ctl { width: 40px; height: 40px; border-radius: 12px; display: inline-flex; align-items: center; justify-content: center; background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); color: var(--ink-strong); }
.ctl:disabled { opacity: 0.45; }
.ctl.primary { background: var(--action-fill); color: #fff; box-shadow: none; }
.spd { height: 34px; padding: 0 10px; border-radius: 10px; font-family: var(--font-mono); font-size: 12px; font-weight: 700; color: var(--ink-body); }
.spd.on { background: var(--surface-graphite); color: var(--brand-300); }
.clock { display: grid; text-align: right; line-height: 1.1; padding-left: 6px; }
.clock .mono-md { color: var(--ink-strong); }
.i-in { position: relative; z-index: 1; padding: 10px; display: grid; gap: 6px; }
.trip { display: flex; gap: 8px; align-items: center; text-align: left; padding: 6px 8px; border-radius: 10px; }
.trip.on, .trip:hover { background: rgba(255, 255, 255, 0.7); }
.trip > span { display: grid; }
.statusline { position: absolute; left: 12px; right: 12px; bottom: 0; z-index: 4; display: flex; justify-content: space-between; gap: 12px; padding: 4px 8px; pointer-events: none; }
.fs-canvas .statusline { right: 330px; }

/* Спящая схема на странице: клик включает управление. */
.sleep { position: absolute; inset: 0; z-index: 3; display: grid; place-items: center; background: rgba(15, 20, 19, 0.16); cursor: pointer; transition: background var(--dur-fast) var(--ease); }
.sleep:hover { background: rgba(15, 20, 19, 0.1); }
.sleep-chip { position: relative; display: grid; justify-items: center; gap: 4px; padding: 14px 22px; border-radius: 14px; color: var(--ink-strong); font-size: 14px; font-weight: 700; }
.sleep-chip > * { position: relative; z-index: 1; }
.sleep-chip .caption { font-weight: 500; }

/* Меню «Добавить объект» и чип постановки. */
.tb.add { padding: 0 12px; }
.tb.add .caret { transition: transform var(--dur-fast) var(--ease); }
.tb.add .caret.open { transform: rotate(180deg); }
.add-menu { position: absolute; z-index: 8; top: 62px; left: 50%; transform: translateX(-50%); width: 380px; border-radius: 14px; }
.am-in { position: relative; z-index: 1; display: grid; gap: 8px; padding: 12px; }
.am-in p { margin: 0; }
.am-list { display: grid; gap: 2px; max-height: 46vh; overflow: auto; }
.am-item { display: grid; grid-template-columns: 16px minmax(0, 1fr) auto 16px; gap: 10px; align-items: center; text-align: left; padding: 8px 8px 8px 10px; border-radius: 10px; cursor: grab; color: var(--ink-body); }
.am-item:hover { background: rgba(255, 255, 255, 0.7); }
.am-item:active { cursor: grabbing; }
.am-item .sw { width: 14px; height: 14px; }
.am-text { display: grid; min-width: 0; }
.am-count { color: var(--ink-muted); }
.am-count.ok, .task-side .ok { color: var(--state-ok); }
.am-item .grip { color: var(--ink-faint); }
.subbar.armed { gap: 10px; padding: 6px 6px 6px 12px; }
.subbar.armed .sw { width: 13px; height: 13px; flex: none; }

/* Секции панели стадий. */
.sect { display: grid; gap: 6px; padding: 10px; border-radius: 12px; background: rgba(255, 255, 255, 0.55); box-shadow: inset 0 0 0 1px var(--border-hairline); }
.sect.req { background: var(--surface-brand-tint); }
.sect-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.task-text { flex: 1; min-width: 0; }
.task-side { display: inline-flex; align-items: center; gap: 6px; flex: none; }
.task-side .mono-sm { color: var(--ink-muted); }

.field { display: grid; gap: 4px; }
.pair { display: flex; gap: 8px; flex-wrap: wrap; }
.pair .field { flex: 1; min-width: 70px; }
.pair .tb.wide { flex: 1; box-shadow: inset 0 0 0 1px var(--border-hairline); }
.keys { display: grid; gap: 4px; color: var(--ink-muted); font-size: 12px; }
.keys kbd { font-family: var(--font-mono); font-size: 11px; padding: 1px 5px; border-radius: 5px; background: rgba(15, 20, 19, 0.06); color: var(--ink-strong); }
.ends { display: grid; gap: 6px; }
.end { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 6px 8px; border-radius: 8px; background: rgba(255, 255, 255, 0.6); }
.link { color: var(--brand-700); font-weight: 700; font-size: 12px; }

.check.glass .ch-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: var(--space-4); }
.ch-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: var(--space-4); }
.chk { display: grid; gap: 6px; padding: 12px; border-radius: 12px; background: rgba(255, 255, 255, 0.55); box-shadow: inset 0 0 0 1px var(--border-hairline); justify-items: start; align-content: start; }
.c-head { display: inline-flex; align-items: center; gap: 8px; }
.c-rows { display: grid; gap: 4px; margin: 0; width: 100%; }
.c-rows > div { display: flex; justify-content: space-between; gap: 10px; }
.c-rows dd { margin: 0; color: var(--ink-strong); text-align: right; }
.notes { margin: 0; padding-left: 16px; display: grid; gap: 2px; }
.legend { display: flex; flex-wrap: wrap; gap: 8px 18px; padding-top: 10px; border-top: 1px solid rgba(15, 20, 19, 0.08); }
.lg { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--ink-body); }
.sw { display: inline-block; width: 13px; height: 13px; flex: none; }
.sw.load { border-radius: 50%; background: var(--c, var(--brand-600)); }
.sw.unload { border-radius: 50%; background: #fff; border: 2px solid var(--c, var(--brand-600)); }
.sw.chg { border-radius: 3px; background: #fff; border: 2px solid #e6a23c; }
.sw.way { transform: rotate(45deg) scale(0.8); background: #fff; border: 2px solid var(--c, var(--brand-600)); }
.sw.zone { border-radius: 3px; border: 1.5px dashed var(--c, var(--brand-600)); background: rgba(31, 122, 90, 0.08); }
.sw.obs { border-radius: 3px; background: rgba(15, 20, 19, 0.14); border: 1px solid rgba(15, 20, 19, 0.3); }
.sw.lift { border-radius: 3px; background: #175fb0; }
.sw.robot { border-radius: 50%; background: var(--brand-600); box-shadow: 0 0 0 2px #fff, 0 0 0 3px rgba(15, 20, 19, 0.2); }
@media (max-width: 1100px) {
  .panel.props { width: 260px; }
  .panel.nav { width: 280px; }
  .panel.monitor { width: 340px; }
  .charts { grid-template-columns: minmax(0, 1fr); }
  .topbar .ready { display: none; }
}
@media (max-width: 800px) {
  .canvas-in { height: 80dvh; }
  .panel { position: static; width: auto; max-height: none; }
  .fs-bar { flex-wrap: wrap; }
}
</style>
