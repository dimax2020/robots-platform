<template>
  <footer class="footer graphite no-print">
    <div class="container inner">
      <div class="brand">
        <Logo :size="40" mint on-graphite />
        <p class="body-sm muted lead">Каталог и подбор роботизированных решений для склада, аэропорта и медучреждения. Экспресс-оценка до обследования объекта.</p>
      </div>
      <div class="cols">
        <div>
          <div class="label">Платформа</div>
          <NuxtLink to="/catalog">Каталог</NuxtLink>
          <NuxtLink to="/catalog/compare">Сравнение</NuxtLink>
          <NuxtLink to="/projects">Проекты</NuxtLink>
          <NuxtLink to="/projects/new">Новый проект</NuxtLink>
        </div>
        <div>
          <div class="label">Демо-площадки</div>
          <NuxtLink to="/projects/demo-warehouse">Склад Внуково-Юг</NuxtLink>
          <NuxtLink to="/projects/demo-airport">Терминал В</NuxtLink>
          <NuxtLink to="/projects/demo-hospital">ГКБ № 52</NuxtLink>
        </div>
        <div>
          <div class="label">Данные</div>
          <NuxtLink to="/admin/sources">Источники</NuxtLink>
          <NuxtLink to="/admin/norms">Нормативы</NuxtLink>
          <NuxtLink to="/admin/catalog">Дерево каталога</NuxtLink>
        </div>
      </div>
    </div>
    <div class="container bottom">
      <span class="mono-sm muted">Кейс ФЦ БАС. Хакатон «Лидеры цифровой трансформации», 2026</span>
      <span class="mono-sm muted">Каталог v2026.09.3 · модель m1.4</span>
    </div>
  </footer>
</template>

<style scoped>
.footer { margin-top: var(--space-20); padding: var(--space-16) 0 var(--space-8); position: relative; overflow: hidden; }
.footer::before { content: ''; position: absolute; inset: 0; background-image: linear-gradient(to right, rgba(255, 255, 255, 0.05) 1px, transparent 1px), linear-gradient(to bottom, rgba(255, 255, 255, 0.05) 1px, transparent 1px); background-size: 40px 40px; mask-image: radial-gradient(ellipse at 20% 0%, #000 10%, transparent 70%); -webkit-mask-image: radial-gradient(ellipse at 20% 0%, #000 10%, transparent 70%); pointer-events: none; }
.inner { display: grid; grid-template-columns: 1.2fr 2fr; gap: var(--space-16); position: relative; }
.lead { max-width: 42ch; margin-top: var(--space-4); }
.cols { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-8); }
.cols > div { display: grid; gap: 10px; align-content: start; }
.cols a { color: var(--ink-on-graphite); font-size: 15px; font-weight: 500; opacity: 0.85; transition: opacity var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease); }
.cols a:hover { opacity: 1; color: var(--brand-300); }
.label { margin-bottom: 6px; }
.bottom { margin-top: var(--space-12); padding-top: var(--space-6); border-top: 1px solid var(--border-graphite); display: flex; justify-content: space-between; gap: var(--space-4); position: relative; }
</style>
