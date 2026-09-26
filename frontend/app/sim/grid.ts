import PF from 'pathfinding'
import type { Floor, Layout, Link } from './types'

export interface MoveLeg { kind: 'move'; floor: string; pts: number[]; cum: number[]; length: number }
export interface LiftLeg { kind: 'lift'; floor: string; toFloor: string; x: number; y: number; seconds: number }
export type Leg = MoveLeg | LiftLeg

export interface Place { floor: string; x: number; y: number }

const cell = (value: number, max: number) => Math.max(0, Math.min(max - 1, Math.floor(value)))

/** Точка внутри многоугольника (чётно-нечётное правило). */
export function insidePolygon(points: number[], x: number, y: number): boolean {
  let inside = false
  const n = points.length / 2
  for (let i = 0, j = n - 1; i < n; j = i++) {
    const xi = points[i * 2]!
    const yi = points[i * 2 + 1]!
    const xj = points[j * 2]!
    const yj = points[j * 2 + 1]!
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}

export const insideFloorAreas = (floor: Floor, x: number, y: number) =>
  floor.areas.length === 0 || floor.areas.some((area) => area.points.length >= 6 && insidePolygon(area.points, x, y))

export const floorBounds = (floor: Floor) => {
  const pts = floor.areas.flatMap((area) => area.points)
  const source = pts.length >= 6 ? pts : [0, 0, floor.width, 0, floor.width, floor.height, 0, floor.height]
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (let i = 0; i < source.length; i += 2) {
    minX = Math.min(minX, source[i]!)
    maxX = Math.max(maxX, source[i]!)
    minY = Math.min(minY, source[i + 1]!)
    maxY = Math.max(maxY, source[i + 1]!)
  }
  return { minX, minY, maxX, maxY, width: maxX - minX, height: maxY - minY }
}

export function blockedCells(floor: Floor, links: Link[]): Uint8Array {
  const { width, height } = floor
  const cells = new Uint8Array(width * height)
  const mark = (x: number, y: number) => {
    if (x >= 0 && y >= 0 && x < width && y < height) cells[y * width + x] = 1
  }
  if (floor.areas.length) {
    for (let y = 0; y < height; y++) {
      for (let x = 0; x < width; x++) {
        if (!insideFloorAreas(floor, x + 0.5, y + 0.5)) cells[y * width + x] = 1
      }
    }
  }
  for (const wall of floor.walls) {
    for (let index = 0; index + 3 < wall.points.length; index += 2) {
      line(wall.points[index]!, wall.points[index + 1]!, wall.points[index + 2]!, wall.points[index + 3]!, mark)
    }
  }
  for (const block of floor.blocks) {
    const x0 = Math.floor(block.x)
    const y0 = Math.floor(block.y)
    const x1 = Math.ceil(block.x + block.w)
    const y1 = Math.ceil(block.y + block.h)
    for (let y = y0; y < y1; y++) for (let x = x0; x < x1; x++) mark(x, y)
  }
  const free = (x: number, y: number) => {
    cells[cell(y, height) * width + cell(x, width)] = 0
  }
  for (const station of floor.stations) free(station.x, station.y)
  for (const link of links) for (const stop of link.stops) if (stop.floor === floor.id) free(stop.x, stop.y)
  return cells
}

function line(x0: number, y0: number, x1: number, y1: number, mark: (x: number, y: number) => void) {
  const steps = Math.max(1, Math.ceil(Math.hypot(x1 - x0, y1 - y0) * 2))
  for (let index = 0; index <= steps; index++) {
    const t = index / steps
    mark(Math.floor(x0 + (x1 - x0) * t), Math.floor(y0 + (y1 - y0) * t))
  }
}

export class Router {
  private grids = new Map<string, PF.Grid>()
  private sizes = new Map<string, { width: number; height: number }>()
  private cache = new Map<string, MoveLeg | null>()
  private finder = new PF.AStarFinder({ diagonalMovement: PF.DiagonalMovement.OnlyWhenNoObstacles })
  private order = new Map<string, number>()
  readonly links: Link[]

  constructor(layout: Layout) {
    this.links = layout.links
    layout.floors.forEach((floor, index) => this.order.set(floor.id, index))
    for (const floor of layout.floors) {
      const cells = blockedCells(floor, layout.links)
      const matrix: number[][] = []
      for (let y = 0; y < floor.height; y++) {
        const row: number[] = []
        for (let x = 0; x < floor.width; x++) row.push(cells[y * floor.width + x]!)
        matrix.push(row)
      }
      this.grids.set(floor.id, new PF.Grid(matrix))
      this.sizes.set(floor.id, { width: floor.width, height: floor.height })
    }
  }

  walk(floor: string, ax: number, ay: number, bx: number, by: number): MoveLeg | null {
    const size = this.sizes.get(floor)
    const grid = this.grids.get(floor)
    if (!size || !grid) return null
    const [sx, sy] = nearestFree(grid, cell(ax, size.width), cell(ay, size.height), size)
    const [ex, ey] = nearestFree(grid, cell(bx, size.width), cell(by, size.height), size)
    const key = `${floor}:${sx},${sy}>${ex},${ey}`
    const cached = this.cache.get(key)
    if (cached !== undefined) return cached ? withEnds(cached, ax, ay, bx, by) : null
    let leg: MoveLeg | null
    if (sx === ex && sy === ey) {
      leg = build(floor, [sx + 0.5, sy + 0.5])
    } else {
      const found = this.finder.findPath(sx, sy, ex, ey, grid.clone())
      leg = found.length ? build(floor, smooth(grid, PF.Util.compressPath(found)).flatMap(([x, y]) => [x! + 0.5, y! + 0.5])) : null
    }
    this.cache.set(key, leg)
    return leg ? withEnds(leg, ax, ay, bx, by) : null
  }

  route(from: Place, to: Place, stairs: boolean): Leg[] | null {
    if (from.floor === to.floor) {
      const leg = this.walk(from.floor, from.x, from.y, to.x, to.y)
      return leg ? [leg] : null
    }
    let best: { legs: Leg[]; cost: number } | null = null
    for (const link of this.links) {
      if (link.kind === 'stairs' && !stairs) continue
      const here = link.stops.find((stop) => stop.floor === from.floor)
      const there = link.stops.find((stop) => stop.floor === to.floor)
      if (!here || !there) continue
      const first = this.walk(from.floor, from.x, from.y, here.x, here.y)
      const second = this.walk(to.floor, there.x, there.y, to.x, to.y)
      if (!first || !second) continue
      const span = Math.abs((this.order.get(to.floor) ?? 0) - (this.order.get(from.floor) ?? 0))
      const seconds = link.wait_s + link.per_floor_s * Math.max(1, span)
      const cost = first.length + second.length + seconds
      if (!best || cost < best.cost) {
        best = { cost, legs: [first, { kind: 'lift', floor: from.floor, toFloor: to.floor, x: here.x, y: here.y, seconds }, second] }
      }
    }
    return best?.legs ?? null
  }

  distance(from: Place, to: Place, stairs: boolean) {
    const legs = this.route(from, to, stairs)
    if (!legs) return Infinity
    return legs.reduce((acc, leg) => acc + (leg.kind === 'move' ? leg.length : leg.seconds), 0)
  }
}

/** Срезаем лесенку A*: оставляем точку только если прямая до следующей задевает препятствие. */
function smooth(grid: PF.Grid, path: number[][]): number[][] {
  if (path.length <= 2) return path
  const out: number[][] = [path[0]!]
  let anchor = 0
  for (let index = 2; index <= path.length; index++) {
    const candidate = path[index]
    const previous = path[index - 1]!
    if (!candidate || !clear(grid, path[anchor]!, candidate)) {
      out.push(previous)
      anchor = index - 1
    }
  }
  return out
}

function clear(grid: PF.Grid, a: number[], b: number[]): boolean {
  const steps = Math.max(1, Math.ceil(Math.hypot(b[0]! - a[0]!, b[1]! - a[1]!) * 3))
  for (let index = 0; index <= steps; index++) {
    const t = index / steps
    const x = Math.round(a[0]! + (b[0]! - a[0]!) * t)
    const y = Math.round(a[1]! + (b[1]! - a[1]!) * t)
    if (!grid.isWalkableAt(x, y)) return false
  }
  return true
}

function nearestFree(grid: PF.Grid, x: number, y: number, size: { width: number; height: number }): [number, number] {
  if (grid.isWalkableAt(x, y)) return [x, y]
  for (let radius = 1; radius <= 4; radius++) {
    for (let dy = -radius; dy <= radius; dy++) {
      for (let dx = -radius; dx <= radius; dx++) {
        if (Math.max(Math.abs(dx), Math.abs(dy)) !== radius) continue
        const nx = x + dx
        const ny = y + dy
        if (nx >= 0 && ny >= 0 && nx < size.width && ny < size.height && grid.isWalkableAt(nx, ny)) return [nx, ny]
      }
    }
  }
  return [x, y]
}

function build(floor: string, pts: number[]): MoveLeg {
  const cum = [0]
  for (let index = 2; index < pts.length; index += 2) {
    cum.push(cum[cum.length - 1]! + Math.hypot(pts[index]! - pts[index - 2]!, pts[index + 1]! - pts[index - 1]!))
  }
  return { kind: 'move', floor, pts, cum, length: cum[cum.length - 1]! }
}

function withEnds(leg: MoveLeg, ax: number, ay: number, bx: number, by: number): MoveLeg {
  const pts = leg.pts.slice()
  pts[0] = ax
  pts[1] = ay
  pts[pts.length - 2] = bx
  pts[pts.length - 1] = by
  return build(leg.floor, pts)
}

export function pointAt(leg: MoveLeg, distance: number): [number, number] {
  const { pts, cum } = leg
  if (distance <= 0 || pts.length <= 2) return [pts[0]!, pts[1]!]
  if (distance >= leg.length) return [pts[pts.length - 2]!, pts[pts.length - 1]!]
  let lo = 0
  let hi = cum.length - 1
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1
    if (cum[mid]! <= distance) lo = mid
    else hi = mid
  }
  const span = cum[hi]! - cum[lo]!
  const t = span > 0 ? (distance - cum[lo]!) / span : 0
  return [pts[lo * 2]! + (pts[hi * 2]! - pts[lo * 2]!) * t, pts[lo * 2 + 1]! + (pts[hi * 2 + 1]! - pts[lo * 2 + 1]!) * t]
}

export function joinLegs(legs: MoveLeg[]): MoveLeg | null {
  const valid = legs.filter((leg) => leg.pts.length >= 2)
  if (!valid.length) return null
  const pts: number[] = []
  for (const leg of valid) {
    const start = pts.length ? 2 : 0
    for (let index = start; index < leg.pts.length; index++) pts.push(leg.pts[index]!)
  }
  return build(valid[0]!.floor, pts)
}
