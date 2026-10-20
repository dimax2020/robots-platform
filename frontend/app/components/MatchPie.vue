<script setup lang="ts">
/* Круг без библиотек: на слабом компьютере это просто заливка, не холст и не график. */
const props = defineProps<{
  green: number
  red: number
  greenLabel: string
  redLabel: string
  note?: string
}>()

const total = computed(() => props.green + props.red)
const turn = computed(() => (total.value ? (props.green / total.value) * 100 : 0))
const paint = computed(() => {
  if (!total.value) return { background: 'rgba(15, 20, 19, 0.08)' }
  return { background: `conic-gradient(var(--state-ok) 0 ${turn.value}%, var(--state-danger) ${turn.value}% 100%)` }
})
const caption = computed(() => `${props.greenLabel}: ${props.green}. ${props.redLabel}: ${props.red}.`)
</script>

<template>
  <div class="pie-box">
    <div class="pie" :style="paint" role="img" :aria-label="caption" />
    <div class="legend">
      <div class="line"><i class="swatch ok" /> <span>{{ greenLabel }}</span> <b>{{ green }}</b></div>
      <div class="line"><i class="swatch bad" /> <span>{{ redLabel }}</span> <b>{{ red }}</b></div>
      <p v-if="note" class="caption">{{ note }}</p>
      <p v-else-if="!total" class="caption">Пока нечего показать.</p>
    </div>
  </div>
</template>

<style scoped>
.pie-box { display: flex; gap: 18px; align-items: center; flex-wrap: wrap; }
.pie { width: 132px; height: 132px; border-radius: 50%; flex: none; box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.legend { display: grid; gap: 8px; min-width: 180px; }
.line { display: flex; align-items: center; gap: 8px; font-size: 14px; color: var(--ink-body); }
.line b { margin-left: auto; font-variant-numeric: tabular-nums; color: var(--ink-strong); }
.swatch { width: 10px; height: 10px; border-radius: 50%; flex: none; }
.swatch.ok { background: var(--state-ok); }
.swatch.bad { background: var(--state-danger); }
</style>
