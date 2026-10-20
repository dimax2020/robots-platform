/**
 * Импорт чертежа AutoCAD (DXF): разбор геометрии, перевод в метры и картинка-подложка в точном масштабе.
 * DWG — закрытый двоичный формат: его сохраняют из AutoCAD как DXF («Сохранить как → DXF»).
 * Стены и стеллажи узнаём по имени слоя: стены становятся стенами схемы, стеллажи — препятствиями.
 */

export interface DxfShape { layer: string; points: number[]; closed: boolean }
export interface DxfText { layer: string; x: number; y: number; height: number; text: string; rotation: number }
export interface DxfPlan {
  /** Линии в метрах, ось Y вниз, левый верхний угол чертежа — (0, 0). */
  shapes: DxfShape[]
  texts: DxfText[]
  width: number
  height: number
  layers: string[]
  units: string
  /** Сколько метров в единице чертежа. */
  scale: number
  /** Габарит здания по слоям стен, м: по нему ставим пол, чтобы размерные линии и подписи снаружи не стали полом. */
  building: { x: number; y: number; w: number; h: number } | null
}

type Pair = [number, string]
type Matrix = [number, number, number, number, number, number]

const UNITS: Record<number, [number, string]> = {
  1: [0.0254, 'дюймы'], 2: [0.3048, 'футы'], 4: [0.001, 'мм'], 5: [0.01, 'см'], 6: [1, 'м'], 14: [0.1, 'дм'],
}
export const WALL_LAYER = /стен|wall|перегор|несущ|a-wall|наружн|колонн|column/i
export const RACK_LAYER = /стеллаж|rack|shelf|оборуд|equip|полк/i

const IDENTITY: Matrix = [1, 0, 0, 1, 0, 0]
const apply = (m: Matrix, x: number, y: number): [number, number] => [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]]
const multiply = (a: Matrix, b: Matrix): Matrix => [
  a[0] * b[0] + a[2] * b[1], a[1] * b[0] + a[3] * b[1],
  a[0] * b[2] + a[2] * b[3], a[1] * b[2] + a[3] * b[3],
  a[0] * b[4] + a[2] * b[5] + a[4], a[1] * b[4] + a[3] * b[5] + a[5],
]

function pairs(text: string): Pair[] {
  const lines = text.split(/\r?\n/)
  const out: Pair[] = []
  for (let index = 0; index + 1 < lines.length; index += 2) {
    const code = Number(lines[index]!.trim())
    if (!Number.isFinite(code)) { index -= 1; continue }
    out.push([code, lines[index + 1]!.trim()])
  }
  return out
}

interface RawEntity { type: string; data: Pair[]; vertices?: Pair[][] }

/** Делит поток пар на сущности; у POLYLINE собирает VERTEX до SEQEND. */
function entities(list: Pair[]): RawEntity[] {
  const out: RawEntity[] = []
  let current: RawEntity | null = null
  let poly: RawEntity | null = null
  for (const pair of list) {
    if (pair[0] === 0) {
      const type = pair[1]
      if (poly && type === 'VERTEX') { current = { type, data: [] }; poly.vertices!.push(current.data); continue }
      if (poly && type === 'SEQEND') { poly = null; current = null; continue }
      current = { type, data: [] }
      out.push(current)
      if (type === 'POLYLINE') { current.vertices = []; poly = current }
      continue
    }
    current?.data.push(pair)
  }
  return out
}

const num = (data: Pair[], code: number, fallback = 0) => {
  const hit = data.find((pair) => pair[0] === code)
  const value = hit ? Number(hit[1]) : NaN
  return Number.isFinite(value) ? value : fallback
}
const str = (data: Pair[], code: number) => data.find((pair) => pair[0] === code)?.[1] ?? ''
const all = (data: Pair[], code: number) => data.filter((pair) => pair[0] === code).map((pair) => Number(pair[1]))

function arcPoints(cx: number, cy: number, r: number, from: number, to: number): number[] {
  let sweep = to - from
  while (sweep <= 0) sweep += Math.PI * 2
  const steps = Math.max(6, Math.ceil(sweep / (Math.PI / 24)))
  const out: number[] = []
  for (let index = 0; index <= steps; index++) {
    const angle = from + (sweep * index) / steps
    out.push(cx + r * Math.cos(angle), cy + r * Math.sin(angle))
  }
  return out
}

/** Дуга между вершинами полилинии по выпуклости (bulge). */
function bulgePoints(x0: number, y0: number, x1: number, y1: number, bulge: number): number[] {
  const chord = Math.hypot(x1 - x0, y1 - y0)
  if (!bulge || chord === 0) return [x1, y1]
  const theta = 4 * Math.atan(bulge)
  const r = chord / (2 * Math.sin(theta / 2))
  const mx = (x0 + x1) / 2
  const my = (y0 + y1) / 2
  const d = r * Math.cos(theta / 2)
  const nx = -(y1 - y0) / chord
  const ny = (x1 - x0) / chord
  const cx = mx + nx * d
  const cy = my + ny * d
  const a0 = Math.atan2(y0 - cy, x0 - cx)
  const a1 = Math.atan2(y1 - cy, x1 - cx)
  const pts = bulge > 0 ? arcPoints(cx, cy, Math.abs(r), a0, a1) : arcPoints(cx, cy, Math.abs(r), a1, a0)
  if (bulge < 0) {
    const reversed: number[] = []
    for (let index = pts.length - 2; index >= 0; index -= 2) reversed.push(pts[index]!, pts[index + 1]!)
    return reversed.slice(2)
  }
  return pts.slice(2)
}

function polyline(vertices: { x: number; y: number; bulge: number }[], closed: boolean): number[] {
  if (!vertices.length) return []
  const out = [vertices[0]!.x, vertices[0]!.y]
  const count = closed ? vertices.length : vertices.length - 1
  for (let index = 0; index < count; index++) {
    const a = vertices[index]!
    const b = vertices[(index + 1) % vertices.length]!
    out.push(...bulgePoints(a.x, a.y, b.x, b.y, a.bulge))
  }
  return out
}

interface Collected { shapes: DxfShape[]; texts: DxfText[] }

function collect(list: RawEntity[], blocks: Map<string, { base: [number, number]; list: RawEntity[] }>, m: Matrix, layerOf: string, out: Collected, depth: number) {
  if (depth > 8) return
  const push = (layer: string, raw: number[], closed: boolean) => {
    if (raw.length < 4) return
    const points: number[] = []
    for (let index = 0; index < raw.length; index += 2) points.push(...apply(m, raw[index]!, raw[index + 1]!))
    out.shapes.push({ layer, points, closed })
  }
  for (const entity of list) {
    const d = entity.data
    const own = str(d, 8) || '0'
    const layer = own === '0' && layerOf ? layerOf : own
    switch (entity.type) {
      case 'LINE':
        push(layer, [num(d, 10), num(d, 20), num(d, 11), num(d, 21)], false)
        break
      case 'LWPOLYLINE': {
        const xs = all(d, 10)
        const ys = all(d, 20)
        const bulges: number[] = []
        let vertex = -1
        for (const pair of d) {
          if (pair[0] === 10) { vertex += 1; bulges[vertex] = 0 }
          if (pair[0] === 42 && vertex >= 0) bulges[vertex] = Number(pair[1]) || 0
        }
        const closed = (num(d, 70) & 1) === 1
        push(layer, polyline(xs.map((x, index) => ({ x, y: ys[index] ?? 0, bulge: bulges[index] ?? 0 })), closed), closed)
        break
      }
      case 'POLYLINE': {
        const closed = (num(d, 70) & 1) === 1
        const vertices = (entity.vertices ?? []).map((v) => ({ x: num(v, 10), y: num(v, 20), bulge: num(v, 42) }))
        push(layer, polyline(vertices, closed), closed)
        break
      }
      case 'CIRCLE':
        push(layer, arcPoints(num(d, 10), num(d, 20), num(d, 40), 0, Math.PI * 2), true)
        break
      case 'ARC':
        push(layer, arcPoints(num(d, 10), num(d, 20), num(d, 40), (num(d, 50) * Math.PI) / 180, (num(d, 51) * Math.PI) / 180), false)
        break
      case 'ELLIPSE': {
        const cx = num(d, 10), cy = num(d, 20), mx = num(d, 11), my = num(d, 21), ratio = num(d, 40, 1)
        const from = num(d, 41, 0), to = num(d, 42, Math.PI * 2)
        const major = Math.hypot(mx, my), rot = Math.atan2(my, mx)
        const pts: number[] = []
        const steps = 48
        for (let index = 0; index <= steps; index++) {
          const t = from + ((to - from) * index) / steps
          const ex = major * Math.cos(t), ey = major * ratio * Math.sin(t)
          pts.push(cx + ex * Math.cos(rot) - ey * Math.sin(rot), cy + ex * Math.sin(rot) + ey * Math.cos(rot))
        }
        push(layer, pts, false)
        break
      }
      case 'SPLINE': {
        const fx = all(d, 11), fy = all(d, 21)
        const xs = fx.length ? fx : all(d, 10)
        const ys = fx.length ? fy : all(d, 20)
        push(layer, xs.flatMap((x, index) => [x, ys[index] ?? 0]), false)
        break
      }
      case 'SOLID': case '3DFACE': {
        const pts = [num(d, 10), num(d, 20), num(d, 11), num(d, 21), num(d, 13), num(d, 23), num(d, 12), num(d, 22)]
        push(layer, pts, true)
        break
      }
      case 'TEXT': case 'MTEXT': {
        const raw = d.filter((pair) => pair[0] === 3 || pair[0] === 1).map((pair) => pair[1]).join('')
        const text = raw.replace(/\\P/g, ' ').replace(/\\[A-Za-z][^;]*;/g, '').replace(/[{}]/g, '').replace(/%%[cdp]/gi, '').trim()
        if (!text) break
        const [x, y] = apply(m, num(d, 10), num(d, 20))
        const scale = Math.hypot(m[0], m[1])
        out.texts.push({ layer, x, y, height: num(d, 40, 2.5) * scale, text: text.slice(0, 80), rotation: num(d, 50) + (Math.atan2(m[1], m[0]) * 180) / Math.PI })
        break
      }
      case 'DIMENSION': {
        /* Размер AutoCAD хранит готовым анонимным блоком: линии, стрелки и число. */
        const block = blocks.get(str(d, 2))
        if (block) collect(block.list, blocks, m, layer, out, depth + 1)
        break
      }
      case 'INSERT': {
        const block = blocks.get(str(d, 2))
        if (!block) break
        const sx = num(d, 41, 1), sy = num(d, 42, 1), angle = (num(d, 50) * Math.PI) / 180
        const cos = Math.cos(angle), sin = Math.sin(angle)
        const cols = Math.max(1, num(d, 70, 1)), rows = Math.max(1, num(d, 71, 1))
        const dx = num(d, 44), dy = num(d, 45)
        for (let row = 0; row < Math.min(rows, 50); row++) {
          for (let col = 0; col < Math.min(cols, 50); col++) {
            const ox = num(d, 10) + (col * dx * cos - row * dy * sin)
            const oy = num(d, 20) + (col * dx * sin + row * dy * cos)
            const local: Matrix = [sx * cos, sx * sin, -sy * sin, sy * cos, ox, oy]
            const base: Matrix = [1, 0, 0, 1, -block.base[0], -block.base[1]]
            collect(block.list, blocks, multiply(m, multiply(local, base)), layer, out, depth + 1)
          }
        }
        break
      }
    }
  }
}

/** Границы по основной массе точек: случайный объект далеко за планом не растягивает подложку. */
function extents(shapes: DxfShape[]) {
  const xs: number[] = []
  const ys: number[] = []
  for (const shape of shapes) for (let index = 0; index < shape.points.length; index += 2) { xs.push(shape.points[index]!); ys.push(shape.points[index + 1]!) }
  if (!xs.length) return null
  xs.sort((a, b) => a - b)
  ys.sort((a, b) => a - b)
  const pick = (list: number[], share: number) => list[Math.min(list.length - 1, Math.max(0, Math.round((list.length - 1) * share)))]!
  const trim = xs.length > 200 ? 0.002 : 0
  let minX = pick(xs, trim), maxX = pick(xs, 1 - trim), minY = pick(ys, trim), maxY = pick(ys, 1 - trim)
  const padX = (maxX - minX) * 0.02, padY = (maxY - minY) * 0.02
  minX -= padX; maxX += padX; minY -= padY; maxY += padY
  return { minX, maxX, minY, maxY }
}

export function parseDxf(text: string): DxfPlan {
  const list = pairs(text)
  if (!list.some((pair) => pair[0] === 0 && pair[1] === 'SECTION')) throw new Error('Это не DXF: в файле нет разделов чертежа. Из AutoCAD сохраните как «DXF».')
  /* Разделы: заголовок (единицы), блоки и сущности. */
  const sections = new Map<string, Pair[]>()
  for (let index = 0; index < list.length; index++) {
    if (list[index]![0] === 0 && list[index]![1] === 'SECTION' && list[index + 1]?.[0] === 2) {
      const name = list[index + 1]![1]
      const start = index + 2
      let end = start
      while (end < list.length && !(list[end]![0] === 0 && list[end]![1] === 'ENDSEC')) end++
      sections.set(name, list.slice(start, end))
      index = end
    }
  }
  const header = sections.get('HEADER') ?? []
  const unitsAt = header.findIndex((pair) => pair[0] === 9 && pair[1] === '$INSUNITS')
  const unitCode = unitsAt >= 0 ? Number(header[unitsAt + 1]?.[1]) : 0

  const blocks = new Map<string, { base: [number, number]; list: RawEntity[] }>()
  const blockPairs = sections.get('BLOCKS') ?? []
  let open: { name: string; base: [number, number]; body: Pair[] } | null = null
  let head: Pair[] | null = null
  for (const pair of blockPairs) {
    if (pair[0] === 0 && pair[1] === 'BLOCK') { head = []; open = null; continue }
    if (head && pair[0] === 0) {
      open = { name: str(head, 2), base: [num(head, 10), num(head, 20)], body: [] }
      head = null
    }
    if (head) { head.push(pair); continue }
    if (pair[0] === 0 && pair[1] === 'ENDBLK') {
      if (open) blocks.set(open.name, { base: open.base, list: entities(open.body) })
      open = null
      continue
    }
    open?.body.push(pair)
  }

  const out: Collected = { shapes: [], texts: [] }
  collect(entities(sections.get('ENTITIES') ?? []), blocks, IDENTITY, '', out, 0)
  if (!out.shapes.length) throw new Error('В чертеже нет линий, которые можно показать на плане.')

  const box = extents(out.shapes)!
  const spanRaw = Math.max(box.maxX - box.minX, box.maxY - box.minY)
  /* Единицы: из заголовка; если не указаны — по размеру: склад в тысячи единиц почти наверняка в миллиметрах. */
  const [scale, units] = UNITS[unitCode] ?? (spanRaw > 2000 ? [0.001, 'мм, определено по размеру'] : [1, 'м, определено по размеру'])
  const toPlan = (x: number, y: number): [number, number] => [(x - box.minX) * scale, (box.maxY - y) * scale]
  const shapes = out.shapes.map((shape) => {
    const points: number[] = []
    for (let index = 0; index < shape.points.length; index += 2) points.push(...toPlan(shape.points[index]!, shape.points[index + 1]!))
    return { ...shape, points }
  })
  const texts = out.texts.map((item) => {
    const [x, y] = toPlan(item.x, item.y)
    return { ...item, x, y, height: item.height * scale }
  })
  const wallPts = shapes.filter((shape) => WALL_LAYER.test(shape.layer)).flatMap((shape) => shape.points)
  const wx = wallPts.filter((_, index) => index % 2 === 0)
  const wy = wallPts.filter((_, index) => index % 2 === 1)
  const building = wx.length >= 4 ? { x: Math.min(...wx), y: Math.min(...wy), w: Math.max(...wx) - Math.min(...wx), h: Math.max(...wy) - Math.min(...wy) } : null
  return {
    building: building && building.w > 2 && building.h > 2 ? building : null,
    shapes,
    texts,
    width: (box.maxX - box.minX) * scale,
    height: (box.maxY - box.minY) * scale,
    layers: [...new Set(out.shapes.map((shape) => shape.layer))].sort(),
    units,
    scale,
  }
}

/** Подложка: чертёж в PNG. Возвращает картинку и сколько метров в пикселе. */
export async function renderDxf(plan: DxfPlan, maxSide = 4096): Promise<{ blob: Blob; width: number; height: number; mpp: number }> {
  const mpp = Math.max(plan.width, plan.height) / maxSide
  const width = Math.max(1, Math.round(plan.width / mpp))
  const height = Math.max(1, Math.round(plan.height / mpp))
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = '#ffffff'
  ctx.fillRect(0, 0, width, height)
  ctx.lineCap = 'round'
  ctx.lineJoin = 'round'
  for (const shape of plan.shapes) {
    const wall = WALL_LAYER.test(shape.layer)
    ctx.strokeStyle = wall ? '#1c2421' : RACK_LAYER.test(shape.layer) ? '#4b5a55' : '#7d8985'
    ctx.lineWidth = wall ? 3 : 1.4
    ctx.beginPath()
    for (let index = 0; index < shape.points.length; index += 2) {
      const x = shape.points[index]! / mpp
      const y = shape.points[index + 1]! / mpp
      if (index) ctx.lineTo(x, y)
      else ctx.moveTo(x, y)
    }
    if (shape.closed) ctx.closePath()
    ctx.stroke()
  }
  ctx.fillStyle = '#3d4845'
  for (const item of plan.texts) {
    const size = item.height / mpp
    if (size < 6) continue
    ctx.save()
    ctx.translate(item.x / mpp, item.y / mpp)
    ctx.rotate((-item.rotation * Math.PI) / 180)
    ctx.font = `${Math.min(120, size)}px Manrope, sans-serif`
    ctx.fillText(item.text, 0, 0)
    ctx.restore()
  }
  const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob((value) => value ? resolve(value) : reject(new Error('Не удалось нарисовать чертёж')), 'image/png'))
  return { blob, width, height, mpp }
}

/** Стены — линии со слоёв стен; препятствия — замкнутые контуры со слоёв стеллажей и оборудования. */
export function dxfObstacles(plan: DxfPlan) {
  const walls: number[][] = []
  const blocks: { x: number; y: number; w: number; h: number }[] = []
  for (const shape of plan.shapes) {
    if (WALL_LAYER.test(shape.layer)) {
      const pts = shape.closed ? [...shape.points, shape.points[0]!, shape.points[1]!] : shape.points
      walls.push(pts.map((value) => Math.round(value * 100) / 100))
    } else if (RACK_LAYER.test(shape.layer) && shape.closed) {
      const xs = shape.points.filter((_, index) => index % 2 === 0)
      const ys = shape.points.filter((_, index) => index % 2 === 1)
      const x = Math.min(...xs), y = Math.min(...ys)
      const w = Math.max(...xs) - x, h = Math.max(...ys) - y
      if (w >= 0.3 && h >= 0.3 && w * h <= plan.width * plan.height * 0.5) blocks.push({ x: round(x), y: round(y), w: round(w), h: round(h) })
    }
  }
  return { walls: walls.slice(0, 4000), blocks: blocks.slice(0, 4000) }
}
const round = (value: number) => Math.round(value * 100) / 100
