import polygonClipping from 'polygon-clipping'
import { floorBounds, insideFloorAreas } from './grid'
import type { Floor, FloorArea, ItemRole, Layout, LayoutGuide, LayoutItem, Link, ProcessKind, RobotSpec, SimProcess, StationKind } from './types'

type Site = Record<string, unknown>

interface ProcessPlan {
  kind: ProcessKind
  unit: string
  perDay?: (site: Site) => number | null
  perShift?: (site: Site) => number | null
  route?: (site: Site) => number | null
  basis: string
}

const num = (site: Site, key: string) => {
  const raw = site[key]
  if (raw === null || raw === undefined || raw === '') return null
  const value = Number(raw)
  return Number.isFinite(value) ? value : null
}
const sum = (site: Site, ...keys: string[]) => {
  const values = keys.map((key) => num(site, key))
  if (values.every((value) => value === null)) return null
  return values.reduce<number>((acc, value) => acc + (value ?? 0), 0)
}
const pickerRoute = (site: Site) => num(site, 'picker_route_m')

const pallets: ProcessPlan = {
  kind: 'transport', unit: 'паллет', perDay: (s) => sum(s, 'inbound_pallets_per_day', 'outbound_pallets_per_day'), route: pickerRoute,
  basis: 'Поток: приёмка + отгрузка паллет в сутки. Маршрут: длина маршрута площадки.',
}
const units: ProcessPlan = {
  kind: 'transport', unit: 'шт.', perDay: (s) => num(s, 'pick_units_per_day'), route: pickerRoute,
  basis: 'Поток: объём отбора в штуках в сутки. Маршрут: длина маршрута площадки.',
}
const fixed = (perDay: number, route: number, unit: string, source: string): ProcessPlan => ({
  kind: 'transport', unit, perDay: () => perDay, route: () => route,
  basis: `Поток ${perDay} ${unit} в сутки и маршрут ${route} м в одну сторону — те же константы, что в формуле количества (${source}).`,
})
const cleaning: ProcessPlan = {
  kind: 'coverage', unit: 'м²', perShift: (s) => num(s, 'clean_area_m2'),
  basis: 'Убираемая площадь за смену, производительность робота — из карточки, м²/ч.',
}
const inventory: ProcessPlan = {
  kind: 'coverage', unit: 'паллетомест', perDay: (s) => num(s, 'pallet_places'),
  basis: 'Все паллетоместа за сутки, пропускная способность робота — из карточки.',
}
const patrol: ProcessPlan = {
  kind: 'patrol', unit: 'обходов', perDay: () => 24,
  basis: '24 обхода периметра в сутки и 240 с остановок на обход — как в формуле количества.',
}

export const PROCESS_PLANS: Record<string, ProcessPlan> = {
  pallet_transport: pallets,
  pallet_storage: pallets,
  auto_pallet_storage: pallets,
  rack_placement: pallets,
  cart_towing: pallets,
  packing: pallets,
  pallet_handling: pallets,
  palletizing: pallets,
  order_picking: {
    kind: 'transport', unit: 'строк', perDay: (s) => num(s, 'pick_lines_per_day'), route: pickerRoute,
    basis: 'Поток: строк отбора в сутки. Маршрут: длина маршрута отборщика на строку.',
  },
  box_transport: units,
  parcel_sorting: units,
  tote_delivery: units,
  apron_transport: fixed(420, 292, 'рейсов', 'аэропорт'),
  baggage_transport: fixed(420, 292, 'рейсов', 'аэропорт'),
  passenger_service: fixed(420, 292, 'рейсов', 'аэропорт'),
  medicine_delivery: fixed(1200, 180, 'доставок', 'медучреждение'),
  biomaterial_delivery: fixed(1200, 180, 'доставок', 'медучреждение'),
  ward_service: fixed(850, 180, 'визитов', 'медучреждение'),
  floor_cleaning: cleaning,
  floor_washing: cleaning,
  inventory,
  warehouse_inventory: inventory,
  perimeter_security: patrol,
  roof_inspection: patrol,
  territory_inspection: patrol,
}

export const ROLE_KIND: Record<ItemRole, StationKind | null> = {
  pickup: 'load',
  dropoff: 'unload',
  charge: 'charge',
  waypoint: 'waypoint',
  work_zone: null,
  obstacle: null,
}

export const KIND_ROLE: Record<StationKind, ItemRole> = { load: 'pickup', unload: 'dropoff', charge: 'charge', waypoint: 'waypoint' }

export const ROLE_LABEL: Record<ItemRole, string> = {
  pickup: 'Загрузка',
  dropoff: 'Выгрузка',
  charge: 'Зарядка',
  waypoint: 'Точка обхода',
  work_zone: 'Зона работы',
  obstacle: 'Препятствие',
}

/** Подпись станции: название объекта из настройки процесса, иначе роль. */
export const stationLabel = (proc: SimProcess | undefined, kind: StationKind, itemKey?: string) => {
  const byKey = itemKey ? proc?.items.find((item) => item.key === itemKey) : undefined
  const byRole = proc?.items.find((item) => item.role === KIND_ROLE[kind])
  return byKey?.label ?? byRole?.label ?? ROLE_LABEL[KIND_ROLE[kind]]
}

export const LOAD_S = 40
export const UNLOAD_S = 40
export const DEFAULT_SPEED = 1

export interface RobotInput {
  name: string
  count: number | null
  specs: { key: string; value: number }[]
}

export function buildProcess(code: string, name: string, robot: RobotInput | null, site: Site, items: LayoutItem[]): SimProcess {
  const plan = PROCESS_PLANS[code]
  const spec = (key: string) => robot?.specs.find((item) => item.key === key)?.value ?? null
  const shift = num(site, 'shift_hours') ?? 8
  const shifts = num(site, 'shifts_per_day') ?? 1
  const hours = shift * shifts
  const speed = spec('speed_loaded_ms')
  const work = spec('work_time_h')
  const charge = spec('charge_time_h')
  const spec_: RobotSpec = {
    name: robot?.name ?? 'Робот не выбран',
    count: Math.max(1, Math.round(robot?.count ?? 1)),
    speed: speed && speed > 0 ? speed : DEFAULT_SPEED,
    speedSource: speed && speed > 0 ? 'card' : 'default',
    workS: work && work > 0 ? work * 3600 : null,
    chargeS: charge && charge > 0 ? charge * 3600 : null,
    stairs: /собак|dog|шагающ|четвероног|гуманоид/i.test(robot?.name ?? ''),
    rate: plan?.kind === 'coverage' ? (code.includes('inventory') ? spec('throughput') : spec('proizvoditelnost')) : null,
  }
  let requiredPerHour = 0
  if (plan?.perDay) requiredPerHour = (plan.perDay(site) ?? 0) / hours
  if (plan?.perShift) requiredPerHour = (plan.perShift(site) ?? 0) / shift
  return {
    code,
    name,
    kind: robot ? (plan?.kind ?? 'none') : 'none',
    robot: spec_,
    requiredPerHour,
    unit: plan?.unit ?? '',
    loadS: LOAD_S,
    unloadS: UNLOAD_S,
    stopS: plan?.kind === 'patrol' ? 240 : 0,
    routeM: plan?.route?.(site) ?? null,
    basis: plan?.basis ?? 'Для процесса нет модели движения: формулы количества нет.',
    items,
  }
}

let counter = 0
export const uid = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${(counter++).toString(36)}`

export const rectOutline = (width: number, height: number) => [0, 0, width, 0, width, height, 0, height]

export function newFloor(name: string, width: number, height: number, areas?: FloorArea[]): Floor {
  return {
    id: uid('f'), name, width, height,
    areas: areas ?? [{ id: uid('ar'), points: rectOutline(width, height) }],
    walls: [], blocks: [], stations: [], zones: [], background: null,
  }
}

/** Пустой этаж компактного размера: не вся площадь объекта, а рабочая зона с запасом. */
export function emptyLayout(site: Site): Layout {
  const floorsCount = Math.max(1, Math.round(num(site, 'floors_count') ?? 1))
  const area = Math.min(num(site, 'free_m2') ?? num(site, 'area_m2') ?? 3000, 6000)
  const width = Math.max(40, Math.min(120, Math.round(Math.sqrt(area * 1.5))))
  const height = Math.max(30, Math.min(80, Math.round(area / width)))
  const floors = Array.from({ length: floorsCount }, (_, index) => newFloor(`${index + 1} этаж`, width, height))
  return { version: 1, floors, links: [], processes: {}, guide: { phase: 'intro', process: '' } }
}

/** Приводит сохранённую схему к текущей модели: участки пола у этажа, концы лифта по этажам. */
export function normalizeLayout(raw: Partial<Layout> & Record<string, unknown>): Layout {
  const floors = (raw.floors ?? []).map((floor) => {
    const f = floor as Floor & { outline?: number[] }
    const areas = f.areas?.length ? f.areas : [{ id: uid('ar'), points: f.outline?.length && f.outline.length >= 6 ? f.outline : rectOutline(f.width, f.height) }]
    const { outline: _outline, ...rest } = f
    /* Стены больше не рисуются руками: граница пола и есть стена. Старые линии убираем. */
    return { ...rest, areas, walls: [], blocks: f.blocks ?? [], stations: f.stations ?? [], zones: f.zones ?? [], background: f.background ?? null }
  })
  const links = (raw.links ?? []).map((link) => {
    const old = link as Link & { x?: number; y?: number; floors?: string[] }
    const stops = old.stops?.length ? old.stops : (old.floors ?? []).slice(0, 2).map((floor) => ({ floor, x: old.x ?? 2.5, y: old.y ?? 2.5 }))
    return { id: old.id, kind: old.kind, name: old.name ?? (old.kind === 'elevator' ? 'Лифт' : 'Лестница'), stops, wait_s: old.wait_s ?? 30, per_floor_s: old.per_floor_s ?? 10 }
  })
  const guide = raw.guide as { phase?: string; process?: string } | undefined
  const legacy: Record<string, LayoutGuide['phase']> = { plan: 'building', floor: 'building', shell: 'building', intro: 'intro', process: 'process', ready: 'ready', building: 'building' }
  return { version: 1, floors, links, processes: raw.processes ?? {}, guide: { phase: legacy[guide?.phase ?? 'intro'] ?? 'intro', process: guide?.process ?? '' } }
}

/** Подгоняет размер сетки этажа под участки пола. Сдвигает объекты только если пол ушёл в минус. */
export function fitFloorToOutline(floor: Floor) {
  const bounds = floorBounds(floor)
  if (bounds.minX < 0 || bounds.minY < 0) {
    const dx = Math.max(0, -bounds.minX)
    const dy = Math.max(0, -bounds.minY)
    for (const area of floor.areas) for (let index = 0; index < area.points.length; index += 2) { area.points[index]! += dx; area.points[index + 1]! += dy }
    for (const wall of floor.walls) for (let index = 0; index < wall.points.length; index += 2) { wall.points[index]! += dx; wall.points[index + 1]! += dy }
    for (const item of [...floor.blocks, ...floor.zones]) { item.x += dx; item.y += dy }
    for (const st of floor.stations) { st.x += dx; st.y += dy }
    if (floor.background) { floor.background.x += dx; floor.background.y += dy }
  }
  const after = floorBounds(floor)
  floor.width = Math.max(4, Math.ceil(after.maxX))
  floor.height = Math.max(4, Math.ceil(after.maxY))
}

/** Сливает пересекающиеся участки пола в один. Возвращает id участка, в который вошёл новый. */
export function mergeAreas(floor: Floor, newId: string): string {
  const rings = floor.areas.filter((area) => area.points.length >= 6).map((area) => ({ id: area.id, ring: toRing(area.points) }))
  const fresh = rings.find((row) => row.id === newId)
  if (!fresh) return newId
  let merged: FloorArea = { id: newId, points: fromRing(fresh.ring) }
  const absorbed = new Set<string>([newId])
  let changed = true
  while (changed) {
    changed = false
    for (const row of rings) {
      if (absorbed.has(row.id)) continue
      let result: [number, number][][][]
      try {
        result = polygonClipping.union([toRing(merged.points)], [row.ring]) as [number, number][][][]
      } catch {
        continue
      }
      if (result.length !== 1) continue
      absorbed.add(row.id)
      merged = { id: row.id, points: fromRing(result[0]![0]!) }
      changed = true
    }
  }
  if (absorbed.size === 1) return newId
  floor.areas = [...floor.areas.filter((area) => !absorbed.has(area.id)), merged]
  return merged.id
}

const toRing = (points: number[]): [number, number][] => {
  const ring: [number, number][] = []
  for (let index = 0; index < points.length; index += 2) ring.push([points[index]!, points[index + 1]!])
  return ring
}
const fromRing = (ring: [number, number][]): number[] => {
  const pts = ring.flat()
  if (pts.length >= 4 && pts[0] === pts[pts.length - 2] && pts[1] === pts[pts.length - 1]) pts.splice(-2, 2)
  return pts.map((value) => Math.round(value * 2) / 2)
}

export function resizeFloor(floor: Floor, width: number, height: number) {
  floor.width = Math.max(4, Math.round(width))
  floor.height = Math.max(4, Math.round(height))
  floor.areas = [{ id: floor.areas[0]?.id ?? uid('ar'), points: rectOutline(floor.width, floor.height) }]
}

/** Сколько объектов данного типа нужно поставить автоматически. */
export function autoCount(item: LayoutItem, proc: SimProcess): number {
  const min = Math.max(item.role === 'waypoint' ? 2 : 1, item.min_count)
  if (item.count_rule === 'by_flow') {
    const perHour = proc.requiredPerHour * 1.25
    const service = item.role === 'pickup' ? proc.loadS : proc.unloadS
    return Math.max(min, Math.min(40, Math.ceil((perHour * service) / 3600 / 0.75)))
  }
  if (item.count_rule === 'by_charge') {
    const { workS, chargeS, count } = proc.robot
    const share = workS && chargeS ? chargeS / (workS + chargeS) : 0.2
    return Math.max(min, Math.min(20, Math.ceil(count * share) + 1))
  }
  return min
}

/** Сколько объектов данного типа уже стоит на схеме. */
export function placedCount(layout: Layout, code: string, item: LayoutItem): number {
  const kind = ROLE_KIND[item.role]
  if (item.role === 'work_zone') return layout.floors.reduce((acc, floor) => acc + floor.zones.filter((zone) => zone.process === code && (zone.item ?? 'zone') === item.key).length, 0)
  if (item.role === 'obstacle') return layout.floors.reduce((acc, floor) => acc + floor.blocks.filter((block) => block.process === code && block.item === item.key).length, 0)
  if (!kind) return 0
  return layout.floors.reduce((acc, floor) => acc + floor.stations.filter((st) => st.process === code && st.kind === kind && (!st.item || st.item === item.key)).length, 0)
}

export const processReady = (layout: Layout, proc: SimProcess) =>
  proc.items.every((item) => placedCount(layout, proc.code, item) >= Math.max(item.role === 'waypoint' ? 2 : 1, item.min_count))

export const hasStations = (layout: Layout, code: string) =>
  layout.floors.some((floor) => floor.stations.some((item) => item.process === code) || floor.zones.some((item) => item.process === code))

export function clearProcess(layout: Layout, code: string) {
  for (const floor of layout.floors) {
    floor.stations = floor.stations.filter((item) => item.process !== code)
    floor.zones = floor.zones.filter((item) => item.process !== code)
    floor.blocks = floor.blocks.filter((item) => item.process !== code)
  }
}

interface Box { x: number; y: number; w: number; h: number }

/** Занятые прямоугольники этажа с запасом в одну клетку. */
function occupied(floor: Floor, links: Layout['links']): Box[] {
  const boxes: Box[] = []
  floor.stations.forEach((st) => boxes.push({ x: st.x - 1.5, y: st.y - 1.5, w: 3, h: 3 }))
  floor.zones.forEach((zone) => boxes.push({ x: zone.x - 1, y: zone.y - 1, w: zone.w + 2, h: zone.h + 2 }))
  floor.blocks.forEach((block) => boxes.push({ x: block.x - 1, y: block.y - 1, w: block.w + 2, h: block.h + 2 }))
  for (const link of links) for (const stop of link.stops) if (stop.floor === floor.id) boxes.push({ x: stop.x - 2, y: stop.y - 2, w: 4, h: 4 })
  for (const wall of floor.walls) {
    for (let index = 0; index + 3 < wall.points.length; index += 2) {
      const x0 = Math.min(wall.points[index]!, wall.points[index + 2]!)
      const x1 = Math.max(wall.points[index]!, wall.points[index + 2]!)
      const y0 = Math.min(wall.points[index + 1]!, wall.points[index + 3]!)
      const y1 = Math.max(wall.points[index + 1]!, wall.points[index + 3]!)
      boxes.push({ x: x0 - 1, y: y0 - 1, w: x1 - x0 + 2, h: y1 - y0 + 2 })
    }
  }
  return boxes
}

const overlaps = (a: Box, b: Box) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y

/** Прямоугольник целиком внутри пола: проверяем углы и центр. */
const insideFloor = (floor: Floor, box: Box) => {
  const pts = [[box.x, box.y], [box.x + box.w, box.y], [box.x, box.y + box.h], [box.x + box.w, box.y + box.h], [box.x + box.w / 2, box.y + box.h / 2]]
  return pts.every(([x, y]) => insideFloorAreas(floor, Math.min(floor.width - 0.01, Math.max(0.01, x!)), Math.min(floor.height - 0.01, Math.max(0.01, y!))))
}

/** Свободное место под прямоугольник: сканируем этаж сверху вниз, слева направо. */
function findSpot(floor: Floor, taken: Box[], w: number, h: number): Box | null {
  for (let y = 2; y + h <= floor.height - 2; y += 1) {
    for (let x = 2; x + w <= floor.width - 2; x += 1) {
      const box = { x, y, w, h }
      if (!taken.some((other) => overlaps(box, other)) && insideFloor(floor, { x: box.x - 1, y: box.y - 1, w: w + 2, h: h + 2 })) return box
    }
  }
  return null
}

/** Ставит объекты процесса из настройки админки в свободные места. Этаж расширяется только если места нет совсем. */
export function placeProcess(layout: Layout, floorId: string, proc: SimProcess, site: Site) {
  const floor = layout.floors.find((item) => item.id === floorId) ?? layout.floors[0]
  if (!floor || !proc.items.length) return
  const taken = occupied(floor, layout.links)
  const route = Math.max(6, Math.round(proc.routeM ?? 25))
  const claim = (box: Box) => taken.push({ x: box.x - 1, y: box.y - 1, w: box.w + 2, h: box.h + 2 })
  const grow = () => {
    const single = floor.areas.length === 1 && floor.areas[0]!.points.length === 8
    if (!single) return
    resizeFloor(floor, floor.width + 20, floor.height + 12)
  }

  const spotOrGrow = (w: number, h: number) => {
    for (let attempt = 0; attempt < 4; attempt++) {
      const box = findSpot(floor, taken, w, h)
      if (box) return box
      grow()
    }
    return null
  }

  const addStations = (item: LayoutItem, count: number, kind: StationKind, anchor?: Box) => {
    const rows = Math.max(1, Math.min(count, Math.floor((floor.height - 6) / 2)))
    const columns = Math.ceil(count / rows)
    const w = columns * 2
    const h = rows * 2
    let box: Box | null = null
    if (anchor) {
      const candidate = { x: anchor.x + route, y: anchor.y, w, h }
      if (candidate.x + w <= floor.width - 2 && !taken.some((other) => overlaps(candidate, other))) box = candidate
    }
    box ??= spotOrGrow(w, h)
    if (!box) return null
    for (let index = 0; index < count; index++) {
      const column = Math.floor(index / rows)
      const row = index % rows
      floor.stations.push({ id: uid('st'), process: proc.code, kind, item: item.key, x: box.x + column * 2 + 0.5, y: box.y + row * 2 + 0.5 })
    }
    claim(box)
    return box
  }

  let pickupBox: Box | undefined
  for (const item of proc.items) {
    const count = autoCount(item, proc)
    if (item.role === 'work_zone') {
      const target = proc.code.includes('inventory') ? 900 : Math.min(num(site, 'clean_area_m2') ?? 1500, 2400)
      const w = Math.max(8, Math.min(floor.width - 6, Math.round(Math.sqrt(target * 1.6))))
      const h = Math.max(6, Math.min(floor.height - 6, Math.round(target / w)))
      const box = spotOrGrow(w, h)
      if (!box) continue
      floor.zones.push({ id: uid('zn'), process: proc.code, item: item.key, x: box.x, y: box.y, w, h })
      if (proc.code.includes('inventory')) {
        for (let y = box.y + 2; y + 1.2 <= box.y + h - 1; y += 4.2) {
          floor.blocks.push({ id: uid('bl'), process: proc.code, item: '__auto_rack', x: box.x + 2, y, w: w - 4, h: 1.2, label: 'Стеллаж' })
        }
      }
      claim(box)
      continue
    }
    if (item.role === 'obstacle') {
      for (let index = 0; index < count; index++) {
        const box = spotOrGrow(6, 2)
        if (!box) break
        floor.blocks.push({ id: uid('bl'), process: proc.code, item: item.key, x: box.x, y: box.y, w: 6, h: 2, label: item.label })
        claim(box)
      }
      continue
    }
    if (item.role === 'waypoint') {
      const inset = 2
      const all: [number, number][] = [[inset, inset], [floor.width - inset - 1, inset], [floor.width - inset - 1, floor.height - inset - 1], [inset, floor.height - inset - 1]]
      const corners = all.filter(([x, y]) => insideFloorAreas(floor, x + 0.5, y + 0.5))
      const fallback: [number, number][] = [[inset, inset], [Math.max(inset + 2, Math.round(floor.width / 2)), inset]]
      const pool = corners.length >= 2 ? corners : fallback
      for (let index = 0; index < Math.max(2, count); index++) {
        const [x, y] = pool[index % pool.length]!
        floor.stations.push({ id: uid('st'), process: proc.code, kind: 'waypoint', item: item.key, x: x + 0.5, y: y + 0.5 })
      }
      continue
    }
    const kind = ROLE_KIND[item.role]
    if (!kind) continue
    const box = addStations(item, count, kind, item.role === 'dropoff' ? pickupBox : undefined)
    if (item.role === 'pickup' && box) pickupBox = box
  }
}

/** Каркас здания по умолчанию: ряды стеллажей внутри пола. Лифт парой между соседними этажами, если этажей несколько. */
export function placeShell(layout: Layout) {
  for (const floor of layout.floors) {
    if (floor.blocks.some((block) => block.item === '__shell_rack')) continue
    const taken = occupied(floor, layout.links)
    const width = Math.max(8, Math.min(24, Math.round(floor.width * 0.4)))
    for (let index = 0; index < 3; index++) {
      const box = findSpot(floor, taken, width, 2)
      if (!box) break
      floor.blocks.push({ id: uid('bl'), item: '__shell_rack', x: box.x, y: box.y, w: width, h: 2, label: 'Стеллаж' })
      taken.push({ x: box.x - 1, y: box.y - 3, w: width + 2, h: 6 })
    }
  }
  if (layout.floors.length > 1 && !layout.links.length) {
    for (let index = 0; index + 1 < layout.floors.length; index++) {
      const lower = layout.floors[index]!
      const upper = layout.floors[index + 1]!
      layout.links.push(newLink('elevator', [{ floor: lower.id, x: 4.5, y: 4.5 }, { floor: upper.id, x: 4.5, y: 4.5 }]))
    }
  }
}

export function newLink(kind: Link['kind'], stops: Link['stops']): Link {
  const elevator = kind === 'elevator'
  return { id: uid('ln'), kind, name: elevator ? 'Лифт' : 'Лестница', stops, wait_s: elevator ? 30 : 5, per_floor_s: elevator ? 10 : 20 }
}
