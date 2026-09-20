<script setup lang="ts">
withDefaults(defineProps<{ title: string; lead?: string; label?: string; size?: 'h1' | 'h2' | 'hero-2' | 'display-3' }>(), { size: 'h2' })
</script>

<template>
  <div class="head">
    <div class="text">
      <div v-if="label" class="label">{{ label }}</div>
      <h2 :class="size">{{ title }}</h2>
      <p v-if="lead" class="body-lg muted lead">{{ lead }}</p>
    </div>
    <div v-if="$slots.default" class="aside"><slot /></div>
  </div>
</template>

<style scoped>
.head { display: flex; align-items: flex-end; justify-content: space-between; gap: var(--space-8); margin-bottom: var(--space-8); }
.text { display: grid; gap: var(--space-3); max-width: 880px; }
.lead { max-width: 68ch; }
.aside { display: flex; gap: var(--space-2); flex: none; }
</style>
