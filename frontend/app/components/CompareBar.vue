<script setup lang="ts">
import { PhScales, PhX } from '@phosphor-icons/vue'
import { products } from '~/data/catalog'
const { ids, clear, toggle } = useCompare()
const route = useRoute()
const items = computed(() => ids.value.map((id) => products.find((p) => p.id === id)!).filter(Boolean))
const visible = computed(() => ids.value.length >= 2 && route.path.startsWith('/catalog') && route.path !== '/catalog/compare')
</script>

<template>
  <Transition name="bar">
    <div v-if="visible" class="bar-wrap no-print">
      <div class="bar glass-graphite">
        <div class="thumbs">
          <span v-for="p in items.slice(0, 4)" :key="p.id" class="thumb" :title="p.name">
            <img :src="p.image" :alt="p.name">
            <button type="button" class="rm" :aria-label="`Убрать ${p.name}`" @click="toggle(p.id)"><PhX :size="10" weight="bold" /></button>
          </span>
        </div>
        <div class="text">
          <div class="h4">К сравнению: {{ items.length }} {{ items.length === 1 ? 'модель' : items.length < 5 ? 'модели' : 'моделей' }}</div>
          <div class="caption">Таблица по одним и тем же полям справочника</div>
        </div>
        <div class="actions">
          <UiButton variant="onGraphite" size="sm" @click="clear">Очистить</UiButton>
          <UiButton to="/catalog/compare" size="sm"><template #icon><PhScales :size="16" weight="bold" /></template>Сравнить</UiButton>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.bar-wrap { position: fixed; left: 0; right: 0; bottom: 16px; z-index: var(--z-sticky); display: flex; justify-content: center; padding: 0 24px; pointer-events: none; }
.bar { pointer-events: auto; display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 20px; padding: 12px 12px 12px 14px; border-radius: 18px; min-width: 560px; }
.thumbs { display: flex; }
.thumb { position: relative; width: 44px; height: 44px; border-radius: 12px; overflow: hidden; background: #fff; box-shadow: 0 0 0 2px var(--surface-graphite); margin-left: -10px; }
.thumb:first-child { margin-left: 0; }
.thumb img { width: 100%; height: 100%; object-fit: cover; }
.rm { position: absolute; top: 2px; right: 2px; width: 16px; height: 16px; border-radius: 50%; background: var(--surface-graphite); color: #fff; display: inline-flex; align-items: center; justify-content: center; opacity: 0; transition: opacity var(--dur-fast) var(--ease); }
.thumb:hover .rm { opacity: 1; }
.text .h4 { color: var(--ink-on-graphite); }
.text .caption { color: var(--ink-muted-graphite); }
.actions { display: flex; gap: 8px; }
.bar-enter-active, .bar-leave-active { transition: opacity var(--dur-mid) var(--ease), transform var(--dur-mid) var(--ease); }
.bar-enter-from, .bar-leave-to { opacity: 0; transform: translateY(12px); }
</style>
