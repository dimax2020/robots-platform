<script setup lang="ts">
import { availabilityLabel, availabilityTone, type Availability } from '~/data/catalog'

/** УГТ и стадия эксплуатации робота. Если общий фильтр готовности отправил робота в «Уточнить», метки подсвечены. */
const props = defineProps<{ trl?: number | null; stage?: string | null; flagged?: boolean }>()
const stageCode = computed(() => (props.stage && props.stage in availabilityLabel ? props.stage as Availability : null))
</script>

<template>
  <span v-if="trl != null || stageCode" class="ready">
    <UiBadge v-if="trl != null" :tone="flagged ? 'warn' : 'neutral'" size="sm" title="Уровень готовности технологии, 1–9">УГТ {{ trl }}</UiBadge>
    <UiBadge v-if="stageCode" :tone="flagged && stageCode === 'rnd' ? 'warn' : availabilityTone[stageCode]" size="sm">{{ availabilityLabel[stageCode] }}</UiBadge>
  </span>
</template>

<style scoped>
.ready { display: inline-flex; flex-wrap: wrap; gap: 4px; }
</style>
