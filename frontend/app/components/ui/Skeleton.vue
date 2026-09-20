<script setup lang="ts">
withDefaults(defineProps<{ w?: string; h?: string; r?: string }>(), { w: '100%', h: '16px', r: '8px' })
</script>

<template>
  <span class="skeleton" :style="{ width: w, height: h, borderRadius: r, display: 'block' }" aria-hidden="true" />
</template>
