<script setup lang="ts">
import { formatDemoValue, formatOrigin, type DemoSyntheticValue } from '~/utils/demoSynthetic'
defineProps<{ values: DemoSyntheticValue[] }>()
</script>

<template>
  <details v-if="values.length" class="demo-synthetic">
    <summary>Синтетические допущения DEV · {{ values.length }}</summary>
    <ul>
      <li v-for="item in values" :key="item.key">
        <strong>{{ item.label }}: {{ formatDemoValue(item.value) }} {{ item.unit }}</strong>
        <span>{{ item.explanation }}</span>
        <small v-for="ref in item.references" :key="ref.url || ref.title">
          Ориентир: <a v-if="ref.url && /^https?:\/\//.test(ref.url)" :href="ref.url" target="_blank" rel="noopener noreferrer">{{ ref.title }}</a><span v-else>{{ ref.title }}</span>
        </small>
        <small>Происхождение: {{ formatOrigin(item.origin) }} · {{ item.requires_vendor_confirmation ? 'требуется подтверждение вендора' : 'требуется проверка параметров и оценки' }}</small>
      </li>
    </ul>
  </details>
</template>

<style scoped>
.demo-synthetic { padding: 10px; border: 1px solid var(--state-warn); border-radius: 10px; font-size: 13px; text-align: left; }
summary { cursor: pointer; font-weight: 700; }
ul { padding-left: 18px; margin: 0; }
li { margin-top: 8px; }
li span, li small { display: block; margin-top: 4px; }
@media print { .demo-synthetic > * { display: block; } }
</style>
