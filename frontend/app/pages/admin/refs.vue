<script setup lang="ts">
import { PhPlus, PhDotsSixVertical, PhArrowRight } from '@phosphor-icons/vue'
import { catalogTree, countNode } from '~/data/catalog'

definePageMeta({ layout: 'admin' })
useHead({ title: 'Админка · Справочники' })

const tab = ref('industries')
const tabs = [
  { id: 'industries', label: 'Отрасли', count: 6 },
  { id: 'objects', label: 'Типы объектов', count: 4 },
  { id: 'processes', label: 'Процессы', count: 9 },
  { id: 'solutions', label: 'Типы решений', count: 8 },
  { id: 'attrs', label: 'Характеристики', count: 27 },
]
const data: Record<string, { code: string; label: string; note?: string; count: number }[]> = {
  industries: [
    { code: 'logistics', label: 'Логистика и склады', count: 6 },
    { code: 'transport', label: 'Транспорт и аэропорты', count: 2 },
    { code: 'health', label: 'Медицина', count: 1 },
    { code: 'manufacturing', label: 'Производство', count: 3 },
    { code: 'retail', label: 'Ритейл', count: 2 },
    { code: 'security', label: 'Охрана и мониторинг', count: 1 },
  ],
  objects: [
    { code: 'warehouse', label: 'Склад', note: 'Полный путь расчёта', count: 8 },
    { code: 'airport', label: 'Аэропорт', note: 'Короткий путь: параметры и подбор', count: 2 },
    { code: 'hospital', label: 'Медучреждение', note: 'Короткий путь: параметры и подбор', count: 1 },
    { code: 'plant', label: 'Цех', note: 'Не в MVP', count: 3 },
  ],
  processes: [
    { code: 'move', label: 'Внутрискладское перемещение', count: 5 }, { code: 'pick', label: 'Комплектация', count: 3 }, { code: 'palletize', label: 'Паллетирование', count: 2 }, { code: 'inventory', label: 'Инвентаризация', count: 1 }, { code: 'sort', label: 'Сортировка', count: 2 }, { code: 'storage', label: 'Плотное хранение', count: 1 }, { code: 'patrol', label: 'Патрулирование', count: 2 }, { code: 'disinfect', label: 'Дезинфекция', count: 1 }, { code: 'transport', label: 'Транспортировка грузов', count: 2 },
  ],
  solutions: catalogTree.flatMap((n) => (n.children ?? []).map((c) => ({ code: c.label.toLowerCase().replace(/\s+/g, '_'), label: c.label, note: n.label, count: countNode(c) }))),
  attrs: [
    { code: 'payload_kg', label: 'Грузоподъёмность, кг', note: 'Технические · число', count: 9 }, { code: 'speed_ms', label: 'Скорость, м/с', note: 'Технические · число', count: 8 }, { code: 'autonomy_h', label: 'Автономность, ч', note: 'Технические · число', count: 7 }, { code: 'accuracy_mm', label: 'Точность позиционирования, мм', note: 'Технические · число', count: 6 }, { code: 'ip', label: 'Класс защиты', note: 'Технические · перечисление', count: 8 }, { code: 'floor_flat', label: 'Ровность пола, мм/2 м', note: 'Инфраструктура · число', count: 5 }, { code: 'floor_load', label: 'Нагрузка на пол, т/м²', note: 'Инфраструктура · число', count: 4 }, { code: 'aisle_mm', label: 'Ширина проезда, мм', note: 'Инфраструктура · число', count: 6 }, { code: 'price_rub', label: 'Цена, ₽', note: 'Экономика · число · интервал', count: 7 },
  ],
}
const list = computed(() => data[tab.value] ?? [])
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
