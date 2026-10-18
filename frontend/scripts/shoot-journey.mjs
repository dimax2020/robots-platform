// Переснять скриншоты карты «Путь подбора» на главной (frontend/public/img/journey).
// Нужны запущенный сайт с демо-складом и Google Chrome. Запуск из frontend/:
//   node scripts/shoot-journey.mjs /tmp/journey http://localhost:3000
// Потом сжать до 1440 px: sips -Z 1440 -s format jpeg -s formatOptions 78 /tmp/journey/*.jpg --out public/img/journey/
import { spawn } from 'node:child_process'
import { writeFileSync, mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
const [outdir, base] = process.argv.slice(2)
const port = 9300 + Math.floor(Math.random() * 500)
const chrome = spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', ['--headless=new', `--remote-debugging-port=${port}`, `--user-data-dir=${mkdtempSync(join(tmpdir(), 'chr-'))}`, '--hide-scrollbars', 'about:blank'], { stdio: 'ignore' })
setTimeout(() => { chrome.kill(); process.exit(2) }, 240000)
const sleep = (ms) => new Promise(r => setTimeout(r, ms))
let t; for (let i = 0; i < 50; i++) { try { t = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find(x => x.type === 'page'); if (t) break } catch {} await sleep(200) }
const ws = new WebSocket(t.webSocketDebuggerUrl); await new Promise(r => ws.onopen = r)
let id = 0; const pend = new Map(); ws.onmessage = (m) => { const d = JSON.parse(m.data); if (d.id && pend.has(d.id)) { pend.get(d.id)(d.result ?? d); pend.delete(d.id) } }
const send = (method, params = {}) => new Promise(r => { const i = ++id; pend.set(i, r); ws.send(JSON.stringify({ id: i, method, params })) })
const ev = async (expression) => (await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true })).result?.value
await send('Page.enable'); await send('Runtime.enable')
await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 2, mobile: false })
await send('Page.navigate', { url: base + '/' }); await sleep(2500)
await ev(`localStorage.setItem('demo-banner-hidden:demo-warehouse','1')`)
const P = base + '/projects/demo-warehouse'
const clickText = (sel, text) => `(() => { const b = [...document.querySelectorAll(${JSON.stringify(sel)})].find(x => x.textContent.includes(${JSON.stringify(text)})); b?.click(); return Boolean(b) })()`
const jobs = [
  ['01-processes', P + '/params', '.setup', 0],
  ['02-object', P + '/params?part=object', '.groups', 0],
  ['03-match', P + '/match', '.tally', 0],
  ['04-compare', P + '/compare', '.table-wrap', 0],
  ['05-economics', P + '/economics', '.detail', -10, clickText('.grid button', 'Буксировка тележек')],
  ['06-whatif', P + '/what-if', '.wi', 0, clickText('.ps', 'Буксировка тележек')],
  ['07-plan', P + '/plan', '.canvas-in', -10, `(async () => { document.querySelector('.sleep')?.remove(); document.querySelector('[aria-label="Пуск"]')?.click(); await new Promise(r => setTimeout(r, 9000)); document.querySelector('[aria-label="Стоп"]')?.click(); document.querySelector('.sleep')?.remove(); return 1 })()`],
  ['08-report', P + '/report', 'main section, .report, .container', 0],
]
for (const [name, url, sel, dy, before] of jobs) {
  await send('Page.navigate', { url }); await sleep(7000)
  if (before) { console.log(name, 'before', await ev(before)); await sleep(2500) }
  await ev('document.querySelectorAll("[id^=nuxt-devtools], nuxt-devtools-frame, #nuxt-devtools-anchor").forEach(e => e.remove())')
  await ev('document.querySelectorAll("*").forEach(e=>{const s=getComputedStyle(e); if(s.opacity==="0") e.style.opacity="1"; if(s.transform!=="none" && e.classList.contains("is-in")===false && e.hasAttribute("data-reveal")) e.style.transform="none"})')
  const rect = await ev(`(() => { const e = document.querySelector(${JSON.stringify(sel)}); if (!e) return null; const r = e.getBoundingClientRect(); return { x: r.left + scrollX, y: r.top + scrollY, w: r.width } })()`)
  if (!rect) { console.log(name, 'нет блока', sel); continue }
  const x = 40, w = 1360, h = Math.round(w * 0.625)
  const y = Math.max(0, rect.y + dy)
  const s = await send('Page.captureScreenshot', { format: 'jpeg', quality: 88, captureBeyondViewport: true, clip: { x, y, width: w, height: h, scale: 1 } })
  writeFileSync(`${outdir}/${name}.jpg`, Buffer.from(s.data, 'base64'))
  console.log(name, Math.round(rect.y))
}
ws.close(); chrome.kill(); process.exit(0)
