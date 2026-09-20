<script setup lang="ts">
import { PhPlus, PhPencilSimple, PhMagnifyingGlass } from '@phosphor-icons/vue'
import { products, availabilityLabel, availabilityTone, type Availability } from '~/data/catalog'

definePageMeta({ layout: 'admin' })
useHead({ title: 'Админка · Продукты' })

const q = ref('')
const status = ref<'' | Availability>('')
const auto = ref<'' | 'yes' | 'no'>('')
const fill = ref<'' | 'low' | 'ok'>('')
const list = computed(() => products.filter((p) =>
  (!q.value || (p.name + p.manufacturer).toLowerCase().includes(q.value.toLowerCase()))
  && (!status.value || p.availability === status.value)
  && (!auto.value || (auto.value === 'yes') === p.autoMatch)
  && (!fill.value || (fill.value === 'low' ? p.completeness < 0.7 : p.completeness >= 0.7)),
))
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Продукты" title="Список продуктов" lead="Фильтры по типу, статусу, готовности к автоподбору и заполненности. Форма карточки повторяет публичную: те же шесть групп из справочника.">
      <UiButton to="/admin/products/new"><template #icon><PhPlus :size="16" weight="bold" /></template>Добавить продукт</UiButton>
    </AdminHead>

    <div class="filters glass" v-reveal>
      <label class="f search"><PhMagnifyingGlass :size="16" weight="bold" /><input v-model="q" class="s-in" placeholder="Название или производитель"></label>
      <select v-model="status" class="select"><option value="">Любой статус</option><option value="operation">В эксплуатации</option><option value="piloting">Пилот</option><option value="rnd">Разработка</option></select>
      <select v-model="auto" class="select"><option value="">Автоподбор: любой</option><option value="yes">Готов к автоподбору</option><option value="no">Не готов</option></select>
      <select v-model="fill" class="select"><option value="">Заполненность: любая</option><option value="ok">70% и выше</option><option value="low">Ниже 70%</option></select>
    </div>

    <div class="tbl glass glass-xl" v-reveal="1">
      <table class="table">
        <thead><tr><th>Продукт</th><th>Тип решения</th><th>Статус</th><th>УГТ</th><th>Автоподбор</th><th>Заполненность</th><th class="num">Изменён</th><th /></tr></thead>
        <tbody>
          <tr v-for="p in list" :key="p.id">
            <td><span class="row"><img :src="p.image" class="thumb" alt=""><span><NuxtLink :to="`/admin/products/${p.slug}`" class="strong">{{ p.name }}</NuxtLink><span class="caption block">{{ p.manufacturer }}</span></span></span></td>
            <td class="body-sm">{{ p.solutionType }}</td>
            <td><UiBadge :tone="availabilityTone[p.availability]" size="sm">{{ availabilityLabel[p.availability] }}</UiBadge></td>
            <td class="mono-sm">{{ p.trl }}</td>
            <td><UiBadge :tone="p.autoMatch ? 'ok' : 'neutral'" size="sm">{{ p.autoMatch ? 'Да' : 'Нет' }}</UiBadge></td>
            <td><span class="fillb"><span class="fill-bar"><span :style="{ width: `${p.completeness * 100}%` }" :class="{ low: p.completeness < 0.7 }" /></span><span class="mono-sm">{{ Math.round(p.completeness * 100) }}%</span></span></td>
            <td class="num mono-sm">18.09.2026</td>
            <td class="num"><NuxtLink :to="`/admin/products/${p.slug}`" class="ic" aria-label="Редактировать"><PhPencilSimple :size="16" /></NuxtLink></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.filters { display: grid; grid-template-columns: 1fr 190px 210px 210px; gap: 10px; padding: 10px; }
.filters > * { position: relative; z-index: 1; }
.search { display: flex; align-items: center; gap: 10px; padding: 0 14px; border-radius: var(--radius-sm); background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); color: var(--ink-muted); }
.s-in { flex: 1; background: none; border: 0; outline: none; min-height: 42px; font-weight: 600; color: var(--ink-strong); }
.tbl { padding: var(--space-3); }
.tbl table { position: relative; z-index: 1; }
.thumb { width: 36px; height: 36px; border-radius: 9px; object-fit: cover; }
.block { display: block; }
.fillb { display: grid; grid-template-columns: 80px auto; gap: 8px; align-items: center; }
.fill-bar { height: 6px; border-radius: 3px; background: rgba(15, 20, 19, 0.08); overflow: hidden; }
.fill-bar span { display: block; height: 100%; background: var(--brand-500); border-radius: 3px; }
.fill-bar span.low { background: var(--state-warn); }
.ic { display: inline-flex; width: 32px; height: 32px; border-radius: 8px; align-items: center; justify-content: center; color: var(--ink-muted); }
.ic:hover { background: rgba(15, 20, 19, 0.06); color: var(--ink-strong); }
</style>
