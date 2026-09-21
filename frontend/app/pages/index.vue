<script setup lang="ts">
import { PhArrowRight, PhArrowUpRight, PhDatabase, PhGitBranch, PhChartLineUp, PhPlay } from '@phosphor-icons/vue'
import { projects, objectTypeLabel, objectTypeImage } from '~/data/projects'

useHead({ title: 'Платформа роботизации. Каталог и подбор решений' })

const { products } = useCatalog()
// На главной показываем четыре самых зрелых решения каталога
const featured = computed(() =>
  [...products.value]
    .sort((a, b) => b.trl - a.trl || b.marketPotential - a.marketPotential || b.completeness - a.completeness)
    .slice(0, 4),
)
const demos = computed(() => projects.filter((p) => p.isDemo))

const rules = [
  { icon: PhDatabase, title: 'У каждого числа есть источник', text: 'Достоверность выводится из типа источника: производитель, дилер, СМИ, каталог, аналог, допущение. Буква не ставится вручную.' },
  { icon: PhGitBranch, title: 'Подбор трёхзначный', text: 'Подходит, исключён, требует проверки. Пустое поле не выкидывает решение, а переводит его в отдельный список с запросом вендору.' },
  { icon: PhChartLineUp, title: 'Экономика интервалом', text: 'Нижняя, центральная и верхняя оценка. Рядом характеристика, которая даёт больше всего неопределённости, и что её сузит.' },
]

/* Hero: параллакс слоёв от курсора. Слои сдвигаются с разной амплитудой, отсюда глубина. */
const stage = ref<HTMLElement | null>(null)
const video = ref<HTMLVideoElement | null>(null)
const px = ref(0)
const py = ref(0)
let raf = 0
const onMove = (e: PointerEvent) => {
  const el = stage.value
  if (!el) return
  const r = el.getBoundingClientRect()
  const nx = ((e.clientX - r.left) / r.width) * 2 - 1
  const ny = ((e.clientY - r.top) / r.height) * 2 - 1
  cancelAnimationFrame(raf)
  raf = requestAnimationFrame(() => { px.value = Math.max(-1, Math.min(1, nx)); py.value = Math.max(-1, Math.min(1, ny)) })
}
const onLeave = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(() => { px.value = 0; py.value = 0 }) }
const stageStyle = computed(() => ({ '--mx': px.value.toFixed(3), '--my': py.value.toFixed(3) }))
const speedUp = (e: Event) => {
  (e.currentTarget as HTMLVideoElement).playbackRate = 1.5
}
onMounted(() => {
  const v = video.value
  if (!v) return
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) { v.pause(); return }
  v.playbackRate = 1.5
})
onBeforeUnmount(() => cancelAnimationFrame(raf))

const objects = [
  { type: 'warehouse' as const, title: 'Склад', text: 'Полный путь: параметры, подбор, три сценария, экономика, what-if, симуляция смены, 2D-план, отчёт.', full: true, processes: ['Перемещение', 'Комплектация', 'Паллетирование', 'Инвентаризация'] },
  { type: 'airport' as const, title: 'Аэропорт', text: 'Параметры площадки и список применимых решений.', full: false, processes: ['Багаж', 'Периметр', 'Дезинфекция'] },
  { type: 'hospital' as const, title: 'Медучреждение', text: 'Параметры корпуса и список применимых решений.', full: false, processes: ['Дезинфекция', 'Доставка'] },
]
</script>

<template>
  <div>
    <!-- Первый экран: сцена с глубиной. Слои снизу вверх: видео → заголовок → робот → стекло -->
    <section class="hero container">
      <div ref="stage" class="stage" :style="stageStyle" @pointermove="onMove" @pointerleave="onLeave">
        <!-- Слой 0: фон, зацикленное видео склада -->
        <div class="layer l-bg" aria-hidden="true">
          <video ref="video" class="bg-video" autoplay muted loop playsinline preload="auto" poster="/img/hero-stage.jpg" @canplay="speedUp">
            <source src="/img/hero-loop.webm" type="video/webm">
            <source src="/img/hero-loop.mp4" type="video/mp4">
          </video>
          <span class="bg-frost" />
        </div>

        <!-- Слой 1: заголовок, уходит за робота -->
        <div class="layer l-text" v-reveal>
          <div class="label kicker">Каталог и подбор роботизированных решений</div>
          <h1 class="hero-1 headline">
            <span class="line">Роботизация</span>
            <span class="line">с расчётом, который</span>
            <span class="line">можно проверить</span>
          </h1>
        </div>

        <!-- Слой 2: робот перед заголовком -->
        <div class="layer l-robot" aria-hidden="true">
          <span class="robot-shadow" />
          <img src="/img/hero-robot.webp" alt="" class="robot" fetchpriority="high" decoding="async">
          <span class="robot-led" />
        </div>

        <!-- Слой 3: стекло перед роботом -->
        <div class="layer l-fore">
          <div class="float f1 glass glass-sheen" v-reveal="2">
            <span class="sheen" aria-hidden="true" />
            <div class="f-head">
              <span class="label">Подбор · склад 12 000 м²</span>
              <UiBadge tone="ok" pulse>Подходит</UiBadge>
            </div>
            <div class="f-row">
              <div>
                <div class="h4">Ronavi H1500</div>
                <div class="caption">AMR палетный · Ronavi Robotics</div>
              </div>
              <div class="f-n"><span class="display-4">7</span><span class="caption">машин</span></div>
            </div>
            <div class="f-formula mono-sm">N = ⌈240 · 1,6 · 4,4 / (480 · 0,85)⌉ · 1,3</div>
          </div>

          <div class="float f2 glass" v-reveal="3">
            <div class="label">Окупаемость</div>
            <div class="f-int">
              <span class="mono-md">2,4</span>
              <span class="bar"><span /></span>
              <span class="mono-md">4,2</span>
              <span class="caption">года</span>
            </div>
            <div class="caption">Ширину даёт производительность: <span class="strong">оценка по аналогу</span></div>
          </div>

          <div class="float f3 glass-graphite glass-graphite-solid" v-reveal="4">
            <div class="mono-sm">A · производитель</div>
            <div class="body-sm">Грузоподъёмность 1 500 кг</div>
            <div class="caption">получено 14 авг 2026</div>
          </div>
        </div>

      </div>
    </section>

    <!-- Метрики -->
    <section class="container metrics" v-reveal>
      <div class="metrics-grid glass glass-xl">
        <UiStat label="Решений в каталоге" value="47" note="в 11 категориях, два формата исходников" />
        <UiStat label="В эксплуатации" value="23" note="ещё 12 в пилоте и 2 в разработке" />
        <UiStat label="Типа объектов" value="3" note="склад, аэропорт, медучреждение" />
        <UiStat label="Горизонт TCO" value="5 лет" note="не меньше, чем требует организатор" />
      </div>
    </section>

    <!-- Тип объекта -->
    <section class="container section">
      <SectionHead title="С какого объекта начать" lead="Склад проходит весь сценарий. Аэропорт и медучреждение в MVP останавливаются на подборе, об этом сказано на кабинете проекта." size="hero-2" />
      <div class="objects">
        <NuxtLink v-for="(o, i) in objects" :key="o.type" :to="`/projects/new?type=${o.type}`" class="obj" :class="o.type" v-reveal="i">
          <img :src="objectTypeImage[o.type]" :alt="o.title" loading="lazy">
          <div class="obj-scrim" />
          <div class="obj-panel glass glass-strong">
            <div class="between">
              <h3 class="h2">{{ o.title }}</h3>
              <UiBadge :tone="o.full ? 'ok' : 'info'">{{ o.full ? 'Полный путь' : 'Параметры и подбор' }}</UiBadge>
            </div>
            <p class="body-sm muted">{{ o.text }}</p>
            <div class="obj-tags">
              <span v-for="p in o.processes" :key="p" class="tag">{{ p }}</span>
            </div>
          </div>
          <span class="obj-arrow glass"><PhArrowUpRight :size="20" weight="bold" /></span>
        </NuxtLink>
      </div>
    </section>

    <!-- Как работает подбор: графит -->
    <section class="container">
      <div class="graphite graphite-section graphite-grid scanline how" style="--scan-h: 560px">
        <div class="orbits" aria-hidden="true">
          <span class="orbit o1 orbit-spin" style="--orbit-dur: 48s"><span class="dot" /></span>
          <span class="orbit o2 orbit-spin" style="--orbit-dur: 32s; animation-direction: reverse" />
          <span class="orbit o3" />
        </div>
        <div class="how-head">
          <div class="label">Как работает подбор</div>
          <h2 class="hero-2">Три правила, которые интерфейс показывает, а не прячет</h2>
        </div>
        <div class="rules">
          <div v-for="(r, i) in rules" :key="r.title" class="rule glass-graphite" v-reveal="i">
            <component :is="r.icon" :size="28" weight="duotone" class="rule-ic" />
            <h3 class="h3">{{ r.title }}</h3>
            <p class="body-sm muted">{{ r.text }}</p>
          </div>
        </div>
        <div class="how-flow mono-sm">
          <span>отрасль и объект</span><i /><span>параметры</span><i /><span>подбор</span><i /><span>сравнение</span><i /><span>экономика</span><i /><span>what-if</span><i /><span>2D-план</span><i /><span>отчёт</span>
        </div>
      </div>
    </section>

    <!-- Демо-наборы -->
    <section class="container section">
      <SectionHead title="Демо-площадки для гостя" lead="Три площадки с загруженными параметрами. Проход без сохранения собственного проекта.">
        <UiButton to="/login" variant="secondary">Войти под ролью</UiButton>
      </SectionHead>
      <div class="demos">
        <NuxtLink v-for="(d, i) in demos" :key="d.id" :to="`/projects/${d.id}`" class="demo glass" v-reveal="i">
          <div class="demo-media"><img :src="objectTypeImage[d.objectType]" :alt="objectTypeLabel[d.objectType]" loading="lazy"></div>
          <div class="demo-body">
            <div class="label">{{ objectTypeLabel[d.objectType] }} · {{ d.industry }}</div>
            <div class="h3">{{ d.name }}</div>
            <div class="demo-meta">
              <span class="mono-sm">{{ d.area?.toLocaleString('ru-RU') }} м²</span>
              <span class="mono-sm">{{ d.shifts }} смены</span>
              <span class="mono-sm">{{ d.tasks }} задачи</span>
            </div>
            <span class="demo-go"><PhPlay :size="14" weight="fill" /> Открыть демо</span>
          </div>
        </NuxtLink>
      </div>
    </section>

    <!-- Каталог -->
    <section class="container section">
      <SectionHead title="Каталог решений" lead="Дерево отрасль → объект → процесс → тип решения → продукт. Один продукт может быть в нескольких ветках без дублей карточек.">
        <UiButton to="/catalog" variant="secondary">Все 47 решений<template #after><PhArrowRight :size="16" weight="bold" /></template></UiButton>
      </SectionHead>
      <div class="grid grid-4">
        <RobotCard v-for="(p, i) in featured" :key="p.id" :product="p" v-reveal="i" />
      </div>
    </section>

    <!-- Оговорка -->
    <section class="container section-tight">
      <div class="disclaimer glass glass-xl">
        <div>
          <div class="h2">Это экспресс-оценка, не акт обследования</div>
          <p class="body muted">Платформа даёт прединвестиционную гипотезу для перехода к полноценному ТЭО. Расчёт открывается снова на той же версии каталога и модели.</p>
        </div>
        <div class="row">
          <UiButton to="/projects/new" size="lg">Начать проект</UiButton>
          <UiButton to="/projects/demo-warehouse/report" variant="ghost" size="lg">Посмотреть демо-отчёт</UiButton>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
/* ---------- Hero: сцена с глубиной ---------- */
.hero { padding-top: var(--space-4); padding-bottom: var(--space-6); }
.stage {
  --mx: 0; --my: 0;
  position: relative;
  min-height: clamp(560px, 82vh, 860px);
  border-radius: var(--radius-2xl);
  overflow: hidden;
  isolation: isolate;
  box-shadow: var(--shadow-lg), inset 0 0 0 1px rgba(255, 255, 255, 0.7);
  background: var(--surface-page);
}
.layer { position: absolute; inset: 0; pointer-events: none; }
.layer > * { pointer-events: auto; }

/* Слой 0: видео и подложки */
.l-bg { transform: translate3d(calc(var(--mx) * -6px), calc(var(--my) * -4px), 0) scale(1.03); transition: transform 600ms var(--ease); }
.bg-video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: 50% 60%; }
.bg-frost {
  position: absolute; inset: 0;
  background: rgba(255, 255, 255, 0.09);
  -webkit-backdrop-filter: blur(5.4px) saturate(125%);
  backdrop-filter: blur(5.4px) saturate(125%);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.45);
}

/* Слой 1: заголовок */
.l-text { padding: clamp(48px, 7vw, 110px) clamp(28px, 4vw, 60px) 0; transform: translate3d(calc(var(--mx) * 8px), calc(var(--my) * 6px), 0); transition: transform 500ms var(--ease); }
.kicker { margin-bottom: clamp(14px, 1.6vw, 24px); }
.headline { display: grid; font-size: clamp(44px, 5.2vw, 96px); line-height: 0.98; letter-spacing: -0.03em; max-width: none; }
.headline .line { display: block; white-space: nowrap; }
.headline .line:nth-child(2) { padding-left: 0.6em; }
.headline .line:nth-child(3) { padding-left: 1.6em; }

/* Слой 2: робот, перед текстом */
.l-robot { transform: translate3d(calc(var(--mx) * 22px), calc(var(--my) * 12px), 0); transition: transform 420ms var(--ease); }
.robot { position: absolute; right: clamp(0px, 2vw, 40px); bottom: -4%; height: clamp(380px, 60%, 550px); width: auto; animation: robot-idle 7s var(--ease) infinite alternate; filter: drop-shadow(0 30px 50px rgba(15, 20, 19, 0.28)); }
.robot-shadow { position: absolute; right: clamp(40px, 6vw, 120px); bottom: -1%; width: clamp(360px, 38%, 660px); height: 12%; border-radius: 50%; background: radial-gradient(closest-side, rgba(15, 20, 19, 0.35), rgba(15, 20, 19, 0)); filter: blur(12px); animation: shadow-idle 7s var(--ease) infinite alternate; }
.robot-led { position: absolute; right: clamp(60px, 7vw, 140px); bottom: 6%; width: clamp(300px, 34%, 600px); height: 40px; border-radius: 50%; background: radial-gradient(closest-side, rgba(43, 209, 141, 0.55), rgba(43, 209, 141, 0)); filter: blur(14px); animation: led-pulse 3.2s ease-in-out infinite; mix-blend-mode: multiply; }
@keyframes robot-idle { to { transform: translate3d(0, -10px, 0); } }
@keyframes shadow-idle { to { transform: scale(0.94); opacity: 0.8; } }
@keyframes led-pulse { 0%, 100% { opacity: 0.55; } 50% { opacity: 1; } }

/* Слой 3: стекло, перед роботом */
.l-fore { transform: translate3d(calc(var(--mx) * 34px), calc(var(--my) * 20px), 0); transition: transform 380ms var(--ease); }
.float { position: absolute; padding: 16px; border-radius: 20px; }
.f1 { left: 50%; bottom: clamp(24px, 3vw, 44px); width: 380px; display: grid; gap: 12px; animation: hover-a 9s var(--ease) infinite alternate; }
.f2 { left: clamp(28px, 4vw, 60px); bottom: clamp(24px, 3vw, 44px); width: 280px; display: grid; gap: 8px; animation: hover-b 11s var(--ease) infinite alternate; }
.f3 { right: clamp(28px, 4vw, 60px); top: 47%; display: grid; gap: 2px; padding: 12px 14px; border-radius: 14px; animation: hover-c 13s var(--ease) infinite alternate; }
.f3 .mono-sm { color: var(--brand-300); }
.f3 .caption { color: var(--ink-muted-graphite); }
@keyframes hover-a { to { transform: translate3d(0, -8px, 0); } }
@keyframes hover-b { to { transform: translate3d(0, 10px, 0); } }
@keyframes hover-c { to { transform: translate3d(0, -6px, 0); } }

.f-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; position: relative; z-index: 1; }
.f-row { display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: center; position: relative; z-index: 1; }
.f-n { display: grid; text-align: right; }
.f-formula { padding: 8px 10px; border-radius: 10px; background: var(--surface-graphite); color: var(--brand-300); position: relative; z-index: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.f-int { display: grid; grid-template-columns: auto 1fr auto auto; align-items: center; gap: 8px; }
.f-int .mono-md { color: var(--ink-strong); }
.bar { height: 6px; border-radius: 3px; background: rgba(15, 20, 19, 0.08); position: relative; overflow: hidden; }
.bar span { position: absolute; left: 18%; right: 26%; top: 0; bottom: 0; border-radius: 3px; background: linear-gradient(90deg, var(--brand-400), var(--brand-600)); }

/* Metrics */
.metrics { padding-bottom: var(--space-8); }
.metrics-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-8); padding: var(--space-8) clamp(32px, 3vw, 56px); }
.metrics-grid > :deep(.stat) { position: relative; z-index: 1; }
.metrics-grid > :deep(.stat + .stat) { padding-left: var(--space-8); border-left: 1px solid rgba(15, 20, 19, 0.08); }

/* Objects */
.objects { display: grid; grid-template-columns: repeat(12, 1fr); grid-auto-rows: clamp(240px, 16vw, 300px); gap: var(--space-4); }
.obj { position: relative; border-radius: var(--radius-xl); overflow: hidden; display: block; box-shadow: var(--shadow-md); transition: transform var(--dur-mid) var(--ease), box-shadow var(--dur-mid) var(--ease); }
.obj:hover { transform: translateY(-3px); box-shadow: var(--shadow-lg); }
.obj.warehouse { grid-column: span 7; grid-row: span 2; }
.obj.airport, .obj.hospital { grid-column: span 5; }
.obj img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; transition: transform 800ms var(--ease); }
.obj:hover img { transform: scale(1.04); }
.obj-scrim { position: absolute; inset: 0; background: linear-gradient(180deg, rgba(15, 20, 19, 0) 40%, rgba(15, 20, 19, 0.25)); }
.obj-panel { position: absolute; left: 16px; right: 16px; bottom: 16px; padding: 18px 20px; display: grid; gap: 10px; border-radius: 18px; }
.obj-panel > * { position: relative; z-index: 1; }
.obj.warehouse .obj-panel { right: auto; width: min(460px, calc(100% - 32px)); }
.obj-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: var(--radius-pill); background: rgba(15, 20, 19, 0.06); color: var(--ink-body); }
.obj-arrow { position: absolute; top: 16px; right: 16px; width: 44px; height: 44px; border-radius: 14px; display: inline-flex; align-items: center; justify-content: center; color: var(--ink-strong); transition: transform var(--dur-fast) var(--ease); }
.obj-arrow svg { position: relative; z-index: 1; }
.obj:hover .obj-arrow { transform: translate(2px, -2px); }

/* How: graphite */
.how { display: grid; gap: var(--space-10); }
.how-head { display: grid; gap: var(--space-3); max-width: 880px; position: relative; z-index: 1; }
.orbits { position: absolute; right: -180px; top: -220px; width: 720px; height: 720px; pointer-events: none; }
.orbit { inset: 0; }
.o1 { inset: 0; }
.o2 { inset: 110px; }
.o3 { inset: 220px; border-color: rgba(43, 209, 141, 0.16); }
.rules { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4); position: relative; z-index: 1; }
.rule { padding: clamp(24px, 2vw, 36px); display: grid; gap: 12px; align-content: start; transition: box-shadow var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease); }
.rule:hover { box-shadow: inset 0 1px 0 var(--glass-g-highlight), 0 0 0 1px var(--glass-g-stroke), var(--glow-brand); transform: translateY(-2px); }
.rule-ic { color: var(--brand-300); }
.how-flow { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; color: var(--ink-muted-graphite); position: relative; z-index: 1; }
.how-flow span { padding: 6px 10px; border-radius: 8px; background: rgba(255, 255, 255, 0.05); box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08); color: var(--ink-on-graphite); }
.how-flow i { width: 18px; height: 1px; background: var(--brand-400); opacity: 0.6; }

/* Demos */
.demos { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4); }
.demo { display: grid; grid-template-rows: clamp(160px, 12vw, 220px) 1fr; border-radius: var(--radius-xl); overflow: hidden; transition: transform var(--dur-mid) var(--ease), box-shadow var(--dur-mid) var(--ease); }
.demo:hover { transform: translateY(-3px); box-shadow: inset 0 1px 0 var(--glass-stroke), 0 0 0 1px var(--glass-stroke-outer), var(--shadow-lg); }
.demo-media { margin: 8px 8px 0; border-radius: 18px; overflow: hidden; }
.demo-media img { width: 100%; height: 100%; object-fit: cover; }
.demo-body { padding: 14px 16px 16px; display: grid; gap: 8px; align-content: start; position: relative; z-index: 1; }
.demo-meta { display: flex; gap: 12px; color: var(--ink-muted); }
.demo-go { display: inline-flex; align-items: center; gap: 6px; margin-top: 6px; font-weight: 700; font-size: 14px; color: var(--link); }

/* Disclaimer */
.disclaimer { display: grid; grid-template-columns: 1fr auto; gap: var(--space-8); align-items: center; padding: clamp(32px, 3vw, 48px) clamp(32px, 3vw, 56px); }
.disclaimer > * { position: relative; z-index: 1; }
.disclaimer p { max-width: 62ch; margin-top: 8px; }

@media (max-width: 1100px) {
  /* Узкие экраны: слои складываются в поток, робот под текстом */
  .stage { min-height: 0; display: flex; flex-direction: column; }
  .layer { position: relative; inset: auto; z-index: 1; }
  .l-bg { position: absolute; inset: 0; z-index: 0; transform: none; }
  .l-text { order: 1; padding: 28px 24px 0; transform: none; }
  .l-robot { order: 2; }
  .l-fore { order: 3; }
  .headline { font-size: clamp(36px, 9vw, 56px); }
  .headline .line { white-space: normal; }
  .headline .line:nth-child(2), .headline .line:nth-child(3) { padding-left: 0; }
  .l-robot { height: 300px; transform: none; }
  .robot { right: 4%; bottom: 0; height: 92%; width: auto; }
  .robot-shadow, .robot-led { display: none; }
  .l-fore { padding: 0 24px 24px; display: grid; gap: 12px; transform: none; }
  .float { position: static; width: auto; animation: none; }
  .f3 { display: none; }
  .metrics-grid { grid-template-columns: 1fr 1fr; }
  .objects { grid-auto-rows: 220px; }
  .obj.warehouse, .obj.airport, .obj.hospital { grid-column: span 12; grid-row: span 1; }
  .rules, .demos { grid-template-columns: 1fr; }
  .disclaimer { grid-template-columns: 1fr; }
}

@media (prefers-reduced-motion: reduce) {
  .l-bg, .l-text, .l-robot, .l-fore { transform: none !important; }
}
@media (prefers-reduced-transparency: reduce) {
  .bg-frost { backdrop-filter: none; -webkit-backdrop-filter: none; background: rgba(255, 255, 255, 0.28); }
}
</style>
