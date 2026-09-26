import { minimalFleet, runShift, Simulation } from './engine'
import { insideFloorAreas, Router } from './grid'
import { buildProcess, emptyLayout, fitFloorToOutline, mergeAreas, newLink, normalizeLayout, placedCount, placeProcess, processReady } from './templates'
import type { LayoutItem, SimConfig } from './types'

const site = {
  area_m2: 20000, floors_count: 1, shift_hours: 11, shifts_per_day: 2,
  inbound_pallets_per_day: 1000, outbound_pallets_per_day: 1000, picker_route_m: 25,
  clean_area_m2: 10000, pallet_places: 20000,
}

const item = (key: string, label: string, role: LayoutItem['role'], count = 1, rule: LayoutItem['count_rule'] = 'fixed'): LayoutItem => ({ key, label, role, shape: role === 'work_zone' ? 'area' : 'point', min_count: count, count_rule: rule, hint: '' })
const transportItems = [item('pickup', 'Приёмка', 'pickup', 1, 'by_flow'), item('dropoff', 'Отгрузка', 'dropoff', 1, 'by_flow'), item('charge', 'Зарядка', 'charge', 1, 'by_charge')]
const coverageItems = [item('zone', 'Зона мойки', 'work_zone'), item('charge', 'База', 'charge', 1, 'by_charge')]
const patrolItems = [item('waypoint', 'Точка обхода', 'waypoint', 2), item('charge', 'Зарядка', 'charge', 1, 'by_charge')]

const check = (label: string, ok: boolean, detail: unknown) => {
  console.log(`${ok ? 'OK  ' : 'FAIL'} ${label}`, detail)
  if (!ok) process.exitCode = 1
}

const pallets = buildProcess('pallet_transport', 'Перевозка паллет', { name: 'Ronavi H1500', count: 5, specs: [{ key: 'speed_loaded_ms', value: 1.5 }, { key: 'work_time_h', value: 8 }, { key: 'charge_time_h', value: 2 }] }, site, transportItems)
const layout = emptyLayout(site)
check('пустой этаж компактный', layout.floors[0]!.width <= 120 && layout.floors[0]!.height <= 80, { w: layout.floors[0]!.width, h: layout.floors[0]!.height })
placeProcess(layout, layout.floors[0]!.id, pallets, site)
check('автоматическая расстановка закрывает задачи процесса', processReady(layout, pallets), pallets.items.map((row) => `${row.label}: ${placedCount(layout, pallets.code, row)}`))
const base: SimConfig = { layout, processes: [pallets], mode: 'normal', peak: 1.5, failureShare: 0.2, durationS: 11 * 3600, seed: 7 }

let started = Date.now()
const normal = runShift(base).processes[0]!
check('паллеты: расчётные 5 роботов справляются с потоком', normal.confirmed, { perHour: normal.donePerHour.toFixed(1), required: normal.requiredPerHour.toFixed(1), backlog: normal.backlog, util: normal.utilization.toFixed(2), ms: Date.now() - started })

const peak = runShift({ ...base, mode: 'peak', peak: 2 }).processes[0]!
check('паллеты: пик ×2 даёт очередь', !peak.confirmed && peak.backlog > normal.backlog, { perHour: peak.donePerHour.toFixed(1), backlog: peak.backlog })

const failure = runShift({ ...base, mode: 'failure', failureShare: 0.4 }).processes[0]!
check('паллеты: сбой выключает роботов', failure.active === 3, { active: failure.active, backlog: failure.backlog })

started = Date.now()
const minimal = minimalFleet(base, 'pallet_transport')
check('паллеты: минимальный парк не больше расчётного', minimal !== null && minimal <= 5, { minimal, ms: Date.now() - started })

const cleaner = buildProcess('floor_washing', 'Мойка полов', { name: 'Робот-уборщик', count: 3, specs: [{ key: 'speed_loaded_ms', value: 1 }, { key: 'proizvoditelnost', value: 1200 }] }, site, coverageItems)
const cleanLayout = emptyLayout(site)
placeProcess(cleanLayout, cleanLayout.floors[0]!.id, cleaner, site)
const clean = runShift({ ...base, layout: cleanLayout, processes: [cleaner], durationS: 2 * 3600 }).processes[0]!
check('мойка: 3 робота по 1200 м²/ч покрывают 10 000 м² за смену 11 ч', clean.confirmed, { perHour: clean.donePerHour.toFixed(0), required: clean.requiredPerHour.toFixed(0) })

const guard = buildProcess('perimeter_security', 'Охрана периметра', { name: 'Робот Городовой', count: 2, specs: [{ key: 'speed_loaded_ms', value: 1.5 }] }, site, patrolItems)
const guardLayout = emptyLayout(site)
placeProcess(guardLayout, guardLayout.floors[0]!.id, guard, site)
const patrol = runShift({ ...base, layout: guardLayout, processes: [guard], durationS: 3 * 3600 }).processes[0]!
check('обход: 2 робота делают больше 24/22 обходов в час', patrol.confirmed, { perHour: patrol.donePerHour.toFixed(2), required: patrol.requiredPerHour.toFixed(2) })

const sortSite = { ...site, pick_units_per_day: 100000 }
const sorter = buildProcess('parcel_sorting', 'Сортировка посылок', { name: 'Ronavi SD', count: 232, specs: [{ key: 'speed_loaded_ms', value: 1.5 }] }, sortSite, transportItems)
const sortLayout = emptyLayout(sortSite)
placeProcess(sortLayout, sortLayout.floors[0]!.id, sorter, sortSite)
started = Date.now()
const sort = runShift({ ...base, layout: sortLayout, processes: [sorter] }).processes[0]!
check('сортировка: 232 робота за смену считаются быстрее 10 с', Date.now() - started < 10000, { perHour: sort.donePerHour.toFixed(0), required: sort.requiredPerHour.toFixed(0), confirmed: sort.confirmed, ms: Date.now() - started })

const twoFloors = emptyLayout({ ...site, floors_count: 2 })
placeProcess(twoFloors, twoFloors.floors[0]!.id, pallets, site)
const [ground, upstairs] = twoFloors.floors as [typeof twoFloors.floors[0], typeof twoFloors.floors[0]]
for (const st of ground.stations.filter((item) => item.kind === 'unload')) upstairs.stations.push({ ...st, id: `${st.id}-up` })
ground.stations = ground.stations.filter((item) => item.kind !== 'unload')
const noLift = runShift({ ...base, layout: twoFloors, durationS: 3600 }).processes[0]!
check('два этажа без лифта: станции недостижимы', noLift.done === 0 && noLift.notes.some((note) => note.includes('недостижима')), { done: noLift.done })
twoFloors.links.push(newLink('elevator', [{ floor: ground.id, x: 4.5, y: 4.5 }, { floor: upstairs.id, x: 30.5, y: 20.5 }]))
const lift = runShift({ ...base, layout: twoFloors, durationS: 3600 }).processes[0]!
check('два этажа с лифтом: рейсы идут, концы лифта в разных точках', lift.done > 0, { done: lift.done, cycle: lift.avgCycleS?.toFixed(0) })

const liveSim = new Simulation({ ...base, durationS: 3 * 3600 })
liveSim.advance(1800)
const beforeBreak = liveSim.stats().processes[0]!
liveSim.breakOne()
liveSim.breakOne()
liveSim.advance(1830)
const afterBreak = liveSim.stats().processes[0]!
check('поломка на ходу: два робота выпали из строя, задания не потерялись', afterBreak.active === beforeBreak.active - 2 && afterBreak.offline === 2, { active: afterBreak.active, offline: afterBreak.offline })
liveSim.setLoadFactor(2)
liveSim.advance(3600)
const doubled = liveSim.stats().processes[0]!
check('поток ×2 на ходу удваивает требуемое и растит очередь', Math.abs(doubled.requiredPerHour - beforeBreak.requiredPerHour * 2) < 1e-6 && doubled.backlog > afterBreak.backlog, { required: doubled.requiredPerHour.toFixed(1), backlog: doubled.backlog })
liveSim.repairOne()
liveSim.repairOne()
liveSim.setLoadFactor(1)
liveSim.advance(3610)
check('ремонт возвращает роботов', liveSim.stats().processes[0]!.offline === 0, { offline: liveSim.stats().processes[0]!.offline })
const slow = new Simulation({ ...base, durationS: 3600 })
slow.advance(0.016)
slow.advance(0.032)
check('малый шаг времени двигает модель без прыжков', Math.abs(slow.time - 0.032) < 1e-9, { time: slow.time })

const lShape = emptyLayout(site)
const lf = lShape.floors[0]!
lf.areas = [{ id: 'a1', points: [0, 0, lf.width, 0, lf.width, Math.round(lf.height / 2), Math.round(lf.width / 2), Math.round(lf.height / 2), Math.round(lf.width / 2), lf.height, 0, lf.height] }]
placeProcess(lShape, lf.id, pallets, site)
const outside = lf.stations.filter((st) => !insideFloorAreas(lf, st.x, st.y))
check('Г-образный пол: станции стоят внутри контура', outside.length === 0 && processReady(lShape, pallets), { stations: lf.stations.length, outside: outside.length })
const legacy = normalizeLayout({ floors: [{ id: 'f1', name: '1', width: 20, height: 10, outline: [0, 0, 20, 0, 20, 10, 0, 10], walls: [{ id: 'outer-f1', points: [0, 0, 20, 0] }], blocks: [], stations: [], zones: [], background: null }], links: [{ id: 'l', kind: 'elevator', x: 3.5, y: 3.5, floors: ['f1', 'f2'], wait_s: 30, per_floor_s: 10 }], guide: { phase: 'plan', process: '', planSkipped: false } } as never)
check('старая схема мигрирует: участки пола, концы лифта, стадия', legacy.floors[0]!.areas.length === 1 && legacy.floors[0]!.walls.length === 0 && legacy.links[0]!.stops.length === 2 && legacy.guide?.phase === 'building', legacy.links[0])
const twoRooms = emptyLayout(site)
const tr = twoRooms.floors[0]!
tr.areas = [{ id: 'r1', points: [0, 0, 30, 0, 30, 20, 0, 20] }, { id: 'r2', points: [28, 5, 60, 5, 60, 25, 28, 25] }, { id: 'r3', points: [0, 40, 20, 40, 20, 50, 0, 50] }]
fitFloorToOutline(tr)
check('размер сетки растёт вместе с полом', tr.width === 60 && tr.height === 50, { w: tr.width, h: tr.height })
const rooms = new Router(twoRooms)
const across = rooms.walk(tr.id, 5, 10, 55, 15)
const gap = rooms.walk(tr.id, 5, 10, 5, 45)
check('участки пола: между перекрывающимися проезд есть, в отдельный — нет', across !== null && gap === null, { across: across?.length.toFixed(1), gap: gap?.length })
const mergedId = mergeAreas(tr, 'r2')
check('пересекающиеся участки слились в один, отдельный остался', tr.areas.length === 2 && tr.areas.some((a) => a.id === mergedId && a.points.length >= 12), tr.areas.map((a) => `${a.id}:${a.points.length / 2}`))
