import { joinLegs, pointAt, Router, type Leg, type MoveLeg, type Place } from './grid'
import { stationLabel } from './templates'
import type { ProcessStats, RobotStatus, RobotTrip, RobotView, SimConfig, SimProcess, SimStats, Station } from './types'

export const STEP_S = 0.5
const LOW_BATTERY = 0.2
const TOP_UP = 0.5
const SETTLE_S = 1800

type Phase = 'idle' | 'to_load' | 'load' | 'to_unload' | 'unload' | 'to_charge' | 'charge' | 'to_work' | 'work' | 'stop' | 'off' | 'stuck'

interface StationRT {
  st: Station
  floor: string
  busy: RobotRT | null
  queue: RobotRT[]
  heading: number
}

interface Task { created: number; started: number }

interface ProcRT {
  proc: SimProcess
  robots: RobotRT[]
  load: StationRT[]
  unload: StationRT[]
  charge: StationRT[]
  loop: MoveLeg | null
  waypointsAt: number[]
  stopEach: number
  rate: number
  pending: Task[]
  head: number
  nextArrival: number
  lambda: number
  required: number
  liveLoad: number
  done: number
  cycleSum: number
  cycles: number
  waitSum: number
  waits: number
  maxQueue: number
  busyS: number
  chargeS: number
  notes: string[]
}

interface RobotRT {
  id: number
  pr: ProcRT
  floor: string
  x: number
  y: number
  phase: Phase
  status: RobotStatus
  battery: number
  legs: Leg[]
  legIndex: number
  legPos: number
  onArrive: (() => void) | null
  headingTo: StationRT | null
  fromLabel: string
  toLabel: string
  station: StationRT | null
  serviceLeft: number
  queuedAt: number
  task: Task | null
  loopPos: number
  nextStop: number
}

function rng(seed: number) {
  let state = seed >>> 0 || 1
  return () => {
    state = (state + 0x6d2b79f5) >>> 0
    let t = state
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export class Simulation {
  readonly router: Router
  readonly config: SimConfig
  time = 0
  private live = { load: 1 }
  private procs: ProcRT[] = []
  private robots: RobotRT[] = []
  private random: () => number

  constructor(config: SimConfig) {
    this.config = config
    this.router = new Router(config.layout)
    this.random = rng(config.seed)
    let id = 1
    for (const proc of config.processes) {
      const pr = this.setup(proc)
      this.procs.push(pr)
      const off = config.mode === 'failure' ? Math.ceil(proc.robot.count * config.failureShare) : 0
      for (let index = 0; index < proc.robot.count; index++) {
        const robot = this.spawn(id++, pr, index, index < off)
        pr.robots.push(robot)
        this.robots.push(robot)
      }
      this.start(pr)
    }
  }

  private setup(proc: SimProcess): ProcRT {
    const stations = (kind: Station['kind']) => this.config.layout.floors.flatMap((floor) =>
      floor.stations.filter((st) => st.process === proc.code && st.kind === kind).map((st) => ({ st, floor: floor.id, busy: null, queue: [] as RobotRT[], heading: 0 })),
    )
    const factor = this.config.mode === 'peak' ? this.config.peak : 1
    const pr: ProcRT = {
      proc,
      robots: [],
      load: stations('load'),
      unload: stations('unload'),
      charge: stations('charge'),
      loop: null,
      waypointsAt: [],
      stopEach: 0,
      rate: proc.robot.rate ?? 0,
      pending: [],
      head: 0,
      nextArrival: 0,
      lambda: (proc.requiredPerHour * factor) / 3600,
      required: proc.requiredPerHour * factor,
      liveLoad: 1,
      done: 0,
      cycleSum: 0,
      cycles: 0,
      waitSum: 0,
      waits: 0,
      maxQueue: 0,
      busyS: 0,
      chargeS: 0,
      notes: [],
    }
    if (proc.robot.speedSource === 'default') pr.notes.push(`Скорости в карточке нет, взято ${proc.robot.speed} м/с.`)
    if (!proc.robot.workS || !proc.robot.chargeS) pr.notes.push('Автономности или времени зарядки в карточке нет: зарядка не моделируется.')
    else if (!pr.charge.length) pr.notes.push('Станций зарядки на схеме нет: робот заряжается на месте.')
    if (proc.kind === 'transport') {
      if (!pr.load.length || !pr.unload.length) pr.notes.push('На схеме нет станций загрузки или выгрузки процесса.')
      pr.nextArrival = pr.lambda > 0 ? this.exp(pr.lambda) : Infinity
    }
    if (proc.kind === 'coverage') {
      if (!pr.rate) pr.notes.push('В карточке нет производительности: покрытие не считается.')
      pr.loop = this.coverLoop(proc.code)
      if (!pr.loop) pr.notes.push('На схеме нет зоны процесса.')
    }
    if (proc.kind === 'patrol') {
      const waypoints = this.config.layout.floors.flatMap((floor) => floor.stations.filter((st) => st.process === proc.code && st.kind === 'waypoint').map((st) => ({ floor: floor.id, st })))
      if (waypoints.length < 2) pr.notes.push('Для обхода нужно минимум две точки на одном этаже.')
      else {
        const floor = waypoints[0]!.floor
        const points = waypoints.filter((item) => item.floor === floor).map((item) => item.st)
        const legs: MoveLeg[] = []
        const at: number[] = [0]
        let total = 0
        for (let index = 0; index < points.length; index++) {
          const a = points[index]!
          const b = points[(index + 1) % points.length]!
          const leg = this.router.walk(floor, a.x, a.y, b.x, b.y)
          if (!leg) continue
          legs.push(leg)
          total += leg.length
          at.push(total)
        }
        pr.loop = joinLegs(legs)
        pr.waypointsAt = at.slice(0, -1)
        pr.stopEach = points.length ? proc.stopS / points.length : 0
        if (!pr.loop) pr.notes.push('Между точками обхода нет прохода.')
      }
    }
    return pr
  }

  private coverLoop(code: string): MoveLeg | null {
    for (const floor of this.config.layout.floors) {
      const zones = floor.zones.filter((zone) => zone.process === code)
      if (!zones.length) continue
      const legs: MoveLeg[] = []
      let last: [number, number] | null = null
      zones.forEach((zone) => {
        let flip = false
        for (let y = Math.floor(zone.y) + 0.5; y < zone.y + zone.h; y += 1) {
          const a: [number, number] = [Math.floor(zone.x) + 0.5, y]
          const b: [number, number] = [Math.floor(zone.x + zone.w) - 0.5, y]
          const [from, to] = flip ? [b, a] : [a, b]
          flip = !flip
          if (last) {
            const hop = this.router.walk(floor.id, last[0], last[1], from[0], from[1])
            if (hop) legs.push(hop)
          }
          const row = this.router.walk(floor.id, from[0], from[1], to[0], to[1])
          if (row) {
            legs.push(row)
            last = to
          }
        }
      })
      if (last && legs[0]) {
        const back = this.router.walk(floor.id, last[0], last[1], legs[0].pts[0]!, legs[0].pts[1]!)
        if (back) legs.push(back)
      }
      return joinLegs(legs)
    }
    return null
  }

  private home(pr: ProcRT, index: number): Place {
    const pool = pr.charge.length ? pr.charge : pr.load.length ? pr.load : pr.unload
    const station = pool[index % Math.max(1, pool.length)]
    if (station) return { floor: station.floor, x: station.st.x, y: station.st.y }
    const floor = this.config.layout.floors[0]
    return { floor: floor?.id ?? '', x: 2.5, y: 2.5 }
  }

  private spawn(id: number, pr: ProcRT, index: number, off: boolean): RobotRT {
    const place = this.home(pr, index)
    return {
      id,
      pr,
      floor: place.floor,
      x: place.x + (index % 3) * 0.3,
      y: place.y + Math.floor(index / 3) % 3 * 0.3,
      phase: off ? 'off' : 'idle',
      status: off ? 'off' : 'idle',
      battery: pr.proc.robot.workS ? pr.proc.robot.workS * (0.55 + 0.45 * this.random()) : Infinity,
      legs: [],
      legIndex: 0,
      legPos: 0,
      onArrive: null,
      headingTo: null,
      fromLabel: '',
      toLabel: '',
      station: null,
      serviceLeft: 0,
      queuedAt: 0,
      task: null,
      loopPos: 0,
      nextStop: 0,
    }
  }

  private start(pr: ProcRT) {
    const active = pr.robots.filter((robot) => robot.phase !== 'off')
    if ((pr.proc.kind === 'coverage' || pr.proc.kind === 'patrol') && pr.loop) {
      active.forEach((robot, index) => {
        robot.loopPos = (pr.loop!.length * index) / Math.max(1, active.length)
        this.toLoop(robot)
      })
    }
  }

  private exp(lambda: number) {
    return -Math.log(1 - this.random()) / lambda
  }

  private travel(robot: RobotRT, to: Place, then: () => void, status: RobotStatus = 'moving') {
    const legs = this.router.route({ floor: robot.floor, x: robot.x, y: robot.y }, to, robot.pr.proc.robot.stairs)
    if (!legs) {
      robot.phase = 'stuck'
      robot.status = 'idle'
      if (!robot.pr.notes.includes('Часть станций недостижима: нет прохода или перехода между этажами.')) {
        robot.pr.notes.push('Часть станций недостижима: нет прохода или перехода между этажами.')
      }
      return
    }
    robot.legs = legs
    robot.legIndex = 0
    robot.legPos = 0
    robot.onArrive = then
    robot.status = status
  }

  private pickStation(robot: RobotRT, pool: StationRT[], service: number) {
    let best: StationRT | null = null
    let cost = Infinity
    const speed = robot.pr.proc.robot.speed
    for (const station of pool) {
      const same = station.floor === robot.floor
      const distance = Math.hypot(station.st.x - robot.x, station.st.y - robot.y) + (same ? 0 : 60)
      const wait = ((station.busy ? 1 : 0) + station.queue.length + station.heading) * service
      const value = distance / speed + wait
      if (value < cost) {
        cost = value
        best = station
      }
    }
    return best
  }

  private headTo(robot: RobotRT, station: StationRT, then: () => void, status: RobotStatus = 'moving') {
    station.heading += 1
    robot.headingTo = station
    robot.fromLabel = robot.toLabel || 'Старт'
    robot.toLabel = stationLabel(robot.pr.proc, station.st.kind, station.st.item)
    this.travel(robot, { floor: station.floor, x: station.st.x, y: station.st.y }, () => {
      station.heading = Math.max(0, station.heading - 1)
      robot.headingTo = null
      then()
    }, status)
    if (robot.phase === 'stuck') {
      station.heading = Math.max(0, station.heading - 1)
      robot.headingTo = null
    }
  }

  private arriveAt(robot: RobotRT, station: StationRT, service: number, done: () => void) {
    robot.station = station
    robot.x = station.st.x
    robot.y = station.st.y
    robot.floor = station.floor
    if (!station.busy) {
      station.busy = robot
      robot.serviceLeft = service
      robot.onArrive = done
      robot.status = robot.phase === 'charge' ? 'charging' : 'service'
      return
    }
    station.queue.push(robot)
    robot.pr.maxQueue = Math.max(robot.pr.maxQueue, station.queue.length)
    robot.queuedAt = this.time
    robot.serviceLeft = service
    robot.onArrive = done
    robot.status = 'queue'
    const spot = station.queue.length
    robot.x = station.st.x - 0.7 * spot
  }

  private release(station: StationRT) {
    station.busy = null
    const next = station.queue.shift()
    if (!next) return
    const pr = next.pr
    pr.waitSum += this.time - next.queuedAt
    pr.waits += 1
    station.busy = next
    next.x = station.st.x
    next.status = next.phase === 'charge' ? 'charging' : 'service'
    station.queue.forEach((robot, index) => { robot.x = station.st.x - 0.7 * (index + 1) })
  }

  private needsCharge(robot: RobotRT) {
    const spec = robot.pr.proc.robot
    return Boolean(spec.workS && spec.chargeS && robot.battery < spec.workS * LOW_BATTERY)
  }

  private wantsTopUp(robot: RobotRT) {
    const spec = robot.pr.proc.robot
    if (!spec.workS || !spec.chargeS || robot.battery >= spec.workS * TOP_UP) return false
    return robot.pr.charge.some((station) => !station.busy && !station.queue.length)
  }

  private goCharge(robot: RobotRT, after: () => void) {
    const spec = robot.pr.proc.robot
    const duration = () => (spec.chargeS ?? 0) * Math.max(0, 1 - robot.battery / (spec.workS ?? 1))
    robot.phase = 'to_charge'
    const station = this.pickStation(robot, robot.pr.charge, spec.chargeS ?? 0)
    const finish = () => {
      robot.battery = spec.workS ?? Infinity
      if (robot.station) this.release(robot.station)
      robot.station = null
      robot.phase = 'idle'
      robot.status = 'idle'
      after()
    }
    if (!station) {
      robot.phase = 'charge'
      robot.status = 'charging'
      robot.serviceLeft = duration()
      robot.onArrive = finish
      return
    }
    this.headTo(robot, station, () => {
      robot.phase = 'charge'
      this.arriveAt(robot, station, duration(), finish)
    })
  }

  private toLoop(robot: RobotRT) {
    const pr = robot.pr
    if (!pr.loop) return
    const [x, y] = pointAt(pr.loop, robot.loopPos)
    robot.phase = 'to_work'
    robot.fromLabel = 'Старт'
    robot.toLabel = 'Маршрут'
    this.travel(robot, { floor: pr.loop.floor, x, y }, () => {
      robot.phase = 'work'
      robot.status = 'working'
      robot.nextStop = this.nextWaypoint(pr, robot.loopPos)
    })
  }

  private nextWaypoint(pr: ProcRT, pos: number) {
    if (!pr.waypointsAt.length || !pr.loop) return Infinity
    const ahead = pr.waypointsAt.find((at) => at > pos + 1e-6)
    return ahead ?? pr.waypointsAt[0]! + pr.loop.length
  }

  private dispatch(pr: ProcRT) {
    if (pr.proc.kind !== 'transport') return
    while (pr.nextArrival <= this.time) {
      pr.pending.push({ created: pr.nextArrival, started: 0 })
      pr.nextArrival += this.exp(pr.lambda)
    }
    if (!pr.load.length || !pr.unload.length) return
    for (const robot of pr.robots) {
      if (robot.phase !== 'idle') continue
      if (this.needsCharge(robot)) {
        this.goCharge(robot, () => {})
        continue
      }
      if (pr.head >= pr.pending.length) {
        if (this.wantsTopUp(robot)) this.goCharge(robot, () => {})
        continue
      }
      const task = pr.pending[pr.head++]!
      task.started = this.time
      robot.task = task
      this.fetch(robot)
    }
    if (pr.head > 2048) {
      pr.pending = pr.pending.slice(pr.head)
      pr.head = 0
    }
  }

  private fetch(robot: RobotRT) {
    const pr = robot.pr
    const station = this.pickStation(robot, pr.load, pr.proc.loadS)
    if (!station) return
    robot.phase = 'to_load'
    this.headTo(robot, station, () => {
      robot.phase = 'load'
      this.arriveAt(robot, station, pr.proc.loadS, () => {
        this.release(station)
        robot.station = null
        this.deliver(robot)
      })
    })
  }

  private deliver(robot: RobotRT) {
    const pr = robot.pr
    const station = this.pickStation(robot, pr.unload, pr.proc.unloadS)
    if (!station) return
    robot.phase = 'to_unload'
    this.headTo(robot, station, () => {
      robot.phase = 'unload'
      this.arriveAt(robot, station, pr.proc.unloadS, () => {
        this.release(station)
        robot.station = null
        pr.done += 1
        if (robot.task) {
          pr.cycleSum += this.time - robot.task.started
          pr.cycles += 1
        }
        robot.task = null
        robot.phase = 'idle'
        robot.status = 'idle'
      })
    }, 'loaded')
  }

  private move(robot: RobotRT, dt: number) {
    let left = dt * robot.pr.proc.robot.speed
    let time = dt
    while (robot.legIndex < robot.legs.length && time > 0) {
      const leg = robot.legs[robot.legIndex]!
      if (leg.kind === 'lift') {
        robot.status = 'lift'
        robot.floor = leg.floor
        robot.x = leg.x
        robot.y = leg.y
        const need = leg.seconds - robot.legPos
        if (time >= need) {
          time -= need
          left = time * robot.pr.proc.robot.speed
          robot.floor = leg.toFloor
          robot.legIndex += 1
          robot.legPos = 0
          robot.status = robot.phase === 'to_unload' ? 'loaded' : 'moving'
        } else {
          robot.legPos += time
          time = 0
        }
        continue
      }
      robot.floor = leg.floor
      const need = leg.length - robot.legPos
      if (left >= need) {
        left -= need
        time = left / robot.pr.proc.robot.speed
        const [x, y] = pointAt(leg, leg.length)
        robot.x = x
        robot.y = y
        robot.legIndex += 1
        robot.legPos = 0
      } else {
        robot.legPos += left
        const [x, y] = pointAt(leg, robot.legPos)
        robot.x = x
        robot.y = y
        time = 0
        left = 0
      }
    }
    if (robot.legIndex >= robot.legs.length) {
      robot.legs = []
      const then = robot.onArrive
      robot.onArrive = null
      then?.()
    }
  }

  private work(robot: RobotRT, dt: number) {
    const pr = robot.pr
    if (!pr.loop) return
    const kind = pr.proc.kind
    if (kind === 'patrol') pr.done += dt / (pr.loop.length / pr.proc.robot.speed + pr.proc.stopS)
    if (robot.phase === 'stop') {
      robot.serviceLeft -= dt
      if (robot.serviceLeft <= 0) {
        robot.phase = 'work'
        robot.status = 'working'
      }
      return
    }
    const speed = kind === 'coverage' && !pr.proc.code.includes('inventory') && pr.rate
      ? Math.min(pr.proc.robot.speed, pr.rate / 3600)
      : pr.proc.robot.speed
    let pos = robot.loopPos + speed * dt
    if (kind === 'coverage' && pr.rate) pr.done += (pr.rate / 3600) * dt
    if (pos >= pr.loop.length) {
      pos -= pr.loop.length
      if (robot.nextStop !== Infinity) robot.nextStop -= pr.loop.length
    }
    if (kind === 'patrol' && pos >= robot.nextStop) {
      pos = Math.max(0, robot.nextStop)
      robot.phase = 'stop'
      robot.status = 'service'
      robot.serviceLeft = pr.stopEach
      robot.nextStop = this.nextWaypoint(pr, pos)
    }
    robot.loopPos = pos
    const [x, y] = pointAt(pr.loop, pos)
    robot.x = x
    robot.y = y
    robot.floor = pr.loop.floor
    if (this.needsCharge(robot)) {
      this.goCharge(robot, () => this.toLoop(robot))
    }
  }

  step(dt = STEP_S) {
    this.time += dt
    for (const pr of this.procs) this.dispatch(pr)
    for (const robot of this.robots) {
      if (robot.phase === 'off' || robot.phase === 'stuck') continue
      const busy = robot.phase !== 'idle'
      if (busy && robot.phase !== 'charge' && robot.phase !== 'to_charge') {
        robot.battery -= dt
        if (robot.status !== 'queue') robot.pr.busyS += dt
      }
      if (robot.phase === 'charge' || robot.phase === 'to_charge') robot.pr.chargeS += dt
      if (robot.legs.length) {
        this.move(robot, dt)
        continue
      }
      if (robot.status === 'queue') continue
      if (robot.onArrive && (robot.status === 'service' || robot.status === 'charging')) {
        robot.serviceLeft -= dt
        if (robot.serviceLeft <= 0) {
          robot.serviceLeft = 0
          const then = robot.onArrive
          robot.onArrive = null
          then?.()
        }
        continue
      }
      if (robot.phase === 'work' || robot.phase === 'stop') this.work(robot, dt)
    }
  }

  advance(until: number) {
    const limit = Math.min(until, this.config.durationS)
    /* Шаг не больше STEP_S, но и не больше остатка: на малой скорости роботы двигаются плавно, а не прыжками раз в полсекунды. */
    while (limit - this.time > 1e-6) this.step(Math.min(STEP_S, limit - this.time))
  }

  get finished() {
    return this.time >= this.config.durationS - 1e-9
  }

  /* Живое управление во время смены. */
  get loadFactor() {
    return this.live.load
  }

  setLoadFactor(factor: number) {
    const value = Math.max(0.1, Math.min(5, factor))
    this.live.load = value
    for (const pr of this.procs) {
      if (pr.proc.kind !== 'transport') continue
      const scale = value / pr.liveLoad
      pr.liveLoad = value
      pr.lambda *= scale
      pr.required *= scale
      if (Number.isFinite(pr.nextArrival)) pr.nextArrival = this.time + Math.max(0, pr.nextArrival - this.time) / scale
    }
  }

  get offline() {
    return this.robots.filter((robot) => robot.phase === 'off').length
  }

  /** Ломает случайного работающего робота: груз возвращается в очередь, станция освобождается. */
  breakOne(process?: string): number | null {
    const pool = this.robots.filter((robot) => robot.phase !== 'off' && robot.phase !== 'stuck' && (!process || robot.pr.proc.code === process))
    if (!pool.length) return null
    const robot = pool[Math.floor(this.random() * pool.length)]!
    this.retire(robot)
    return robot.id
  }

  /** Возвращает в строй одного сломанного робота. */
  repairOne(process?: string): number | null {
    const pool = this.robots.filter((robot) => robot.phase === 'off' && (!process || robot.pr.proc.code === process))
    const robot = pool[0]
    if (!robot) return null
    robot.phase = 'idle'
    robot.status = 'idle'
    if (robot.pr.loop) this.toLoop(robot)
    return robot.id
  }

  setOffline(count: number) {
    let guard = 0
    while (this.offline < count && guard++ < 2000) if (this.breakOne() === null) break
    while (this.offline > count && guard++ < 4000) if (this.repairOne() === null) break
  }

  private retire(robot: RobotRT) {
    const station = robot.station
    if (station) {
      if (station.busy === robot) this.release(station)
      else station.queue = station.queue.filter((other) => other !== robot)
      station.queue.forEach((other, index) => { other.x = station.st.x - 0.7 * (index + 1) })
    }
    if (robot.headingTo) {
      robot.headingTo.heading = Math.max(0, robot.headingTo.heading - 1)
      robot.headingTo = null
    }
    if (robot.task) {
      robot.pr.pending.splice(robot.pr.head, 0, { ...robot.task, started: 0 })
      robot.task = null
    }
    robot.station = null
    robot.legs = []
    robot.onArrive = null
    robot.serviceLeft = 0
    robot.phase = 'off'
    robot.status = 'off'
  }

  views(out: RobotView[] = []): RobotView[] {
    out.length = this.robots.length
    this.robots.forEach((robot, index) => {
      const spec = robot.pr.proc.robot
      const view = out[index] ?? ({} as RobotView)
      view.id = robot.id
      view.process = robot.pr.proc.code
      view.floor = robot.floor
      view.x = robot.x
      view.y = robot.y
      view.status = robot.status
      view.battery = spec.workS ? Math.max(0, robot.battery / spec.workS) : 1
      view.trip = tripOf(robot)
      out[index] = view
    })
    return out
  }

  stats(): SimStats {
    const hours = Math.max(this.time, STEP_S) / 3600
    const processes: ProcessStats[] = this.procs.map((pr) => {
      const active = pr.robots.filter((robot) => robot.phase !== 'off').length
      const donePerHour = pr.done / hours
      const backlog = pr.proc.kind === 'transport' ? pr.pending.length - pr.head : 0
      const settled = this.time >= Math.min(SETTLE_S, this.config.durationS)
      const meets = pr.proc.kind === 'transport'
        ? backlog <= Math.max(3, pr.lambda * 900) && pr.done > 0
        : donePerHour >= pr.required * 0.95
      const notes = [...pr.notes]
      if (!settled) notes.push('Прогон меньше 30 минут: итог ещё не устоялся.')
      if (pr.proc.kind === 'none') notes.push('Для процесса нет модели движения.')
      return {
        code: pr.proc.code,
        name: pr.proc.name,
        unit: pr.proc.unit,
        robots: pr.robots.length,
        active,
        offline: pr.robots.length - active,
        queued: pr.robots.filter((robot) => robot.status === 'queue').length,
        requiredPerHour: pr.required,
        donePerHour,
        done: pr.done,
        backlog,
        utilization: active ? Math.min(1, pr.busyS / (active * Math.max(this.time, STEP_S))) : 0,
        chargingShare: active ? Math.min(1, pr.chargeS / (active * Math.max(this.time, STEP_S))) : 0,
        avgWaitS: pr.waits ? pr.waitSum / pr.waits : 0,
        maxQueue: pr.maxQueue,
        avgCycleS: pr.cycles ? pr.cycleSum / pr.cycles : null,
        confirmed: pr.proc.kind !== 'none' && settled && meets && pr.required > 0,
        notes,
      }
    })
    return { timeS: this.time, processes }
  }
}

function tripOf(robot: RobotRT): RobotTrip | null {
  const loop = robot.pr.loop
  if ((robot.phase === 'work' || robot.phase === 'stop') && loop && robot.floor === loop.floor) {
    /* Показываем реальный кусок петли впереди робота: путь не перерисовывается, а укорачивается спереди по мере движения. */
    const lookahead = Math.min(loop.length, 40)
    const path = [robot.x, robot.y]
    const start = robot.loopPos
    let cursor = 0
    while (cursor + 1 < loop.cum.length && loop.cum[cursor + 1]! <= start) cursor++
    let ahead = 0
    let pos = start
    while (ahead < lookahead) {
      const nextIndex = cursor + 1
      if (nextIndex >= loop.cum.length) break
      const nextAt = loop.cum[nextIndex]!
      const segment = nextAt - pos
      if (ahead + segment >= lookahead) {
        const [x, y] = pointAt(loop, pos + (lookahead - ahead))
        path.push(x, y)
        ahead = lookahead
        break
      }
      path.push(loop.pts[nextIndex * 2]!, loop.pts[nextIndex * 2 + 1]!)
      ahead += segment
      pos = nextAt
      cursor = nextIndex
    }
    const left = loop.length - robot.loopPos
    return {
      from: robot.pr.proc.kind === 'patrol' ? 'Точка обхода' : 'Обход зоны',
      to: robot.pr.proc.kind === 'patrol' ? 'Следующая точка' : 'Конец обхода',
      leftM: left,
      totalM: loop.length,
      path,
    }
  }
  if (!robot.legs.length || !robot.toLabel) return null
  let left = 0
  let total = 0
  const path: number[] = []
  let sameFloor = true
  for (let index = 0; index < robot.legs.length; index++) {
    const leg = robot.legs[index]!
    if (leg.kind === 'lift') {
      if (index >= robot.legIndex) sameFloor = false
      continue
    }
    total += leg.length
    if (index < robot.legIndex) continue
    const start = index === robot.legIndex ? robot.legPos : 0
    left += Math.max(0, leg.length - start)
    if (!sameFloor || leg.floor !== robot.floor) continue
    if (!path.length) path.push(robot.x, robot.y)
    const from = segmentIndex(leg, start)
    for (let point = from; point < leg.pts.length; point += 2) path.push(leg.pts[point]!, leg.pts[point + 1]!)
  }
  if (left < 0.05) return null
  return { from: robot.fromLabel || 'Старт', to: robot.toLabel, leftM: left, totalM: total, path }
}

function segmentIndex(leg: MoveLeg, distance: number) {
  let index = 0
  while (index + 1 < leg.cum.length && leg.cum[index + 1]! < distance) index++
  return index * 2
}

export function runShift(config: SimConfig): SimStats {
  const sim = new Simulation(config)
  sim.advance(config.durationS)
  return sim.stats()
}

export function minimalFleet(config: SimConfig, code: string, limitS = 3 * 3600): number | null {
  const proc = config.processes.find((item) => item.code === code)
  if (!proc || proc.kind === 'none' || proc.requiredPerHour <= 0) return null
  const probe = (count: number) => {
    const single: SimConfig = {
      ...config,
      durationS: Math.min(config.durationS, limitS),
      processes: [{ ...proc, robot: { ...proc.robot, count } }],
    }
    return runShift(single).processes[0]?.confirmed ?? false
  }
  let hi = Math.max(2, proc.robot.count)
  let guard = 0
  while (!probe(hi)) {
    hi *= 2
    if (++guard > 4 || hi > 1200) return null
  }
  let lo = 1
  while (lo < hi) {
    const mid = Math.floor((lo + hi) / 2)
    if (probe(mid)) hi = mid
    else lo = mid + 1
  }
  return lo
}
