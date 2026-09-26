<script setup lang="ts">
/**
 * Редактор схемы в духе Figma: колесо сдвигает, Ctrl+колесо приближает к курсору, пробел — рука,
 * рамка выделяет несколько объектов, Shift добавляет к выделению, стрелки двигают на 1 м (Shift — 5 м),
 * умные направляющие при перетаскивании, ручки размера у прямоугольников, Delete удаляет, Esc снимает выделение.
 * Отмена и повтор — у родителя, редактор сообщает о каждом завершённом изменении через `change`.
 */
import type KonvaNS from 'konva'
import polygonClipping from 'polygon-clipping'
import { fitFloorToOutline, mergeAreas, newLink, stationLabel, uid } from '~/sim/templates'
import { floorBounds } from '~/sim/grid'
import type { Floor, Layout, LinkKind, RobotView, SimProcess, StationKind, Visibility } from '~/sim/types'

export type EditorMode = 'building' | 'robots' | 'view'
export type EditorTool = 'select' | 'hand' | 'floor' | 'block' | 'zone' | 'station' | 'link' | 'calibrate'
export type SelKind = 'station' | 'block' | 'zone' | 'wall' | 'link' | 'area' | 'background'
export interface PlanSelection { kind: SelKind; id: string }

const props = defineProps<{
  layout: Layout
  floorId: string
  mode: EditorMode
  tool: EditorTool
  process: string
  stationKind: StationKind
  stationItem: string
  linkKind: LinkKind
  pendingLink: string
  colors: Record<string, string>
  processes: Record<string, SimProcess>
  visibility: Record<string, Visibility>
  highlight: string
  calibrateMeters: number
  selection: PlanSelection[]
  focusRobot: number | null
  snap: boolean
}>()
const emit = defineEmits<{
  change: [label: string]
  ready: []
  calibrated: [factor: number]
  hint: [text: string]
  select: [value: PlanSelection[]]
  focus: [id: number]
  tool: [value: EditorTool]
  linkStop: [linkId: string]
  zoom: [value: number]
}>()

const BLUE = '#0d99ff'
const BLUE_SOFT = 'rgba(13, 153, 255, 0.12)'
const GUIDE = '#ff3b6b'
const INK = '#1d2624'

const host = ref<HTMLDivElement | null>(null)
const zoom = ref(8)
let Konva: typeof KonvaNS | null = null
let stage: KonvaNS.Stage | null = null
let floorLayer: KonvaNS.Layer | null = null
let planLayer: KonvaNS.Layer | null = null
let robotLayer: KonvaNS.Layer | null = null
let uiLayer: KonvaNS.Layer | null = null
let robotDots: KonvaNS.Circle[] = []
let routeNodes: KonvaNS.Node[] = []
let observer: ResizeObserver | null = null
const images = new Map<string, HTMLImageElement>()

/* Состояние ввода. */
let spaceHeld = false
let penPoints: number[] = []
let rectStart: { x: number; y: number } | null = null
let calibration: { x: number; y: number }[] = []
let drag: { start: { x: number; y: number }; origin: Map<string, number[]>; moved: boolean } | null = null
let marquee: { start: { x: number; y: number } } | null = null
let hovered = ''

const floor = computed<Floor | undefined>(() => props.layout.floors.find((item) => item.id === props.floorId))
const step = () => (props.snap ? 0.5 : 0.05)
const snap = (value: number, s = step()) => Math.round(value / s) * s
const center = (value: number) => Math.floor(value) + 0.5
const color = (code: string) => props.colors[code] ?? '#1f7a5a'
const shown = (code?: string) => !code || (props.visibility[code] ?? 'full') !== 'hidden'
const alpha = (code?: string) => {
  if (!code) return 1
  if (props.highlight && props.highlight !== code) return 0.3
  return (props.visibility[code] ?? 'full') === 'dim' ? 0.35 : 1
}
const isSelected = (kind: SelKind, id: string) => props.selection.some((item) => item.kind === kind && item.id === id)

const STATUS_STROKE: Record<string, string> = { charging: '#e6a23c', queue: '#0f1413', lift: '#175fb0', off: '#9aa3a0' }

onMounted(async () => {
  Konva = (await import('konva')).default
  if (!host.value) return
  stage = new Konva.Stage({ container: host.value, width: host.value.clientWidth, height: host.value.clientHeight })
  floorLayer = new Konva.Layer()
  planLayer = new Konva.Layer()
  robotLayer = new Konva.Layer()
  uiLayer = new Konva.Layer({ listening: false })
  stage.add(floorLayer, planLayer, robotLayer, uiLayer)
  observer = new ResizeObserver(() => {
    if (!stage || !host.value) return
    stage.size({ width: host.value.clientWidth, height: host.value.clientHeight })
    renderFloor()
  })
  observer.observe(host.value)
  stage.on('wheel', onWheel)
  stage.on('mousedown touchstart', onDown)
  stage.on('mousemove touchmove', onMove)
  stage.on('mouseup touchend', onUp)
  stage.on('dblclick dbltap', onDouble)
  stage.on('dragmove', () => renderFloor())
  stage.on('dragend', () => { zoom.value = stage!.scaleX(); emit('zoom', zoom.value) })
  window.addEventListener('keydown', onKey)
  window.addEventListener('keyup', onKeyUp)
  fitContent()
  applyTool()
  emit('ready')
})

onBeforeUnmount(() => {
  observer?.disconnect()
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('keyup', onKeyUp)
  stage?.destroy()
  stage = null
})

watch(() => props.floorId, () => { resetDraft(); fitContent() })
watch(() => [props.tool, props.mode], () => { resetDraft(); applyTool() })
watch(() => props.selection, () => render())
watch(() => [props.colors, props.visibility, props.highlight, props.pendingLink], () => render(), { deep: true })

const pointer = () => {
  const pos = planLayer?.getRelativePointerPosition()
  return pos ? { x: pos.x, y: pos.y } : null
}

function cursorFor() {
  if (spaceHeld || props.tool === 'hand' || props.mode === 'view') return 'grab'
  if (props.tool === 'select') return 'default'
  return 'crosshair'
}

function applyTool() {
  if (!stage) return
  stage.draggable(props.tool === 'hand' || spaceHeld || props.mode === 'view')
  stage.container().style.cursor = cursorFor()
  if (props.mode === 'view') {
    emit('hint', 'Просмотр: колесо сдвигает, Ctrl + колесо приближает, клик по роботу подсвечивает его маршрут. Изменить схему — кнопка «Редактировать».')
    render()
    return
  }
  const hints: Record<EditorTool, string> = {
    select: props.mode === 'building'
      ? 'Клик выбирает участок пола, препятствие, лифт или чертёж. Рамка — несколько объектов. Колесо сдвигает, Ctrl + колесо приближает.'
      : 'Клик выбирает станцию или зону. Здание здесь не редактируется — для этого вкладка «Здание».',
    hand: 'Тяните, чтобы сдвинуть схему. Пробел делает то же самое в любом инструменте.',
    floor: 'Участок пола: протяните прямоугольник или кликайте углы и замкните на первой точке. Стены появятся по границе сами. Участки можно накладывать — получится проход.',
    block: 'Препятствие: протяните прямоугольник. Робот его объезжает.',
    zone: 'Зона процесса: протяните прямоугольник по площади работы.',
    station: 'Кликните место станции. Она встанет в центр клетки.',
    link: props.pendingLink ? 'Теперь кликните, где этот же переход выходит на этом этаже.' : 'Кликните, где стоит лифт или лестница на этом этаже. Потом укажите второй конец на другом.',
    calibrate: `Кликните два конца отрезка длиной ${props.calibrateMeters} м на чертеже.`,
  }
  emit('hint', hints[props.tool])
  render()
}

/* Камера. */
function frameBox(x0: number, y0: number, x1: number, y1: number) {
  if (!stage || !host.value) return
  const pad = 40
  const w = Math.max(4, x1 - x0)
  const h = Math.max(4, y1 - y0)
  const scale = Math.max(0.5, Math.min(60, (host.value.clientWidth - pad * 2) / w, (host.value.clientHeight - pad * 2) / h))
  stage.scale({ x: scale, y: scale })
  stage.position({ x: (host.value.clientWidth - w * scale) / 2 - x0 * scale, y: (host.value.clientHeight - h * scale) / 2 - y0 * scale })
  zoom.value = scale
  emit('zoom', scale)
  render()
}
function fit() {
  const f = floor.value
  if (!f) return
  const b = floorBounds(f)
  frameBox(b.minX, b.minY, b.maxX, b.maxY)
}
function fitContent() {
  const f = floor.value
  if (!f) return
  const xs: number[] = []
  const ys: number[] = []
  const push = (x: number, y: number) => { xs.push(x); ys.push(y) }
  f.stations.forEach((item) => { push(item.x - 1, item.y - 1); push(item.x + 1, item.y + 1) })
  f.zones.forEach((item) => { push(item.x, item.y); push(item.x + item.w, item.y + item.h) })
  f.blocks.forEach((item) => { push(item.x, item.y); push(item.x + item.w, item.y + item.h) })
  props.layout.links.forEach((link) => link.stops.filter((stop) => stop.floor === f.id).forEach((stop) => { push(stop.x - 1, stop.y - 1); push(stop.x + 1, stop.y + 1) }))
  if (xs.length < 4) return fit()
  const b = floorBounds(f)
  frameBox(Math.max(b.minX, Math.min(...xs) - 3), Math.max(b.minY, Math.min(...ys) - 3), Math.min(b.maxX, Math.max(...xs) + 3), Math.min(b.maxY, Math.max(...ys) + 3))
}
function zoomBy(factor: number, at?: { x: number; y: number }) {
  if (!stage) return
  const old = stage.scaleX()
  const next = Math.max(0.5, Math.min(80, old * factor))
  const point = at ?? { x: stage.width() / 2, y: stage.height() / 2 }
  const world = { x: (point.x - stage.x()) / old, y: (point.y - stage.y()) / old }
  stage.scale({ x: next, y: next })
  stage.position({ x: point.x - world.x * next, y: point.y - world.y * next })
  zoom.value = next
  emit('zoom', next)
  render()
}
function zoomTo(scale: number) {
  if (!stage) return
  zoomBy(scale / stage.scaleX())
}
function onWheel(event: KonvaNS.KonvaEventObject<WheelEvent>) {
  event.evt.preventDefault()
  if (!stage) return
  if (event.evt.ctrlKey || event.evt.metaKey) {
    const point = stage.getPointerPosition() ?? undefined
    zoomBy(Math.exp(-event.evt.deltaY * 0.01), point)
    return
  }
  stage.position({ x: stage.x() - event.evt.deltaX, y: stage.y() - event.evt.deltaY })
  renderFloor()
  planLayer?.batchDraw()
}

/* Пол, сетка и подложка. */
function loadImage(url: string, done: (img: HTMLImageElement) => void) {
  const cached = images.get(url)
  if (cached?.complete && cached.naturalWidth) return done(cached)
  const img = cached ?? new window.Image()
  img.onload = () => done(img)
  if (!cached) {
    img.src = url
    images.set(url, img)
  }
}

function renderFloor() {
  if (!Konva || !floorLayer || !floor.value || !stage) return
  const K = Konva
  const f = floor.value
  const scale = stage.scaleX()
  floorLayer.destroyChildren()
  const bounds = floorBounds(f)
  const building = props.mode === 'building'
  const areas = f.areas.filter((area) => area.points.length >= 6)
  const rings = areas.map((area) => {
    const ring: [number, number][] = []
    for (let i = 0; i < area.points.length; i += 2) ring.push([area.points[i]!, area.points[i + 1]!])
    return [ring]
  })
  let union: [number, number][][][] = []
  try {
    union = rings.length ? (polygonClipping.union(rings[0]!, ...rings.slice(1)) as [number, number][][][]) : []
  } catch {
    union = rings
  }
  /* Пол: заливка каждого участка, сетка обрезана по объединению. */
  const areaNodes = new Map<string, KonvaNS.Line>()
  for (const area of areas) {
    const chosen = isSelected('area', area.id)
    const hover = hovered === `area:${area.id}`
    const node = new K.Line({
      points: area.points, closed: true, name: `area:${area.id}`, listening: building,
      fill: chosen ? '#f3fbf7' : '#ffffff', shadowColor: 'rgba(15, 20, 19, 0.16)', shadowBlur: 20 / scale, shadowOffsetY: 5 / scale, shadowEnabled: !chosen,
      stroke: chosen || hover ? BLUE : undefined, strokeWidth: 1.5, strokeScaleEnabled: false,
    })
    areaNodes.set(area.id, node)
    floorLayer.add(node)
  }
  const gridStep = scale >= 6 ? 1 : scale >= 2 ? 5 : 10
  const gridShape = new K.Shape({
    listening: false,
    sceneFunc(ctx) {
      ctx.beginPath()
      for (let x = Math.ceil(bounds.minX); x <= bounds.maxX; x += gridStep) { ctx.moveTo(x, bounds.minY); ctx.lineTo(x, bounds.maxY) }
      for (let y = Math.ceil(bounds.minY); y <= bounds.maxY; y += gridStep) { ctx.moveTo(bounds.minX, y); ctx.lineTo(bounds.maxX, y) }
      ctx.lineWidth = 1 / scale
      ctx.strokeStyle = 'rgba(15, 20, 19, 0.06)'
      ctx.stroke()
      ctx.beginPath()
      for (let x = Math.ceil(bounds.minX / 10) * 10; x <= bounds.maxX; x += 10) { ctx.moveTo(x, bounds.minY); ctx.lineTo(x, bounds.maxY) }
      for (let y = Math.ceil(bounds.minY / 10) * 10; y <= bounds.maxY; y += 10) { ctx.moveTo(bounds.minX, y); ctx.lineTo(bounds.maxX, y) }
      ctx.strokeStyle = 'rgba(15, 20, 19, 0.12)'
      ctx.stroke()
    },
  })
  const clip = new K.Group({
    listening: false,
    clipFunc: (ctx) => {
      ctx.beginPath()
      for (const area of areas) {
        ctx.moveTo(area.points[0]!, area.points[1]!)
        for (let i = 2; i < area.points.length; i += 2) ctx.lineTo(area.points[i]!, area.points[i + 1]!)
        ctx.closePath()
      }
    },
  })
  clip.add(gridShape)
  const bg = f.background
  if (bg) {
    loadImage(bg.url, (img) => {
      if (!floorLayer || floor.value?.background !== bg) return
      const node = new K.Image({
        image: img, x: bg.x, y: bg.y, width: img.naturalWidth * bg.mpp, height: img.naturalHeight * bg.mpp, opacity: bg.opacity,
        name: 'background:bg', listening: building && props.tool === 'select' && !bg.locked,
      })
      clip.add(node)
      node.moveToBottom()
      gridShape.moveToTop()
      floorLayer.batchDraw()
    })
  }
  floorLayer.add(clip)
  /* Стены: контур объединения участков, включая внутренние дыры. */
  const wallNodes: KonvaNS.Line[] = []
  for (const polygon of union) {
    for (const ring of polygon) {
      const wall = new K.Line({ points: ring.flat(), closed: true, stroke: INK, strokeWidth: 3.5, lineJoin: 'round', strokeScaleEnabled: false, listening: false, fillEnabled: false })
      wallNodes.push(wall)
      floorLayer.add(wall)
    }
  }
  if (building && props.tool === 'select' && props.selection.length === 1 && props.selection[0]!.kind === 'area') {
    const area = areas.find((item) => item.id === props.selection[0]!.id)
    const node = area ? areaNodes.get(area.id) : undefined
    if (area && node) {
      for (let index = 0; index < area.points.length; index += 2) {
        addVertexHandle(floorLayer, area.points, index, () => {
          node.points(area.points)
          if (areas.length === 1 && wallNodes[0]) wallNodes[0].points(area.points)
          floorLayer?.batchDraw()
        }, () => {
          fitFloorToOutline(floor.value!)
          emit('change', 'Контур пола')
          render()
        })
      }
    }
  }
  floorLayer.add(new K.Text({ x: bounds.minX, y: bounds.minY - 22 / scale, text: `${f.name} · ${Math.round(bounds.width)} × ${Math.round(bounds.height)} м`, fontSize: 13 / scale, fontFamily: 'Manrope', fontStyle: '700', fill: '#3b4643', listening: false }))
  floorLayer.batchDraw()
}

function addVertexHandle(layer: KonvaNS.Layer, points: number[], index: number, live: () => void, done: () => void) {
  if (!Konva || !stage) return
  const scale = stage.scaleX()
  const size = 10 / scale
  const handle = new Konva.Rect({ x: points[index]!, y: points[index + 1]!, offsetX: size / 2, offsetY: size / 2, width: size, height: size, fill: '#fff', stroke: BLUE, strokeWidth: 2, strokeScaleEnabled: false, draggable: true, cornerRadius: size / 5 })
  handle.on('mouseenter', () => { if (stage) stage.container().style.cursor = 'crosshair' })
  handle.on('mouseleave', () => { if (stage) stage.container().style.cursor = cursorFor() })
  handle.on('mousedown touchstart', (event) => { event.cancelBubble = true })
  handle.on('dragmove', () => {
    points[index] = snap(handle.x(), 1)
    points[index + 1] = snap(handle.y(), 1)
    handle.position({ x: points[index]!, y: points[index + 1]! })
    live()
  })
  handle.on('dragend', () => done())
  layer.add(handle)
}

/* Объекты. */
function render() {
  if (!Konva || !planLayer || !floor.value || !stage) return
  renderFloor()
  const K = Konva
  const f = floor.value
  const scale = stage.scaleX()
  planLayer.destroyChildren()
  const building = props.mode === 'building'
  const selectable = props.tool === 'select' && props.mode !== 'view'
  const outline = (kind: SelKind, id: string, tone: string) => isSelected(kind, id) ? BLUE : hovered === `${kind}:${id}` ? BLUE : tone
  const widthFor = (kind: SelKind, id: string, base: number) => isSelected(kind, id) ? 2 : base
  /* Чужой режим рисуется бледнее и не ловит клики. В просмотре всё видно, ничего не выбирается. */
  const view = props.mode === 'view'
  const other = view ? 1 : 0.28
  const robotsLayer = props.mode === 'robots'

  for (const zone of f.zones) {
    if (!shown(zone.process)) continue
    const tone = color(zone.process)
    const fade = view ? alpha(zone.process) : building ? other : alpha(zone.process)
    const node = new K.Rect({
      x: zone.x, y: zone.y, width: zone.w, height: zone.h, name: `zone:${zone.id}`, opacity: fade, listening: robotsLayer,
      fill: `${tone}18`, stroke: outline('zone', zone.id, tone), strokeWidth: widthFor('zone', zone.id, 1.5), dash: isSelected('zone', zone.id) ? undefined : [6, 4], strokeScaleEnabled: false,
    })
    planLayer.add(node)
    if (scale >= 3) {
      const item = props.processes[zone.process]?.items.find((row) => row.key === (zone.item ?? 'zone'))
      planLayer.add(new K.Text({ x: zone.x + 0.5, y: zone.y + 0.4, text: item?.label ?? props.processes[zone.process]?.name ?? zone.process, fontSize: 12 / scale, fontFamily: 'Manrope', fontStyle: '600', fill: tone, opacity: fade, listening: false }))
    }
  }
  for (const block of f.blocks) {
    if (!shown(block.process)) continue
    const fade = building || view ? alpha(block.process) : 0.75
    planLayer.add(new K.Rect({
      x: block.x, y: block.y, width: block.w, height: block.h, name: `block:${block.id}`, opacity: fade, cornerRadius: 0.15, listening: building,
      fill: '#dfe5e2', stroke: outline('block', block.id, '#8d9894'), strokeWidth: widthFor('block', block.id, 1), strokeScaleEnabled: false,
    }))
    if (scale >= 5 && block.label && block.w >= 3) planLayer.add(new K.Text({ x: block.x + 0.35, y: block.y + 0.25, width: block.w - 0.7, text: block.label, fontSize: 11 / scale, fontFamily: 'Manrope', fill: '#3b4643', opacity: fade, listening: false, ellipsis: true, wrap: 'none' }))
  }
  for (const wall of f.walls) {
    const line = new K.Line({ points: wall.points, name: `wall:${wall.id}`, stroke: outline('wall', wall.id, INK), strokeWidth: isSelected('wall', wall.id) ? 4 : 3, lineCap: 'round', lineJoin: 'round', strokeScaleEnabled: false, hitStrokeWidth: 14, listening: building })
    planLayer.add(line)
    if (isSelected('wall', wall.id) && selectable && props.selection.length === 1) {
      for (let index = 0; index < wall.points.length; index += 2) addVertexHandle(planLayer, wall.points, index, () => { line.points(wall.points); planLayer?.batchDraw() }, () => { emit('change', 'Стена'); render() })
    }
  }
  for (const link of props.layout.links) {
    const stop = link.stops.find((item) => item.floor === f.id)
    if (!stop) continue
    const otherStop = link.stops.find((item) => item.floor !== f.id)
    const otherFloor = otherStop ? props.layout.floors.find((item) => item.id === otherStop.floor)?.name : null
    const group = new K.Group({ x: stop.x, y: stop.y, name: `link:${link.id}`, listening: building, opacity: building || view ? 1 : 0.8 })
    const fill = link.kind === 'elevator' ? '#175fb0' : '#6b5bd6'
    group.add(new K.Rect({ x: -1, y: -1, width: 2, height: 2, fill, cornerRadius: 0.3, stroke: outline('link', link.id, 'transparent'), strokeWidth: 2, strokeScaleEnabled: false }))
    group.add(new K.Text({ x: -1, y: -0.6, width: 2, align: 'center', text: link.kind === 'elevator' ? 'Л' : 'С', fontSize: 1.2, fontStyle: 'bold', fontFamily: 'Manrope', fill: '#fff', listening: false }))
    if (scale >= 4) group.add(new K.Text({ x: 1.3, y: -0.7, text: otherStop ? `${link.name} → ${otherFloor ?? '?'}` : `${link.name}: второй конец не указан`, fontSize: 11 / scale, fontFamily: 'Manrope', fill: otherStop ? '#3b4643' : '#b2582b', listening: false }))
    if (!otherStop) group.add(new K.Circle({ radius: 1.5, stroke: '#b2582b', strokeWidth: 1.5, dash: [4, 3], strokeScaleEnabled: false, listening: false }))
    planLayer.add(group)
  }
  for (const station of f.stations) {
    if (!shown(station.process)) continue
    const tone = color(station.process)
    const group = new K.Group({ x: station.x, y: station.y, name: `station:${station.id}`, opacity: building ? other : alpha(station.process), listening: robotsLayer })
    const chosen = isSelected('station', station.id) || hovered === `station:${station.id}`
    if (chosen) group.add(new K.Circle({ radius: 0.95, fill: BLUE_SOFT, stroke: BLUE, strokeWidth: 1.5, strokeScaleEnabled: false, listening: false }))
    if (station.kind === 'charge') group.add(new K.Rect({ x: -0.5, y: -0.5, width: 1, height: 1, fill: '#fff', stroke: '#e6a23c', strokeWidth: 2, strokeScaleEnabled: false, cornerRadius: 0.2 }))
    else if (station.kind === 'waypoint') group.add(new K.RegularPolygon({ sides: 4, radius: 0.6, fill: '#fff', stroke: tone, strokeWidth: 2, strokeScaleEnabled: false }))
    else group.add(new K.Circle({ radius: 0.55, fill: station.kind === 'load' ? tone : '#fff', stroke: tone, strokeWidth: 2, strokeScaleEnabled: false }))
    if (scale >= 4 && !building) group.add(new K.Text({ x: 0.85, y: -0.45, text: stationLabel(props.processes[station.process], station.kind, station.item), fontSize: 11 / scale, fontFamily: 'Manrope', fill: '#3b4643', listening: false }))
    planLayer.add(group)
  }
  planLayer.batchDraw()
  renderUi()
}

/* Слой выделения, направляющих и черновиков. */
function renderUi(guides: { x?: number; y?: number }[] = []) {
  if (!Konva || !uiLayer || !stage || !floor.value) return
  const K = Konva
  const scale = stage.scaleX()
  uiLayer.destroyChildren()
  const f = floor.value
  const boxes = props.selection.map(bboxOf).filter((box): box is Box => Boolean(box))
  if (boxes.length > 1) {
    const union = boxes.reduce((acc, box) => ({ x: Math.min(acc.x, box.x), y: Math.min(acc.y, box.y), x2: Math.max(acc.x2, box.x + box.w), y2: Math.max(acc.y2, box.y + box.h) }), { x: Infinity, y: Infinity, x2: -Infinity, y2: -Infinity })
    uiLayer.add(new K.Rect({ x: union.x, y: union.y, width: union.x2 - union.x, height: union.y2 - union.y, stroke: BLUE, strokeWidth: 1, dash: [4, 3], strokeScaleEnabled: false }))
  }
  const single = props.selection.length === 1 ? props.selection[0]! : null
  if (single && (single.kind === 'block' || single.kind === 'zone') && props.tool === 'select') {
    const box = bboxOf(single)
    if (box) {
      uiLayer.add(new K.Rect({ x: box.x, y: box.y, width: box.w, height: box.h, stroke: BLUE, strokeWidth: 1.5, strokeScaleEnabled: false }))
      uiLayer.add(new K.Text({ x: box.x, y: box.y + box.h + 6 / scale, width: box.w, align: 'center', text: `${fmt(box.w)} × ${fmt(box.h)} м`, fontSize: 11 / scale, fontFamily: 'JetBrains Mono', fill: BLUE, listening: false }))
    }
  }
  for (const guide of guides) {
    const b = floorBounds(f)
    if (guide.x !== undefined) uiLayer.add(new K.Line({ points: [guide.x, b.minY - 2, guide.x, b.maxY + 2], stroke: GUIDE, strokeWidth: 1, strokeScaleEnabled: false }))
    if (guide.y !== undefined) uiLayer.add(new K.Line({ points: [b.minX - 2, guide.y, b.maxX + 2, guide.y], stroke: GUIDE, strokeWidth: 1, strokeScaleEnabled: false }))
  }
  const at = pointer()
  if (props.tool === 'floor' && penPoints.length && at) {
    const pts = [...penPoints, snap(at.x, 1), snap(at.y, 1)]
    uiLayer.add(new K.Line({ points: pts, stroke: INK, strokeWidth: 2, dash: [6, 4], strokeScaleEnabled: false, closed: penPoints.length >= 6, fill: 'rgba(255,255,255,0.5)' }))
    for (let i = 0; i < penPoints.length; i += 2) uiLayer.add(new K.Circle({ x: penPoints[i], y: penPoints[i + 1], radius: 4 / scale, fill: '#fff', stroke: BLUE, strokeWidth: 1.5, strokeScaleEnabled: false }))
  }
  if (rectStart && at && (props.tool === 'block' || props.tool === 'zone' || props.tool === 'floor')) {
    const r = normalized(rectStart, at)
    uiLayer.add(new K.Rect({ x: r.x, y: r.y, width: r.width, height: r.height, stroke: BLUE, strokeWidth: 1.5, dash: [6, 4], strokeScaleEnabled: false, fill: BLUE_SOFT }))
    uiLayer.add(new K.Text({ x: r.x, y: r.y + r.height + 6 / scale, width: Math.max(r.width, 6), align: 'center', text: `${fmt(r.width)} × ${fmt(r.height)} м`, fontSize: 11 / scale, fontFamily: 'JetBrains Mono', fill: BLUE }))
  }
  if (marquee && at) {
    const r = normalized(marquee.start, at, 0.01)
    uiLayer.add(new K.Rect({ x: r.x, y: r.y, width: r.width, height: r.height, stroke: BLUE, strokeWidth: 1, strokeScaleEnabled: false, fill: 'rgba(13, 153, 255, 0.08)' }))
  }
  if (props.tool === 'calibrate' && calibration.length && at) {
    const first = calibration[0]!
    uiLayer.add(new K.Line({ points: [first.x, first.y, at.x, at.y], stroke: '#e6a23c', strokeWidth: 2, dash: [6, 4], strokeScaleEnabled: false }))
    uiLayer.add(new K.Text({ x: (first.x + at.x) / 2, y: (first.y + at.y) / 2 - 16 / scale, text: `${props.calibrateMeters} м`, fontSize: 12 / scale, fontFamily: 'JetBrains Mono', fill: '#8a5200' }))
  }
  uiLayer.batchDraw()
}

interface Box { x: number; y: number; w: number; h: number }
const fmt = (value: number) => value.toLocaleString('ru-RU', { maximumFractionDigits: 1 })
const normalized = (a: { x: number; y: number }, b: { x: number; y: number }, s = step()) => {
  const x0 = snap(Math.min(a.x, b.x), s)
  const y0 = snap(Math.min(a.y, b.y), s)
  const x1 = snap(Math.max(a.x, b.x), s)
  const y1 = snap(Math.max(a.y, b.y), s)
  return { x: x0, y: y0, width: Math.max(0, x1 - x0), height: Math.max(0, y1 - y0) }
}

function bboxOf(sel: PlanSelection): Box | null {
  const f = floor.value
  if (!f) return null
  if (sel.kind === 'block') { const b = f.blocks.find((i) => i.id === sel.id); return b ? { x: b.x, y: b.y, w: b.w, h: b.h } : null }
  if (sel.kind === 'zone') { const z = f.zones.find((i) => i.id === sel.id); return z ? { x: z.x, y: z.y, w: z.w, h: z.h } : null }
  if (sel.kind === 'station') { const s = f.stations.find((i) => i.id === sel.id); return s ? { x: s.x - 0.6, y: s.y - 0.6, w: 1.2, h: 1.2 } : null }
  if (sel.kind === 'link') { const stop = props.layout.links.find((i) => i.id === sel.id)?.stops.find((s) => s.floor === f.id); return stop ? { x: stop.x - 1, y: stop.y - 1, w: 2, h: 2 } : null }
  if (sel.kind === 'wall' || sel.kind === 'area') {
    const w = sel.kind === 'wall' ? f.walls.find((i) => i.id === sel.id) : f.areas.find((i) => i.id === sel.id)
    if (!w) return null
    const xs = w.points.filter((_, i) => i % 2 === 0)
    const ys = w.points.filter((_, i) => i % 2 === 1)
    return { x: Math.min(...xs), y: Math.min(...ys), w: Math.max(...xs) - Math.min(...xs), h: Math.max(...ys) - Math.min(...ys) }
  }
  return null
}

function targetOf(node: KonvaNS.Node | null): PlanSelection | null {
  let current: KonvaNS.Node | null = node
  while (current && current !== stage && !current.name()) current = current.getParent()
  const [kind, id] = (current?.name() ?? '').split(':')
  if (!id) return null
  if (kind === 'wall' || kind === 'block' || kind === 'zone' || kind === 'station' || kind === 'link' || kind === 'area' || kind === 'background') return { kind, id }
  return null
}

/* Ввод. */
function onDown(event: KonvaNS.KonvaEventObject<MouseEvent | TouchEvent>) {
  const at = pointer()
  if (!at || !floor.value) return
  if (spaceHeld || props.tool === 'hand' || props.mode === 'view') return
  if (props.tool === 'block' || props.tool === 'zone' || props.tool === 'floor') {
    rectStart = at
    return
  }
  if (props.tool !== 'select') return
  const target = targetOf(event.target)
  const shift = 'shiftKey' in event.evt && event.evt.shiftKey
  if (!target) {
    if (!shift) emit('select', [])
    marquee = { start: at }
    return
  }
  if (target.kind === 'background' && floor.value.background && !floor.value.background.locked) {
    emit('select', [target])
    drag = { start: at, origin: new Map([['background', [floor.value.background.x, floor.value.background.y]]]), moved: false }
    return
  }
  let next: PlanSelection[]
  if (shift) next = isSelected(target.kind, target.id) ? props.selection.filter((s) => !(s.kind === target.kind && s.id === target.id)) : [...props.selection, target]
  else next = isSelected(target.kind, target.id) ? props.selection : [target]
  emit('select', next)
  const origin = new Map<string, number[]>()
  for (const sel of next) {
    const f = floor.value
    if (sel.kind === 'block') { const b = f.blocks.find((i) => i.id === sel.id); if (b) origin.set(`block:${b.id}`, [b.x, b.y]) }
    if (sel.kind === 'zone') { const z = f.zones.find((i) => i.id === sel.id); if (z) origin.set(`zone:${z.id}`, [z.x, z.y]) }
    if (sel.kind === 'station') { const s = f.stations.find((i) => i.id === sel.id); if (s) origin.set(`station:${s.id}`, [s.x, s.y]) }
    if (sel.kind === 'link') { const stop = props.layout.links.find((i) => i.id === sel.id)?.stops.find((st) => st.floor === f.id); if (stop) origin.set(`link:${sel.id}`, [stop.x, stop.y]) }
    if (sel.kind === 'wall') { const w = f.walls.find((i) => i.id === sel.id); if (w) origin.set(`wall:${w.id}`, [...w.points]) }
    if (sel.kind === 'area') { const a = f.areas.find((i) => i.id === sel.id); if (a) origin.set(`area:${a.id}`, [...a.points]) }
  }
  drag = { start: at, origin, moved: false }
}

function onMove(event: KonvaNS.KonvaEventObject<MouseEvent | TouchEvent>) {
  const at = pointer()
  if (!at || !stage || props.mode === 'view') return
  if (props.tool === 'select' && !drag && !marquee) {
    const target = targetOf(event.target)
    const key = target ? `${target.kind}:${target.id}` : ''
    if (key !== hovered) {
      const wasArea = hovered.startsWith('area:')
      hovered = key
      stage.container().style.cursor = target ? 'move' : cursorFor()
      if (key.startsWith('area:') || wasArea) renderFloor()
      else render()
    }
  }
  if (drag) {
    const dx = at.x - drag.start.x
    const dy = at.y - drag.start.y
    if (!drag.moved && Math.hypot(dx, dy) * stage.scaleX() < 3) return
    drag.moved = true
    applyDrag(dx, dy)
    return
  }
  if (marquee || rectStart || penPoints.length || (props.tool === 'calibrate' && calibration.length)) renderUi()
}

function applyDrag(dx: number, dy: number) {
  const f = floor.value
  if (!f || !drag) return
  const guides: { x?: number; y?: number }[] = []
  const first = drag.origin.entries().next().value as [string, number[]] | undefined
  let sx = snap(dx)
  let sy = snap(dy)
  if (first && props.snap) {
    const [key, origin] = first
    const box = movingBox(key, origin, sx, sy)
    if (box) {
      const threshold = 6 / (stage?.scaleX() ?? 8)
      const others = candidates(new Set(drag.origin.keys()))
      const mine = { xs: [box.x, box.x + box.w / 2, box.x + box.w], ys: [box.y, box.y + box.h / 2, box.y + box.h] }
      let bestX: { d: number; shift: number; at: number } | null = null
      let bestY: { d: number; shift: number; at: number } | null = null
      for (const x of mine.xs) for (const ox of others.xs) { const d = Math.abs(ox - x); if (d < threshold && (!bestX || d < bestX.d)) bestX = { d, shift: ox - x, at: ox } }
      for (const y of mine.ys) for (const oy of others.ys) { const d = Math.abs(oy - y); if (d < threshold && (!bestY || d < bestY.d)) bestY = { d, shift: oy - y, at: oy } }
      if (bestX) { sx += bestX.shift; guides.push({ x: bestX.at }) }
      if (bestY) { sy += bestY.shift; guides.push({ y: bestY.at }) }
    }
  }
  for (const [key, origin] of drag.origin) {
    const [kind, id] = key.split(':') as [string, string]
    if (kind === 'background' && f.background) { f.background.x = origin[0]! + sx; f.background.y = origin[1]! + sy }
    if (kind === 'block') { const b = f.blocks.find((i) => i.id === id); if (b) { b.x = origin[0]! + sx; b.y = origin[1]! + sy } }
    if (kind === 'zone') { const z = f.zones.find((i) => i.id === id); if (z) { z.x = origin[0]! + sx; z.y = origin[1]! + sy } }
    if (kind === 'station') { const s = f.stations.find((i) => i.id === id); if (s) { s.x = center(origin[0]! + sx); s.y = center(origin[1]! + sy) } }
    if (kind === 'link') { const stop = props.layout.links.find((i) => i.id === id)?.stops.find((st) => st.floor === f.id); if (stop) { stop.x = center(origin[0]! + sx); stop.y = center(origin[1]! + sy) } }
    if (kind === 'wall') { const w = f.walls.find((i) => i.id === id); if (w) w.points = origin.map((v, i) => v + (i % 2 === 0 ? sx : sy)) }
    if (kind === 'area') { const a = f.areas.find((i) => i.id === id); if (a) a.points = origin.map((v, i) => v + (i % 2 === 0 ? snap(sx, 1) : snap(sy, 1))) }
  }
  render()
  renderUi(guides)
}

function movingBox(key: string, origin: number[], sx: number, sy: number): Box | null {
  const f = floor.value
  if (!f) return null
  const [kind, id] = key.split(':') as [string, string]
  if (kind === 'block') { const b = f.blocks.find((i) => i.id === id); return b ? { x: origin[0]! + sx, y: origin[1]! + sy, w: b.w, h: b.h } : null }
  if (kind === 'zone') { const z = f.zones.find((i) => i.id === id); return z ? { x: origin[0]! + sx, y: origin[1]! + sy, w: z.w, h: z.h } : null }
  if (kind === 'station' || kind === 'link') return { x: origin[0]! + sx - 0.5, y: origin[1]! + sy - 0.5, w: 1, h: 1 }
  return null
}

function candidates(exclude: Set<string>) {
  const f = floor.value
  const xs: number[] = []
  const ys: number[] = []
  if (!f) return { xs, ys }
  const push = (box: Box) => { xs.push(box.x, box.x + box.w / 2, box.x + box.w); ys.push(box.y, box.y + box.h / 2, box.y + box.h) }
  const b = floorBounds(f)
  push({ x: b.minX, y: b.minY, w: b.width, h: b.height })
  f.blocks.forEach((i) => { if (!exclude.has(`block:${i.id}`)) push({ x: i.x, y: i.y, w: i.w, h: i.h }) })
  f.zones.forEach((i) => { if (!exclude.has(`zone:${i.id}`)) push({ x: i.x, y: i.y, w: i.w, h: i.h }) })
  f.stations.forEach((i) => { if (!exclude.has(`station:${i.id}`)) push({ x: i.x - 0.5, y: i.y - 0.5, w: 1, h: 1 }) })
  return { xs, ys }
}

function onUp(event: KonvaNS.KonvaEventObject<MouseEvent | TouchEvent>) {
  if (props.mode === 'view') return
  const at = pointer()
  const f = floor.value
  if (!f) return
  if (drag) {
    const moved = drag.moved
    const movedArea = moved && [...drag.origin.keys()].some((key) => key.startsWith('area:'))
    drag = null
    if (moved) {
      if (movedArea && f) {
        const first = props.selection.find((sel) => sel.kind === 'area')
        const merged = first ? mergeAreas(f, first.id) : ''
        fitFloorToOutline(f)
        if (merged && merged !== first?.id) emit('select', [{ kind: 'area', id: merged }])
      }
      emit('change', 'Перемещение')
      render()
    } else onClick(event)
    return
  }
  if (marquee) {
    const start = marquee.start
    marquee = null
    if (at && Math.hypot(at.x - start.x, at.y - start.y) * (stage?.scaleX() ?? 1) > 4) {
      const r = normalized(start, at, 0.01)
      const hits: PlanSelection[] = []
      const inside = (box: Box) => box.x >= r.x && box.y >= r.y && box.x + box.w <= r.x + r.width && box.y + box.h <= r.y + r.height
      const building = props.mode === 'building'
      if (building) {
        f.blocks.forEach((i) => { if (shown(i.process) && inside({ x: i.x, y: i.y, w: i.w, h: i.h })) hits.push({ kind: 'block', id: i.id }) })
        f.walls.forEach((w) => { const box = bboxOf({ kind: 'wall', id: w.id }); if (box && inside(box)) hits.push({ kind: 'wall', id: w.id }) })
        props.layout.links.forEach((l) => { const stop = l.stops.find((s) => s.floor === f.id); if (stop && inside({ x: stop.x - 1, y: stop.y - 1, w: 2, h: 2 })) hits.push({ kind: 'link', id: l.id }) })
        f.areas.forEach((a) => { const box = bboxOf({ kind: 'area', id: a.id }); if (box && inside(box)) hits.push({ kind: 'area', id: a.id }) })
      } else {
        f.zones.forEach((i) => { if (shown(i.process) && inside({ x: i.x, y: i.y, w: i.w, h: i.h })) hits.push({ kind: 'zone', id: i.id }) })
        f.stations.forEach((i) => { if (shown(i.process) && inside({ x: i.x - 0.5, y: i.y - 0.5, w: 1, h: 1 })) hits.push({ kind: 'station', id: i.id }) })
      }
      emit('select', hits)
    }
    renderUi()
    return
  }
  if (rectStart && at) {
    const start = rectStart
    rectStart = null
    const r = normalized(start, at, props.tool === 'floor' ? 1 : step())
    const dragged = r.width >= 1 && r.height >= 1
    if (props.tool === 'floor') {
      if (dragged) {
        const area = { id: uid('ar'), points: [r.x, r.y, r.x + r.width, r.y, r.x + r.width, r.y + r.height, r.x, r.y + r.height] }
        f.areas.push(area)
        finishFloor('Участок пола', area.id)
      } else {
        penClick(at, 1)
      }
      return
    }
    if (!dragged) return renderUi()
    if (props.tool === 'block') f.blocks.push({ id: uid('bl'), x: r.x, y: r.y, w: r.width, h: r.height, label: 'Препятствие' })
    else f.zones.push({ id: uid('zn'), process: props.process, item: props.stationItem || undefined, x: r.x, y: r.y, w: r.width, h: r.height })
    emit('change', props.tool === 'block' ? 'Препятствие' : 'Зона')
    emit('select', [{ kind: props.tool === 'block' ? 'block' : 'zone', id: props.tool === 'block' ? f.blocks.at(-1)!.id : f.zones.at(-1)!.id }])
    emit('tool', 'select')
    render()
    return
  }
  if (props.tool === 'station' || props.tool === 'link' || props.tool === 'calibrate') onClick(event)
}

function penClick(at: { x: number; y: number }, s: number) {
  const x = snap(at.x, s)
  const y = snap(at.y, s)
  const n = penPoints.length
  if (n >= 6 && props.tool === 'floor' && Math.hypot(penPoints[0]! - x, penPoints[1]! - y) < 1.01) return closePen()
  if (n >= 2 && penPoints[n - 2] === x && penPoints[n - 1] === y) return
  penPoints.push(x, y)
  renderUi()
}

function closePen() {
  const f = floor.value
  if (!f || penPoints.length < 6) return
  const area = { id: uid('ar'), points: [...penPoints] }
  f.areas.push(area)
  penPoints = []
  finishFloor('Участок пола', area.id)
}

function finishFloor(label: string, areaId: string) {
  const f = floor.value
  if (!f) return
  penPoints = []
  /* Пересекающиеся участки становятся одним: без шва на полу и без стены между ними. */
  const merged = mergeAreas(f, areaId)
  fitFloorToOutline(f)
  emit('change', merged === areaId ? label : 'Участки пола объединены')
  emit('select', [{ kind: 'area', id: merged }])
  emit('tool', 'select')
  render()
}

function onClick(event: KonvaNS.KonvaEventObject<MouseEvent | TouchEvent>) {
  const f = floor.value
  const at = pointer()
  if (!f || !at) return
  if (props.tool === 'select') return
  if (props.tool === 'station') {
    if (!props.process) return emit('hint', 'Сначала выберите процесс и объект.')
    f.stations.push({ id: uid('st'), process: props.process, kind: props.stationKind, item: props.stationItem || undefined, x: center(at.x), y: center(at.y) })
    emit('change', 'Станция')
    render()
    return
  }
  if (props.tool === 'link') {
    if (props.pendingLink) {
      const link = props.layout.links.find((item) => item.id === props.pendingLink)
      if (!link) return
      if (link.stops.some((stop) => stop.floor === f.id)) return emit('hint', 'На этом этаже конец уже стоит. Переключитесь на другой этаж.')
      link.stops.push({ floor: f.id, x: center(at.x), y: center(at.y) })
      emit('change', `${link.name}: второй конец`)
      emit('linkStop', link.id)
      emit('select', [{ kind: 'link', id: link.id }])
      emit('tool', 'select')
      render()
      return
    }
    const link = newLink(props.linkKind, [{ floor: f.id, x: center(at.x), y: center(at.y) }])
    props.layout.links.push(link)
    emit('change', `${link.name}: первый конец`)
    emit('linkStop', link.id)
    render()
    return
  }
  if (props.tool === 'calibrate') {
    calibration.push(at)
    if (calibration.length < 2) return renderUi()
    const [a, b] = calibration as [{ x: number; y: number }, { x: number; y: number }]
    calibration = []
    const measured = Math.hypot(b.x - a.x, b.y - a.y)
    const bg = f.background
    if (!bg || measured < 0.01 || !(props.calibrateMeters > 0)) return renderUi()
    const factor = props.calibrateMeters / measured
    bg.x = a.x - (a.x - bg.x) * factor
    bg.y = a.y - (a.y - bg.y) * factor
    bg.mpp *= factor
    emit('calibrated', factor)
    emit('change', 'Масштаб чертежа')
    emit('tool', 'select')
    render()
  }
}

function onDouble() {
  if (props.tool === 'floor' && penPoints.length >= 6) closePen()
}

function resetDraft() {
  penPoints = []
  rectStart = null
  calibration = []
  marquee = null
  drag = null
  renderUi()
}

function onKey(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  if (target && ['INPUT', 'SELECT', 'TEXTAREA'].includes(target.tagName)) return
  if (props.mode === 'view') {
    if (event.shiftKey && event.key === '1') { event.preventDefault(); fit() }
    if (event.shiftKey && event.key === '2') { event.preventDefault(); fitContent() }
    return
  }
  if (event.code === 'Space' && !spaceHeld) {
    spaceHeld = true
    event.preventDefault()
    if (stage) { stage.draggable(true); stage.container().style.cursor = 'grab' }
    return
  }
  const meta = event.metaKey || event.ctrlKey
  if (meta && (event.key === '0')) { event.preventDefault(); zoomTo(10); return }
  if (event.shiftKey && event.key === '1') { event.preventDefault(); fit(); return }
  if (event.shiftKey && event.key === '2') { event.preventDefault(); fitContent(); return }
  if (event.key === 'Enter') {
    if (props.tool === 'floor' && penPoints.length >= 6) closePen()
    return
  }
  if (event.key === 'Escape') {
    if (penPoints.length || rectStart || calibration.length) { resetDraft(); return }
    if (props.tool !== 'select') { emit('tool', 'select'); return }
    emit('select', [])
    return
  }
  if (event.key === 'Backspace' && props.tool === 'floor' && penPoints.length) {
    event.preventDefault()
    penPoints.splice(-2, 2)
    renderUi()
    return
  }
  if (props.tool !== 'select' || meta) return
  if (event.key.startsWith('Arrow') && props.selection.length) {
    event.preventDefault()
    const d = event.shiftKey ? 5 : 1
    nudge(event.key === 'ArrowLeft' ? -d : event.key === 'ArrowRight' ? d : 0, event.key === 'ArrowUp' ? -d : event.key === 'ArrowDown' ? d : 0)
  }
}

function onKeyUp(event: KeyboardEvent) {
  if (event.code === 'Space') {
    spaceHeld = false
    applyTool()
  }
}

function nudge(dx: number, dy: number) {
  const f = floor.value
  if (!f) return
  for (const sel of props.selection) {
    if (sel.kind === 'block') { const b = f.blocks.find((i) => i.id === sel.id); if (b) { b.x += dx; b.y += dy } }
    if (sel.kind === 'zone') { const z = f.zones.find((i) => i.id === sel.id); if (z) { z.x += dx; z.y += dy } }
    if (sel.kind === 'station') { const s = f.stations.find((i) => i.id === sel.id); if (s) { s.x += dx; s.y += dy } }
    if (sel.kind === 'link') { const stop = props.layout.links.find((i) => i.id === sel.id)?.stops.find((st) => st.floor === f.id); if (stop) { stop.x += dx; stop.y += dy } }
    if (sel.kind === 'wall') { const w = f.walls.find((i) => i.id === sel.id); if (w) w.points = w.points.map((v, i) => v + (i % 2 === 0 ? dx : dy)) }
    if (sel.kind === 'area') { const a = f.areas.find((i) => i.id === sel.id); if (a) a.points = a.points.map((v, i) => v + (i % 2 === 0 ? dx : dy)) }
  }
  emit('change', 'Сдвиг стрелками')
  render()
}

/* Ручки размера у прямоугольников: единственный выделенный блок или зона. */
let transformer: KonvaNS.Transformer | null = null
watch(() => [props.selection, props.tool], () => attachTransformer(), { deep: true })
function attachTransformer() {
  transformer?.destroy()
  transformer = null
  if (!Konva || !planLayer || !floor.value || props.tool !== 'select' || props.selection.length !== 1) return
  const sel = props.selection[0]!
  if (sel.kind !== 'block' && sel.kind !== 'zone') return
  const node = planLayer.findOne(`.${sel.kind}:${sel.id}`)
  if (!node) return
  transformer = new Konva.Transformer({
    rotateEnabled: false, ignoreStroke: true, borderStroke: BLUE, borderStrokeWidth: 1.5, anchorStroke: BLUE, anchorFill: '#fff', anchorSize: 8, anchorCornerRadius: 2, padding: 0,
    keepRatio: false, enabledAnchors: ['top-left', 'top-center', 'top-right', 'middle-left', 'middle-right', 'bottom-left', 'bottom-center', 'bottom-right'],
  })
  planLayer.add(transformer)
  transformer.nodes([node])
  transformer.on('transform', () => renderUi())
  transformer.on('transformend', () => {
    const box = { x: snap(node.x()), y: snap(node.y()), w: Math.max(0.5, snap(node.width() * node.scaleX())), h: Math.max(0.5, snap(node.height() * node.scaleY())) }
    const target = sel.kind === 'block' ? floor.value?.blocks.find((i) => i.id === sel.id) : floor.value?.zones.find((i) => i.id === sel.id)
    if (!target) return
    Object.assign(target, box)
    emit('change', 'Размер')
    render()
    attachTransformer()
  })
  planLayer.batchDraw()
}

/* Роботы и маршруты. */
function drawRobots(views: RobotView[]) {
  if (!Konva || !robotLayer || !stage) return
  routeNodes.forEach((node) => node.destroy())
  routeNodes = []
  const visible = views.filter((view) => view.floor === props.floorId && shown(view.process))
  const moving = visible.filter((view) => view.trip && view.trip.path.length >= 4)
  const scale = stage.scaleX()
  for (const view of moving) {
    const trip = view.trip!
    const focused = view.id === props.focusRobot
    const line = new Konva.Line({ points: trip.path, stroke: color(view.process), strokeWidth: focused ? 3 : 1.5, dash: [7, 5], lineCap: 'round', lineJoin: 'round', strokeScaleEnabled: false, listening: false, opacity: (focused ? 1 : 0.7) * alpha(view.process) })
    robotLayer.add(line)
    routeNodes.push(line)
    if (focused || moving.length <= 8) {
      const label = new Konva.Label({ x: view.x + 0.7, y: view.y - 1.4, listening: false })
      label.add(new Konva.Tag({ fill: 'rgba(255,255,255,0.94)', cornerRadius: 4 / scale, pointerDirection: 'down', pointerWidth: 6 / scale, pointerHeight: 4 / scale, shadowColor: 'rgba(0,0,0,0.12)', shadowBlur: 6 / scale }))
      label.add(new Konva.Text({ text: `${trip.from} → ${trip.to} · ${trip.leftM.toLocaleString('ru-RU', { maximumFractionDigits: trip.leftM >= 100 ? 0 : 1 })} м`, fontSize: 12 / scale, fontFamily: 'Manrope', fill: '#0f1413', padding: 4 / scale }))
      robotLayer.add(label)
      routeNodes.push(label)
    }
  }
  while (robotDots.length < visible.length) {
    const dot = new Konva.Circle({ radius: 0.45, strokeWidth: 2, strokeScaleEnabled: false, perfectDrawEnabled: false })
    dot.on('click tap', () => emit('focus', Number(dot.getAttr('robotId'))))
    robotDots.push(dot)
    robotLayer.add(dot)
  }
  robotDots.forEach((dot, index) => {
    const view = visible[index]
    if (!view) return dot.visible(false)
    dot.visible(true)
    dot.setAttr('robotId', view.id)
    dot.listening(props.tool === 'select' || props.mode === 'view')
    dot.opacity(alpha(view.process))
    dot.position({ x: view.x, y: view.y })
    const tone = view.status === 'off' ? '#9aa3a0' : color(view.process)
    dot.fill(view.status === 'loaded' ? '#0f1413' : tone)
    dot.stroke(view.id === props.focusRobot ? '#fff36a' : (STATUS_STROKE[view.status] ?? '#ffffff'))
    dot.radius(view.id === props.focusRobot ? 0.7 : 0.45)
    dot.moveToTop()
  })
  robotLayer.batchDraw()
}
function clearRobots() {
  routeNodes.forEach((node) => node.destroy())
  routeNodes = []
  robotDots.forEach((dot) => dot.destroy())
  robotDots = []
  robotLayer?.batchDraw()
}
function exportPng() {
  return stage?.toDataURL({ pixelRatio: 2 }) ?? ''
}

defineExpose({ fit, fitContent, zoomBy, zoomTo, drawRobots, clearRobots, render, exportPng })
</script>

<template>
  <div class="editor">
    <div ref="host" class="stage" />
  </div>
</template>

<style scoped>
.editor { position: relative; width: 100%; height: 100%; min-height: 480px; background: #e7ecea; background-image: radial-gradient(rgba(15, 20, 19, 0.08) 1px, transparent 1px); background-size: 18px 18px; }
.stage { position: absolute; inset: 0; }
</style>
