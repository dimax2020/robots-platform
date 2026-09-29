<script setup lang="ts">
/* Теги в не более чем `rows` строк. То, что не влезло, заменяется на «и ещё N». */
const props = withDefaults(defineProps<{ tags: string[]; rows?: number }>(), { rows: 2 })

const root = ref<HTMLElement | null>(null)
const shown = ref(props.tags.length)
const measuring = ref(true)
let token = 0

const rowCount = () => {
  const el = root.value
  if (!el) return 0
  return new Set(Array.from(el.children).map((child) => (child as HTMLElement).offsetTop)).size
}

async function fit() {
  const run = ++token
  measuring.value = true
  shown.value = props.tags.length
  await nextTick()
  while (run === token && rowCount() > props.rows && shown.value > 0) {
    shown.value -= 1
    await nextTick()
  }
  if (run === token) measuring.value = false
}

let observer: ResizeObserver | null = null
let lastWidth = 0
onMounted(() => {
  fit()
  if (!root.value || typeof ResizeObserver === 'undefined') return
  lastWidth = root.value.clientWidth
  observer = new ResizeObserver(() => {
    const width = root.value?.clientWidth ?? 0
    if (Math.abs(width - lastWidth) < 2) return
    lastWidth = width
    fit()
  })
  observer.observe(root.value)
})
onBeforeUnmount(() => { observer?.disconnect(); token++ })
watch(() => props.tags.join('|'), fit)
</script>

<template>
  <div ref="root" class="tags" :class="{ measuring }">
    <span v-for="tag in tags.slice(0, shown)" :key="tag" class="tag">{{ tag }}</span>
    <span v-if="shown < tags.length" class="tag more">и ещё {{ tags.length - shown }}</span>
  </div>
</template>

<style scoped>
.tags { display: flex; flex-wrap: wrap; gap: 6px; }
.tags.measuring { visibility: hidden; }
.tag { font-size: 12px; font-weight: 600; padding: 4px 10px; border-radius: var(--radius-pill); background: rgba(15, 20, 19, 0.06); color: var(--ink-body); white-space: nowrap; }
.tag.more { background: rgba(15, 20, 19, 0.12); color: var(--ink-strong); }
</style>
