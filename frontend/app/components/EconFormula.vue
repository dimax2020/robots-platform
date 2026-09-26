<script setup lang="ts">
import { figValue, SOURCE_TONE, type EconFig } from '~/composables/usePlatformEconomy'

const props = defineProps<{ fig: EconFig; dark?: boolean }>()
const subst = computed(() => {
  const text = props.fig.subst?.trim() ?? ''
  if (!text) return ''
  return text.startsWith('=') ? text : `= ${text}`
})
</script>

<template>
  <div class="formula" :class="{ dark }">
    <div class="f-tex">
      <UiTex :tex="fig.tex" display />
      <UiTex v-if="subst" :tex="subst" display class="f-subst" />
    </div>
    <dl v-if="fig.vars.length" class="f-vars">
      <div v-for="(item, index) in fig.vars" :key="`${item.symbol}-${index}`" class="f-var">
        <dt><UiTex :tex="item.symbol" /></dt>
        <dd class="f-what">
          <span class="body-sm">{{ item.label }}</span>
          <span v-if="item.note" class="caption">{{ item.note }}</span>
        </dd>
        <dd class="mono-sm f-val">{{ figValue(item.value, item.unit) }}</dd>
        <dd><UiBadge :tone="SOURCE_TONE[item.source]" size="sm">{{ item.source_label }}</UiBadge></dd>
      </div>
    </dl>
    <p v-if="fig.note" class="caption f-note">{{ fig.note }}</p>
  </div>
</template>

<style scoped>
.formula { display: grid; gap: 12px; padding: 14px 16px; border-radius: 14px; background: rgba(255, 255, 255, 0.72); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); color: var(--ink-strong); }
.formula.dark { background: rgba(255, 255, 255, 0.06); box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.1); color: var(--ink-on-graphite); }
.f-tex { display: grid; gap: 4px; }
.f-subst { color: var(--brand-700); }
.dark .f-subst { color: var(--brand-300); }
.f-vars { display: grid; gap: 0; margin: 0; }
.f-var { display: grid; grid-template-columns: minmax(64px, auto) minmax(0, 1fr) auto auto; gap: 12px; align-items: center; padding: 8px 0; border-top: 1px solid rgba(15, 20, 19, 0.06); }
.dark .f-var { border-top-color: rgba(255, 255, 255, 0.08); }
.f-var dt { margin: 0; }
.f-var dd { margin: 0; }
.f-what { display: grid; gap: 2px; min-width: 0; }
.f-val { white-space: nowrap; }
.f-note { margin: 0; }
.dark .caption { color: var(--ink-muted-graphite); }
@media (max-width: 720px) {
  .f-var { grid-template-columns: auto minmax(0, 1fr); }
  .f-val, .f-var dd:last-child { grid-column: 2; }
}
</style>
