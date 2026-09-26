<script setup lang="ts">
import katex from 'katex'

const props = defineProps<{ tex: string; display?: boolean }>()
const html = computed(() => katex.renderToString(props.tex || '', {
  displayMode: Boolean(props.display),
  throwOnError: false,
  strict: 'ignore',
  output: 'html',
}))
</script>

<template>
  <span class="tex" :class="{ block: display }" v-html="html" />
</template>

<style scoped>
.tex { color: inherit; }
.tex.block { display: block; overflow-x: auto; overflow-y: hidden; padding: 2px 0; }
.tex :deep(.katex) { font-size: 1.08em; }
.tex.block :deep(.katex-display) { margin: 0; text-align: left; }
.tex.block :deep(.katex-display > .katex) { text-align: left; }
</style>
