<script setup lang="ts">
import { PhCaretDown, PhFunction } from '@phosphor-icons/vue'
/** Метка «раскрывается»: ставится внутрь кнопки, у которой под собой формула или расшифровка. */
withDefaults(defineProps<{ open?: boolean; label?: string; dark?: boolean }>(), { label: 'формула' })
</script>

<template>
  <span class="xh" :class="{ open, dark, bare: !label }" aria-hidden="true">
    <PhFunction :size="12" weight="bold" />
    <span v-if="label" class="xh-t">{{ label }}</span>
    <PhCaretDown :size="10" weight="bold" class="xh-caret" />
  </span>
</template>

<style scoped>
.xh {
  display: inline-flex; align-items: center; gap: 4px; flex: none;
  height: 22px; padding: 0 8px; border-radius: 999px;
  font-size: 11px; font-weight: 700; line-height: 1; white-space: nowrap;
  color: var(--link); background: var(--surface-brand-tint); box-shadow: inset 0 0 0 1px rgba(10, 107, 69, 0.14);
  transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
}
.xh.bare { padding: 0 6px; }
.xh-caret { transition: transform var(--dur-fast) var(--ease); }
.xh.open .xh-caret { transform: rotate(180deg); }
button:hover .xh, .xh.open { background: var(--brand-600); color: #fff; box-shadow: none; }
.xh.dark { color: var(--brand-300); background: rgba(98, 232, 174, 0.12); box-shadow: inset 0 0 0 1px rgba(98, 232, 174, 0.24); }
button:hover .xh.dark, .xh.dark.open { background: var(--brand-400); color: var(--brand-900); box-shadow: none; }
@media print { .xh { display: none; } }
</style>
