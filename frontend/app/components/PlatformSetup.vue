<script setup lang="ts">
import { PhCheck } from '@phosphor-icons/vue'
import type { LiveProcess } from '~/composables/useLiveProject'
import { processIcon } from '~/data/processIcons'

/** Выбор процессов. Список и сохранение ведёт шаг параметров: от выбора зависит, какие поля площадки он спросит. */
const props = defineProps<{ processes: LiveProcess[]; readonly?: boolean }>()
const emit = defineEmits<{ toggle: [code: string]; all: [on: boolean] }>()

const picked = computed(() => props.processes.filter((item) => item.enabled).length)
const allOn = computed(() => picked.value === props.processes.length)
</script>

<template>
  <div class="setup">
    <div class="count glass">
      <span class="count-text">
        Выбрано для роботизации: <span class="count-n">{{ picked }} из {{ processes.length }}</span>
      </span>
      <template v-if="!readonly">
        <button v-if="!allOn" type="button" class="count-btn" @click="emit('all', true)">Выбрать все</button>
        <button v-else type="button" class="count-btn" @click="emit('all', false)">Снять все</button>
      </template>
    </div>

    <div class="procs">
      <button
        v-for="process in processes"
        :key="process.code"
        type="button"
        class="proc"
        :class="{ on: process.enabled, still: readonly }"
        :aria-pressed="process.enabled"
        :disabled="readonly"
        @click="emit('toggle', process.code)"
      >
        <span class="ico"><component :is="processIcon(process.code)" :size="24" weight="duotone" /></span>
        <span class="proc-copy">
          <span class="proc-name">{{ process.name }}</span>
          <span v-if="process.description" class="proc-desc">{{ process.description }}</span>
          <span v-if="!process.enabled && process.disabled_reason" class="loss" :title="process.disabled_reason">Выключен: невыгоден по экономике</span>
        </span>
        <span class="tick" aria-hidden="true"><PhCheck v-if="process.enabled" :size="14" weight="bold" /></span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.setup { display: grid; gap: var(--space-4); }
.count { display: flex; justify-content: space-between; align-items: center; gap: var(--space-4); padding: 16px 20px; border-radius: 16px; }
.count > * { position: relative; z-index: 1; }
.count-text { font-size: 16px; font-weight: 600; color: var(--ink-body); }
.count-n { font-weight: 800; color: var(--ink-strong); }
.count-btn { font-size: 14px; font-weight: 700; color: var(--link); padding: 6px 10px; border-radius: 8px; }
.count-btn:hover { background: rgba(15, 20, 19, 0.05); }
.procs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.proc {
  display: grid; grid-template-columns: auto 1fr auto; gap: 16px; align-items: center; text-align: left;
  padding: 18px 20px; border-radius: 18px; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.08);
  transition: background var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
}
.proc:hover:not(.still) { background: #fff; box-shadow: inset 0 0 0 1px var(--border-strong); }
.proc.on { background: #fff; box-shadow: inset 0 0 0 2px var(--brand-500); }
.proc.still { cursor: default; }
.ico { width: 48px; height: 48px; border-radius: 14px; display: inline-flex; align-items: center; justify-content: center; background: rgba(15, 20, 19, 0.05); color: var(--ink-muted); }
.proc.on .ico { background: var(--surface-brand-tint); color: var(--brand-700); }
.proc-copy { display: grid; gap: 4px; min-width: 0; }
.proc-name { font-size: 16px; font-weight: 700; line-height: 1.3; color: var(--ink-strong); }
.proc-desc { font-size: 14px; line-height: 1.45; color: var(--ink-muted); }
.loss { font-size: 12px; font-weight: 600; color: var(--state-danger); }
.tick { width: 24px; height: 24px; border-radius: 8px; display: inline-flex; align-items: center; justify-content: center; box-shadow: inset 0 0 0 1.5px rgba(15, 20, 19, 0.2); flex: none; }
.proc.on .tick { background: var(--brand-500); color: #fff; box-shadow: none; }
@media (max-width: 1100px) {
  .procs { grid-template-columns: 1fr; }
}
</style>
