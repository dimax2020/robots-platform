<script setup lang="ts">
import type { AttrValue } from '~/data/catalog'
const props = defineProps<{ attr: AttrValue; align?: 'left' | 'right'; compact?: boolean }>()
const display = computed(() => {
  const v = props.attr.value
  if (typeof v === 'number') return v.toLocaleString('ru-RU')
  return v ?? ''
})
</script>

<template>
  <span class="cell" :class="[attr.status, align]">
    <template v-if="attr.status === 'known'">
      <span class="v mono-md">{{ display }}<span v-if="attr.unit" class="unit"> {{ attr.unit }}</span></span>
      <UiSourceTag v-if="attr.sourceId" :source-id="attr.sourceId" :quote="attr.quote" :align="align === 'right' ? 'right' : 'left'" />
    </template>
    <span v-else-if="attr.status === 'unknown'" class="state state-unknown">нет данных</span>
    <span v-else class="state state-na">не применимо</span>
  </span>
</template>

<style scoped>
.cell { display: inline-flex; align-items: center; gap: 8px; }
.cell.right { justify-content: flex-end; }
.v { color: var(--ink-strong); }
.unit { color: var(--ink-muted); font-weight: 500; }
.state { font-size: 12px; font-weight: 600; padding: 3px 8px; border-radius: 6px; }
.state-unknown { background: var(--state-warn-tint); color: var(--state-warn); }
.state-na { background: var(--state-neutral-tint); color: var(--state-neutral); }
</style>
