<script setup lang="ts">
import { PhArrowRight, PhHandshake, PhCheckCircle } from '@phosphor-icons/vue'
import { scenarios, isFullPath } from '~/data/projects'
import { useLiveProject } from '~/composables/useLiveProject'
import { demoProducts as products } from '~/data/demo'

const route = useRoute()
const doc = useLiveProject(computed(() => route.params.id as string))
const project = computed(() => doc.shell.value)
useHead({ title: () => `Состав парка · ${project.value?.name ?? 'проект'}` })
const p = (id: string) => products.find((x) => x.id === id)!
const chosen = ref('s2')
const f = (n: number) => n.toLocaleString('ru-RU')
</script>

<template>
  <ProjectShell v-if="project" :project="project" current="economics" title="Состав парка" lead="Три способа закрыть объект — часть шага «Экономика». Числа в млн ₽, интервалом: нижняя, центральная и верхняя оценка.">
    <template #actions>
      <UiButton :to="`/projects/${project.id}/economics`" size="lg">К экономике<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
    </template>

    <UiCallout v-if="!isFullPath(project)" tone="info" title="Страница закрыта для этого типа объекта">Состав парка, экономика, what-if и визуализация собираются только для склада. Ниже показан демонстрационный склад.</UiCallout>

    <div class="scen" v-reveal>
      <article v-for="(s, i) in scenarios" :key="s.id" class="sc" :class="[i === 0 ? 'glass' : chosen === s.id ? 'glass-graphite glass-graphite-solid chosen' : 'glass', { base: i === 0 }]" @click="i > 0 && (chosen = s.id)">
        <div class="sc-in">
          <div class="sc-head">
            <span class="mono-sm n">{{ i }}</span>
            <div>
              <h2 class="h3">{{ s.title }}</h2>
              <div class="caption">{{ s.subtitle }}</div>
            </div>
            <PhCheckCircle v-if="chosen === s.id && i > 0" :size="22" weight="fill" class="chk" />
          </div>

          <div v-if="s.fleet.length" class="fleet">
            <div v-for="fl in s.fleet" :key="fl.productId" class="fl">
              <img :src="p(fl.productId).image" alt="">
              <span class="body-sm">{{ p(fl.productId).name }}</span>
              <span class="mono-md">× {{ fl.count }}</span>
            </div>
          </div>
          <p v-else class="body-sm muted note-base">{{ s.note }}</p>

          <dl class="nums">
            <div><dt class="caption">CAPEX, млн ₽</dt><dd class="mono-md">{{ s.capex[1] ? `${f(s.capex[0])}–${f(s.capex[2])}` : '0' }}</dd></div>
            <div><dt class="caption">OPEX в год</dt><dd class="mono-md">{{ f(s.opex[0]) }}–{{ f(s.opex[2]) }}</dd></div>
            <div><dt class="caption">Эффект в год</dt><dd class="mono-md">{{ s.effect[1] ? `${f(s.effect[0])}–${f(s.effect[2])}` : 'не применимо' }}</dd></div>
          </dl>

          <div class="pay">
            <span class="caption">Окупаемость</span>
            <template v-if="s.payback[1]">
              <UiInterval :low="s.payback[0]" :mid="s.payback[1]" :high="s.payback[2]" :min="0" :max="6" unit="лет" :graphite="chosen === s.id && i > 0" />
            </template>
            <span v-else class="body-sm muted">Базовый сценарий: с ним сравниваются остальные</span>
          </div>

          <div v-if="s.raas" class="raas"><PhHandshake :size="16" weight="duotone" /> <span class="body-sm">Есть ветка RaaS: вендор Weibot даёт услугу вместо покупки, CAPEX ниже на 38–44 млн ₽, OPEX выше на 19 млн ₽ в год.</span></div>
          <p v-if="s.note && s.fleet.length" class="caption sc-note">{{ s.note }}</p>
        </div>
      </article>
    </div>
  </ProjectShell>
</template>

<style scoped>
.scen { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4); align-items: stretch; }
.sc { border-radius: var(--radius-xl); cursor: default; transition: transform var(--dur-mid) var(--ease), box-shadow var(--dur-mid) var(--ease); }
.sc:not(.base) { cursor: pointer; }
.sc:not(.base):hover { transform: translateY(-3px); }
.sc-in { position: relative; z-index: 1; padding: var(--space-6); display: grid; gap: var(--space-5); align-content: start; height: 100%; }
.sc-head { display: grid; grid-template-columns: auto 1fr auto; gap: 12px; align-items: start; }
.n { width: 28px; height: 28px; border-radius: 8px; background: var(--surface-graphite); color: var(--brand-300); display: inline-flex; align-items: center; justify-content: center; }
.chosen .n { background: var(--brand-400); color: var(--brand-900); }
.chk { color: var(--brand-300); }
.fleet { display: grid; gap: 8px; }
.fl { display: grid; grid-template-columns: 36px 1fr auto; gap: 10px; align-items: center; }
.fl img { width: 36px; height: 36px; border-radius: 8px; object-fit: cover; }
.chosen .fl .mono-md { color: var(--brand-300); }
.nums { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; padding: 14px 0; border-top: 1px solid rgba(15, 20, 19, 0.08); border-bottom: 1px solid rgba(15, 20, 19, 0.08); }
.chosen .nums { border-color: rgba(255, 255, 255, 0.12); }
.nums dd { margin: 0; color: var(--ink-strong); }
.chosen .nums dd { color: var(--ink-on-graphite); }
.pay { display: grid; gap: 10px; }
.raas { display: flex; gap: 8px; align-items: flex-start; padding: 10px 12px; border-radius: 10px; background: rgba(43, 209, 141, 0.12); color: var(--brand-200); }
.raas svg { flex: none; color: var(--brand-300); margin-top: 2px; }
.sc:not(.chosen) .raas { background: var(--surface-brand-tint); color: var(--brand-ink); }
.sc:not(.chosen) .raas svg { color: var(--brand-700); }
.sc-note { margin-top: auto; }
.note-base { min-height: 96px; }
@media (max-width: 1100px) { .scen { grid-template-columns: 1fr; } }
</style>
