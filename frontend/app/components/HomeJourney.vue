<script setup lang="ts">
import { PhFlagCheckered, PhRocketLaunch } from '@phosphor-icons/vue'

/** Карта пути подбора на главной: скриншот шага, описание и кривая к следующему шагу. Скриншоты — demo-warehouse. */
const steps = [
  { img: '/img/journey/01-processes.jpg', title: 'Выберите процессы', text: 'Отметьте работу, которую хотите отдать роботам: уборку, перевозку паллет, доставку. Для полного подбора оставьте все.' },
  { img: '/img/journey/02-object.jpg', title: 'Введите параметры объекта', text: 'Платформа спросит только то, что нужно выбранным процессам: площадь, смены, проходы, потоки. Можно подставить демо-данные или загрузить Excel.' },
  { img: '/img/journey/03-match.jpg', title: 'Получите подбор', text: 'Каждый робот каталога проходит фильтры процесса и получает вердикт: подходит, с условием, уточнить или не подходит, с причиной.' },
  { img: '/img/journey/04-compare.jpg', title: 'Сравните роботов', text: 'Подходящие роботы в одной таблице, лучшее значение подсвечено. Оптимальный выбран заранее, но можно взять другого.' },
  { img: '/img/journey/05-economics.jpg', title: 'Посчитайте экономику', text: 'Три сценария: без роботов, покупка и аренда. Срок окупаемости, затраты и эффект, у каждого числа формула и источник.' },
  { img: '/img/journey/06-whatif.jpg', title: 'Проверьте допущения', text: 'Меняйте коэффициенты и включайте меры господдержки: расчёт пересчитывается сразу и подсказывает, что сделает процесс выгодным.' },
  { img: '/img/journey/07-plan.jpg', title: 'Посмотрите на плане', text: '2D-план объекта с зонами и станциями. Запустите смену: роботы поедут по маршрутам, а монитор покажет загрузку и очереди.' },
  { img: '/img/journey/08-report.jpg', title: 'Заберите отчёт', text: 'Парк роботов, экономика и план в одном документе. Печать в PDF, выгрузка в Excel и CSV.' },
]
</script>

<template>
  <div class="journey">
    <div class="start"><PhRocketLaunch :size="18" weight="duotone" /> Старт: новый проект или демо-объект</div>

    <template v-for="(s, i) in steps" :key="s.img">
      <!-- Кривая от скриншота прошлого шага к скриншоту этого: шаги идут змейкой слева направо и обратно. -->
      <svg v-if="i > 0" class="curve" :class="{ flip: i % 2 === 0 }" viewBox="0 0 1000 120" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <linearGradient :id="`jg-${i}`" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stop-color="var(--brand-300)" />
            <stop offset="1" stop-color="var(--brand-600)" />
          </linearGradient>
        </defs>
        <path d="M 237 0 C 237 70, 763 50, 763 120" fill="none" :stroke="`url(#jg-${i})`" stroke-width="3" stroke-dasharray="2 9" stroke-linecap="round" vector-effect="non-scaling-stroke" />
      </svg>

      <article class="stop" :class="{ right: i % 2 === 1 }" v-reveal>
        <figure class="shot">
          <span class="bar" aria-hidden="true"><i /><i /><i /></span>
          <img :src="s.img" :alt="`Шаг ${i + 1}: ${s.title}`" loading="lazy" decoding="async" width="1440" height="900">
          <span class="badge">{{ i + 1 }}</span>
        </figure>
        <div class="copy">
          <div class="label">Шаг {{ i + 1 }} из {{ steps.length }}</div>
          <h3 class="h2">{{ s.title }}</h3>
          <p class="body-lg muted">{{ s.text }}</p>
        </div>
      </article>
    </template>

    <div class="finish"><PhFlagCheckered :size="18" weight="duotone" /> Готово: гипотеза для ТЭО с роботами, цифрами и планом</div>
  </div>
</template>

<style scoped>
.journey { display: grid; justify-items: stretch; max-width: 1080px; margin: 0 auto; }
.start, .finish { justify-self: center; display: inline-flex; align-items: center; gap: 8px; padding: 10px 16px; border-radius: 999px; font-size: 14px; font-weight: 700; background: var(--surface-graphite); color: var(--ink-on-graphite); }
.start { margin-bottom: 28px; }
.finish { margin-top: 40px; background: var(--brand-600); color: #fff; }
.start svg { color: var(--brand-300); }

/* Остановка: скриншот и текст в равных колонках. Каждая вторая зеркальная. */
.stop { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 56px; align-items: center; }
.stop.right .shot { order: 2; }
.stop.right .copy { order: 1; text-align: right; justify-items: end; }
.shot { position: relative; margin: 0; padding: 26px 6px 6px; border-radius: 18px; background: #fff; box-shadow: 0 0 0 1px rgba(15, 20, 19, 0.06), 0 24px 60px rgba(15, 20, 19, 0.12), 0 2px 6px rgba(15, 20, 19, 0.05); }
.shot img { display: block; width: 100%; height: auto; aspect-ratio: 16 / 10; object-fit: cover; object-position: top; border-radius: 12px; background: #eef2f0; }
.bar { position: absolute; top: 9px; left: 14px; display: flex; gap: 6px; }
.bar i { width: 9px; height: 9px; border-radius: 50%; background: rgba(15, 20, 19, 0.12); }
.badge { position: absolute; top: -16px; left: calc(50% - 19px); width: 38px; height: 38px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; font-family: var(--font-display); font-size: 16px; background: var(--brand-500); color: #fff; box-shadow: 0 0 0 6px var(--surface-page), 0 8px 20px rgba(10, 107, 69, 0.35); }
.copy { display: grid; gap: 12px; max-width: 46ch; }
.copy .label { color: var(--brand-700); }
.copy .h2 { font-size: clamp(24px, 1.9vw, 30px); }

/* Кривая между остановками: из центра скриншота слева в центр скриншота справа. */
.curve { display: block; width: 100%; height: 96px; margin: -8px 0 6px; overflow: visible; }
.curve.flip { transform: scaleX(-1); }

@media (max-width: 1100px) {
  .stop, .stop.right { grid-template-columns: 1fr; gap: var(--space-5); }
  .stop.right .shot { order: 0; }
  .stop.right .copy { order: 1; text-align: left; justify-items: start; }
  .curve { height: 56px; }
  .curve path { d: path('M 500 0 C 500 30, 500 30, 500 120'); }
}
</style>
