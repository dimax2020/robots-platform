export type StationKind = 'load' | 'unload' | 'charge' | 'waypoint'
export type LinkKind = 'elevator' | 'stairs'
export type ProcessKind = 'transport' | 'coverage' | 'patrol' | 'none'
export type LoadMode = 'normal' | 'peak' | 'failure'
export type ItemRole = 'pickup' | 'dropoff' | 'charge' | 'waypoint' | 'work_zone' | 'obstacle'
export type Visibility = 'full' | 'dim' | 'hidden'

export interface LayoutItem {
  key: string
  label: string
  role: ItemRole
  shape: 'point' | 'area'
  min_count: number
  count_rule: 'fixed' | 'by_flow' | 'by_charge'
  hint: string
}

export interface Wall { id: string; points: number[] }
export interface Block { id: string; x: number; y: number; w: number; h: number; label: string; process?: string; item?: string }
export interface Station { id: string; process: string; kind: StationKind; x: number; y: number; item?: string }
export interface Zone { id: string; process: string; x: number; y: number; w: number; h: number; item?: string }
export interface Background { url: string; x: number; y: number; mpp: number; opacity: number; width: number; height: number; locked?: boolean }

export interface FloorArea { id: string; points: number[] }

export interface Floor {
  id: string
  name: string
  width: number
  height: number
  /** Участки пола, м. Роботы ездят внутри них; стены — это граница участков. */
  areas: FloorArea[]
  walls: Wall[]
  blocks: Block[]
  stations: Station[]
  zones: Zone[]
  background: Background | null
}

export interface LinkStop { floor: string; x: number; y: number }

/** Лифт или лестница: два конца на разных этажах, каждый стоит там, где его поставили. */
export interface Link {
  id: string
  kind: LinkKind
  name: string
  stops: LinkStop[]
  wait_s: number
  per_floor_s: number
}

export interface ProcessSettings {
  visibility: Visibility
  robots: boolean
}

export interface LayoutGuide {
  phase: 'intro' | 'building' | 'process' | 'ready'
  process: string
}

export interface Layout {
  version: 1
  floors: Floor[]
  links: Link[]
  guide?: LayoutGuide
  processes?: Record<string, ProcessSettings>
}

export interface RobotSpec {
  name: string
  count: number
  speed: number
  speedSource: 'card' | 'default'
  workS: number | null
  chargeS: number | null
  stairs: boolean
  rate: number | null
}

export interface SimProcess {
  code: string
  name: string
  kind: ProcessKind
  robot: RobotSpec
  requiredPerHour: number
  unit: string
  loadS: number
  unloadS: number
  stopS: number
  routeM: number | null
  basis: string
  items: LayoutItem[]
}

export interface SimConfig {
  layout: Layout
  processes: SimProcess[]
  mode: LoadMode
  peak: number
  failureShare: number
  durationS: number
  seed: number
}

export type RobotStatus = 'idle' | 'moving' | 'loaded' | 'service' | 'queue' | 'charging' | 'lift' | 'working' | 'off'

export interface RobotTrip {
  from: string
  to: string
  leftM: number
  totalM: number
  path: number[]
}

export interface RobotView {
  id: number
  process: string
  floor: string
  x: number
  y: number
  status: RobotStatus
  battery: number
  trip: RobotTrip | null
}

export interface ProcessStats {
  code: string
  name: string
  unit: string
  robots: number
  active: number
  offline: number
  queued: number
  requiredPerHour: number
  donePerHour: number
  done: number
  backlog: number
  utilization: number
  chargingShare: number
  avgWaitS: number
  maxQueue: number
  avgCycleS: number | null
  confirmed: boolean
  notes: string[]
}

export interface SimStats {
  timeS: number
  processes: ProcessStats[]
}
