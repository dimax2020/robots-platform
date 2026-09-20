<script setup lang="ts">
withDefaults(defineProps<{
  variant?: 'primary' | 'secondary' | 'ghost' | 'onGraphite' | 'glass' | 'danger'
  size?: 'lg' | 'md' | 'sm'
  to?: string
  disabled?: boolean
  block?: boolean
  type?: 'button' | 'submit'
}>(), { variant: 'primary', size: 'md', type: 'button' })
</script>

<template>
  <NuxtLink v-if="to && !disabled" :to="to" class="btn" :class="[`btn-${variant}`, `btn-${size}`, { block }]">
    <slot name="icon" />
    <span class="btn-label"><slot /></span>
    <slot name="after" />
  </NuxtLink>
  <button v-else :type="type" class="btn" :class="[`btn-${variant}`, `btn-${size}`, { block }]" :disabled="disabled">
    <slot name="icon" />
    <span class="btn-label"><slot /></span>
    <slot name="after" />
  </button>
</template>

<style scoped>
.btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  white-space: nowrap;
  font-weight: 700;
  letter-spacing: -0.005em;
  border-radius: var(--radius-sm);
  transition: background var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease), border-color var(--dur-fast) var(--ease);
  user-select: none;
}
.btn:active:not(:disabled) { transform: translateY(1px); }
.btn:disabled { opacity: 0.45; cursor: not-allowed; }
.block { width: 100%; }

.btn-lg { min-height: 52px; padding: 0 24px; font-size: 16px; border-radius: 12px; }
.btn-md { min-height: 44px; padding: 0 18px; font-size: 15px; }
.btn-sm { min-height: 36px; padding: 0 14px; font-size: 14px; }

.btn-primary { background: var(--action-fill); color: var(--on-brand); box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.18), 0 1px 2px rgba(4, 48, 31, 0.2); }
.btn-primary:hover:not(:disabled) { background: var(--action-fill-hover); box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22), 0 6px 18px rgba(10, 107, 69, 0.28); }

.btn-secondary { background: rgba(255, 255, 255, 0.72); color: var(--ink-strong); box-shadow: inset 0 0 0 1px var(--border-hairline), var(--shadow-sm); -webkit-backdrop-filter: blur(12px); backdrop-filter: blur(12px); }
.btn-secondary:hover:not(:disabled) { background: #fff; box-shadow: inset 0 0 0 1px var(--border-strong), var(--shadow-md); }

.btn-ghost { background: transparent; color: var(--ink-strong); }
.btn-ghost:hover:not(:disabled) { background: rgba(15, 20, 19, 0.06); }

.btn-onGraphite { background: rgba(255, 255, 255, 0.08); color: var(--ink-on-graphite); box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.2); -webkit-backdrop-filter: blur(12px); backdrop-filter: blur(12px); }
.btn-onGraphite:hover:not(:disabled) { background: rgba(255, 255, 255, 0.14); box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.3), var(--glow-brand); }

.btn-glass {
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.7), rgba(255, 255, 255, 0.35)), rgba(255, 255, 255, 0.4);
  color: var(--ink-strong);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.9), 0 0 0 1px rgba(15, 20, 19, 0.08), var(--shadow-md);
  -webkit-backdrop-filter: blur(18px) saturate(160%);
  backdrop-filter: blur(18px) saturate(160%);
}
.btn-glass:hover:not(:disabled) { box-shadow: inset 0 1px 0 rgba(255, 255, 255, 1), 0 0 0 1px rgba(15, 20, 19, 0.12), var(--shadow-lg); }

.btn-danger { background: var(--state-danger-tint); color: var(--state-danger); }
.btn-danger:hover:not(:disabled) { background: #f7cfcc; }

.btn :deep(svg) { flex: none; }
</style>
