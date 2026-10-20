<script setup lang="ts">
import { PhLockSimple } from '@phosphor-icons/vue'
import { steps, type Project } from '~/data/projects'
import { useProjectProgress } from '~/composables/useStepPass'

const props = defineProps<{
  project: Project
  current?: string
  /** tone — статус подшага точкой: ok зелёная, cond и warn жёлтая, bad красная, off пустая. */
  substages?: { id: string; label: string; to: string; tone?: string }[]
  currentSub?: string
  /** Предупреждение у шага: значок «!» и подсказка при наведении. Ключ — код шага. */
  alerts?: Record<string, { title: string; items: string[]; note: string }>
}>()

/* Первый проход: шаг открывается, когда пройден предыдущий. Демо и чужие проекты не блокируются.
   До монтирования всё открыто, чтобы страница с сервера не мигала замками. */
const progress = useProjectProgress(computed(() => props.project.id))
const lockable = computed(() => !props.project.readonly && !props.project.isDemo)
const alive = ref(false)
onMounted(() => { alive.value = true })
const locked = (code: string) => alive.value && lockable.value && !progress.isOpen(code)
const openCount = computed(() => lockable.value && alive.value ? progress.open.value : props.project.step)
const lockHint = (i: number) => `Сначала пройдите «${steps[i - 1]?.label ?? ''}»`
const tip = ref<{ code: string; left: number } | null>(null)
const showTip = (code: string, event: Event) => {
  const li = (event.currentTarget as HTMLElement).closest('li')
  tip.value = { code, left: li ? li.offsetLeft : 0 }
}
const hideTip = () => { tip.value = null }

const shown = computed(() => {
  const all = props.substages ?? []
  if (all.length <= 3) return { items: all, rest: 0 }
  const index = Math.max(0, all.findIndex((item) => item.id === props.currentSub))
  const start = Math.max(0, Math.min(index - 1, all.length - 3))
  const items = all.slice(start, start + 3)
  return { items, rest: all.length - (start + items.length) }
})
const currentIndex = computed(() => Math.max(0, steps.findIndex((step) => step.path === props.current)))
const subShift = computed(() => shown.value.items.length
  ? { '--sub-i': currentIndex.value, '--sub-n': steps.length }
  : undefined)
</script>

<template>
  <nav class="steps" :style="subShift" aria-label="Шаги расчёта">
    <ol>
      <!-- project.step из mapProject — индекс рельса с 1, поэтому done/next сравниваем с i+1. Номер шага тот же, что в кабинете проекта. -->
      <li v-for="(s, i) in steps" :key="s.code" :class="{ done: i + 1 < openCount, cur: s.path === current, next: i + 1 === openCount, locked: locked(s.code) }">
        <span v-if="locked(s.code)" class="lk" :title="lockHint(i)" aria-disabled="true">
          <span class="dot"><PhLockSimple :size="12" weight="bold" /></span>
          <span class="t">{{ s.label }}</span>
        </span>
        <NuxtLink v-else :to="`/projects/${project.id}/${s.path}`" :aria-current="s.path === current ? 'step' : undefined">
          <span class="dot">{{ i + 1 }}</span>
          <span class="t">{{ s.label }}</span>
          <span
            v-if="alerts?.[s.code]"
            class="alert"
            tabindex="0"
            :aria-label="alerts[s.code]!.title"
            @mouseenter="showTip(s.code, $event)"
            @mouseleave="hideTip"
            @focus="showTip(s.code, $event)"
            @blur="hideTip"
            @click.prevent
          >!</span>
        </NuxtLink>
      </li>
    </ol>
    <div v-if="tip && alerts?.[tip.code]" class="tip" role="tooltip" :style="{ left: `${tip.left}px` }">
      <div class="tip-title">{{ alerts[tip.code]!.title }}</div>
      <ul><li v-for="item in alerts[tip.code]!.items" :key="item">{{ item }}</li></ul>
      <p>{{ alerts[tip.code]!.note }}</p>
    </div>
    <div v-if="shown.items.length" class="subrow">
      <NuxtLink v-for="sub in shown.items" :key="sub.id" :to="sub.to" class="sub" :class="{ on: sub.id === currentSub }" :title="sub.label" :aria-current="sub.id === currentSub ? 'step' : undefined">
        <span class="sdot" :class="sub.tone" />
        <span class="slabel">{{ sub.label }}</span>
      </NuxtLink>
      <span v-if="shown.rest" class="caption more">ещё {{ shown.rest }}</span>
    </div>
  </nav>
</template>

<style scoped>
.steps { position: relative; display: grid; gap: 8px; }
.alert { display: inline-flex; align-items: center; justify-content: center; width: 20px; height: 20px; margin-left: auto; border-radius: 50%; font-size: 13px; font-weight: 800; background: var(--state-warn); color: #fff; cursor: help; flex: none; }
.alert:focus-visible { outline: 2px solid var(--state-warn); outline-offset: 2px; }
.tip { position: absolute; top: 52px; z-index: 5; width: 360px; padding: 14px 16px; border-radius: 14px; background: var(--surface-graphite); color: var(--ink-on-graphite); box-shadow: 0 18px 40px rgba(15, 20, 19, 0.22); font-size: 13px; line-height: 1.45; }
.tip-title { font-weight: 700; margin-bottom: 6px; }
.tip ul { margin: 0 0 8px; padding-left: 18px; display: grid; gap: 2px; }
.tip p { margin: 0; color: rgba(241, 245, 243, 0.75); }
/* Шаги — стрелки слева направо: правый край заострён, левый вырезан под предыдущую стрелку. */
.steps ol { --tip: 14px; display: flex; align-items: center; gap: 4px; width: 100%; padding: 4px; border-radius: 14px; background: rgba(15, 20, 19, 0.05); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.04); overflow-x: auto; }
li { flex: 1; min-width: 0; }
li > a, li > .lk {
  display: flex; align-items: center; gap: 8px; height: 40px; padding: 0 calc(var(--tip) + 8px) 0 calc(var(--tip) + 8px);
  clip-path: polygon(0 0, calc(100% - var(--tip)) 0, 100% 50%, calc(100% - var(--tip)) 100%, 0 100%, var(--tip) 50%);
  background: rgba(255, 255, 255, 0.55); font-size: 14px; font-weight: 600; color: var(--ink-muted); white-space: nowrap;
  transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease);
}
li > .lk { color: var(--ink-faint); background: rgba(255, 255, 255, 0.3); cursor: not-allowed; }
li:first-child > a { padding-left: 10px; border-radius: 10px 0 0 10px; clip-path: polygon(0 0, calc(100% - var(--tip)) 0, 100% 50%, calc(100% - var(--tip)) 100%, 0 100%); }
li > a:hover, li > a:focus-visible { background: #fff; color: var(--ink-strong); outline: none; }
.dot { display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 24px; border-radius: 8px; background: rgba(15, 20, 19, 0.06); font-family: var(--font-mono); font-size: 12px; font-weight: 700; flex: none; }
.done .dot { background: var(--surface-brand-tint); color: var(--brand-700); }
.done > a { color: var(--ink-body); }
.cur > a, .cur > a:hover { background: var(--surface-graphite); color: var(--ink-on-graphite); }
.cur > a .dot { background: var(--brand-400); color: var(--brand-900); }
.next:not(.cur) > a { color: var(--ink-strong); }
.next:not(.cur) > a .dot { background: #fff; box-shadow: inset 0 0 0 1.5px var(--brand-500); color: var(--brand-700); }
.subrow { --stage: calc((100% - 8px - (var(--sub-n) - 1) * 4px) / var(--sub-n)); display: grid; gap: 4px; box-sizing: border-box; width: var(--stage); margin-left: calc(4px + var(--sub-i) * (var(--stage) + 4px)); padding: 4px; border-radius: 12px; background: transparent; box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.12); }
.sub { display: flex; align-items: center; gap: 8px; min-width: 0; min-height: 32px; padding: 6px 8px; border-radius: 8px; font-size: 13px; font-weight: 600; line-height: 1.3; color: var(--ink-muted); }
.slabel { min-width: 0; line-height: 1.35; }
.sub:hover { background: rgba(255, 255, 255, 0.7); color: var(--ink-strong); }
.sub.on { background: rgba(255, 255, 255, 0.85); color: var(--ink-strong); box-shadow: inset 0 0 0 1px var(--brand-400); }
.sdot { width: 8px; height: 8px; border-radius: 99px; background: rgba(15, 20, 19, 0.16); flex: none; }
.sub.on .sdot { background: var(--brand-500); }
.sdot.ok, .sub.on .sdot.ok { background: var(--brand-500); }
.sdot.cond, .sdot.warn, .sub.on .sdot.cond, .sub.on .sdot.warn { background: #e0a43a; }
.sdot.bad, .sub.on .sdot.bad { background: #e5584b; }
.sdot.off, .sub.on .sdot.off { background: transparent; box-shadow: inset 0 0 0 1.5px rgba(15, 20, 19, 0.3); }
.more { padding: 2px 8px 4px; }
@media (max-width: 800px) {
  /* Под шагом колонка слишком узкая, подпись обрезалась. На телефоне список шагов на всю ширину. */
  .subrow { width: 100%; margin-left: 0; }
  li > a { height: auto; min-height: 40px; padding-top: 6px; padding-bottom: 6px; white-space: normal; line-height: 1.3; }
}
</style>
