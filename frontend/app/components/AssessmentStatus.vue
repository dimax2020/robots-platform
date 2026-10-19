<script setup lang="ts">
import type { MatchHit } from '~/composables/usePlatformCompare'
defineProps<{ hit: MatchHit }>()
const labels: Record<string, string> = { pass: 'Подходит', conditional: 'С условием', unknown: 'Недостаточно данных', fail: 'Несовместим' }
const tones: Record<string, 'ok' | 'warn' | 'info' | 'danger'> = { pass: 'ok', conditional: 'warn', unknown: 'info', fail: 'danger' }
</script>

<template>
  <div class="assessment-status">
    <DemoSyntheticNotice v-if="hit.demo_synthetic?.length" :values="hit.demo_synthetic" />
    <div><span class="caption">Техническая применимость: </span><UiBadge :tone="tones[hit.verdict] || 'info'" size="sm">{{ hit.uses_demo_synthetic && hit.verdict === 'pass' ? 'Подходит при демодопущениях' : labels[hit.verdict] || hit.verdict }}</UiBadge></div>
    <p v-if="hit.notes.length" class="caption">{{ hit.notes.join(' · ') }}</p>
    <p class="caption">Количество: {{ hit.sizing_ready ? `${hit.count?.toLocaleString('ru-RU')} шт.` : 'не определено' }}</p>
    <p v-if="hit.sizing?.reasons.length" class="caption">{{ hit.sizing.reasons.map(r => r.message).join(' · ') }}</p>
    <p class="caption">Экономика: {{ hit.demo_economic_ready ? 'демонстрационный расчёт' : hit.economic_ready ? 'готова к расчёту' : 'неполные данные или ограничения применимости' }}</p>
    <p v-if="hit.economic_reasons?.length" class="caption">{{ hit.economic_reasons.filter(r => !hit.sizing?.reasons.some(s => s.code === r.code)).map(r => r.message).join(' · ') }}</p>
  </div>
</template>

<style scoped>
.assessment-status { display: grid; gap: 6px; text-align: left; }
.assessment-status p { margin: 0; }
</style>
