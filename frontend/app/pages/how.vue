<script setup lang="ts">
import { PhArrowRight } from '@phosphor-icons/vue'
import { platformGet } from '~/composables/usePlatform'
import { demoPath, useDemoProjects } from '~/composables/useDemoProjects'

useHead({ title: 'Как это работает · Платформа роботизации' })

interface PlatformTree {
  objects: { code: string; name: string; in_match?: boolean; processes: string[] }[]
  processes: { code: string; name: string; product_count: number }[]
}
const tree = ref<PlatformTree | null>(null)
onMounted(() => {
  platformGet<PlatformTree>('/catalog/tree').then((data) => { tree.value = data }).catch(() => { tree.value = null })
})
const { role } = useRole()
const demoStore = useDemoProjects()
</script>

<template>
  <div>
    <section class="container intro" v-reveal>
      <div class="label">Как это работает</div>
      <h1 class="hero-1">Как платформа подбирает роботов</h1>
      <p class="body-lg muted lead">Сначала — как устроены данные: объект, процессы, фильтры и роботы. Затем — путь пользователя от выбора процессов до готового отчёта, на настоящих экранах демо-склада.</p>
    </section>

    <!-- Как устроена платформа: графит -->
    <section class="container">
      <div class="graphite graphite-section graphite-grid scanline how">
        <div class="orbits" aria-hidden="true">
          <span class="orbit o1"><span class="dot" /></span>
          <span class="orbit o2" />
          <span class="orbit o3" />
        </div>
        <div class="how-head">
          <div class="label">Как устроена платформа</div>
          <h2 class="hero-2">Объект, процессы, фильтры, роботы</h2>
          <p class="body-lg how-lead">Каталог роботов разложен по процессам. У каждого процесса свои фильтры: они сравнивают характеристики робота с параметрами вашего объекта. А у каждого объекта свой набор процессов. Нажмите на объект или процесс, чтобы посмотреть.</p>
        </div>
        <HomeModel :tree="tree" />
      </div>
    </section>

    <!-- Путь подбора: карта шагов со скриншотами -->
    <section class="container section">
      <SectionHead label="Путь подбора" title="От процессов до отчёта за восемь шагов" lead="Так выглядит работа с платформой: каждый шаг на настоящем экране демо-склада." size="hero-2" />
      <HomeJourney />
      <div class="journey-cta">
        <UiButton :to="demoStore.first.value ? demoPath(demoStore.first.value) : '/projects/new'" size="lg">Пройти путь на демо-объекте<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
        <UiButton to="/projects/new" variant="secondary" size="lg">{{ role === 'guest' ? 'Выбрать демо-проект' : 'Начать свой проект' }}</UiButton>
      </div>
    </section>
  </div>
</template>

<style scoped>
.intro { padding-top: var(--space-12); padding-bottom: var(--space-10); display: grid; gap: var(--space-4); }
.intro .lead { max-width: 70ch; }
.how { display: grid; gap: var(--space-10); }
.how-head { display: grid; gap: var(--space-3); max-width: 880px; position: relative; z-index: 1; }
.how-lead { max-width: 72ch; color: rgba(241, 245, 243, 0.72); }
.journey-cta { display: flex; justify-content: center; flex-wrap: wrap; gap: 12px; margin-top: var(--space-10); }
.orbits { position: absolute; right: -180px; top: -220px; width: 720px; height: 720px; pointer-events: none; }
.orbit { inset: 0; }
.o1 { inset: 0; }
.o2 { inset: 110px; }
.o3 { inset: 220px; border-color: rgba(43, 209, 141, 0.16); }
</style>
