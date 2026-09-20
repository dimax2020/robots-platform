<script setup lang="ts">
defineProps<{ title: string; lead?: string; label?: string }>()
</script>

<template>
  <div class="ah" v-reveal>
    <div class="ah-text">
      <div v-if="label" class="label">{{ label }}</div>
      <h1 class="h1">{{ title }}</h1>
      <p v-if="lead" class="body muted">{{ lead }}</p>
    </div>
    <div v-if="$slots.default" class="ah-actions"><slot /></div>
  </div>
</template>

<style scoped>
.ah { display: flex; justify-content: space-between; align-items: flex-end; gap: var(--space-6); }
.ah-text { display: grid; gap: 8px; max-width: 68ch; }
.ah-actions { display: flex; gap: 8px; flex: none; }
</style>
