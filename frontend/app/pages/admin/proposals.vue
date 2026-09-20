<script setup lang="ts">
import { PhCheck, PhX, PhPencilSimple, PhArrowSquareOut, PhQuotes, PhLinkSimple, PhUploadSimple, PhHandPointing, PhClockCounterClockwise } from '@phosphor-icons/vue'
import { proposals as seed, type Proposal } from '~/data/projects'

definePageMeta({ layout: 'admin' })
useHead({ title: 'Админка · Очередь правок' })

const items = reactive<Proposal[]>(seed.map((p) => ({ ...p })))
const tab = ref<'pending' | 'all'>('pending')
const tabs = computed(() => [
  { id: 'pending', label: 'Ожидают', count: items.filter((i) => i.status === 'pending').length },
  { id: 'all', label: 'Все', count: items.length },
])
const shown = computed(() => (tab.value === 'pending' ? items.filter((i) => i.status === 'pending') : items))
const decide = (p: Proposal, s: Proposal['status']) => { p.status = s }
const originIcon = { url: PhLinkSimple, import: PhUploadSimple, manual: PhHandPointing }
const originLabel = { url: 'Парсер по URL', import: 'Импорт из файла', manual: 'Ручная правка' }
const statusTone: Record<Proposal['status'], 'warn' | 'ok' | 'danger'> = { pending: 'warn', accepted: 'ok', rejected: 'danger' }
const statusLabel: Record<Proposal['status'], string> = { pending: 'Ожидает', accepted: 'Принято', rejected: 'Отклонено' }
const fmt = (d: string) => new Date(d).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Очередь правок" title="Предложения к каталогу" lead="Каждое предложение: продукт, поле, значение, цитата и ссылка. Принять, отклонить или исправить перед принятием. Ничего не публикуется без человека." />

    <div class="bar" v-reveal>
      <UiTabs v-model="tab" :tabs="tabs" />
      <div class="caption"><PhClockCounterClockwise :size="12" /> Парсер последний раз работал сегодня в 10:14</div>
    </div>

    <TransitionGroup name="list" tag="div" class="queue">
      <article v-for="(p, i) in shown" :key="p.id" class="card glass" :class="{ done: p.status !== 'pending' }" v-reveal="Math.min(i, 5)">
        <div class="c-in">
          <div class="c-top">
            <span class="origin caption"><component :is="originIcon[p.origin]" :size="14" weight="duotone" /> {{ originLabel[p.origin] }} · <span class="mono-sm">{{ p.id }}</span></span>
            <span class="right caption">{{ fmt(p.at) }} <UiBadge :tone="statusTone[p.status]" size="sm">{{ statusLabel[p.status] }}</UiBadge></span>
          </div>
          <div class="c-main">
            <div class="c-what">
              <div class="h3">{{ p.product }}</div>
              <div class="body-sm muted">{{ p.field }}</div>
            </div>
            <div class="c-val">
              <div class="caption">Предлагаемое значение</div>
              <div class="mono-lg">{{ p.value }}</div>
            </div>
            <div class="c-proof">
              <div v-if="p.quote" class="quote body-sm"><PhQuotes :size="14" weight="fill" /> «{{ p.quote }}»</div>
              <div v-else class="caption warn">Цитаты нет: принять можно только после проверки вручную</div>
              <a v-if="p.url" :href="p.url" target="_blank" rel="noreferrer" class="link mono-sm">{{ p.url.replace('https://', '') }} <PhArrowSquareOut :size="12" /></a>
              <span v-else class="caption">Без ссылки</span>
            </div>
          </div>
          <div v-if="p.status === 'pending'" class="c-actions">
            <UiButton size="sm" @click="decide(p, 'accepted')"><template #icon><PhCheck :size="14" weight="bold" /></template>Принять</UiButton>
            <UiButton size="sm" variant="secondary"><template #icon><PhPencilSimple :size="14" weight="bold" /></template>Исправить</UiButton>
            <UiButton size="sm" variant="ghost" @click="decide(p, 'rejected')"><template #icon><PhX :size="14" weight="bold" /></template>Отклонить</UiButton>
          </div>
        </div>
      </article>
    </TransitionGroup>
    <div v-if="!shown.length" class="empty glass" v-reveal><div class="e-in"><div class="h3">Очередь пуста</div><div class="body-sm muted">Все предложения обработаны. Изменения попадут в каталог после публикации версии.</div><UiButton to="/admin/publish" size="sm" variant="secondary">К публикации</UiButton></div></div>
  </div>
</template>

<style scoped>
.bar { display: flex; justify-content: space-between; align-items: center; gap: var(--space-4); }
.bar .caption { display: inline-flex; gap: 6px; align-items: center; }
.queue { display: grid; gap: var(--space-3); }
.card { transition: opacity var(--dur-mid) var(--ease); }
.card.done { opacity: 0.62; }
.c-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: var(--space-4); }
.c-top { display: flex; justify-content: space-between; align-items: center; }
.origin, .right { display: inline-flex; gap: 6px; align-items: center; }
.c-main { display: grid; grid-template-columns: 1.2fr 1fr 1.6fr; gap: var(--space-6); align-items: start; }
.c-what, .c-val, .c-proof { display: grid; gap: 4px; }
.quote { display: flex; gap: 6px; align-items: flex-start; color: var(--ink-body); }
.quote svg { color: var(--brand-700); margin-top: 3px; flex: none; }
.warn { color: var(--state-warn); }
.c-actions { display: flex; gap: 8px; padding-top: var(--space-3); border-top: 1px solid var(--border-hairline); }
.empty .e-in { position: relative; z-index: 1; padding: var(--space-8); display: grid; gap: 8px; justify-items: start; }
.list-leave-active { transition: all var(--dur-mid) var(--ease); position: absolute; }
.list-leave-to { opacity: 0; transform: translateY(-6px); }
@media (max-width: 1100px) { .c-main { grid-template-columns: 1fr; } }
</style>
