import assert from 'node:assert/strict'
import { assessmentLabel, countExplanation, significantReasons } from '../app/utils/assessmentPresentation'
import { buildProcess, emptyLayout, processReady } from '../app/sim/templates'
import { readFileSync } from 'node:fs'
import { automaticChoice, eligibleForEconomy, includedInTechnicalComparison, selectionIssue, normalizeCompareStore } from '../app/utils/fleetSelection'
import { pickReportSheets } from '../app/utils/exportTables'
import { formatDemoValue } from '../app/utils/demoSynthetic'
const cases = JSON.parse(readFileSync(new URL('../../platform/tests/fixtures/fleet-selection.json', import.meta.url), 'utf8'))
for (const c of cases) {
  const id = c.explicit ? c.chosen_id : c.chosen_id || automaticChoice(c.group)
  const hit = c.group.hits.find((h: { product_id: string }) => h.product_id === id)
  assert.equal(eligibleForEconomy(hit) ? hit.product_id : null, c.expected, c.name)
}
assert.match(selectionIssue({ hits: [] }, 'deleted'), /Сохранённое/)
assert.equal(formatDemoValue(['indoor']), 'indoor')
const syntheticSheets = [{ name: 'Синтетические допущения', rows: [['origin', 'demo_synthetic']] }, { name: 'Расчёт количества', rows: [['model', 'cleaning_area_v1']] }]
for (const flag of [false, true]) {
  assert.deepEqual(pickReportSheets(syntheticSheets, { match: flag, economy: flag, whatif: flag }), syntheticSheets)
}
const preliminary = { product_id: 'preliminary', verdict: 'pass', count: null, economic_ready: false }
assert.equal(includedInTechnicalComparison(preliminary), true)
assert.equal(eligibleForEconomy(preliminary), false)
const demo = { product_id: 'demo', verdict: 'pass', count: 6, economic_ready: false, demo_economic_ready: true, calculation_mode: 'demo' }
assert.equal(eligibleForEconomy(demo), true)
assert.equal(automaticChoice({ hits: [demo], calculation_mode: 'demo', demo_best_product_id: 'demo' }), 'demo')
assert.equal(automaticChoice({ hits: [demo], demo_best_product_id: 'demo' }), '')
assert.equal(eligibleForEconomy({ ...demo, calculation_mode: 'ordinary' }), false)
for (const verdict of ['unknown', 'fail', 'conditional']) assert.equal(eligibleForEconomy({ ...demo, verdict }), false)
for (const verdict of ['unknown', 'conditional']) assert.equal(includedInTechnicalComparison({ ...preliminary, verdict }), true)
assert.equal(includedInTechnicalComparison({ ...preliminary, verdict: 'fail' }), false)
for (const count of [NaN, Infinity, -1, 1.2]) assert.equal(eligibleForEconomy({ product_id: 'a', verdict: 'pass', count, economic_ready: true }), false)
console.log(`${cases.length} общих сценариев выбора + границы чисел: OK`)

assert.deepEqual(normalizeCompareStore({ chosen: { old: 'deleted', bad: 42 }, extra: { broken: 1 }, excluded: null }).chosen, { old: 'deleted' })
assert.deepEqual(normalizeCompareStore(null).extra, {})
assert.deepEqual(normalizeCompareStore({ excluded: { move: ['a', false] } }).excluded, { move: ['a'] })

for (const count of [null, 0, -1, 1.5, Infinity]) {
  const proc = buildProcess('pallet_transport', 'Тест', { name: 'Тест', count, specs: [] }, {}, [])
  assert.equal(proc.robot.count, 0)
  assert.equal(processReady(emptyLayout({}), proc), false)
}

const assumed = { ...preliminary, applicability: 'conditional', economic_ready: true, count: 10, name: 'Тест', slug: 'test', notes: [] }
assert.equal(assessmentLabel(assumed), 'Подходит при допущениях')
assert.equal(eligibleForEconomy(assumed), true)
assert.equal(countExplanation(assumed), '10 шт.')
assert.equal(significantReasons({ ...assumed, reasons: [{ code: 'optional', severity: 'info', message: 'Некритичное уточнение' }] }).length, 0)
