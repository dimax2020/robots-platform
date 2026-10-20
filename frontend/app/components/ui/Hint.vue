<script setup lang="ts">
import { PhLightbulb } from '@phosphor-icons/vue'

/** Подсказка пользователю: что сделать или чего не хватает. Всегда жёлтая — чтобы читалась с первого взгляда. */
withDefaults(defineProps<{ compact?: boolean }>(), { compact: false })
</script>

<template>
  <div class="hint" :class="{ compact }" role="note">
    <PhLightbulb :size="compact ? 14 : 16" weight="fill" class="h-ic" />
    <span class="h-text"><slot /></span>
    <span v-if="$slots.action" class="h-act"><slot name="action" /></span>
  </div>
</template>

<style scoped>
.hint { display: flex; align-items: center; gap: 10px; padding: 9px 12px; border-radius: 12px; background: #fff3cf; box-shadow: inset 0 0 0 1px rgba(214, 154, 45, 0.35); color: #5c3700; font-size: 13.5px; line-height: 1.45; }
.hint.compact { gap: 8px; padding: 5px 10px; border-radius: 9px; font-size: 13px; }
.h-ic { flex: none; color: #d69a2d; align-self: flex-start; margin-top: 2px; }
.compact .h-ic { margin-top: 2px; }
.h-text { flex: 1; min-width: 0; }
.h-act { flex: none; display: inline-flex; align-items: center; gap: 8px; }
</style>
