<script setup lang="ts">
import { PhArrowRight, PhCaretDown, PhEnvelopeSimple } from '@phosphor-icons/vue'
import { projectById, capexLines, opexLines, effectLines, norms, scenarios, type CostLine } from '~/data/projects'
import { demoSourceById as sourceById } from '~/data/demo'

const route = useRoute()
const project = computed(() => projectById(route.params.id as string))
useHead({ title: () => `Экономика · ${project.value.name}` })

const s = scenarios[2]!
const sum = (l: CostLine[]) => l.reduce((a, b) => a + b.value, 0)
const capex = computed(() => sum(capexLines))
const opex = computed(() => sum(opexLines))
const effect = computed(() => sum(effectLines))
const net = computed(() => effect.value - opex.value + 21.6) // + экономия базового OPEX (mock)
const f = (n: number, d = 1) => n.toLocaleString('ru-RU', { maximumFractionDigits: d, minimumFractionDigits: d })
const openCoef = ref<string | null>(null)
const coefs = norms.slice(0, 5)
const tco = [
  { year: 1, base: 194, robo: 108 + 56 },
  { year: 2, base: 388, robo: 108 + 112 },
  { year: 3, base: 582, robo: 108 + 168 },
  { year: 4, base: 776, robo: 108 + 224 },
  { year: 5, base: 970, robo: 108 + 280 },
]
const maxT = Math.max(...tco.map((t) => t.base))
</script>

<template>
  <ProjectShell :project="project" current="economics" title="Экономика и интервал окупаемости" lead="Состав парка переведён в деньги. Каждый коэффициент открывается: значение, единица, источник, обоснование. Недокументированных множителей нет.">
    <template #actions>
      <UiButton :to="`/projects/${project.id}/scenarios`" variant="secondary">Состав парка</UiButton>
      <UiButton :to="`/projects/${project.id}/what-if`" size="lg">К what-if<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
    </template>

    <UiCallout tone="warn" title="Числа демонстрационные">
      Страница экономики — заглушка: CAPEX, OPEX, эффект и окупаемость не считаются движком. Состав парка шага 5 открывается отдельно.
      <div class="call-actions">
        <UiButton :to="`/projects/${project.id}/scenarios`" size="sm" variant="secondary">Открыть состав парка</UiButton>
      </div>
    </UiCallout>

    <div class="top" v-reveal>
      <div class="result glass-graphite glass-graphite-solid">
        <div class="label">Оптимальный состав парка · окупаемость</div>
        <UiInterval :low="s.payback[0]" :mid="s.payback[1]" :high="s.payback[2]" :min="0" :max="6" unit="лет" graphite />
        <div class="kpis">
          <div><span class="caption">ROI за 5 лет</span><span class="mono-lg">184–262%</span></div>
          <div><span class="caption">TCO за 5 лет</span><span class="mono-lg">{{ f(capex + opex * 5, 0) }} млн ₽</span></div>
          <div><span class="caption">Чистый эффект в год</span><span class="mono-lg">{{ f(net, 1) }} млн ₽</span></div>
        </div>
      </div>
      <div class="uncertainty glass">
        <div class="u-in">
          <div class="label">Что раздувает неопределённость</div>
          <div class="h3">Производительность Ronavi H1500</div>
          <p class="body-sm muted">Значение 42 палет/ч взято по аналогу класса (достоверность C). Оно даёт <span class="strong">61% ширины интервала</span> окупаемости: от 2,4 до 4,2 года.</p>
          <div class="u-bar"><span style="width: 61%">производительность</span><span style="width: 22%">ФОТ</span><span style="width: 17%">прочее</span></div>
          <div class="u-act">
            <span class="body-sm">Сузит интервал: паспортная производительность на палете 1 200 × 800 при маршруте 85 м.</span>
            <UiButton variant="secondary" size="sm"><template #icon><PhEnvelopeSimple :size="14" weight="bold" /></template>Запрос вендору</UiButton>
          </div>
        </div>
      </div>
    </div>

    <div class="cols" v-reveal="1">
      <section class="col glass">
        <div class="c-in">
          <div class="c-head"><div><div class="h3">CAPEX</div><div class="caption">единовременно, млн ₽</div></div><span class="mono-lg">{{ f(capex, 1) }}</span></div>
          <ul class="lines">
            <li v-for="l in capexLines" :key="l.label">
              <span class="body-sm">{{ l.label }}<span v-if="l.note" class="caption block">{{ l.note }}</span></span>
              <span class="ln-v"><span class="mono-md">{{ f(l.value) }}</span><UiSourceTag :source-id="l.sourceId" align="right" /></span>
            </li>
          </ul>
        </div>
      </section>
      <section class="col glass">
        <div class="c-in">
          <div class="c-head"><div><div class="h3">OPEX за год</div><div class="caption">млн ₽ в год</div></div><span class="mono-lg">{{ f(opex, 1) }}</span></div>
          <ul class="lines">
            <li v-for="l in opexLines" :key="l.label">
              <span class="body-sm">{{ l.label }}<span v-if="l.note" class="caption block">{{ l.note }}</span></span>
              <span class="ln-v"><span class="mono-md">{{ f(l.value) }}</span><UiSourceTag :source-id="l.sourceId" align="right" /></span>
            </li>
          </ul>
        </div>
      </section>
      <section class="col glass">
        <div class="c-in">
          <div class="c-head"><div><div class="h3">Эффект за год</div><div class="caption">млн ₽ в год</div></div><span class="mono-lg">{{ f(effect, 1) }}</span></div>
          <ul class="lines">
            <li v-for="l in effectLines" :key="l.label">
              <span class="body-sm">{{ l.label }}<span v-if="l.note" class="caption block">{{ l.note }}</span></span>
              <span class="ln-v"><span class="mono-md" :class="{ dim: !l.value }">{{ l.value ? f(l.value) : '0–9,4' }}</span><UiSourceTag :source-id="l.sourceId" align="right" /></span>
            </li>
          </ul>
          <div class="tco">
            <div class="caption">TCO накопительно, млн ₽</div>
            <div class="tco-rows">
              <div v-for="t in tco" :key="t.year" class="tco-row">
                <span class="mono-sm y">{{ t.year }} г.</span>
                <span class="tco-bars">
                  <span class="tb base" :style="{ width: `${(t.base / maxT) * 100}%` }"><i>{{ t.base }}</i></span>
                  <span class="tb robo" :style="{ width: `${(t.robo / maxT) * 100}%` }"><i>{{ t.robo }}</i></span>
                </span>
              </div>
            </div>
            <div class="legend caption"><span><i class="sw base" /> без роботизации</span><span><i class="sw robo" /> оптимальный парк</span></div>
          </div>
        </div>
      </section>
    </div>

    <section class="coefs glass" v-reveal="2">
      <div class="c-in">
        <div class="c-head"><div><div class="h3">Коэффициенты расчёта</div><div class="caption">Каждый открывается: значение, единица, источник, обоснование</div></div></div>
        <div class="coef-list">
          <div v-for="c in coefs" :key="c.key" class="coef" :class="{ open: openCoef === c.key }">
            <button type="button" class="coef-btn" @click="openCoef = openCoef === c.key ? null : c.key">
              <span class="mono-sm key">{{ c.key }}</span>
              <span class="body-sm strong">{{ c.label }}</span>
              <span class="mono-md">{{ c.value }} <span class="muted">{{ c.unit }}</span></span>
              <UiSourceTag :source-id="c.sourceId" />
              <PhCaretDown :size="14" weight="bold" class="caret" />
            </button>
            <div v-if="openCoef === c.key" class="coef-body">
              <div><span class="caption">Обоснование</span><p class="body-sm">{{ c.rationale }}</p></div>
              <div><span class="caption">Источник</span><p class="body-sm">{{ sourceById(c.sourceId)?.publisher }}</p></div>
              <div><span class="caption">Меняется в what-if</span><p class="body-sm">{{ c.editable ? 'Да' : 'Нет, только в админке' }}</p></div>
            </div>
          </div>
        </div>
      </div>
    </section>
  </ProjectShell>
</template>

<style scoped>
.top { display: grid; grid-template-columns: minmax(0, 7fr) minmax(0, 5fr); gap: var(--space-4); }
.result { padding: var(--space-6); display: grid; gap: var(--space-6); }
.kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4); padding-top: var(--space-4); border-top: 1px solid rgba(255, 255, 255, 0.1); }
.kpis > div { display: grid; gap: 4px; }
.kpis .mono-lg { color: var(--brand-300); }
.uncertainty .u-in { position: relative; z-index: 1; padding: var(--space-6); display: grid; gap: 12px; }
.u-bar { display: flex; gap: 3px; height: 30px; border-radius: 8px; overflow: hidden; }
.u-bar span { display: inline-flex; align-items: center; padding: 0 10px; font-family: var(--font-mono); font-size: 11px; color: #fff; white-space: nowrap; overflow: hidden; }
.u-bar span:nth-child(1) { background: var(--state-warn); }
.u-bar span:nth-child(2) { background: var(--brand-600); }
.u-bar span:nth-child(3) { background: var(--border-strong); }
.u-act { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding-top: 8px; border-top: 1px solid rgba(15, 20, 19, 0.08); }
.cols { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4); align-items: start; }
.c-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: var(--space-4); }
.c-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.c-head .mono-lg { color: var(--ink-strong); }
.lines { display: grid; }
.lines li { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; padding: 10px 0; border-top: 1px solid rgba(15, 20, 19, 0.06); }
.lines li:first-child { border-top: 0; }
.ln-v { display: inline-flex; align-items: center; gap: 8px; flex: none; }
.ln-v .mono-md { color: var(--ink-strong); }
.dim { color: var(--ink-muted); }
.block { display: block; }
.tco { display: grid; gap: 8px; padding-top: 10px; border-top: 1px solid rgba(15, 20, 19, 0.06); }
.tco-rows { display: grid; gap: 6px; }
.tco-row { display: grid; grid-template-columns: 34px 1fr; gap: 8px; align-items: center; }
.tco-bars { display: grid; gap: 2px; }
.tb { display: flex; align-items: center; justify-content: flex-end; height: 10px; border-radius: 3px; min-width: 24px; }
.tb i { font-style: normal; font-family: var(--font-mono); font-size: 9px; color: #fff; padding-right: 4px; line-height: 1; }
.tb.base { background: var(--border-strong); }
.tb.robo { background: var(--brand-600); }
.legend { display: flex; gap: 14px; }
.sw { display: inline-block; width: 10px; height: 10px; border-radius: 3px; vertical-align: -1px; margin-right: 4px; }
.sw.base { background: var(--border-strong); }
.sw.robo { background: var(--brand-600); }
.y { color: var(--ink-muted); }
.coef-list { display: grid; gap: 6px; }
.coef { border-radius: 12px; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.coef-btn { width: 100%; display: grid; grid-template-columns: 120px 1fr auto auto auto; gap: 14px; align-items: center; padding: 10px 14px; text-align: left; }
.key { color: var(--ink-muted); }
.caret { color: var(--ink-faint); transition: transform var(--dur-fast) var(--ease); }
.open .caret { transform: rotate(180deg); }
.coef-body { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 16px; padding: 4px 14px 14px 148px; }
.coef-body .caption { display: block; margin-bottom: 2px; }
.call-actions { margin-top: 10px; }
@media (max-width: 1100px) { .top, .cols { grid-template-columns: 1fr; } .coef-btn { grid-template-columns: 1fr auto; } .coef-body { padding-left: 14px; grid-template-columns: 1fr; } }
</style>
