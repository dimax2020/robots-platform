<script setup lang="ts">
import { PhPencilSimple, PhMagnifyingGlass } from '@phosphor-icons/vue'
import { availabilityLabel, availabilityTone, type Availability } from '~/data/catalog'

const { products } = useCatalog()

definePageMeta({ layout: 'admin' })
useHead({ title: 'Админка · Продукты' })

const q = ref('')
const status = ref<'' | Availability>('')
const auto = ref<'' | 'yes' | 'no'>('')
const fill = ref<'' | 'low' | 'ok'>('')
// Порог задаётся вручную: у большинства решений заполнены только цена, регион и класс,
// поэтому единой отсечки, годной и для поиска пробелов, и для отбора готовых карточек, нет
const fillPct = ref(70)
const threshold = computed(() => fillPct.value / 100)
const list = computed(() => products.value.filter((p) =>
  (!q.value || (p.name + p.manufacturer).toLowerCase().includes(q.value.toLowerCase()))
  && (!status.value || p.availability === status.value)
  && (!auto.value || (auto.value === 'yes') === p.autoMatch)
  && (!fill.value || (fill.value === 'low' ? p.completeness < threshold.value : p.completeness >= threshold.value)),
))
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Продукты" title="Список продуктов" lead="Фильтры по типу, статусу, готовности к автоподбору и заполненности: порог заполненности задаётся ползунком. Форма карточки повторяет публичную: те же шесть групп из справочника.">
    </AdminHead>

    <div class="filters glass" v-reveal>
      <label class="f search"><PhMagnifyingGlass :size="16" weight="bold" /><input v-model="q" class="s-in" placeholder="Название или производитель"></label>
      <select v-model="status" class="select"><option value="">Любой статус</option><option value="operation">В эксплуатации</option><option value="piloting">Пилот</option><option value="rnd">Разработка</option></select>
      <select v-model="auto" class="select"><option value="">Автоподбор: любой</option><option value="yes">Готов к автоподбору</option><option value="no">Не готов</option></select>
      <select v-model="fill" class="select"><option value="">Заполненность: любая</option><option value="ok">Не ниже порога</option><option value="low">Ниже порога</option></select>
      <label class="f thr">
        <span class="caption">Порог</span>
        <input
          v-model.number="fillPct"
          type="range"
          min="0"
          max="100"
          step="5"
          class="range"
          :style="{ '--pct': `${fillPct}%` }"
          aria-label="Порог заполненности карточки, процент"
        >
        <span class="mono-sm thr-val">{{ fillPct }}%</span>
      </label>
    </div>

    <div class="count caption">
      Показано {{ list.length }} из {{ products.length }}. Порог {{ fillPct }}% — им же окрашены полосы в таблице.
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
            <td><span class="fillb"><span class="fill-bar"><span :style="{ width: `${p.completeness * 100}%` }" :class="{ low: p.completeness < threshold }" /></span><span class="mono-sm">{{ Math.round(p.completeness * 100) }}%</span></span></td>
            <td class="num mono-sm">18.09.2026</td>
            <td class="num"><NuxtLink :to="`/admin/products/${p.slug}`" class="ic" aria-label="Редактировать"><PhPencilSimple :size="16" /></NuxtLink></td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
/* max-content у селектов: подписи вроде «Заполненность: любая» длиннее любой ровной
   сетки и на фиксированной ширине обрезаются многоточием */
.filters { display: grid; grid-template-columns: minmax(240px, 1fr) repeat(3, max-content) 205px; gap: 10px; padding: 10px; }
.filters > * { position: relative; z-index: 1; }
.search, .thr { display: flex; align-items: center; gap: 10px; padding: 0 14px; border-radius: var(--radius-sm); background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); color: var(--ink-muted); }
.s-in { flex: 1; background: none; border: 0; outline: none; min-height: 42px; font-weight: 600; color: var(--ink-strong); }
.thr { min-height: 42px; cursor: pointer; }
.thr .range { flex: 1; }
.thr-val { flex: none; width: 4ch; text-align: right; color: var(--ink-strong); }
.count { padding: 0 10px; }
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

@media (max-width: 1100px) { .filters { grid-template-columns: 1fr 1fr; } }
</style>
