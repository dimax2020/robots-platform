<script setup lang="ts">
import { PhCoins, PhRobot, PhStack } from '@phosphor-icons/vue'
import type { RobotChoice } from '~/composables/usePlatformEconomy'

/** Почему этот робот, сколько их и как они входят в CAPEX: ответ на «почему такие роботы и заложены ли они в вложения». */
defineProps<{ choice: RobotChoice }>()
</script>

<template>
  <section class="why" aria-label="Почему этот робот">
    <div class="w-row">
      <PhRobot :size="16" weight="bold" class="w-ico" />
      <span class="w-label caption">Почему он</span>
      <span class="body-sm">{{ choice.why }}</span>
    </div>
    <div class="w-row">
      <PhStack :size="16" weight="bold" class="w-ico" />
      <span class="w-label caption">Сколько</span>
      <span class="body-sm">{{ choice.count }}</span>
    </div>
    <div class="w-row">
      <PhCoins :size="16" weight="bold" class="w-ico" />
      <span class="w-label caption">В CAPEX</span>
      <span class="body-sm">{{ choice.money }}<span v-if="choice.rent" class="caption w-rent"> {{ choice.rent }}</span></span>
    </div>
  </section>
</template>

<style scoped>
.why { display: grid; gap: 8px; padding: 12px 14px; border-radius: 14px; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px var(--border-hairline); }
.w-row { display: grid; grid-template-columns: 16px 92px minmax(0, 1fr); gap: 10px; align-items: baseline; }
.w-ico { color: var(--brand-600); align-self: center; }
.w-label { font-weight: 700; color: var(--ink-muted); text-transform: none; }
.w-rent { display: block; margin-top: 2px; color: var(--ink-muted); }
@media (max-width: 600px) {
  .w-row { grid-template-columns: 16px minmax(0, 1fr); }
  .w-row .body-sm { grid-column: 2; }
}
</style>
