<script setup lang="ts">
import { PhArrowRight, PhArrowCounterClockwise } from '@phosphor-icons/vue'
import { projectById } from '~/data/projects'

const route = useRoute()
const project = computed(() => projectById(route.params.id as string))
useHead({ title: () => `What-if · ${project.value.name}` })

interface Knob { key: string; label: string; unit: string; base: number; min: number; max: number; step: number; value: number; elasticity: number }
const knobs = reactive<Knob[]>([
  { key: 'fot', label: 'Стоимость персонала', unit: 'млн ₽ в год на ставку', base: 3.9, min: 2.5, max: 6, step: 0.1, value: 3.9, elasticity: -0.9 },
  { key: 'mode', label: 'Режим работы', unit: 'смен в сутки', base: 2, min: 1, max: 3, step: 1, value: 2, elasticity: -0.6 },
  { key: 'perf', label: 'Производительность', unit: '% от паспортной', base: 100, min: 60, max: 120, step: 5, value: 100, elasticity: -0.7 },
  { key: 'capex', label: 'Стоимость оборудования', unit: '% от каталога', base: 100, min: 70, max: 140, step: 5, value: 100, elasticity: 0.8 },
  { key: 'service', label: 'Стоимость обслуживания', unit: '% от CAPEX в год', base: 8, min: 4, max: 14, step: 0.5, value: 8, elasticity: 0.25 },
  { key: 'load', label: 'Коэффициент загрузки', unit: 'коэф.', base: 0.85, min: 0.6, max: 0.95, step: 0.05, value: 0.85, elasticity: -0.5 },
  { key: 'horizon', label: 'Горизонт расчёта', unit: 'лет', base: 5, min: 3, max: 10, step: 1, value: 5, elasticity: 0 },
])

const base = { low: 2.4, mid: 3.0, high: 4.2 }
const factor = computed(() => knobs.reduce((acc, k) => acc * Math.pow(k.value / k.base, k.elasticity), 1))
const payback = computed(() => ({ low: base.low * factor.value, mid: base.mid * factor.value, high: base.high * factor.value }))
const delta = computed(() => payback.value.mid - base.mid)
const band = computed(() => payback.value.mid <= 3 ? 'до 3 лет' : payback.value.mid <= 5 ? '3–5 лет' : 'более 5 лет')
const interpretation = computed(() => {
  const m = payback.value.mid
  if (m <= 3) return 'Проект окупается в границах типичного инвестиционного цикла склада. Главный риск: производительность взята по аналогу и не подтверждена паспортом.'
  if (m <= 5) return 'Окупаемость в зоне, где решение зависит от стоимости денег и планов по объёму. Стоит запросить у вендора паспортную производительность и рассмотреть RaaS.'
  return 'При этих допущениях роботизация не даёт быстрого эффекта. Проверьте, не завышен ли CAPEX и не занижен ли ФОТ: обычно ошибка именно там.'
})
const sens = computed(() => knobs.filter((k) => k.elasticity !== 0).map((k) => ({ ...k, effect: Math.abs(k.elasticity) * 0.2 * base.mid })).sort((a, b) => b.effect - a.effect).slice(0, 4))
const reset = () => knobs.forEach((k) => { k.value = k.base })
const f = (n: number, d = 1) => n.toLocaleString('ru-RU', { maximumFractionDigits: d, minimumFractionDigits: d })
const pct = (k: Knob) => `${((k.value - k.min) / (k.max - k.min)) * 100}%`
const changed = computed(() => knobs.filter((k) => k.value !== k.base).length)
</script>

<template>
  <ProjectShell :project="project" current="what-if" title="What-if и чувствительность" lead="Меняйте допущения и смотрите, как едет интервал. Интерпретация без жёсткого порога: рядом число, риски и смысл, не красный или зелёный штамп.">
    <template #actions>
      <UiButton variant="secondary" :disabled="!changed" @click="reset"><template #icon><PhArrowCounterClockwise :size="16" weight="bold" /></template>Сбросить</UiButton>
      <UiButton :to="`/projects/${project.id}/plan`" size="lg">К плану<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
    </template>

    <div class="wi">
      <section class="knobs glass" v-reveal>
        <div class="k-in">
          <div class="between"><div class="h3">Допущения</div><span class="caption">{{ changed ? `изменено ${changed}` : 'базовые значения' }}</span></div>
          <div v-for="k in knobs" :key="k.key" class="knob" :class="{ changed: k.value !== k.base }">
            <div class="knob-head">
              <span class="body-sm strong">{{ k.label }}</span>
              <span class="mono-md">{{ f(k.value, k.step < 1 ? 2 : 0) }} <span class="muted unit">{{ k.unit }}</span></span>
            </div>
            <input v-model.number="k.value" type="range" :min="k.min" :max="k.max" :step="k.step" class="range" :style="{ '--pct': pct(k) }" :aria-label="k.label">
            <div class="knob-foot caption"><span>{{ f(k.min, k.step < 1 ? 2 : 0) }}</span><span v-if="k.value !== k.base">база {{ f(k.base, k.step < 1 ? 2 : 0) }}</span><span>{{ f(k.max, k.step < 1 ? 2 : 0) }}</span></div>
          </div>
        </div>
      </section>

      <div class="out">
        <section class="res glass-graphite glass-graphite-solid" v-reveal="1">
          <div class="between"><span class="label">Окупаемость при этих допущениях</span><span class="mono-sm delta" :class="{ up: delta > 0.05, down: delta < -0.05 }">{{ delta > 0 ? '+' : '' }}{{ f(delta, 1) }} года к центральной</span></div>
          <UiInterval :low="payback.low" :mid="payback.mid" :high="payback.high" :min="0" :max="8" unit="лет" graphite :bands="[{ to: 3, label: 'до 3 лет' }, { to: 5, label: '3–5 лет' }, { to: 8, label: 'более 5 лет' }]" />
          <div class="interp">
            <div class="h4">Интервал рекомендации: {{ band }}</div>
            <p class="body-sm">{{ interpretation }}</p>
          </div>
        </section>

        <section class="sens glass" v-reveal="2">
          <div class="k-in">
            <div><div class="h3">Чувствительность</div><div class="caption">Сдвиг центральной оценки при изменении параметра на ±20%</div></div>
            <div class="sens-list">
              <div v-for="s in sens" :key="s.key" class="sens-row">
                <span class="body-sm">{{ s.label }}</span>
                <span class="sens-bar"><span :style="{ width: `${(s.effect / sens[0]!.effect) * 100}%` }" /></span>
                <span class="mono-md">±{{ f(s.effect, 2) }} <span class="muted unit">года</span></span>
              </div>
            </div>
            <div class="caption">Три параметра с наибольшим влиянием: производительность, стоимость персонала и стоимость оборудования. Именно их стоит подтверждать документами первыми.</div>
          </div>
        </section>
      </div>
    </div>
  </ProjectShell>
</template>

<style scoped>
.wi { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); gap: var(--space-4); align-items: start; }
.k-in { position: relative; z-index: 1; padding: var(--space-6); display: grid; gap: var(--space-5); }
.knob { display: grid; gap: 8px; padding: 12px 14px; border-radius: 12px; transition: background var(--dur-fast) var(--ease); }
.knob.changed { background: var(--surface-brand-tint); }
.knob-head { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.knob-head .mono-md { color: var(--ink-strong); }
.unit { font-family: var(--font-sans); font-weight: 500; font-size: 12px; }
.knob-foot { display: flex; justify-content: space-between; }
.out { display: grid; gap: var(--space-4); position: sticky; top: 96px; }
.res { padding: var(--space-6); display: grid; gap: var(--space-8); }
.delta { color: var(--ink-muted-graphite); }
.delta.up { color: #f0ad45; }
.delta.down { color: var(--brand-300); }
.interp { display: grid; gap: 6px; padding-top: var(--space-4); border-top: 1px solid rgba(255, 255, 255, 0.1); }
.interp .h4 { color: var(--brand-300); }
.sens-list { display: grid; gap: 10px; }
.sens-row { display: grid; grid-template-columns: 200px 1fr auto; gap: 14px; align-items: center; }
.sens-bar { height: 8px; border-radius: 4px; background: rgba(15, 20, 19, 0.06); overflow: hidden; }
.sens-bar span { display: block; height: 100%; border-radius: 4px; background: linear-gradient(90deg, var(--brand-400), var(--brand-600)); transition: width var(--dur-mid) var(--ease); }
.sens-row .mono-md { color: var(--ink-strong); }
@media (max-width: 1100px) { .wi { grid-template-columns: 1fr; } .out { position: static; } }
</style>
