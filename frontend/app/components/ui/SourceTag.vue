<script setup lang="ts">
import { PhArrowSquareOut, PhQuotes } from '@phosphor-icons/vue'
import { confidenceByKind, sourceKindLabel, type Confidence, type Source } from '~/data/catalog'
import { demoSourceById } from '~/data/demo'

const props = defineProps<{ sourceId?: string; quote?: string; align?: 'left' | 'right'; text?: string; source?: Source }>()
const src = computed(() => props.source ?? demoSourceById(props.sourceId))
const parsed = computed(() => {
  if (!props.text) return undefined
  const m = props.text.match(/^\[([A-D])\]\s*(.*)$/i)
  if (!m) return { letter: undefined as Confidence | undefined, rest: props.text }
  return { letter: m[1]!.toUpperCase() as Confidence, rest: m[2] || props.text }
})
const conf = computed(() => (src.value ? confidenceByKind[src.value.kind] : parsed.value?.letter))
const fmt = (d: string) => new Date(d).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
</script>

<template>
  <span v-if="src || parsed" class="src" :class="[`c-${conf}`, align === 'right' ? 'right' : '']" tabindex="0">
    <span class="letter">{{ conf || '?' }}</span>
    <span class="pop glass glass-strong" role="tooltip">
      <template v-if="src">
        <span class="pop-head">
          <span class="label">{{ sourceKindLabel[src.kind] }}</span>
          <span class="conf">достоверность {{ conf }}</span>
        </span>
        <span class="pub">{{ src.publisher }}</span>
        <span v-if="quote || src.quote" class="quote"><PhQuotes :size="14" weight="fill" /> {{ quote || src.quote }}</span>
        <span class="dates mono-sm">получено {{ fmt(src.fetchedAt) }}<template v-if="src.checkedAt !== src.fetchedAt"> · проверено {{ fmt(src.checkedAt) }}</template></span>
        <a v-if="src.url && src.url.startsWith('http')" class="pop-link" :href="src.url" target="_blank" rel="noreferrer">Открыть источник <PhArrowSquareOut :size="14" /></a>
        <span v-else class="pop-file mono-sm">{{ src.url || 'без ссылки' }}</span>
      </template>
      <template v-else>
        <span class="pop-head">
          <span class="label">Источник расчёта</span>
          <span v-if="conf" class="conf">достоверность {{ conf }}</span>
        </span>
        <span class="pub">{{ parsed?.rest }}</span>
      </template>
    </span>
  </span>
</template>

<style scoped>
.src { position: relative; display: inline-flex; vertical-align: middle; }
.letter {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 7px;
  font-family: var(--font-mono); font-size: 11px; font-weight: 700;
  cursor: help; transition: transform var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
}
.src:hover .letter, .src:focus-visible .letter { transform: translateY(-1px); }
.c-A .letter { background: var(--state-ok-tint); color: var(--state-ok); }
.c-B .letter { background: var(--state-info-tint); color: var(--state-info); }
.c-C .letter { background: var(--state-warn-tint); color: var(--state-warn); }
.c-D .letter { background: var(--state-neutral-tint); color: var(--state-neutral); }

.pop {
  position: absolute;
  z-index: var(--z-dropdown);
  top: calc(100% + 8px);
  left: 0;
  width: 300px;
  padding: 14px;
  display: grid;
  gap: 8px;
  text-align: left;
  font-size: 13px;
  color: var(--ink-body);
  opacity: 0;
  pointer-events: none;
  transform: translateY(-4px) scale(0.98);
  transition: opacity var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease);
  border-radius: var(--radius-md);
}
.right .pop { left: auto; right: 0; }
.src:hover .pop, .src:focus-visible .pop, .src:focus-within .pop { opacity: 1; pointer-events: auto; transform: none; }
.pop-head { display: flex; justify-content: space-between; align-items: baseline; gap: 8px; }
.conf { font-family: var(--font-mono); font-size: 11px; color: var(--ink-muted); }
.pub { font-weight: 700; color: var(--ink-strong); }
.quote { display: flex; gap: 6px; align-items: flex-start; padding: 8px 10px; border-radius: 8px; background: rgba(15, 20, 19, 0.04); font-style: italic; color: var(--ink-body); }
.quote svg { flex: none; color: var(--ink-faint); margin-top: 2px; }
.dates, .pop-file { color: var(--ink-muted); }
.pop-link { display: inline-flex; align-items: center; gap: 6px; color: var(--link); font-weight: 600; }
</style>
