import assert from 'node:assert/strict'
import { buildProcess, emptyLayout, processReady } from '../app/sim/templates'
import { readFileSync } from 'node:fs'
import { automaticChoice, eligibleForEconomy, includedInTechnicalComparison, selectionIssue, normalizeCompareStore } from '../app/utils/fleetSelection'
const cases = JSON.parse(readFileSync(new URL('../../platform/tests/fixtures/fleet-selection.json', import.meta.url), 'utf8'))
for (const c of cases) {
  const id = c.explicit ? c.chosen_id : c.chosen_id || automaticChoice(c.group)
  const hit = c.group.hits.find((h: { product_id: string }) => h.product_id === id)
  assert.equal(eligibleForEconomy(hit) ? hit.product_id : null, c.expected, c.name)
}
assert.match(selectionIssue({ hits: [] }, 'deleted'), /Сохранённое/)
const preliminary = { product_id: 'preliminary', verdict: 'pass', count: null, economic_ready: false }
assert.equal(includedInTechnicalComparison(preliminary), true)
assert.equal(eligibleForEconomy(preliminary), false)
for (const verdict of ['unknown', 'conditional', 'fail']) assert.equal(includedInTechnicalComparison({ ...preliminary, verdict }), false)
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
