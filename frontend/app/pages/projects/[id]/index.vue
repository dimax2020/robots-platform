<script setup lang="ts">
import { PhArrowRight, PhArrowLeft, PhLock, PhCheck, PhClockCounterClockwise, PhCopy } from '@phosphor-icons/vue'
import { projectById, objectTypeLabel, objectTypeImage, steps, isFullPath, scenarios } from '~/data/projects'
import { products } from '~/data/catalog'

const route = useRoute()
const project = computed(() => projectById(route.params.id as string))
useHead({ title: () => `${project.value.name} · Кабинет проекта` })
const full = computed(() => isFullPath(project.value))
const available = computed(() => (full.value ? steps.length : 2))
const nextStep = computed(() => steps[Math.min(project.value.step, steps.length) - 1]!)
const best = scenarios[2]!
const fleet = best.fleet.map((f) => ({ ...f, p: products.find((x) => x.id === f.productId)! }))
const fmt = (d: string) => new Date(d).toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })
const stepDesc: Record<string, string> = {
  params: 'Профиль площадки и список задач',
  match: 'Подходит, требует проверки, исключён',
  scenarios: 'Без роботизации, по задачам, оптимальный парк',
  economics: 'CAPEX, OPEX, эффект, интервал окупаемости',
  'what-if': 'Чувствительность к допущениям',
  plan: '2D-план и реплей смены',
  report: 'Печать, Excel, выгрузка плана',
}
</script>

<template>
  <section class="container cab">
    <NuxtLink to="/projects" class="back body-sm"><PhArrowLeft :size="14" weight="bold" /> Проекты</NuxtLink>

    <div class="hero glass glass-xl" v-reveal>
      <img :src="objectTypeImage[project.objectType]" alt="" class="hero-img">
      <div class="hero-body">
        <div class="row tags">
          <UiBadge tone="neutral">{{ objectTypeLabel[project.objectType] }}</UiBadge>
          <UiBadge :tone="full ? 'ok' : 'info'">{{ full ? 'Полный путь' : 'Урезанный путь: параметры и подбор' }}</UiBadge>
          <UiBadge v-if="project.isDemo" tone="warn">Демо, без сохранения</UiBadge>
        </div>
        <h1 class="hero-2">{{ project.name }}</h1>
        <div class="facts">
          <div><span class="caption">Площадь</span><span class="mono-md">{{ project.area?.toLocaleString('ru-RU') }} м²</span></div>
          <div><span class="caption">Смены</span><span class="mono-md">{{ project.shifts }}</span></div>
          <div><span class="caption">Задач</span><span class="mono-md">{{ project.tasks }}</span></div>
          <div><span class="caption">Обновлён</span><span class="mono-md">{{ fmt(project.updatedAt) }}</span></div>
        </div>
        <div class="versions">
          <PhClockCounterClockwise :size="16" />
          <span class="body-sm">Последний прогон на каталоге <span class="mono-md strong">{{ project.catalogVersion }}</span> и модели <span class="mono-md strong">{{ project.modelVersion }}</span>. Расчёт откроется с теми же исходными данными.</span>
        </div>
      </div>
      <div class="hero-cta">
        <UiButton :to="`/projects/${project.id}/${nextStep.path}`" size="lg">Продолжить: {{ nextStep.label }}<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
        <UiButton variant="secondary"><template #icon><PhCopy :size="16" /></template>Копировать проект</UiButton>
      </div>
    </div>

    <div class="grid-12 main">
      <div class="span-7 steps-col" v-reveal="1">
        <div class="h3">Шаги расчёта</div>
        <ol class="steps">
          <li v-for="(s, i) in steps" :key="s.code" class="st glass" :class="{ done: i + 1 < project.step && i < available, cur: i + 1 === project.step && i < available, locked: i >= available }">
            <span class="st-n"><PhCheck v-if="i + 1 < project.step && i < available" :size="14" weight="bold" /><PhLock v-else-if="i >= available" :size="13" weight="bold" /><span v-else class="mono-sm">{{ i + 1 }}</span></span>
            <div class="st-body">
              <div class="h4">{{ s.label }}</div>
              <div class="caption">{{ i >= available ? 'Для этого типа объекта шаг в MVP не собирается' : stepDesc[s.code] }}</div>
            </div>
            <NuxtLink v-if="i < available" :to="`/projects/${project.id}/${s.path}`" class="st-go"><PhArrowRight :size="16" weight="bold" /></NuxtLink>
          </li>
        </ol>
        <UiCallout v-if="!full" tone="info" title="Урезанный путь">Экраны экономики, what-if, плана и глубокого отчёта для аэропорта и медучреждения в MVP не собираются. Доступны параметры и список применимых решений.</UiCallout>
      </div>

      <aside class="span-5 side" v-reveal="2">
        <div v-if="full" class="result glass-graphite glass-graphite-solid">
          <div class="label">Последний результат</div>
          <div class="h3">{{ best.title }}</div>
          <div class="caption">{{ best.subtitle }}</div>
          <div class="pay">
            <span class="caption">Окупаемость</span>
            <span class="display-3">{{ best.payback[0].toLocaleString('ru-RU') }}–{{ best.payback[2].toLocaleString('ru-RU') }} <span class="unit">лет</span></span>
            <span class="caption">центральная оценка {{ best.payback[1].toLocaleString('ru-RU') }} года</span>
          </div>
          <ul class="fleet">
            <li v-for="f in fleet" :key="f.productId"><img :src="f.p.image" alt=""><span class="body-sm">{{ f.p.name }}</span><span class="mono-md">× {{ f.count }}</span></li>
          </ul>
          <UiButton :to="`/projects/${project.id}/economics`" variant="onGraphite" block>Открыть экономику</UiButton>
        </div>
        <div v-else class="result glass">
          <div class="r-in">
            <div class="label">Подбор</div>
            <div class="h3">Список применимых решений</div>
            <p class="body-sm muted">Для {{ objectTypeLabel[project.objectType].toLowerCase() }} платформа показывает, какие решения проходят жёсткие проверки. Экономика в MVP закрыта.</p>
            <UiButton :to="`/projects/${project.id}/match`" block>Открыть подбор</UiButton>
          </div>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.cab { padding-top: var(--space-8); padding-bottom: var(--space-16); display: grid; gap: var(--space-8); }
.back { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-muted); font-weight: 600; }
.hero { display: grid; grid-template-columns: 260px 1fr auto; gap: var(--space-8); align-items: center; padding: 12px; }
.hero > * { position: relative; z-index: 1; }
.hero-img { width: 260px; height: 220px; object-fit: cover; border-radius: 22px; }
.hero-body { display: grid; gap: 14px; padding: 8px 0; }
.facts { display: flex; gap: var(--space-8); }
.facts > div { display: grid; gap: 2px; }
.facts .mono-md { color: var(--ink-strong); }
.versions { display: flex; gap: 8px; align-items: flex-start; color: var(--ink-muted); max-width: 64ch; }
.hero-cta { display: grid; gap: 8px; padding-right: 12px; align-self: start; padding-top: 8px; }
.main { align-items: start; }
.steps-col { display: grid; gap: var(--space-4); }
.steps { display: grid; gap: 8px; }
.st { display: grid; grid-template-columns: auto 1fr auto; gap: 14px; align-items: center; padding: 12px 14px; border-radius: 16px; }
.st > * { position: relative; z-index: 1; }
.st-n { width: 32px; height: 32px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; background: rgba(15, 20, 19, 0.06); color: var(--ink-muted); }
.done .st-n { background: var(--surface-brand-tint); color: var(--brand-700); }
.cur .st-n { background: var(--surface-graphite); color: var(--brand-300); }
.cur { box-shadow: inset 0 1px 0 var(--glass-stroke), 0 0 0 2px var(--brand-500), var(--glass-shadow); }
.locked { opacity: 0.6; }
.st-go { width: 36px; height: 36px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; color: var(--ink-strong); background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); transition: all var(--dur-fast) var(--ease); }
.st-go:hover { background: var(--surface-graphite); color: #fff; }
.side { position: sticky; top: 96px; }
.result { padding: var(--space-6); display: grid; gap: 12px; }
.r-in { position: relative; z-index: 1; display: grid; gap: 12px; }
.pay { display: grid; gap: 4px; padding: 14px 0; border-top: 1px solid rgba(255, 255, 255, 0.1); border-bottom: 1px solid rgba(255, 255, 255, 0.1); }
.pay .display-3 { color: var(--brand-300); }
.unit { font-family: var(--font-sans); font-size: 16px; font-weight: 600; color: var(--ink-muted-graphite); }
.fleet { display: grid; gap: 8px; }
.fleet li { display: grid; grid-template-columns: 36px 1fr auto; gap: 10px; align-items: center; }
.fleet img { width: 36px; height: 36px; border-radius: 8px; object-fit: cover; }
.fleet .mono-md { color: var(--brand-300); }
@media (max-width: 1100px) { .hero { grid-template-columns: 1fr; } .hero-img { width: 100%; height: 200px; } .span-7, .span-5 { grid-column: span 12; } .side { position: static; } }
</style>
