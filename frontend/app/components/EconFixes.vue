<script setup lang="ts">
import { PhCaretDown, PhMagicWand } from '@phosphor-icons/vue'
import type { EconFix } from '~/composables/usePlatformEconomy'

/** Что платформа поправила в проекте сама: одной строкой, по клику — список с причинами и кнопкой «Вернуть». */
const props = defineProps<{ fixes: EconFix[]; busy?: boolean }>()
const emit = defineEmits<{ undo: [EconFix]; undoAll: [] }>()

const open = ref(false)
const summary = computed(() => {
  const off = props.fixes.filter((item) => item.kind === 'off').length
  const count = props.fixes.filter((item) => item.kind === 'count')
  const parts = []
  if (count.length) parts.push(count.length === 1 ? `подобрала число роботов: ${count[0]!.name.toLowerCase()} ${count[0]!.change}` : `подобрала число роботов на ${count.length} процессах`)
  if (off) parts.push(`убрала из итога ${off} ${off === 1 ? 'процесс' : off < 5 ? 'процесса' : 'процессов'}`)
  return parts.join(', ')
})
</script>

<template>
  <div class="fixes">
    <button type="button" class="f-head" :aria-expanded="open" @click="open = !open">
      <PhMagicWand :size="18" weight="bold" class="f-icon" />
      <span class="body-sm"><b>Платформа поправила проект:</b> {{ summary }}.</span>
      <span class="f-more">{{ open ? 'Свернуть' : 'Что и почему' }}<PhCaretDown :size="12" weight="bold" class="caret" :class="{ up: open }" /></span>
    </button>
    <ul v-if="open" class="f-list">
      <li v-for="fix in fixes" :key="fix.key">
        <span class="f-text">
          <span class="body-sm"><b>{{ fix.name }}</b> · {{ fix.change }}</span>
          <span class="caption">{{ fix.reason }}</span>
        </span>
        <UiButton variant="ghost" size="sm" :disabled="busy" @click="emit('undo', fix)">Вернуть</UiButton>
      </li>
      <li class="f-foot">
        <span class="caption">Скидки вендора и господдержку платформа сама не включает: о них нужно договориться. Они — в условиях у процессов.</span>
        <UiButton v-if="fixes.length > 1" variant="secondary" size="sm" :disabled="busy" @click="emit('undoAll')">Вернуть всё</UiButton>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.fixes { border-radius: 14px; background: var(--surface-brand-tint); }
.f-head { width: 100%; display: grid; grid-template-columns: auto minmax(0, 1fr) auto; align-items: center; gap: 12px; padding: 12px 16px; text-align: left; }
.f-icon { color: var(--brand-700); }
.f-more { display: inline-flex; align-items: center; gap: 4px; font-size: 13px; font-weight: 700; color: var(--link); white-space: nowrap; }
.caret { transition: transform var(--dur-fast) var(--ease); }
.caret.up { transform: rotate(180deg); }
.f-list { display: grid; margin: 0; padding: 0 16px 12px 46px; list-style: none; }
.f-list li { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 8px 0; border-top: 1px solid rgba(15, 20, 19, 0.07); }
.f-text { display: grid; gap: 2px; min-width: 0; }
.f-foot .caption { max-width: 70ch; }
@media (max-width: 600px) {
  .f-head { grid-template-columns: minmax(0, 1fr) auto; }
  .f-icon { display: none; }
  .f-list { padding-left: 16px; }
}
</style>
