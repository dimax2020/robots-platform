<script setup lang="ts">
import { PhPlus, PhDotsSixVertical, PhArrowRight } from '@phosphor-icons/vue'
import { attrGroups, type TreeNode } from '~/data/catalog'

const { catalogTree, products, attributeDefs } = useCatalog()

definePageMeta({ layout: 'admin' })
useHead({ title: 'Админка · Справочники' })

const tab = ref('industries')

/** Уровни дерева каталога: у каждого узла считаем уникальные продукты в поддереве. */
const atDepth = (depth: number) => {
  const acc = new Map<string, { note: string; ids: Set<string> }>()
  const walk = (n: TreeNode, d: number, parent: string) => {
    if (d === depth) {
      const entry = acc.get(n.label) ?? { note: parent, ids: new Set<string>() }
      const collect = (x: TreeNode) => { x.productIds?.forEach((id) => entry.ids.add(id)); x.children?.forEach(collect) }
      collect(n)
      if (entry.note !== parent && !entry.note.includes(parent)) entry.note = `${entry.note}, ${parent}`
      acc.set(n.label, entry)
      return
    }
    n.children?.forEach((c) => walk(c, d + 1, n.label))
  }
  catalogTree.value.forEach((n) => walk(n, 0, ''))
  return [...acc.entries()]
    .map(([label, { note, ids }]) => ({ code: slugOf(label), label, note: note || undefined, count: ids.size }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, 'ru'))
}

const slugOf = (s: string) => s.toLowerCase().replace(/[^a-zа-яё0-9]+/g, '_').replace(/^_|_$/g, '')

const groupLabel = (code: string) => attrGroups.find((g) => g.code === code)?.label ?? code
const datatypeLabel: Record<string, string> = {
  number: 'число', text: 'текст', bool: 'да/нет', enum: 'перечисление', range: 'интервал',
}

const data = computed<Record<string, { code: string; label: string; note?: string; count: number }[]>>(() => ({
  industries: atDepth(0),
  objects: atDepth(1),
  processes: atDepth(2),
  solutions: atDepth(3),
  attrs: attributeDefs.value.map((d) => ({
    code: d.key,
    label: d.unit ? `${d.label}, ${d.unit}` : d.label,
    note: `${groupLabel(d.group_code)} · ${datatypeLabel[d.datatype] ?? d.datatype}`,
    // Сколько продуктов уже имеют это значение: у ТТХ из CSV это ноль, и так и должно быть видно
    count: products.value.filter((p) => p.attrs.some((a) => a.key === d.key && a.status === 'known')).length,
  })),
}))

const tabs = computed(() => [
  { id: 'industries', label: 'Отрасли', count: data.value.industries!.length },
  { id: 'objects', label: 'Типы объектов', count: data.value.objects!.length },
  { id: 'processes', label: 'Процессы', count: data.value.processes!.length },
  { id: 'solutions', label: 'Типы решений', count: data.value.solutions!.length },
  { id: 'attrs', label: 'Характеристики', count: data.value.attrs!.length },
])

const list = computed(() => data.value[tab.value] ?? [])
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Справочники" title="Отрасли, объекты, процессы, решения, характеристики" lead="Для типа решения задан набор характеристик, для типа объекта заданы параметры площадки и разрешённые процессы. Порядок полей в справочнике задаёт порядок в карточке.">
      <UiButton><template #icon><PhPlus :size="16" weight="bold" /></template>Добавить запись</UiButton>
    </AdminHead>

    <UiTabs v-model="tab" :tabs="tabs" />

    <div class="list glass glass-xl" v-reveal>
      <div class="l-in">
        <div v-for="(r, i) in list" :key="r.code" class="row">
          <span class="drag" aria-hidden="true"><PhDotsSixVertical :size="16" /></span>
          <span class="mono-sm idx">{{ String(i + 1).padStart(2, '0') }}</span>
          <span class="row-main">
            <span class="body strong">{{ r.label }}</span>
            <span v-if="r.note" class="caption">{{ r.note }}</span>
          </span>
          <span class="mono-sm code">{{ r.code }}</span>
          <span class="cnt caption">{{ r.count }} <span class="muted">{{ tab === 'attrs' ? 'типов решений' : 'продуктов' }}</span></span>
          <NuxtLink to="#" class="go" aria-label="Открыть"><PhArrowRight :size="16" weight="bold" /></NuxtLink>
        </div>
      </div>
    </div>

    <UiCallout tone="info" title="Отдельная страница для пар «объект → параметры»">Для склада: площадь, высота, ровность пола, нагрузка на пол, ширина проездов, температура, Wi-Fi, длительность смены и число смен. Для аэропорта и медучреждения набор короче: только то, что нужно короткому пути подбора.</UiCallout>
  </div>
</template>

<style scoped>
.list { padding: var(--space-2); }
.l-in { position: relative; z-index: 1; display: grid; }
.row { display: grid; grid-template-columns: auto auto 1fr auto 150px auto; gap: var(--space-4); align-items: center; padding: 12px 14px; border-radius: 12px; transition: background var(--dur-fast) var(--ease); }
.row:hover { background: rgba(255, 255, 255, 0.55); }
.row + .row { border-top: 1px solid var(--border-hairline); }
.drag { color: var(--ink-faint); cursor: grab; }
.idx { color: var(--ink-faint); }
.row-main { display: grid; gap: 2px; }
.code { color: var(--ink-muted); padding: 3px 8px; border-radius: 6px; background: rgba(15, 20, 19, 0.05); }
.cnt { text-align: right; }
.go { display: inline-flex; width: 32px; height: 32px; border-radius: 8px; align-items: center; justify-content: center; color: var(--ink-muted); }
.go:hover { background: var(--surface-graphite); color: var(--brand-300); }
</style>
