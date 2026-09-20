<script setup lang="ts">
import { PhUploadSimple, PhPlus, PhTrash, PhPencilSimple, PhArrowRight, PhFileXls } from '@phosphor-icons/vue'
import { projectById, demoTasks, objectTypeLabel } from '~/data/projects'

const route = useRoute()
const project = computed(() => projectById(route.params.id as string))
useHead({ title: () => `Параметры · ${project.value.name}` })

// Поля площадки приходят из справочника по типу объекта (заглушка)
const siteFields: Record<string, { key: string; label: string; unit?: string; value: string; edited?: boolean; hint?: string }[]> = {
  warehouse: [
    { key: 'area', label: 'Площадь', unit: 'м²', value: '12 000' },
    { key: 'height', label: 'Высота стеллажей', unit: 'мм', value: '5 400' },
    { key: 'aisle', label: 'Ширина проездов', unit: 'мм', value: '2 900', edited: true, hint: 'Было 3 200 из xlsx' },
    { key: 'floor', label: 'Ровность пола', unit: 'мм на 2 м', value: '3' },
    { key: 'floor_load', label: 'Нагрузка на пол', unit: 'т/м²', value: '2,5' },
    { key: 'shifts', label: 'Смен в сутки', value: '2' },
    { key: 'shift_h', label: 'Длительность смены', unit: 'ч', value: '8' },
    { key: 'wifi', label: 'Покрытие Wi-Fi', value: 'Полное, 5 ГГц' },
    { key: 'temp', label: 'Температура', unit: '°C', value: 'от +12 до +26' },
    { key: 'staff', label: 'Персонал склада', unit: 'чел.', value: '38' },
  ],
  airport: [
    { key: 'area', label: 'Площадь багажной зоны', unit: 'м²', value: '6 400' },
    { key: 'apron', label: 'Расстояние до перрона', unit: 'м', value: '420' },
    { key: 'flights', label: 'Рейсов в пик', unit: 'в час', value: '14' },
    { key: 'shifts', label: 'Смен в сутки', value: '3' },
    { key: 'gnss', label: 'Покрытие RTK GNSS', value: 'Частичное' },
  ],
  hospital: [
    { key: 'area', label: 'Площадь корпуса', unit: 'м²', value: '9 800' },
    { key: 'floors', label: 'Этажей', value: '6' },
    { key: 'lifts', label: 'Лифты с доступом для роботов', value: '2 из 4' },
    { key: 'rooms', label: 'Палат для дезинфекции', value: '84' },
    { key: 'shifts', label: 'Смен в сутки', value: '3' },
  ],
}
const fields = computed(() => siteFields[project.value.objectType] ?? siteFields.warehouse!)
const tasks = ref(demoTasks.map((t) => ({ ...t })))
const fmtNum = (v: number) => v.toLocaleString('ru-RU')
</script>

<template>
  <ProjectShell :project="project" current="params" title="Параметры площадки и задач" lead="Поля площадки зависят от типа объекта и приходят из справочника. Ручные правки видны как правки и не растворяются в исходных данных.">
    <template #actions>
      <UiButton variant="secondary"><template #icon><PhFileXls :size="16" weight="duotone" /></template>Импорт xlsx / csv</UiButton>
      <UiButton :to="`/projects/${project.id}/match`" size="lg">Запустить подбор<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
    </template>

    <div class="grid-12 params">
      <div class="span-5 site glass" v-reveal>
        <div class="sec-head">
          <div><div class="h3">Площадка</div><div class="caption">{{ objectTypeLabel[project.objectType] }} · {{ fields.length }} полей из справочника</div></div>
          <UiBadge tone="info" size="sm">из xlsx · 19 сен</UiBadge>
        </div>
        <div class="fields">
          <label v-for="f in fields" :key="f.key" class="fld" :class="{ edited: f.edited }">
            <span class="fld-label body-sm">{{ f.label }}<span v-if="f.unit" class="muted"> · {{ f.unit }}</span></span>
            <span class="fld-in">
              <input class="input input-mono" :value="f.value">
              <PhPencilSimple v-if="f.edited" :size="14" weight="bold" class="edit-ic" :title="f.hint" />
            </span>
            <span v-if="f.edited" class="caption edited-note">Правка вручную. {{ f.hint }}</span>
          </label>
        </div>
      </div>

      <div class="span-7 tasks" v-reveal="1">
        <div class="tasks-head sec-head">
          <div><div class="h3">Задачи</div><div class="caption">Процесс, поток, маршрут, тара, пиковая нагрузка, времена погрузки и разгрузки</div></div>
          <UiButton variant="secondary" size="sm"><template #icon><PhPlus :size="14" weight="bold" /></template>Добавить задачу</UiButton>
        </div>
        <div class="task-list">
          <div v-for="(t, i) in tasks" :key="t.id" class="task glass">
            <div class="task-top">
              <span class="mono-sm tn">{{ i + 1 }}</span>
              <select class="select task-proc" :value="t.process">
                <option>Внутрискладское перемещение</option><option>Комплектация заказов</option><option>Паллетирование</option><option>Инвентаризация</option><option>Приёмка и отгрузка</option>
              </select>
              <button type="button" class="ic" aria-label="Удалить задачу"><PhTrash :size="16" /></button>
            </div>
            <div class="task-grid">
              <label class="tf"><span class="caption">Поток</span><input class="input input-mono" :value="t.flow"></label>
              <label class="tf"><span class="caption">Длина маршрута · м</span><input class="input input-mono" :value="t.route ? fmtNum(t.route) : ''" :placeholder="t.route ? '' : 'не применимо'"></label>
              <label class="tf"><span class="caption">Тара</span><input class="input" :value="t.container"></label>
              <label class="tf"><span class="caption">Пиковая нагрузка · коэф.</span><input class="input input-mono" :value="String(t.peak).replace('.', ',')"></label>
              <label class="tf"><span class="caption">Погрузка · с</span><input class="input input-mono" :value="t.load || ''" :placeholder="t.load ? '' : 'не применимо'"></label>
              <label class="tf"><span class="caption">Разгрузка · с</span><input class="input input-mono" :value="t.unload || ''" :placeholder="t.unload ? '' : 'не применимо'"></label>
            </div>
          </div>
        </div>
        <div class="upload glass">
          <PhUploadSimple :size="22" weight="duotone" />
          <div><div class="h4">Импорт параметров из xlsx или csv</div><div class="caption">Соответствие колонок задаётся профилем импорта. Ручные правки после импорта помечаются.</div></div>
          <UiButton variant="secondary" size="sm">Выбрать файл</UiButton>
        </div>
      </div>
    </div>
  </ProjectShell>
</template>

<style scoped>
.params { align-items: start; }
.site { padding: var(--space-6); display: grid; gap: var(--space-5); position: sticky; top: 96px; }
.site > * { position: relative; z-index: 1; }
.sec-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-4); }
.fields { display: grid; gap: 12px; }
.fld { display: grid; gap: 6px; }
.fld-label { font-weight: 600; color: var(--ink-strong); }
.fld-in { position: relative; }
.edit-ic { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); color: var(--state-warn); }
.edited .input { border-color: rgba(138, 82, 0, 0.35); background: #fff8ee; }
.edited-note { color: var(--state-warn); }
.tasks { display: grid; gap: var(--space-4); }
.task-list { display: grid; gap: 10px; }
.task { padding: 14px 16px 16px; display: grid; gap: 12px; }
.task > * { position: relative; z-index: 1; }
.task-top { display: grid; grid-template-columns: auto 1fr auto; gap: 10px; align-items: center; }
.tn { width: 28px; height: 28px; border-radius: 8px; background: var(--surface-graphite); color: var(--brand-300); display: inline-flex; align-items: center; justify-content: center; }
.task-proc { max-width: 360px; font-weight: 700; color: var(--ink-strong); }
.ic { width: 36px; height: 36px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; color: var(--ink-muted); transition: all var(--dur-fast) var(--ease); }
.ic:hover { background: var(--state-danger-tint); color: var(--state-danger); }
.task-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.tf { display: grid; gap: 4px; }
.upload { display: grid; grid-template-columns: auto 1fr auto; gap: 14px; align-items: center; padding: 16px 18px; border-style: dashed; }
.upload > * { position: relative; z-index: 1; }
.upload svg { color: var(--brand-700); }
@media (max-width: 1100px) { .span-5, .span-7 { grid-column: span 12; } .site { position: static; } }
</style>
