<script setup lang="ts">
import { PhScales, PhCheck, PhMapPin } from '@phosphor-icons/vue'
import { type Product, availabilityLabel, availabilityTone, formatRub } from '~/data/catalog'

const props = defineProps<{ product: Product; compact?: boolean }>()
const { has, toggle } = useCompare()
const inCompare = computed(() => has(props.product.id))
</script>

<template>
  <article class="card-r glass" :class="{ compact }">
    <NuxtLink :to="`/catalog/${product.slug}`" class="media" :aria-label="product.name">
      <img :src="product.image" :alt="product.name" loading="lazy">
      <span class="badges">
        <UiBadge :tone="availabilityTone[product.availability]" :pulse="product.availability === 'operation'">{{ availabilityLabel[product.availability] }}</UiBadge>
        <UiBadge tone="neutral" mono size="sm">УГТ {{ product.trl }}</UiBadge>
      </span>
    </NuxtLink>
    <div class="body">
      <div class="label">{{ product.solutionType }}</div>
      <NuxtLink :to="`/catalog/${product.slug}`" class="h3 name truncate-2">{{ product.name }}</NuxtLink>
      <div class="vendor body-sm muted"><span class="strong">{{ product.manufacturer }}</span> <PhMapPin :size="12" /> {{ product.city }}</div>
      <dl class="specs">
        <div v-for="h in product.highlights.slice(0, 4)" :key="h.label">
          <dt>{{ h.label }}</dt>
          <dd class="mono-md" :class="{ dim: h.value.startsWith('нет') }">{{ h.value }}</dd>
        </div>
      </dl>
      <div class="foot">
        <div class="price">
          <span class="mono-lg">{{ formatRub(product.priceRub) }}</span>
          <span v-if="product.priceNote" class="caption">{{ product.priceNote }}</span>
        </div>
        <button type="button" class="cmp" :class="{ on: inCompare }" :aria-pressed="inCompare" @click="toggle(product.id)">
          <PhCheck v-if="inCompare" :size="16" weight="bold" /><PhScales v-else :size="16" weight="bold" />
          {{ inCompare ? 'В сравнении' : 'Сравнить' }}
        </button>
      </div>
      <div v-if="!product.autoMatch" class="noauto caption">Не участвует в автоподборе: УГТ ниже 7 или стадия разработки</div>
    </div>
  </article>
</template>

<style scoped>
.card-r { display: grid; grid-template-rows: auto 1fr; border-radius: var(--radius-xl); overflow: hidden; height: 100%; transition: transform var(--dur-mid) var(--ease), box-shadow var(--dur-mid) var(--ease); }
.card-r:hover { transform: translateY(-3px); box-shadow: inset 0 1px 0 var(--glass-stroke), 0 0 0 1px var(--glass-stroke-outer), var(--shadow-lg); }
.media { position: relative; display: block; aspect-ratio: 4 / 3; margin: 8px; border-radius: 18px; overflow: hidden; background: #e9eeec; }
.media img { width: 100%; height: 100%; object-fit: cover; transition: transform 600ms var(--ease); }
.card-r:hover .media img { transform: scale(1.03); }
.badges { position: absolute; left: 10px; top: 10px; display: flex; gap: 6px; }
.body { display: grid; gap: 8px; padding: 8px 16px 16px; align-content: start; }
.name { color: var(--ink-strong); }
.vendor { display: flex; align-items: center; gap: 4px; }
.specs { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 12px; margin-top: 6px; padding-top: 12px; border-top: 1px solid rgba(15, 20, 19, 0.08); }
.specs dt { font-size: 12px; color: var(--ink-muted); }
.specs dd { margin: 0; color: var(--ink-strong); }
.specs dd.dim { color: var(--state-warn); font-weight: 500; font-size: 12px; font-family: var(--font-sans); }
.foot { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; margin-top: 8px; }
.price { display: grid; }
.price .mono-lg { color: var(--ink-strong); }
.cmp { display: inline-flex; align-items: center; gap: 6px; height: 36px; padding: 0 12px; border-radius: 10px; font-size: 13px; font-weight: 700; color: var(--ink-strong); background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease); white-space: nowrap; }
.cmp:hover { background: #fff; box-shadow: inset 0 0 0 1px var(--border-strong); }
.cmp.on { background: var(--surface-brand-tint); color: var(--brand-ink); box-shadow: inset 0 0 0 1px rgba(10, 107, 69, 0.2); }
.noauto { padding: 8px 10px; border-radius: 8px; background: var(--state-neutral-tint); }
.compact .specs { display: none; }
</style>
