<script setup lang="ts">
withDefaults(defineProps<{
  label: string
  value: string
  note?: string
  graphite?: boolean
  size?: 'md' | 'lg'
}>(), { size: 'md' })
</script>

<template>
  <div class="stat" :class="{ graphite, lg: size === 'lg' }">
    <div class="label">{{ label }}</div>
    <div class="value">{{ value }}</div>
    <div v-if="note" class="caption note">{{ note }}</div>
  </div>
</template>

<style scoped>
.stat { display: grid; gap: 6px; align-content: start; }
.value { font-family: var(--font-display); font-weight: 600; font-size: 32px; line-height: 1.05; letter-spacing: -0.02em; color: var(--ink-strong); font-variant-numeric: tabular-nums; }
.lg .value { font-size: 44px; }
.graphite .value { color: var(--ink-on-graphite); }
.graphite .label, .graphite .note { color: var(--ink-muted-graphite); }
.note { max-width: 26ch; }
</style>
