<script setup lang="ts">
/* Что именно уйдёт в каталог, обычными словами. Одинаково видно и производителю, и администратору. */
defineProps<{ facts: { label: string; value: string }[] }>()
</script>

<template>
  <dl v-if="facts.length" class="facts">
    <div v-for="item in facts" :key="item.label + item.value" class="line">
      <dt>{{ item.label }}</dt>
      <dd>{{ item.value }}</dd>
    </div>
  </dl>
</template>

<style scoped>
.facts { display: grid; gap: 6px; margin: 0; }
.line { display: grid; grid-template-columns: minmax(108px, 160px) minmax(0, 1fr); gap: 8px 12px; align-items: start; min-width: 0; }
dt { color: var(--ink-muted); font-size: 13px; font-weight: 600; }
dd { margin: 0; min-width: 0; color: var(--ink-strong); font-size: 14px; line-height: 1.4; overflow-wrap: anywhere; }
@media (max-width: 720px) {
  .line { grid-template-columns: 1fr; gap: 2px; }
}
</style>
