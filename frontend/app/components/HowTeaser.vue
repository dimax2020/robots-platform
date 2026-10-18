<script setup lang="ts">
import { PhArrowRight } from '@phosphor-icons/vue'

/** Ссылка с главной на «Как это работает»: мини-карта шагов и веер скриншотов. */
const steps = ['Процессы', 'Параметры', 'Подбор', 'Сравнение', 'Экономика', 'What-if', 'План', 'Отчёт']
const shots = ['/img/journey/03-match.jpg', '/img/journey/05-economics.jpg', '/img/journey/07-plan.jpg']
</script>

<template>
  <NuxtLink to="/how" class="teaser glass glass-xl">
    <div class="copy">
      <div class="label">Как это работает</div>
      <div class="h2">Восемь шагов от процессов до отчёта</div>
      <p class="body muted">Как устроены данные платформы и что происходит на каждом шаге подбора — на настоящих экранах демо-склада.</p>
      <span class="go">Посмотреть, как это работает <PhArrowRight :size="16" weight="bold" /></span>
    </div>

    <ol class="map" aria-hidden="true">
      <li v-for="(s, i) in steps" :key="s"><span class="pin">{{ i + 1 }}</span><span class="name">{{ s }}</span></li>
    </ol>

    <div class="fan" aria-hidden="true">
      <img v-for="(src, i) in shots" :key="src" :src="src" alt="" loading="lazy" decoding="async" :class="`f${i}`">
    </div>
  </NuxtLink>
</template>

<style scoped>
.teaser { position: relative; display: grid; grid-template-columns: minmax(0, 4fr) minmax(0, 5fr) 260px; gap: var(--space-8); align-items: center; padding: var(--space-6) var(--space-8); overflow: hidden; transition: box-shadow var(--dur-mid) var(--ease), transform var(--dur-mid) var(--ease); }
.teaser > * { position: relative; z-index: 1; }
.teaser:hover { transform: translateY(-2px); box-shadow: inset 0 1px 0 var(--glass-stroke), 0 0 0 1px var(--brand-400), var(--shadow-lg); }
.copy { display: grid; gap: 10px; }
.copy .label { color: var(--brand-700); }
.go { display: inline-flex; align-items: center; gap: 8px; margin-top: 4px; font-weight: 700; color: var(--link); }
.teaser:hover .go svg { transform: translateX(3px); }
.go svg { transition: transform var(--dur-fast) var(--ease); }

/* Мини-карта: восемь точек на пунктирной линии, как маршрут. */
.map { position: relative; list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(8, 1fr); }
.map::before { content: ''; position: absolute; left: 6%; right: 6%; top: 17px; border-top: 2px dashed rgba(10, 107, 69, 0.35); }
.map li { position: relative; display: grid; justify-items: center; gap: 8px; }
.map li:nth-child(even) { transform: translateY(18px); }
.pin { width: 34px; height: 34px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-family: var(--font-display); font-size: 14px; background: #fff; color: var(--brand-700); box-shadow: inset 0 0 0 2px var(--brand-400), 0 4px 10px rgba(10, 107, 69, 0.15); }
.map li:first-child .pin, .map li:last-child .pin { background: var(--brand-500); color: #fff; box-shadow: 0 4px 12px rgba(10, 107, 69, 0.3); }
.name { font-size: 12px; font-weight: 600; color: var(--ink-muted); white-space: nowrap; }

/* Веер скриншотов. */
.fan { position: relative; height: 170px; }
.fan img { position: absolute; width: 200px; aspect-ratio: 16 / 10; object-fit: cover; object-position: top; border-radius: 12px; background: #fff; box-shadow: 0 0 0 4px #fff, 0 14px 30px rgba(15, 20, 19, 0.18); transition: transform var(--dur-mid) var(--ease); }
.f0 { left: 0; top: 30px; transform: rotate(-8deg); }
.f1 { left: 30px; top: 12px; transform: rotate(-1deg); }
.f2 { left: 60px; top: 0; transform: rotate(6deg); }
.teaser:hover .f0 { transform: rotate(-12deg) translateX(-8px); }
.teaser:hover .f2 { transform: rotate(10deg) translateX(8px); }

@media (max-width: 1100px) {
  .teaser { grid-template-columns: 1fr; padding: var(--space-6); }
  .map, .fan { display: none; }
}
</style>
