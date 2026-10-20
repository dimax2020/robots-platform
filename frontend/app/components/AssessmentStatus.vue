<script setup lang="ts">
import type { MatchHit } from '~/composables/usePlatformCompare'
import { significantReasons, countExplanation, clarificationMessages } from '~/utils/assessmentPresentation'
import { eligibleForEconomy } from '~/utils/fleetSelection'
defineProps<{ hit: MatchHit }>()
</script>

<template>
  <div class="assessment-status">
    <p v-for="item in significantReasons(hit).slice(0, 2)" :key="item.code + item.message" class="caption">{{ item.message }}</p>
    <p class="caption">Количество: {{ countExplanation(hit) }}</p>
    <p class="caption">Экономика: {{ eligibleForEconomy(hit) ? (hit.demo_economic_ready ? 'доступен демонстрационный расчёт' : 'доступна к расчёту') : hit.verdict === 'fail' ? 'робот несовместим с требованиями' : 'требуется уточнить исходные данные' }}</p>
    <details v-if="clarificationMessages(hit).length || hit.assumptions?.length" class="clarifications">
      <summary>Что необходимо уточнить</summary>
      <AssumptionList v-if="hit.assumptions?.length" :values="hit.assumptions" />
      <ul v-if="clarificationMessages(hit).length" class="caption">
        <li v-for="message in clarificationMessages(hit)" :key="message">{{ message }}</li>
      </ul>
    </details>
  </div>
</template>

<style scoped>
.assessment-status { display: grid; gap: 6px; text-align: left; }
.assessment-status p { margin: 0; }
summary { cursor: pointer; font-size: 13px; font-weight: 600; }
ul { padding-left: 18px; }
</style>
