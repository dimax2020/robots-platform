<script setup lang="ts">
import type { SelectionAssumption } from '~/composables/usePlatformCompare'
import { formatDemoValue } from '~/utils/demoSynthetic'
defineProps<{ values: SelectionAssumption[] }>()
const origin = (value: string) => ({ demo_synthetic: 'демодополнение DEV', catalog_assumption: 'допущение из источника каталога', derived_assumption: 'вывод из рабочей скорости с грузом', selection_policy: 'допущение предварительной оценки' } as Record<string, string>)[value] || value
</script>

<template>
  <ul class="assumptions caption">
    <li v-for="item in values" :key="item.key">
      <strong>{{ item.label }}: {{ formatDemoValue(item.value) }} {{ item.unit }}</strong>
      <p>{{ item.explanation }}</p>
      <p>Основание: {{ origin(item.origin) }}<template v-if="item.source?.publisher"> · {{ item.source.publisher }}</template><template v-if="item.source_id"> · источник №{{ item.source_id }}</template>.</p>
      <p v-for="ref in item.references" :key="ref.url || ref.title">
        Ориентир: <a v-if="ref.url && /^https?:\/\//.test(ref.url)" :href="ref.url" target="_blank" rel="noopener noreferrer">{{ ref.title }}</a><span v-else>{{ ref.title }}</span>
      </p>
      <p v-if="item.requires_vendor_confirmation">Необходимо уточнить у вендора.</p>
    </li>
  </ul>
</template>

<style scoped>
.assumptions { padding-left: 18px; text-align: left; }
li { margin: 10px 0; }
p { margin: 4px 0; }
</style>
