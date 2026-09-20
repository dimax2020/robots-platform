<script setup lang="ts">
withDefaults(defineProps<{ size?: number; mint?: boolean; wordmark?: boolean; onGraphite?: boolean }>(), { size: 36, wordmark: true })
</script>

<template>
  <NuxtLink to="/" class="logo" :class="{ onGraphite }" aria-label="Платформа роботизации, на главную">
    <span class="mark" :style="{ width: `${size}px`, height: `${size}px` }">
      <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
        <path d="M24 3 42.2 13.5v21L24 45 5.8 34.5v-21L24 3Z" :stroke="mint ? '#62E8AE' : 'currentColor'" stroke-width="2" stroke-linejoin="round" />
        <path d="M14 33 20 21l7 6 6-12" :stroke="mint ? '#62E8AE' : 'currentColor'" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
        <circle cx="33" cy="15" r="3" :fill="mint ? '#2BD18D' : '#14A76F'" />
      </svg>
    </span>
    <span v-if="wordmark" class="word">
      <span class="w1">Платформа</span>
      <span class="w2">роботизации</span>
    </span>
  </NuxtLink>
</template>

<style scoped>
.logo { display: inline-flex; align-items: center; gap: 12px; color: var(--ink-strong); }
.mark { display: inline-flex; border-radius: 10px; background: var(--surface-graphite); color: #f1f5f3; padding: 6px; box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.12); }
.mark svg { width: 100%; height: 100%; }
.word { display: grid; line-height: 1.05; }
.w1 { font-family: var(--font-display); font-weight: 700; font-size: 13px; letter-spacing: -0.01em; }
.w2 { font-size: 12px; font-weight: 600; color: var(--ink-muted); letter-spacing: 0.01em; }
.onGraphite { color: var(--ink-on-graphite); }
.onGraphite .mark { background: rgba(255, 255, 255, 0.08); box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.14); }
.onGraphite .w2 { color: var(--ink-muted-graphite); }
</style>
