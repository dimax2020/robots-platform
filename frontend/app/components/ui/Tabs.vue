<script setup lang="ts">
const props = defineProps<{ tabs: { id: string; label: string; count?: number }[]; modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [string] }>()
const idx = computed(() => Math.max(0, props.tabs.findIndex((t) => t.id === props.modelValue)))
</script>

<template>
  <div class="tabs" role="tablist" :style="{ '--n': tabs.length, '--i': idx }">
    <span class="thumb" aria-hidden="true" />
    <button
      v-for="t in tabs" :key="t.id" role="tab" type="button" class="tab" :class="{ on: t.id === modelValue }" :aria-selected="t.id === modelValue"
      @click="emit('update:modelValue', t.id)"
    >
      {{ t.label }}<span v-if="t.count !== undefined" class="count">{{ t.count }}</span>
    </button>
  </div>
</template>

<style scoped>
.tabs {
  position: relative;
  display: grid;
  grid-template-columns: repeat(var(--n), minmax(0, 1fr));
  padding: 4px;
  border-radius: var(--radius-md);
  background: rgba(15, 20, 19, 0.05);
  box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.04);
}
.thumb {
  position: absolute;
  top: 4px; bottom: 4px;
  left: 4px;
  width: calc((100% - 8px) / var(--n));
  transform: translateX(calc(var(--i) * 100%));
  border-radius: 9px;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.95), rgba(255, 255, 255, 0.75));
  box-shadow: inset 0 1px 0 #fff, 0 1px 2px rgba(15, 20, 19, 0.08), 0 6px 18px rgba(15, 20, 19, 0.08);
  transition: transform var(--dur-mid) var(--ease);
}
.tab { position: relative; z-index: 1; min-height: 40px; padding: 0 14px; border-radius: 9px; font-size: 14px; font-weight: 600; color: var(--ink-muted); display: inline-flex; align-items: center; justify-content: center; gap: 8px; transition: color var(--dur-fast) var(--ease); white-space: nowrap; }
.tab.on { color: var(--ink-strong); }
.count { font-family: var(--font-mono); font-size: 11px; padding: 2px 6px; border-radius: 6px; background: rgba(15, 20, 19, 0.06); color: var(--ink-muted); }
.tab.on .count { background: var(--surface-brand-tint); color: var(--brand-ink); }
</style>
