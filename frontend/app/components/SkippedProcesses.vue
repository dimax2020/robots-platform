<script setup lang="ts">
import { PhCaretDown, PhInfo } from '@phosphor-icons/vue'

defineProps<{ rows: { code: string; name: string; reason: string }[] }>()
const open = ref(false)
</script>

<template>
  <section v-if="rows.length" class="note">
    <button type="button" class="head" :aria-expanded="open" @click="open = !open">
      <PhInfo :size="20" weight="duotone" class="ic" />
      <span class="title">Процессы без роботов не считаем <span class="count">{{ rows.length }}</span></span>
      <PhCaretDown :size="16" weight="bold" class="caret" :class="{ up: open }" />
    </button>
    <ul v-show="open" class="list">
      <li v-for="row in rows" :key="row.code"><span class="strong">{{ row.name }}.</span> {{ row.reason }}</li>
    </ul>
  </section>
</template>

<style scoped>
.note { border-radius: var(--radius-md); background: var(--state-info-tint); color: #123f75; }
.head { display: flex; align-items: center; gap: 12px; width: 100%; padding: 14px 16px; text-align: left; color: inherit; }
.ic { flex: none; color: var(--state-info); }
.title { flex: 1; font-weight: 700; font-size: 14px; }
.count { font-weight: 600; color: #3d6ea8; }
.caret { flex: none; color: #3d6ea8; transition: transform var(--dur-fast) var(--ease); }
.caret.up { transform: rotate(180deg); }
.list { margin: 0; padding: 0 16px 14px 48px; display: grid; gap: 4px; font-size: 14px; line-height: 1.45; }
.strong { font-weight: 700; }
</style>
