<script setup lang="ts">
import { platformGet } from '~/composables/usePlatform'

const route = useRoute()
const slug = computed(() => route.params.slug as string)
const missing = ref(false)

onMounted(async () => {
  try {
    await platformGet(`/catalog/products/${slug.value}`)
    await navigateTo(`/catalog/card/${slug.value}`, { replace: true })
  } catch {
    missing.value = true
  }
})
useHead({ title: 'Карточка каталога' })
</script>

<template>
  <section v-if="missing" class="container miss">
    <div class="label">Каталог</div>
    <h1 class="hero-2">Карточка в новом каталоге</h1>
    <p class="body muted">Этой модели нет среди карточек платформы. Откройте витрину и выберите решение оттуда.</p>
    <UiButton to="/catalog">К витрине</UiButton>
  </section>
</template>

<style scoped>
.miss { padding-top: var(--space-16); padding-bottom: var(--space-16); display: grid; gap: var(--space-4); max-width: 62ch; }
</style>
