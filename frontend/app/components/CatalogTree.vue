<script setup lang="ts">
import { PhCaretRight } from '@phosphor-icons/vue'
import { countNode, type TreeNode } from '~/data/catalog'

const props = withDefaults(defineProps<{ nodes: TreeNode[]; depth?: number; selected?: string; openAll?: boolean }>(), { depth: 0 })
const emit = defineEmits<{ select: [label: string, ids: string[], node: TreeNode] }>()

const open = reactive<Record<string, boolean>>({})
props.nodes.forEach((n, i) => { open[n.label] = props.openAll || (props.depth < 2 && i === 0) })

const idsOf = (n: TreeNode): string[] => n.productIds ? n.productIds : Array.from(new Set((n.children ?? []).flatMap(idsOf)))
// countNode считает уникальные позиции: одно решение законно попадает в несколько ветвей,
// и сумма счётчиков детей завышает число втрое
const countOf = countNode
const toggle = (n: TreeNode) => {
  if (n.children) open[n.label] = !open[n.label]
  emit('select', n.label, idsOf(n), n)
}
</script>

<template>
  <ul class="tree" :class="`d${depth}`">
    <li v-for="n in nodes" :key="n.label">
      <button type="button" class="node" :class="{ on: selected === n.label, leaf: !n.children, open: open[n.label] }" @click="toggle(n)">
        <PhCaretRight v-if="n.children" :size="12" weight="bold" class="caret" />
        <span v-else class="leaf-dot" />
        <span class="t">{{ n.label }}</span>
        <span class="c mono-sm">{{ countOf(n) }}</span>
      </button>
      <CatalogTree v-if="n.children && open[n.label]" :nodes="n.children" :depth="depth + 1" :selected="selected" :open-all="openAll" @select="(l, ids, node) => emit('select', l, ids, node)" />
    </li>
  </ul>
</template>

<style scoped>
.tree { display: grid; gap: 2px; }
.tree.d1 { padding-left: 14px; margin-top: 2px; border-left: 1px solid var(--border-hairline); margin-left: 9px; }
.tree.d2, .tree.d3 { padding-left: 14px; margin-top: 2px; border-left: 1px solid var(--border-hairline); margin-left: 9px; }
.node { width: 100%; display: grid; grid-template-columns: 14px 1fr auto; align-items: center; gap: 8px; min-height: 34px; padding: 0 8px; border-radius: 9px; font-size: 14px; font-weight: 600; color: var(--ink-body); text-align: left; transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease); }
.d0 > li > .node { font-weight: 700; color: var(--ink-strong); }
.d3 .node, .leaf { font-weight: 500; }
.node:hover { background: rgba(15, 20, 19, 0.05); }
.node.on { background: var(--surface-brand-tint); color: var(--brand-ink); }
.caret { color: var(--ink-faint); transition: transform var(--dur-fast) var(--ease); }
.node.open .caret { transform: rotate(90deg); }
.leaf-dot { width: 4px; height: 4px; border-radius: 50%; background: var(--border-strong); margin: 0 auto; }
.c { color: var(--ink-muted); }
.node.on .c { color: var(--brand-700); }
.t { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
