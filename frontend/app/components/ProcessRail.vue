<script setup lang="ts">
import { PhCaretDown, PhCaretLeft, PhCaretRight, PhCheckCircle, PhCircle, PhSquaresFour, PhWarningCircle } from '@phosphor-icons/vue'

/**
 * Процессы шага: итог по объекту сверху и все процессы со статусом и коротким итогом этого шага.
 * Один и тот же список на подборе, сравнении и экономике — пользователь всегда видит, где он и сколько осталось.
 * Широкий экран — колонка слева. Узкий — компактная панель «← текущий процесс →», полный список по нажатию.
 */
export interface RailItem { id: string; label: string; to: string; tone?: string; meta?: string }
const props = defineProps<{ summary: RailItem; items: RailItem[]; current?: string }>()

const index = computed(() => props.items.findIndex((item) => item.id === props.current))
const progress = computed(() => index.value >= 0 ? `${index.value + 1} из ${props.items.length}` : `${props.items.length}`)
/* Порядок для стрелок узкой панели: итог, затем процессы. */
const order = computed(() => [props.summary, ...props.items])
const position = computed(() => order.value.findIndex((item) => item.id === props.current))
const currentItem = computed(() => order.value[position.value] ?? props.summary)
const prev = computed(() => position.value > 0 ? order.value[position.value - 1] : null)
const next = computed(() => position.value >= 0 && position.value < order.value.length - 1 ? order.value[position.value + 1] : null)
const open = ref(false)

/* Текущий процесс всегда виден: прокручиваем только сам список, страница остаётся на месте. */
const root = ref<HTMLElement | null>(null)
const reveal = () => nextTick(() => {
  const box = root.value
  const on = box?.querySelector<HTMLElement>('.r-item.on')
  if (!box || !on || box.scrollHeight <= box.clientHeight) return
  const top = on.offsetTop - box.clientHeight / 2 + on.clientHeight / 2
  box.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
})
onMounted(reveal)
watch(() => props.current, () => { open.value = false; reveal() })
watch(open, (value) => { if (value) reveal() })
const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') open.value = false }
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
const icon = (tone?: string) => tone === 'ok' ? PhCheckCircle : tone === 'warn' ? PhWarningCircle : PhCircle
</script>

<template>
  <div class="rail-wrap" :class="{ open }">
    <!-- Узкий экран: стрелки к соседним процессам и текущий процесс; по нажатию — весь список. -->
    <div class="r-bar glass">
      <NuxtLink v-if="prev" :to="prev.to" class="r-step" :aria-label="`Назад: ${prev.label}`"><PhCaretLeft :size="18" weight="bold" /></NuxtLink>
      <span v-else class="r-step off" aria-hidden="true"><PhCaretLeft :size="18" weight="bold" /></span>
      <button type="button" class="r-pick" :aria-expanded="open" aria-controls="process-rail-list" @click="open = !open">
        <component :is="currentItem.id === summary.id ? PhSquaresFour : icon(currentItem.tone)" :size="18" :weight="currentItem.tone === 'ok' || currentItem.tone === 'warn' ? 'fill' : 'bold'" class="r-ico" :class="currentItem.tone" />
        <span class="r-text">
          <span class="r-name">{{ currentItem.label }}</span>
          <span class="r-meta">{{ currentItem.id === summary.id ? `${items.length} процессов` : `процесс ${progress}` }}{{ currentItem.meta ? ` · ${currentItem.meta}` : '' }}</span>
        </span>
        <PhCaretDown :size="16" weight="bold" class="r-caret" />
      </button>
      <NuxtLink v-if="next" :to="next.to" class="r-step" :aria-label="`Дальше: ${next.label}`"><PhCaretRight :size="18" weight="bold" /></NuxtLink>
      <span v-else class="r-step off" aria-hidden="true"><PhCaretRight :size="18" weight="bold" /></span>
    </div>
    <button v-if="open" type="button" class="r-backdrop" aria-label="Закрыть список процессов" @click="open = false" />

    <nav id="process-rail-list" ref="root" class="rail glass" aria-label="Процессы шага">
      <div class="r-head">
        <span class="label">Процессы</span>
        <span class="caption mono">{{ progress }}</span>
      </div>
      <NuxtLink :to="summary.to" class="r-sum" :class="{ on: summary.id === current }" :aria-current="summary.id === current ? 'page' : undefined" @click="open = false">
        <PhSquaresFour :size="18" weight="bold" />
        <span class="r-text"><span class="r-name">{{ summary.label }}</span><span v-if="summary.meta" class="r-meta">{{ summary.meta }}</span></span>
      </NuxtLink>
      <ol class="r-list">
        <li v-for="item in items" :key="item.id">
          <NuxtLink :to="item.to" class="r-item" :class="[item.tone, { on: item.id === current }]" :aria-current="item.id === current ? 'page' : undefined" :title="item.label" @click="open = false">
            <component :is="icon(item.tone)" :size="16" :weight="item.tone === 'ok' || item.tone === 'warn' ? 'fill' : 'bold'" class="r-ico" />
            <span class="r-text"><span class="r-name">{{ item.label }}</span><span v-if="item.meta" class="r-meta">{{ item.meta }}</span></span>
          </NuxtLink>
        </li>
      </ol>
    </nav>
  </div>
</template>

<style scoped>
.rail-wrap { position: sticky; top: 96px; align-self: start; z-index: 20; }
/* Под шапкой сайта: она прилипает сверху на 12 px и занимает 68 px. */
.rail { display: grid; gap: 6px; padding: 12px; border-radius: 18px; max-height: calc(100dvh - 112px); overflow: auto; }
.rail > * { position: relative; z-index: 1; }
.r-bar, .r-backdrop { display: none; }
.r-head { display: flex; justify-content: space-between; align-items: baseline; padding: 2px 6px 4px; }
.r-head .mono { font-family: var(--font-mono); color: var(--ink-muted); }
.r-sum, .r-item { display: grid; grid-template-columns: 18px minmax(0, 1fr); gap: 10px; align-items: start; padding: 7px 10px; border-radius: 12px; color: var(--ink-body); transition: background var(--dur-fast) var(--ease); }
.r-sum { background: rgba(15, 20, 19, 0.04); font-weight: 700; color: var(--ink-strong); margin-bottom: 4px; }
.r-sum svg { color: var(--brand-600); margin-top: 1px; }
.r-sum:hover, .r-item:hover { background: rgba(255, 255, 255, 0.85); }
.r-sum.on, .r-item.on { background: var(--surface-graphite); color: #fff; }
.r-sum.on svg { color: var(--brand-300); }
.r-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; }
.r-text { display: grid; gap: 1px; min-width: 0; text-align: left; }
.r-name { font-size: 14px; line-height: 1.3; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.r-meta { font-size: 12px; line-height: 1.3; color: var(--ink-muted); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.on .r-meta { color: var(--ink-muted-graphite); }
.r-ico { margin-top: 1px; color: var(--ink-faint); }
.r-item.ok .r-ico, .r-ico.ok { color: var(--brand-500); }
.r-item.warn .r-ico, .r-ico.warn { color: var(--state-warn); }
.r-item.on .r-ico { color: var(--brand-300); }
.r-item.on.warn .r-ico { color: #f0b14a; }

/* Узкий экран: компактная панель над содержимым, прилипает к верху; список — выпадающим слоем под ней. */
@media (max-width: 1100px) {
  .rail-wrap { top: 92px; }
  .r-bar { position: relative; z-index: 2; display: grid; grid-template-columns: 44px minmax(0, 1fr) 44px; align-items: center; gap: 4px; padding: 6px; border-radius: 16px; box-shadow: 0 6px 20px rgba(15, 20, 19, 0.08); }
  .r-bar > * { position: relative; z-index: 1; }
  .r-step { display: inline-flex; align-items: center; justify-content: center; width: 44px; height: 44px; border-radius: 12px; color: var(--ink-strong); }
  .r-step:hover { background: rgba(15, 20, 19, 0.06); }
  .r-step.off { color: var(--ink-faint); opacity: 0.4; }
  .r-pick { display: grid; grid-template-columns: 18px minmax(0, 1fr) 16px; align-items: center; gap: 10px; min-height: 44px; padding: 4px 10px; border-radius: 12px; background: rgba(15, 20, 19, 0.04); }
  .r-pick .r-ico { color: var(--brand-600); margin: 0; }
  .r-caret { color: var(--ink-muted); transition: transform var(--dur-fast) var(--ease); }
  .open .r-caret { transform: rotate(180deg); }
  .rail { display: none; position: absolute; z-index: 3; left: 0; right: 0; top: calc(100% + 6px); max-height: min(calc(100dvh - 180px), 560px); box-shadow: 0 16px 40px rgba(15, 20, 19, 0.18); background: #fff; }
  .open .rail { display: grid; }
  .r-backdrop { display: block; position: fixed; inset: 0; z-index: 1; background: rgba(15, 20, 19, 0.2); border: 0; padding: 0; }
}
@media (max-width: 600px) {
  .r-bar { grid-template-columns: 40px minmax(0, 1fr) 40px; }
  .r-step { width: 40px; height: 40px; }
}
</style>
