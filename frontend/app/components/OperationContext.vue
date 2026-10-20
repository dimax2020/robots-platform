<script setup lang="ts">
import type { OperationContext } from '~/composables/usePlatformCompare'
import { formatDemoValue } from '~/utils/demoSynthetic'
defineProps<{ operation?: OperationContext | null }>()
</script>

<template>
  <UiCallout v-if="operation" tone="info" :title="operation.zone">
    <p>{{ operation.explanation }}</p>
    <details>
      <summary>Условия операции · допущения DEV</summary>
      <dl>
        <template v-for="(field, key) in operation.fields" :key="key">
          <dt>{{ field.label }}</dt>
          <dd>{{ formatDemoValue(operation.effective_fields[key] ?? field.value) }} {{ field.unit }}. {{ field.explanation }}</dd>
        </template>
      </dl>
    </details>
  </UiCallout>
</template>

<style scoped>
p { margin: 0 0 8px; }
summary { cursor: pointer; }
dt { font-weight: 600; margin-top: 8px; }
dd { margin-left: 0; }
</style>
