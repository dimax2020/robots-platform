export interface Gap { key: string; label: string; used_in: string }
export interface Highlight { label: string; value: string; missing: boolean }
export interface ProcessRef { code: string; name: string }

export interface AnalyticsRobot {
  slug: string
  name: string
  summary: string | null
  price_rub: number | null
  image_url: string | null
  trl: number | null
  availability: string | null
  solution_type: string | null
  manufacturer: string
  city: string
  state: 'in' | 'out' | 'note'
  headline: string
  gaps: Gap[]
  processes: ProcessRef[]
  offers: number
  highlights: Highlight[]
  revision_comment: string
  has_cabinet?: boolean
}

export interface MatchEvent {
  at: string | null
  object_name: string
  outcome: 'success' | 'empty'
  site: { key: string; label: string; value: string | number }[]
  reasons: string[]
  noted: { slug: string; name: string; missing: string[] }[]
  blocked: { slug: string; name: string; reasons: string[] }[]
  text: string
}

export interface ReasonStat { text: string; count: number }
export interface MatchTotals { total: number; success: number; empty: number }

export interface VendorBoard {
  cards: number
  processes: number
  objects: number
  offers: number
  process_names: string[]
  object_names: string[]
  pie: { in: number; out: number; note: number }
  matches: MatchTotals
  reasons: ReasonStat[]
  events: MatchEvent[]
  robots: AnalyticsRobot[]
  city: string
}

export const stateLabel: Record<AnalyticsRobot['state'], string> = {
  in: 'В подборе',
  note: 'С пометкой',
  out: 'Не в подборе',
}
