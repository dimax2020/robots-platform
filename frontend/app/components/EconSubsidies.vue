<script setup lang="ts">
import { PhCaretDown } from '@phosphor-icons/vue'
import { millions, type EconSubsidy } from '~/composables/usePlatformEconomy'

const props = defineProps<{ items: EconSubsidy[]; horizon: number; busy?: string; locked?: boolean; to?: string }>()
const emit = defineEmits<{ toggle: [string] }>()

const open = ref('')
const once = computed(() => props.items.filter((item) => item.enabled && item.kind === 'once').reduce((sum, item) => sum + (item.value ?? 0), 0))
const yearly = computed(() => props.items.filter((item) => item.enabled && item.kind === 'year').reduce((sum, item) => sum + (item.total ?? 0), 0))
const amount = (item: EconSubsidy) => item.kind === 'once'
  ? `−${millions(item.value)} к CAPEX`
  : `+${millions(item.value)} в первый год`
const extra = (item: EconSubsidy) => item.kind === 'once' ? 'единовременно' : `${millions(item.total)} за ${props.horizon} лет`
</script>

<template>
  <section class="subs glass">
    <div class="s-in">
      <div class="s-head">
        <div>
          <div class="h3">Господдержка</div>
          <div class="caption">Включите меры, на которые может претендовать проект. Они входят в сценарий покупки: разовые уменьшают CAPEX, годовые добавляются к эффекту. Право на меру подтверждается условиями программы.</div>
        </div>
        <div v-if="once || yearly" class="s-total">
          <span v-if="once"><span class="caption">разовые</span><span class="mono-md">−{{ millions(once) }}</span></span>
          <span v-if="yearly"><span class="caption">годовые за {{ horizon }} лет</span><span class="mono-md">+{{ millions(yearly) }}</span></span>
        </div>
        <UiButton v-if="to" :to="to" variant="secondary" size="sm">Ставки и лимиты</UiButton>
      </div>
      <div class="s-grid">
        <div v-for="item in items" :key="item.code" class="sub" :class="{ on: item.enabled }">
          <div class="sub-top">
            <button
              type="button"
              class="switch"
              role="switch"
              :aria-checked="item.enabled"
              :aria-label="item.label"
              :disabled="locked || busy === item.code"
              @click="emit('toggle', item.code)"
            ><i /></button>
            <span class="sub-name">
              <span class="body-sm strong">{{ item.label }}</span>
              <span class="caption">{{ item.subtitle }}</span>
            </span>
          </div>
          <button type="button" class="sub-sum" @click="open = open === item.code ? '' : item.code">
            <span>
              <span class="mono-md">{{ amount(item) }}</span>
              <span class="caption block">{{ item.enabled ? extra(item) : `если включить · ${extra(item)}` }}</span>
            </span>
            <PhCaretDown :size="14" weight="bold" class="caret" :class="{ up: open === item.code }" />
          </button>
          <EconFormula v-if="open === item.code" :fig="item.fig" dense />
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.s-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: var(--space-4); }
.s-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-4); }
.s-head > div:first-child { max-width: 70ch; }
.s-total { display: flex; gap: 18px; flex: none; margin-left: auto; }
.s-total > span { display: grid; gap: 2px; justify-items: end; }
.s-total .mono-md { color: var(--brand-700); font-size: 18px; }
.s-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }
.sub { display: grid; gap: 10px; align-content: start; padding: 14px; border-radius: var(--radius-lg); background: rgba(255, 255, 255, 0.55); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); transition: background var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease); }
.sub.on { background: #fff; box-shadow: inset 0 0 0 1px var(--brand-400), 0 8px 20px rgba(13, 132, 85, 0.08); }
.sub-top { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 12px; align-items: center; }
.sub-name { display: grid; gap: 1px; min-width: 0; }
.sub-name .body-sm { color: var(--ink-strong); }
.switch { position: relative; width: 38px; height: 22px; border-radius: 999px; background: rgba(15, 20, 19, 0.14); transition: background var(--dur-fast) var(--ease); flex: none; }
.switch i { position: absolute; top: 3px; left: 3px; width: 16px; height: 16px; border-radius: 50%; background: #fff; box-shadow: 0 1px 3px rgba(15, 20, 19, 0.25); transition: transform var(--dur-fast) var(--ease); }
.switch[aria-checked='true'] { background: var(--brand-600); }
.switch[aria-checked='true'] i { transform: translateX(16px); }
.switch:disabled { opacity: 0.5; cursor: not-allowed; }
.sub-sum { display: flex; justify-content: space-between; align-items: center; gap: 8px; width: 100%; text-align: left; padding-top: 10px; border-top: 1px solid rgba(15, 20, 19, 0.06); }
.sub-sum .mono-md { color: var(--ink-muted); }
.on .sub-sum .mono-md { color: var(--brand-700); }
.block { display: block; }
.caret { color: var(--ink-faint); transition: transform var(--dur-fast) var(--ease); flex: none; }
.caret.up { transform: rotate(180deg); }
@media (max-width: 900px) {
  .s-head { flex-direction: column; }
  .s-total { margin-left: 0; }
  .s-total > span { justify-items: start; }
}
</style>
