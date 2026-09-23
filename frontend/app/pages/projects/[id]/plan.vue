<script setup lang="ts">
import { PhPlay, PhPause, PhArrowCounterClockwise, PhArrowRight, PhDownloadSimple, PhWarning } from '@phosphor-icons/vue'
import { projectById, scenarios } from '~/data/projects'

const route = useRoute()
const project = computed(() => projectById(route.params.id as string))
useHead({ title: () => `Визуализация · ${project.value.name}` })

const playing = ref(true)
const speed = ref(1)
const scenario = ref('s2')
const canvas = ref<{ reset: () => void } | null>(null)
const robotsFor: Record<string, number> = { s1: 7, s2: 9 }
const robots = computed(() => robotsFor[scenario.value] ?? 7)
const tick = reactive({ t: 0, util: 0.82, queue: 1 })
const onTick = (p: { t: number; util: number; queue: number }) => { tick.t = p.t; tick.util = p.util; tick.queue = p.queue }
const shiftClock = computed(() => {
  const minutes = Math.floor((tick.t / 60) * 480) % 480
  const h = 8 + Math.floor(minutes / 60)
  const m = minutes % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
})
const reset = () => { canvas.value?.reset(); tick.t = 0 }
const util = computed(() => Math.round(tick.util * 100))
</script>

<template>
  <ProjectShell :project="project" current="plan" title="Визуализация" lead="Реплей того же прогона, который дал цифру количества. Если в прогоне 9 машин, на плане 9 машин. Это схема объекта, не игра.">
    <template #actions>
      <UiButton variant="secondary"><template #icon><PhDownloadSimple :size="16" weight="bold" /></template>Выгрузить план</UiButton>
      <UiButton :to="`/projects/${project.id}/report`" size="lg">К отчёту<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
    </template>

    <div class="plan-grid">
      <div class="canvas glass glass-xl" v-reveal>
        <div class="canvas-in">
          <PlanCanvas ref="canvas" :robots="robots" :speed="speed" :playing="playing" :scenario="scenarios.find(s => s.id === scenario)?.title" @tick="onTick" />
        </div>
        <div class="controls glass glass-strong">
          <div class="ctl-group">
            <button type="button" class="ctl primary" :aria-label="playing ? 'Стоп' : 'Пуск'" @click="playing = !playing"><PhPause v-if="playing" :size="18" weight="fill" /><PhPlay v-else :size="18" weight="fill" /></button>
            <button type="button" class="ctl" aria-label="Перезапуск" @click="reset"><PhArrowCounterClockwise :size="18" weight="bold" /></button>
          </div>
          <div class="ctl-group speed">
            <span class="caption">Скорость</span>
            <button v-for="s in [0.5, 1, 2, 4]" :key="s" type="button" class="spd" :class="{ on: speed === s }" @click="speed = s">×{{ s }}</button>
          </div>
          <div class="ctl-group">
            <span class="caption">Сценарий</span>
            <select v-model="scenario" class="select sc-sel">
              <option value="s1">Подбор по задачам · 7 AMR</option>
              <option value="s2">Оптимальный состав · 9 AMR</option>
            </select>
          </div>
          <div class="clock"><span class="caption">Смена</span><span class="mono-lg">{{ shiftClock }}</span></div>
        </div>
      </div>

      <aside class="side" v-reveal="1">
        <div class="kpi glass-graphite glass-graphite-solid">
          <div class="label">Загрузка парка</div>
          <div class="ring" :style="{ '--p': util }">
            <svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="52" class="track" /><circle cx="60" cy="60" r="52" class="fill" :style="{ strokeDasharray: `${(util / 100) * 326.7} 326.7` }" /></svg>
            <div class="ring-num"><span class="display-3">{{ util }}%</span><span class="caption">средняя за смену</span></div>
          </div>
          <div class="kpi-rows">
            <div><span class="caption">Машин на плане</span><span class="mono-md">{{ robots }}</span></div>
            <div><span class="caption">Очередь на зарядке</span><span class="mono-md">{{ tick.queue }}</span></div>
            <div><span class="caption">Рейсов за смену</span><span class="mono-md">{{ robots === 9 ? '384' : '312' }} <span class="muted">/ 384 план</span></span></div>
          </div>
        </div>
        <UiCallout v-if="util > 95" tone="warn" title="Загрузка выше 95%">Стоит пересчитать состав с запасом: парк работает без резерва на пиковые часы и зарядку.</UiCallout>
        <div class="legend glass">
          <div class="l-in">
            <div class="h4">Обозначения</div>
            <div class="lg"><i class="sw robot" /> Робот в работе, номер по прогону</div>
            <div class="lg"><i class="sw chg" /> Робот на зарядке</div>
            <div class="lg"><i class="sw route" /> Маршрут по оси проезда</div>
            <div class="lg"><i class="sw st" /> Станция комплектации</div>
            <div class="lg"><i class="sw zone" /> Зона приёмки и отгрузки</div>
          </div>
        </div>
        <div class="caption note"><PhWarning :size="12" weight="fill" /> 3D нет. Библиотеки сцены нет. Симуляция подтверждает расчётное количество машин, не украшает отчёт.</div>
      </aside>
    </div>
  </ProjectShell>
</template>

<style scoped>
.plan-grid { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: var(--space-4); align-items: start; }
.canvas { padding: 12px; display: grid; gap: 12px; }
.canvas-in { position: relative; z-index: 1; border-radius: 18px; overflow: hidden; background: rgba(255, 255, 255, 0.55); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.controls { position: relative; z-index: 1; display: grid; grid-template-columns: auto auto auto 1fr; gap: var(--space-6); align-items: center; padding: 10px 14px; border-radius: 16px; }
.controls > * { position: relative; z-index: 1; }
.ctl-group { display: flex; align-items: center; gap: 8px; }
.ctl { width: 44px; height: 44px; border-radius: 12px; display: inline-flex; align-items: center; justify-content: center; background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); color: var(--ink-strong); transition: all var(--dur-fast) var(--ease); }
.ctl:hover { background: #fff; }
.ctl.primary { background: var(--action-fill); color: #fff; box-shadow: none; }
.ctl.primary:hover { background: var(--action-fill-hover); }
.spd { height: 36px; padding: 0 12px; border-radius: 10px; font-family: var(--font-mono); font-size: 13px; font-weight: 700; color: var(--ink-body); background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px var(--border-hairline); transition: all var(--dur-fast) var(--ease); }
.spd.on { background: var(--surface-graphite); color: var(--brand-300); box-shadow: none; }
.sc-sel { width: 260px; min-height: 40px; }
.clock { display: grid; text-align: right; justify-self: end; }
.clock .mono-lg { color: var(--ink-strong); }
.side { display: grid; gap: var(--space-4); position: sticky; top: 96px; }
.kpi { padding: var(--space-6); display: grid; gap: var(--space-4); }
.ring { position: relative; width: 160px; height: 160px; margin: 0 auto; }
.ring svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.track { fill: none; stroke: rgba(255, 255, 255, 0.1); stroke-width: 10; }
.fill { fill: none; stroke: var(--brand-400); stroke-width: 10; stroke-linecap: round; transition: stroke-dasharray var(--dur-slow) var(--ease); }
.ring-num { position: absolute; inset: 0; display: grid; place-content: center; text-align: center; gap: 2px; }
.ring-num .display-3 { color: var(--ink-on-graphite); }
.kpi-rows { display: grid; gap: 8px; padding-top: 12px; border-top: 1px solid rgba(255, 255, 255, 0.1); }
.kpi-rows > div { display: flex; justify-content: space-between; align-items: baseline; }
.kpi-rows .mono-md { color: var(--brand-300); }
.l-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: 10px; }
.lg { display: flex; align-items: center; gap: 10px; font-size: 13px; color: var(--ink-body); }
.sw { display: inline-block; width: 18px; height: 12px; border-radius: 3px; flex: none; }
.sw.robot { background: var(--surface-graphite); box-shadow: inset 0 2px 0 var(--brand-400); }
.sw.chg { background: var(--surface-graphite); box-shadow: inset 0 2px 0 var(--state-warn); }
.sw.route { background: repeating-linear-gradient(90deg, var(--brand-500) 0 4px, transparent 4px 8px); height: 2px; }
.sw.st { width: 12px; height: 12px; border-radius: 50%; background: #fff; border: 2px solid var(--brand-600); }
.sw.zone { background: rgba(23, 95, 176, 0.1); border: 1px solid rgba(23, 95, 176, 0.3); }
.note { display: flex; gap: 6px; align-items: flex-start; padding: 0 4px; }
@media (max-width: 1100px) { .plan-grid { grid-template-columns: 1fr; } .side { position: static; } .controls { grid-template-columns: 1fr 1fr; } }
</style>
