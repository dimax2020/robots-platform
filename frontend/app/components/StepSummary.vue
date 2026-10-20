<script setup lang="ts">
import { PhArrowRight, PhCheckCircle, PhCircleDashed, PhWarningCircle } from '@phosphor-icons/vue'
import type { SummaryRow } from '~/composables/useStepPass'

/** Итог шага: главные цифры и все процессы списком. Строка ведёт на страницу процесса. */
defineProps<{ stats: { label: string; value: string }[]; rows: SummaryRow[]; hint?: string }>()
const ICON = { ok: PhCheckCircle, warn: PhWarningCircle, todo: PhCircleDashed } as const
</script>

<template>
  <section class="summary glass">
    <div class="s-in">
      <div class="stats">
        <div v-for="stat in stats" :key="stat.label" class="stat">
          <span class="caption">{{ stat.label }}</span>
          <span class="mono-lg">{{ stat.value }}</span>
        </div>
      </div>
      <UiHint v-if="hint">{{ hint }}</UiHint>
      <ul class="rows">
        <li v-for="row in rows" :key="row.code">
          <NuxtLink :to="row.to" class="row" :class="row.tone">
            <component :is="ICON[row.tone]" :size="18" weight="fill" class="r-ic" />
            <span class="r-name body-sm strong">{{ row.name }}</span>
            <span class="r-robot">
              <img v-if="row.image" :src="row.image" :alt="row.robot ?? ''" loading="lazy">
              <span v-else class="r-blank" aria-hidden="true" />
              <span class="r-copy">
                <span class="body-sm">{{ row.robot ?? '—' }}</span>
                <span v-if="row.detail" class="caption">{{ row.detail }}</span>
              </span>
            </span>
            <span class="r-aside mono-sm">{{ row.aside }}</span>
            <PhArrowRight :size="16" weight="bold" class="r-go" />
          </NuxtLink>
        </li>
      </ul>
    </div>
  </section>
</template>

<style scoped>
.summary { border-radius: var(--radius-xl); }
.s-in { position: relative; z-index: 1; padding: var(--space-6); display: grid; gap: var(--space-5); }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.stat { display: grid; gap: 2px; padding: 14px 16px; border-radius: 16px; background: #fff; box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.07); }
.stat .mono-lg { font-size: 22px; font-weight: 700; color: var(--ink-strong); }
.rows { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.row { display: grid; grid-template-columns: 18px minmax(160px, 1fr) minmax(0, 1.6fr) auto 16px; gap: 14px; align-items: center; padding: 10px 14px; border-radius: 14px; background: rgba(255, 255, 255, 0.65); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); color: inherit; transition: box-shadow var(--dur-fast) var(--ease); }
.row:hover { box-shadow: inset 0 0 0 1.5px var(--brand-400); }
.row.ok .r-ic { color: var(--brand-600); }
.row.warn .r-ic { color: #d69a2d; }
.row.todo .r-ic { color: var(--ink-faint); }
.row.todo .r-name, .row.todo .r-robot { color: var(--ink-muted); }
.r-robot { display: flex; align-items: center; gap: 10px; min-width: 0; }
.r-robot img { width: 44px; height: 34px; object-fit: contain; border-radius: 8px; background: #e9eeec; flex: none; }
.r-blank { width: 44px; height: 34px; flex: none; }
.r-copy { display: grid; gap: 1px; min-width: 0; }
.r-aside { color: var(--ink-muted); white-space: nowrap; }
.r-go { color: var(--ink-faint); }
.row:hover .r-go { color: var(--link); }
@media (max-width: 900px) {
  .row { grid-template-columns: 18px minmax(0, 1fr) 16px; }
  .r-robot, .r-aside { grid-column: 2; }
}
</style>
