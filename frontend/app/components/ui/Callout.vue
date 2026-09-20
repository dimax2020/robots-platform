<script setup lang="ts">
import { PhInfo, PhWarning, PhShieldCheck, PhXCircle } from '@phosphor-icons/vue'
withDefaults(defineProps<{ tone?: 'info' | 'warn' | 'ok' | 'danger'; title?: string }>(), { tone: 'info' })
const icons = { info: PhInfo, warn: PhWarning, ok: PhShieldCheck, danger: PhXCircle }
</script>

<template>
  <div class="callout" :class="`tone-${tone}`" role="note">
    <component :is="icons[tone]" :size="20" weight="duotone" class="ic" />
    <div class="body">
      <div v-if="title" class="title">{{ title }}</div>
      <div class="text"><slot /></div>
    </div>
  </div>
</template>

<style scoped>
.callout { display: flex; gap: 12px; padding: 14px 16px; border-radius: var(--radius-md); font-size: 14px; line-height: 1.5; }
.ic { flex: none; margin-top: 1px; }
.title { font-weight: 700; margin-bottom: 2px; }
.tone-info { background: var(--state-info-tint); color: #123f75; }
.tone-info .ic { color: var(--state-info); }
.tone-warn { background: var(--state-warn-tint); color: #5c3700; }
.tone-warn .ic { color: var(--state-warn); }
.tone-ok { background: var(--state-ok-tint); color: var(--brand-ink); }
.tone-ok .ic { color: var(--state-ok); }
.tone-danger { background: var(--state-danger-tint); color: #7a1c19; }
.tone-danger .ic { color: var(--state-danger); }
</style>
