<script setup lang="ts">
import { PhPlus, PhCopy, PhTrash, PhArrowRight, PhLockSimple } from '@phosphor-icons/vue'
import { projects, objectTypeLabel, objectTypeImage, steps, isFullPath } from '~/data/projects'
import { fetchErrorMessage } from '~/composables/useCalc'

useHead({ title: 'Проекты' })
const { role } = useRole()
const { projects: live, pending, error } = useProjects()
const own = computed(() => live.value)
const demo = computed(() => projects.filter((p) => p.isDemo))
const fmt = (d: string) => {
  if (!d) return '—'
  const dt = new Date(d)
  return Number.isNaN(dt.getTime()) ? '—' : dt.toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}
const stepLabel = (p: (typeof projects)[number]) => steps[Math.min(p.step, steps.length) - 1]?.label ?? 'Параметры'
</script>

<template>
  <section class="container projects">
    <div class="between head" v-reveal>
      <div>
        <div class="label">Проекты</div>
        <h1 class="hero-2">Сохранённые расчёты</h1>
        <p class="body muted">Каждый прогон хранит версию каталога и модели: расчёт открывается снова с теми же исходными данными.</p>
      </div>
      <UiButton to="/projects/new" size="lg"><template #icon><PhPlus :size="18" weight="bold" /></template>Новый проект</UiButton>
    </div>

    <UiCallout v-if="role === 'guest'" tone="info" title="Гость видит только демо">Своих проектов у гостя нет. Войдите как пользователь, чтобы сохранять расчёты. Демо-площадки открываются без входа.</UiCallout>

    <div v-if="role !== 'guest'" class="block" v-reveal>
      <div class="h3 block-title">Мои проекты <span class="mono-sm muted">{{ own.length }}</span></div>
      <UiCallout v-if="error" tone="danger" title="Не удалось загрузить проекты">{{ fetchErrorMessage(error, 'Сервер не ответил.') }}</UiCallout>
      <div v-else-if="pending" class="list glass glass-xl"><UiSkeleton h="120px" /></div>
      <div v-else-if="!own.length" class="list glass glass-xl">
        <div class="empty-own">
          <div class="h4">Пока нет сохранённых расчётов</div>
          <div class="caption">Создайте проект — площадка и задачи предзаполнятся из профиля объекта.</div>
        </div>
      </div>
      <div v-else class="list glass glass-xl">
        <table class="table">
          <thead><tr><th>Название</th><th>Тип объекта</th><th>Шаг</th><th>Обновлён</th><th>Версия каталога</th><th class="num">Действия</th></tr></thead>
          <tbody>
            <tr v-for="p in own" :key="p.id">
              <td><NuxtLink :to="`/projects/${p.id}`" class="strong name">{{ p.name }}</NuxtLink><div class="caption">{{ p.industry }}</div></td>
              <td><span class="row"><img :src="objectTypeImage[p.objectType]" class="thumb" alt="">{{ objectTypeLabel[p.objectType] }}</span></td>
              <td><span class="progress"><span class="bar"><span :style="{ width: `${(p.step / steps.length) * 100}%` }" /></span><span class="caption">{{ stepLabel(p) }}</span></span></td>
              <td class="mono-sm">{{ fmt(p.updatedAt) }}</td>
              <td class="mono-sm">{{ p.catalogVersion }} · {{ p.modelVersion }}</td>
              <td class="num actions">
                <UiButton :to="`/projects/${p.id}`" size="sm" variant="secondary">Открыть <template #after><PhArrowRight :size="14" weight="bold" /></template></UiButton>
                <button type="button" class="ic" aria-label="Копировать"><PhCopy :size="16" /></button>
                <button type="button" class="ic danger" aria-label="Удалить"><PhTrash :size="16" /></button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="block" v-reveal="1">
      <div class="h3 block-title">Демо-площадки <span class="mono-sm muted">{{ demo.length }}</span></div>
      <div class="demos">
        <NuxtLink v-for="p in demo" :key="p.id" :to="`/projects/${p.id}`" class="demo glass">
          <img :src="objectTypeImage[p.objectType]" :alt="objectTypeLabel[p.objectType]">
          <div class="demo-body">
            <div class="between"><span class="label">{{ objectTypeLabel[p.objectType] }}</span><UiBadge :tone="isFullPath(p) ? 'ok' : 'info'" size="sm">{{ isFullPath(p) ? 'Полный путь' : 'До подбора' }}</UiBadge></div>
            <div class="h4">{{ p.name }}</div>
            <div class="caption"><PhLockSimple :size="12" /> Без сохранения · {{ p.catalogVersion }}</div>
          </div>
        </NuxtLink>
      </div>
    </div>
  </section>
</template>

<style scoped>
.projects { padding-top: var(--space-12); padding-bottom: var(--space-16); display: grid; gap: var(--space-8); }
.head { align-items: flex-end; }
.head > div { display: grid; gap: 10px; max-width: 64ch; }
.block { display: grid; gap: var(--space-4); }
.block-title { display: flex; align-items: baseline; gap: 10px; }
.list { padding: var(--space-3); }
.list table { position: relative; z-index: 1; }
.empty-own { position: relative; z-index: 1; padding: var(--space-8); display: grid; gap: 6px; }
.name { color: var(--ink-strong); }
.thumb { width: 28px; height: 28px; border-radius: 8px; object-fit: cover; }
.progress { display: grid; gap: 4px; min-width: 140px; }
.bar { height: 4px; border-radius: 2px; background: rgba(15, 20, 19, 0.08); overflow: hidden; }
.bar span { display: block; height: 100%; border-radius: 2px; background: var(--brand-500); }
.actions { white-space: nowrap; }
.ic { display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 8px; color: var(--ink-muted); margin-left: 4px; transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease); vertical-align: middle; }
.ic:hover { background: rgba(15, 20, 19, 0.06); color: var(--ink-strong); }
.ic.danger:hover { background: var(--state-danger-tint); color: var(--state-danger); }
.demos { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4); }
.demo { display: grid; grid-template-columns: 96px 1fr; gap: 12px; padding: 8px; align-items: center; transition: transform var(--dur-mid) var(--ease); }
.demo:hover { transform: translateY(-2px); }
.demo img { width: 96px; height: 96px; object-fit: cover; border-radius: 12px; position: relative; z-index: 1; }
.demo-body { display: grid; gap: 4px; padding-right: 8px; position: relative; z-index: 1; }
.demo-body .caption { display: inline-flex; align-items: center; gap: 4px; }
</style>
