<script setup lang="ts">
import { PhArrowsClockwise, PhArrowSquareOut, PhWarningCircle, PhCheckCircle, PhFile } from '@phosphor-icons/vue'
import { sources, sourceKindLabel, confidenceByKind, products } from '~/data/catalog'

definePageMeta({ layout: 'admin' })
useHead({ title: 'Админка · Источники' })

const changed = new Set(['s-ronavi'])
const usage = (id: string) => products.reduce((n, p) => n + p.attrs.filter((a) => a.sourceId === id).length, 0)
const fmt = (d: string) => new Date(d).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
const kinds = Object.entries(sourceKindLabel) as [keyof typeof sourceKindLabel, string][]
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Источники" title="Реестр источников" lead="Для каждого источника: тип, издатель, ссылка, дата получения, дата проверки и число значений в каталоге, которые на него ссылаются. Буква достоверности выводится из типа.">
      <UiButton variant="secondary"><template #icon><PhArrowsClockwise :size="16" weight="bold" /></template>Перепроверить все</UiButton>
    </AdminHead>

    <div class="legend" v-reveal>
      <div v-for="[k, l] in kinds" :key="k" class="lg glass">
        <span class="lg-in"><span class="letter" :class="`c-${confidenceByKind[k]}`">{{ confidenceByKind[k] }}</span><span class="body-sm">{{ l }}</span></span>
      </div>
    </div>

    <div class="tbl glass glass-xl" v-reveal="1">
      <table class="table">
        <thead><tr><th>Источник</th><th>Тип</th><th>Ссылка</th><th class="num">Получено</th><th class="num">Проверено</th><th class="num">Значений</th><th>Состояние</th></tr></thead>
        <tbody>
          <tr v-for="s in sources" :key="s.id" :class="{ hot: changed.has(s.id) }">
            <td><span class="strong">{{ s.publisher }}</span><span class="caption block mono-sm">{{ s.id }}</span></td>
            <td><span class="kind"><span class="letter sm" :class="`c-${confidenceByKind[s.kind]}`">{{ confidenceByKind[s.kind] }}</span><span class="body-sm">{{ sourceKindLabel[s.kind] }}</span></span></td>
            <td><a v-if="s.url.startsWith('http')" :href="s.url" target="_blank" rel="noreferrer" class="link mono-sm">{{ s.url.replace('https://', '') }} <PhArrowSquareOut :size="12" /></a><span v-else-if="s.url" class="mono-sm muted"><PhFile :size="12" /> {{ s.url.replace('file://', '') }}</span><span v-else class="caption">без ссылки</span></td>
            <td class="num mono-sm">{{ fmt(s.fetchedAt) }}</td>
            <td class="num mono-sm">{{ fmt(s.checkedAt) }}</td>
            <td class="num mono-sm">{{ usage(s.id) }}</td>
            <td><span v-if="changed.has(s.id)" class="state warn"><PhWarningCircle :size="14" weight="fill" /> Изменился</span><span v-else class="state ok"><PhCheckCircle :size="14" weight="fill" /> Без изменений</span></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.legend { display: grid; grid-template-columns: repeat(6, 1fr); gap: 10px; }
.lg-in { position: relative; z-index: 1; display: flex; gap: 10px; align-items: center; padding: 12px 14px; }
.letter { width: 28px; height: 28px; border-radius: 8px; display: inline-flex; align-items: center; justify-content: center; font-family: var(--font-mono); font-weight: 700; font-size: 13px; flex: none; }
.letter.sm { width: 22px; height: 22px; font-size: 11px; border-radius: 6px; }
.c-A { background: var(--surface-graphite); color: var(--brand-300); }
.c-B { background: var(--surface-brand-tint); color: var(--brand-ink); }
.c-C { background: var(--state-warn-tint); color: var(--state-warn); }
.c-D { background: rgba(15, 20, 19, 0.08); color: var(--ink-muted); }
.tbl { padding: var(--space-3); }
.tbl table { position: relative; z-index: 1; }
.block { display: block; }
.kind { display: inline-flex; gap: 8px; align-items: center; }
tr.hot td { background: var(--state-warn-tint); }
tr.hot td:first-child { border-radius: 10px 0 0 10px; }
tr.hot td:last-child { border-radius: 0 10px 10px 0; }
.tbl td.num, .tbl th.num { white-space: nowrap; }
.state { display: inline-flex; gap: 6px; align-items: center; font-size: 13px; font-weight: 600; white-space: nowrap; }
.state.warn { color: var(--state-warn); }
.state.ok { color: var(--state-ok); }
@media (max-width: 1100px) { .legend { grid-template-columns: repeat(3, 1fr); } }
</style>
