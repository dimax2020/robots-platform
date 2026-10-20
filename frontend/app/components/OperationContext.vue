<script setup lang="ts">
import { PhMapPin } from '@phosphor-icons/vue'
import type { OperationContext } from '~/composables/usePlatformCompare'

/** Где работает процесс — одной меткой. Технические условия демо-расчёта пользователю не показываем. */
defineProps<{ operation?: OperationContext | null }>()
</script>

<template>
  <span v-if="operation?.zone" class="zone caption"><PhMapPin :size="14" weight="bold" />Рабочая зона: {{ operation.zone }}</span>
</template>

<style scoped>
.zone { display: inline-flex; align-items: center; gap: 6px; justify-self: start; padding: 6px 12px; border-radius: 999px; background: rgba(15, 20, 19, 0.05); color: var(--ink-body); font-weight: 600; }
.zone svg { color: var(--brand-600); }
</style>
