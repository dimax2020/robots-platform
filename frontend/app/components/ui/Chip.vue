<script setup lang="ts">
import { PhX } from '@phosphor-icons/vue'
withDefaults(defineProps<{
  active?: boolean
  removable?: boolean
  count?: number | string
  graphite?: boolean
}>(), {})
defineEmits<{ remove: [] }>()
</script>

<template>
  <button type="button" class="chip" :class="{ active, removable, graphite }">
    <span class="chip-label"><slot /></span>
    <span v-if="count !== undefined" class="chip-count">{{ count }}</span>
    <span v-if="removable" class="chip-x" aria-label="Снять фильтр" @click.stop="$emit('remove')"><PhX :size="12" weight="bold" /></span>
  </button>
</template>

<style scoped>
.chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 0 14px;
  border-radius: var(--radius-pill);
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-body);
  background: rgba(255, 255, 255, 0.6);
  box-shadow: inset 0 0 0 1px var(--border-hairline), inset 0 1px 0 rgba(255, 255, 255, 0.9);
  -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px);
  transition: background var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease);
  white-space: nowrap;
}
.chip:hover { background: #fff; box-shadow: inset 0 0 0 1px var(--border-strong), inset 0 1px 0 rgba(255, 255, 255, 0.9); }
.chip:active { transform: translateY(1px); }
.chip-count { font-family: var(--font-mono); font-size: 12px; color: var(--ink-muted); font-variant-numeric: tabular-nums; }
.chip.active { background: var(--action-fill); color: var(--on-brand); box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18); }
.chip.active .chip-count { color: rgba(255, 255, 255, 0.7); }
.chip.removable { background: var(--surface-brand-tint); color: var(--brand-ink); box-shadow: inset 0 0 0 1px rgba(10, 107, 69, 0.18); padding-right: 8px; }
.chip.removable .chip-count { color: var(--brand-700); }
.chip-x { display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; border-radius: 50%; background: rgba(4, 48, 31, 0.08); transition: background var(--dur-fast) var(--ease); }
.chip-x:hover { background: rgba(4, 48, 31, 0.18); }
.chip.graphite { background: rgba(255, 255, 255, 0.07); color: var(--ink-on-graphite); box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.14); }
.chip.graphite .chip-count { color: var(--ink-muted-graphite); }
.chip.graphite.active { background: var(--brand-400); color: var(--brand-900); }
</style>
