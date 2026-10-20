<script setup lang="ts">
import type { MatchHit } from '~/composables/usePlatformCompare'
import { significantReasons, clarificationMessages } from '~/utils/assessmentPresentation'

/** Почему робот не подошёл или что уточнить — одной строкой, остальное по клику. У подходящего робота пусто: статус говорит сам. */
const props = defineProps<{ hit: MatchHit }>()
const reasons = computed(() => props.hit.verdict === 'pass' ? [] : significantReasons(props.hit).map((item) => item.message))
const more = computed(() => props.hit.verdict === 'pass' ? [] : clarificationMessages(props.hit).filter((message) => !reasons.value.slice(0, 1).includes(message)))
</script>

<template>
  <div v-if="reasons.length || more.length" class="assessment-status">
    <p v-if="reasons[0]" class="caption">{{ reasons[0] }}</p>
    <details v-if="more.length" class="clarifications">
      <summary>{{ hit.verdict === 'fail' ? 'Почему не подходит' : 'Каких данных не хватает' }} · {{ more.length }}</summary>
      <ul class="caption">
        <li v-for="message in more" :key="message">{{ message }}</li>
      </ul>
    </details>
  </div>
</template>

<style scoped>
.assessment-status { display: grid; gap: 4px; text-align: left; }
.assessment-status p { margin: 0; color: var(--ink-body); }
summary { cursor: pointer; font-size: 13px; font-weight: 600; color: var(--link); }
ul { margin: 6px 0 0; padding-left: 18px; display: grid; gap: 2px; }
</style>
