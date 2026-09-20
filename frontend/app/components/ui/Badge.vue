<script setup lang="ts">
withDefaults(defineProps<{
  tone?: 'ok' | 'warn' | 'danger' | 'info' | 'neutral' | 'brand'
  pulse?: boolean
  size?: 'sm' | 'md'
  mono?: boolean
}>(), { tone: 'neutral', size: 'md' })
</script>

<template>
  <span class="badge" :class="[`tone-${tone}`, `size-${size}`, { mono }]">
    <span v-if="pulse && tone === 'ok'" class="pulse" aria-hidden="true" />
    <slot />
  </span>
</template>

<style scoped>
.badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: var(--radius-pill);
  font-weight: 700;
  white-space: nowrap;
  line-height: 1;
}
.size-md { padding: 6px 10px; font-size: 12px; }
.size-sm { padding: 4px 8px; font-size: 11px; }
.mono { font-family: var(--font-mono); font-weight: 500; letter-spacing: 0.04em; }
.tone-ok { background: var(--state-ok-tint); color: var(--state-ok); }
.tone-warn { background: var(--state-warn-tint); color: var(--state-warn); }
.tone-danger { background: var(--state-danger-tint); color: var(--state-danger); }
.tone-info { background: var(--state-info-tint); color: var(--state-info); }
.tone-neutral { background: var(--state-neutral-tint); color: var(--state-neutral); }
.tone-brand { background: var(--brand-900); color: var(--brand-300); }
.pulse { width: 6px; height: 6px; }
.pulse::after { inset: -3px; }
</style>
