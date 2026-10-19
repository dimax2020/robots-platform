<script setup lang="ts">
import { PhFlask } from '@phosphor-icons/vue'
import { formatOrigin } from '~/utils/demoSynthetic'

defineProps<{ origin: string; explanation: string }>()
const tooltipId = useId()
const trigger = ref<HTMLButtonElement | null>(null)
const popup = ref<HTMLElement | null>(null)
let pinned = false
let hideTimer: ReturnType<typeof setTimeout> | undefined

const cancelHide = () => { if (hideTimer) clearTimeout(hideTimer) }
const show = () => {
  cancelHide()
  if (!popup.value || !trigger.value) return
  popup.value.showPopover()
  const anchor = trigger.value.getBoundingClientRect()
  const box = popup.value.getBoundingClientRect()
  popup.value.style.left = `${Math.max(8, Math.min(anchor.left, window.innerWidth - box.width - 8))}px`
  popup.value.style.top = `${anchor.bottom + box.height + 8 <= window.innerHeight ? anchor.bottom + 8 : Math.max(8, anchor.top - box.height - 8)}px`
}
const hide = () => {
  cancelHide()
  hideTimer = setTimeout(() => {
    if (!pinned && !popup.value?.matches(':hover') && document.activeElement !== trigger.value) popup.value?.hidePopover()
  }, 150)
}
const pin = () => { pinned = true; show() }
const toggled = (event: Event) => { if ((event as ToggleEvent).newState === 'closed') pinned = false }
onBeforeUnmount(cancelHide)
</script>

<template>
  <button ref="trigger" type="button" class="synthetic-marker" title="Синтетика" aria-label="Синтетика"
    :aria-describedby="tooltipId" :popovertarget="tooltipId" popovertargetaction="show"
    @mouseenter="show" @mouseleave="hide" @focus="show" @blur="hide" @click="pin">
    <PhFlask :size="16" weight="duotone" aria-hidden="true" />
  </button>
  <div :id="tooltipId" ref="popup" popover="auto" role="tooltip" class="synthetic-popover"
    @mouseenter="cancelHide" @mouseleave="hide" @toggle="toggled">
    <strong>Синтетика</strong>
    <p>Происхождение: {{ formatOrigin(origin) }}</p>
    <p>{{ explanation }}</p>
  </div>
</template>

<style scoped>
.synthetic-marker { display: inline-flex; align-items: center; justify-content: center; vertical-align: middle; padding: 3px; margin-left: 4px; border-radius: 5px; color: #956014; background: #fff5dc; cursor: help; }
.synthetic-marker:hover { background: #ffedbd; }
.synthetic-marker:focus-visible { outline: 2px solid var(--brand-400); outline-offset: 2px; }
.synthetic-popover { position: fixed; inset: auto; margin: 0; width: min(360px, calc(100vw - 16px)); max-height: 70vh; overflow-y: auto; padding: 12px 14px; border: 1px solid #eadbb5; border-radius: 10px; background: #fffdf6; color: var(--ink-strong); font: 13px/1.5 var(--font-sans); box-shadow: 0 8px 24px rgba(15, 20, 19, .16); text-align: left; }
.synthetic-popover p { margin: 6px 0 0; }
@media print {
  .synthetic-marker { padding: 0; margin-left: 2px; background: none; color: #5c3700; }
  .synthetic-marker svg { width: 11px; height: 11px; }
  .synthetic-popover { display: none !important; }
}
</style>
