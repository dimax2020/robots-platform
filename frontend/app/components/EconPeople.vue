<script setup lang="ts">
import { PhArrowRight } from '@phosphor-icons/vue'
import type { EconRelease } from '~/composables/usePlatformEconomy'

/** Кого заменяют роботы: численность по процессам, сколько уходит, сколько нужно диспетчеров. */
const props = defineProps<{ items: EconRelease[]; dispatchers: number | null; check?: string; ask?: () => void }>()

const fmt = (value: number) => value.toLocaleString('ru-RU', { maximumFractionDigits: 1 })
/* Где затраты введены суммой, людей не знаем: такие процессы в счёт людей не входят. */
const staffed = computed(() => props.items.filter((item) => item.source && item.staff > 0 && !item.by_cost))
const now = computed(() => staffed.value.reduce((sum, item) => sum + item.staff, 0))
const gone = computed(() => staffed.value.reduce((sum, item) => sum + item.fte, 0))
const added = computed(() => props.dispatchers ?? 0)
const net = computed(() => gone.value - added.value)
const missing = computed(() => props.items.filter((item) => !item.source || !item.staff).length)
const max = computed(() => Math.max(1, now.value, gone.value + added.value))
const where = (item: EconRelease) => {
  if (item.by_cost) return `затраты ${fmt((item.cost_month ?? 0) / 1e6)} млн ₽ в месяц`
  if (item.source === 'task') return `указано на процессе: ${fmt(item.staff)} чел.`
  if (item.source === 'role') return `${item.role}: ${fmt(item.staff * item.split)} чел.${item.split > 1 ? ` на ${item.split} процесса` : ''}`
  return 'нет данных'
}
</script>

<template>
  <div class="people">
    <div class="flow">
      <div class="step">
        <span class="caption">Сейчас на этих операциях</span>
        <span class="n">{{ fmt(now) }}<small> чел.</small></span>
        <span class="bar"><i class="now" :style="{ width: `${(now / max) * 100}%` }" /></span>
      </div>
      <PhArrowRight :size="18" weight="bold" class="arr" />
      <div class="step">
        <span class="caption">Уходят: работу берут роботы</span>
        <span class="n good">−{{ fmt(gone) }}<small> чел.</small></span>
        <span class="bar"><i class="gone" :style="{ width: `${(gone / max) * 100}%` }" /></span>
      </div>
      <PhArrowRight :size="18" weight="bold" class="arr" />
      <div class="step">
        <span class="caption">Нужны диспетчеры парка</span>
        <span class="n warn">+{{ fmt(added) }}<small> чел.</small></span>
        <span class="bar"><i class="added" :style="{ width: `${(added / max) * 100}%` }" /></span>
      </div>
      <PhArrowRight :size="18" weight="bold" class="arr" />
      <div class="step total">
        <span class="caption">{{ net >= 0 ? 'Итого людей меньше' : 'Итого людей больше' }}</span>
        <span class="n" :class="net >= 0 ? 'good' : 'bad'">{{ net > 0 ? '−' : net < 0 ? '+' : '' }}{{ fmt(Math.abs(net)) }}<small> чел.</small></span>
        <span class="caption">{{ net >= 0 ? 'диспетчерами могут стать высвобожденные сотрудники' : 'диспетчеров нужно больше, чем уходит людей: парк слишком велик для этой работы' }}</span>
      </div>
    </div>

    <UiCallout v-if="check" tone="warn">{{ check }}</UiCallout>

    <div class="t-wrap">
      <table class="tbl">
        <thead>
          <tr><th>Процесс</th><th>Откуда численность</th><th>Роботы берут</th><th>Уходит</th></tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.process_code" :class="{ empty: !item.fte }">
            <th>
              <span class="body-sm strong">{{ item.process_name }}</span>
              <span v-if="item.note" class="caption note">{{ item.note }}</span>
              <span v-else-if="item.capped" class="caption note">Не больше, чем людей на часы работы роботов: {{ fmt(item.cap ?? 0) }} чел.</span>
            </th>
            <td><UiBadge :tone="item.source ? 'info' : 'warn'" size="sm">{{ item.by_cost ? 'затраты' : item.source === 'task' ? 'процесс' : item.source === 'role' ? 'роль' : 'нет' }}</UiBadge> <span class="caption">{{ where(item) }}</span></td>
            <td class="mono">{{ item.work?.coverage != null ? `${Math.round(item.work.coverage * 100)}% операций` : item.staff ? `${Math.round(item.auto * 100)}%` : '—' }}<span v-if="item.auto_note" class="caption block">{{ item.auto_note }}</span></td>
            <td class="mono strong">{{ item.by_cost ? `${Math.round(item.fte * 100)}% затрат` : item.fte ? `${fmt(item.fte)} чел.` : '0' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
    <p class="caption method">
      Роботы забирают операции: их выработка в час на часы работы площадки против объёма процесса. Уходит столько людей, какую долю операций берут роботы,
      целыми ставками в каждой смене. Если указаны затраты суммой — уходит та же доля затрат. Без людей или затрат экономия не считается.
      
    </p>
    <UiHint v-if="missing">
      У {{ missing }} процессов нет данных о людях или затратах — экономия по ним не считается.
      <template v-if="ask" #action><UiButton variant="secondary" size="sm" @click="ask">Вопросы заказчику</UiButton></template>
    </UiHint>
  </div>
</template>

<style scoped>
.people { display: grid; gap: var(--space-5); }
.flow { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr) 18px) minmax(0, 1fr); gap: 12px; align-items: center; }
.step { display: grid; gap: 6px; padding: 14px 16px; border-radius: 16px; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); align-self: stretch; align-content: start; }
.step.total { background: var(--surface-graphite); }
.step.total .caption { color: var(--ink-muted-graphite); }
.step.total .n { color: #fff; }
.n { font-family: var(--font-mono); font-weight: 700; font-size: clamp(24px, 2vw, 32px); line-height: 1.1; color: var(--ink-strong); font-variant-numeric: tabular-nums; }
.n small { font-size: 0.5em; font-weight: 600; color: inherit; opacity: 0.7; }
.n.good { color: var(--brand-600); }
.step.total .n.good { color: var(--brand-300); }
.n.warn { color: #b7791f; }
.n.bad { color: #ff8a80; }
.bar { height: 6px; border-radius: 3px; background: rgba(15, 20, 19, 0.06); overflow: hidden; }
.bar i { display: block; height: 100%; border-radius: 3px; }
.bar .now { background: #8a9692; }
.bar .gone { background: var(--brand-500); }
.bar .added { background: #f0b14a; }
.arr { color: var(--ink-faint); }
.t-wrap { overflow-x: auto; }
.tbl { width: 100%; border-collapse: collapse; }
.tbl th, .tbl td { padding: 12px 10px; border-bottom: 1px solid rgba(15, 20, 19, 0.06); text-align: left; vertical-align: top; }
.tbl thead th { font-size: 12px; font-weight: 700; color: var(--ink-muted); }
.tbl tbody th { display: grid; gap: 2px; font-weight: 400; }
.tbl tr.empty .strong { color: var(--ink-muted); }
.note { color: #9a5b00; }
.mono { font-family: var(--font-mono); font-variant-numeric: tabular-nums; white-space: nowrap; }
.block { display: block; white-space: normal; }
.method { margin: 0; }
.link { color: var(--link); font-weight: 600; text-decoration: underline; text-underline-offset: 2px; }
@media (max-width: 1100px) { .flow { grid-template-columns: 1fr 1fr; } .arr { display: none; } }
</style>
