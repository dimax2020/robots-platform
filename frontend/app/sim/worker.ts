import { minimalFleet, runShift } from './engine'
import type { SimConfig, SimStats } from './types'

export interface WorkerRequest { id: number; config: SimConfig }
export interface WorkerResponse { id: number; stats: SimStats; minimal: Record<string, number | null>; ms: number }

self.onmessage = (event: MessageEvent<WorkerRequest>) => {
  const { id, config } = event.data
  const started = performance.now()
  const stats = runShift(config)
  const minimal: Record<string, number | null> = {}
  for (const proc of config.processes) minimal[proc.code] = minimalFleet(config, proc.code)
  const response: WorkerResponse = { id, stats, minimal, ms: performance.now() - started }
  self.postMessage(response)
}
