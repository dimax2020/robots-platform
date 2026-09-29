<script setup lang="ts">
import { PhCaretRight, PhCaretDown, PhPencilSimple } from '@phosphor-icons/vue'
import { platformGet } from '~/composables/usePlatform'
import { fetchErrorMessage } from '~/utils/errors'
import { pluralRu } from '~/data/adminLabels'

definePageMeta({ layout: 'admin', middleware: 'admin', pageTransition: false })
useHead({ title: 'Админка · Дерево каталога' })

interface TypeNode { code: string; name: string; products: number }
interface ProcessNode { code: string; name: string; products: number; types: TypeNode[] }
interface ObjectNode { code: string; name: string; in_match?: boolean; processes: ProcessNode[] }
interface IndustryNode { code: string; name: string; objects: ObjectNode[] }
interface Tree {
  industries: IndustryNode[]
  orphan_processes: ProcessNode[]
  totals: { products: number; untyped: number; without_process: number; types: number }
}

const tree = ref<Tree | null>(null)
const failure = ref('')
const open = reactive(new Set<string>())
const toggle = (key: string) => { if (open.has(key)) open.delete(key); else open.add(key) }

const load = async () => {
  try {
    tree.value = await platformGet<Tree>('/admin/catalog/tree')
    for (const industry of tree.value.industries) open.add(`i:${industry.code}`)
  } catch (err) {
    failure.value = fetchErrorMessage(err, 'Не удалось загрузить дерево')
  }
}
onMounted(load)

const objectProducts = (obj: ObjectNode) => obj.processes.reduce((sum, item) => sum + item.products, 0)
const productsLink = (process: string, type: string) => `/admin/products?process=${process}&type=${type || '-'}`
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Каталог" title="Дерево каталога" lead="Отрасль → объект → процесс → тип решения → продукт, как в ТЗ 3.3.1. Тип под процессом выводится из роботов процесса. Карандаш открывает редактор узла." />
    <UiCallout v-if="failure" tone="danger">{{ failure }}</UiCallout>

    <div v-if="tree" class="totals">
      <NuxtLink to="/admin/products" class="glass tot"><span class="tot-in"><span class="display-4">{{ tree.totals.products }}</span><span class="caption">продуктов в каталоге</span></span></NuxtLink>
      <NuxtLink to="/admin/catalog/types" class="glass tot"><span class="tot-in"><span class="display-4">{{ tree.totals.types }}</span><span class="caption">типов решений</span></span></NuxtLink>
      <NuxtLink to="/admin/catalog/types?tab=untyped" class="glass tot" :class="{ warn: tree.totals.untyped }"><span class="tot-in"><span class="display-4">{{ tree.totals.untyped }}</span><span class="caption">без типа решения</span></span></NuxtLink>
      <NuxtLink to="/admin/products?process=-" class="glass tot" :class="{ warn: tree.totals.without_process }"><span class="tot-in"><span class="display-4">{{ tree.totals.without_process }}</span><span class="caption">не привязаны к процессу</span></span></NuxtLink>
    </div>

    <section v-if="tree" class="glass glass-xl a-panel">
      <div v-for="industry in tree.industries" :key="industry.code || 'none'" class="lvl">
        <div class="node n0">
          <button type="button" class="tg" @click="toggle(`i:${industry.code}`)"><component :is="open.has(`i:${industry.code}`) ? PhCaretDown : PhCaretRight" :size="14" weight="bold" /></button>
          <span class="h4">{{ industry.name }}</span>
          <span class="caption">{{ industry.objects.length }} {{ pluralRu(industry.objects.length, 'объект', 'объекта', 'объектов') }}</span>
          <NuxtLink v-if="industry.code" to="/admin/catalog/industries" class="ed" title="Изменить отрасль"><PhPencilSimple :size="14" /></NuxtLink>
        </div>
        <template v-if="open.has(`i:${industry.code}`)">
          <div v-if="!industry.objects.length" class="caption empty">Объектов нет. Их выбирают на странице отраслей.</div>
          <div v-for="obj in industry.objects" :key="obj.code" class="lvl">
            <div class="node n1">
              <button type="button" class="tg" @click="toggle(`o:${industry.code}:${obj.code}`)"><component :is="open.has(`o:${industry.code}:${obj.code}`) ? PhCaretDown : PhCaretRight" :size="14" weight="bold" /></button>
              <span class="body-sm strong">{{ obj.name }}</span>
              <span class="caption">{{ obj.processes.length }} {{ pluralRu(obj.processes.length, 'процесс', 'процесса', 'процессов') }} · {{ objectProducts(obj) }} привязок роботов</span>
              <span v-if="obj.in_match === false" class="a-pill">не в подборе</span>
              <NuxtLink :to="`/admin/objects?code=${obj.code}`" class="ed" title="Настроить объект"><PhPencilSimple :size="14" /></NuxtLink>
            </div>
            <template v-if="open.has(`o:${industry.code}:${obj.code}`)">
              <div v-if="!obj.processes.length" class="caption empty">У объекта нет процессов.</div>
              <div v-for="proc in obj.processes" :key="proc.code" class="lvl">
                <div class="node n2">
                  <button type="button" class="tg" :disabled="!proc.types.length" @click="toggle(`p:${obj.code}:${proc.code}`)"><component :is="open.has(`p:${obj.code}:${proc.code}`) ? PhCaretDown : PhCaretRight" :size="14" weight="bold" /></button>
                  <span class="body-sm">{{ proc.name }}</span>
                  <span class="a-pill" :class="{ warn: !proc.products }">{{ proc.products }} {{ pluralRu(proc.products, 'робот', 'робота', 'роботов') }}</span>
                  <NuxtLink :to="`/admin/processes?code=${proc.code}`" class="ed" title="Настроить процесс"><PhPencilSimple :size="14" /></NuxtLink>
                </div>
                <div v-if="open.has(`p:${obj.code}:${proc.code}`)" class="types">
                  <NuxtLink v-for="type in proc.types" :key="type.code || 'none'" :to="productsLink(proc.code, type.code)" class="type" :class="{ warn: !type.code }">
                    <span>{{ type.name }}</span><span class="mono-sm">{{ type.products }}</span>
                  </NuxtLink>
                </div>
              </div>
            </template>
          </div>
        </template>
      </div>

      <div v-if="tree.orphan_processes.length" class="a-block">
        <div class="h4">Процессы без объекта</div>
        <p class="caption">В подбор не попадают: у них нет объекта, значит, проект их не видит.</p>
        <div class="a-chips">
          <NuxtLink v-for="proc in tree.orphan_processes" :key="proc.code" :to="`/admin/processes?code=${proc.code}`" class="a-pill warn">{{ proc.name }} · {{ proc.products }}</NuxtLink>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.totals { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-4); }
.tot { border-radius: var(--radius-lg); }
.tot-in { position: relative; z-index: 1; display: grid; gap: 4px; padding: var(--space-4) var(--space-5); }
.tot.warn .display-4 { color: var(--state-warn); }
.lvl { display: grid; gap: 2px; }
.node { display: flex; align-items: center; gap: 10px; min-height: 38px; border-radius: 10px; padding-right: 8px; }
.node:hover { background: rgba(15, 20, 19, 0.04); }
.n1 { padding-left: 28px; }
.n2 { padding-left: 56px; }
.tg { width: 26px; height: 26px; border-radius: 7px; display: inline-grid; place-items: center; color: var(--ink-muted); flex: none; }
.tg:disabled { opacity: 0.3; }
.tg:hover:not(:disabled) { background: rgba(15, 20, 19, 0.06); }
.ed { margin-left: auto; color: var(--ink-faint); width: 28px; height: 28px; display: inline-grid; place-items: center; border-radius: 8px; }
.ed:hover { color: var(--link); background: rgba(15, 20, 19, 0.05); }
.empty { padding: 4px 0 8px 64px; }
.types { display: flex; flex-wrap: wrap; gap: 6px; padding: 4px 0 10px 92px; }
.type { display: inline-flex; gap: 8px; align-items: center; padding: 5px 10px; border-radius: 10px; font-size: 13.5px; font-weight: 600; background: var(--surface-brand-tint); color: var(--brand-ink); }
.type.warn { background: var(--state-warn-tint); color: var(--state-warn); }
.type:hover { filter: brightness(0.97); }
@media (max-width: 1100px) { .totals { grid-template-columns: 1fr 1fr; } }
</style>
