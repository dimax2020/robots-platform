<script setup lang="ts">
import { PhInfo, PhWarning } from '@phosphor-icons/vue'
import { PRELIMINARY, type EconReport } from '~/composables/usePlatformEconomy'

const props = defineProps<{
  report?: Pick<EconReport, 'status' | 'scope' | 'uses_demo_synthetic' | 'disclaimer'> | null
  text?: string
}>()
const incomplete = computed(() => props.report?.status === 'incomplete')
const labels = computed(() => [
  ...(props.report?.scope === 'automation_program' ? ['Охват: программа роботизации'] : []),
])
const fullText = computed(() => props.text || props.report?.disclaimer || PRELIMINARY)
</script>

<template>
  <details class="assessment-notice" :class="{ incomplete }">
    <summary>
      <component :is="incomplete ? PhWarning : PhInfo" :size="18" weight="duotone" class="notice-icon" />
      <strong>{{ incomplete ? 'Расчёт неполный' : 'Предварительная оценка' }}</strong>
      <span v-for="label in labels" :key="label" class="notice-label">{{ label }}</span>
      <span class="notice-more">Подробнее</span>
    </summary>
    <div class="notice-body">
      <p class="notice-text">{{ fullText }}</p>
      <slot />
    </div>
  </details>
</template>

<style scoped>
.assessment-notice { padding: 12px 16px; border: 1px solid #d4e1e9; border-radius: 12px; background: #f5f9fc; color: var(--ink-body); font-size: 14px; line-height: 1.5; }
.assessment-notice.incomplete { border-color: #eadbb5; background: #fffcf4; }
summary { display: flex; align-items: center; flex-wrap: wrap; gap: 6px 12px; cursor: pointer; list-style: none; }
summary::-webkit-details-marker { display: none; }
summary:focus-visible { outline: 3px solid var(--brand-400); outline-offset: 4px; border-radius: 4px; }
.notice-icon { flex: none; color: var(--state-info); }
.incomplete .notice-icon { color: var(--state-warn); }
.notice-label { color: var(--ink-muted); }
.notice-more { margin-left: auto; color: var(--link); text-decoration: underline; }
.notice-more::before { content: '▸ '; }
[open] > summary .notice-more::before { content: '▾ '; }
.notice-body { margin-top: 12px; display: grid; gap: 12px; }
.notice-text { margin: 0; }
@media print {
  .assessment-notice { padding: 8px; font-size: 10px; break-inside: avoid; background: none; }
  .assessment-notice::details-content { content-visibility: visible; display: block; }
  .notice-body { display: block !important; }
  .notice-more { display: none; }
}
</style>
