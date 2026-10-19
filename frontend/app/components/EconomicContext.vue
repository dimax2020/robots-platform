<script setup lang="ts">
import type { EconReport, EconFleet } from '~/composables/usePlatformEconomy'
import { siteFieldMeta } from '~/data/siteFields'
import { formatOrigin } from '~/utils/demoSynthetic'
const props = defineProps<{ report: EconReport }>()
const processName = (code?: string) => props.report.fleet.find(p => p.process_code === code)?.process_name
  || props.report.manual_processes?.find(p => p.process_code === code)?.process_name || 'Объект'
const inputMeta = (sizing: EconFleet['sizing'], key: string) => {
  const source = sizing?.input_provenance?.[key]
  const site = siteFieldMeta.find(field => field.key === key)
  const labels: Record<string, string> = { work_time_h: 'Автономность', charge_time_h: 'Зарядка', payload_kg: 'Буксируемая нагрузка' }
  return { label: source?.label || site?.plain || site?.label || labels[key] || key,
    unit: source?.unit || site?.unit || '', origin: source?.origin || (source?.source_id ? 'published_catalog' : 'project_input') }
}
const capacity = (sizing: EconFleet['sizing']) => {
  const area = sizing?.daily_capacity_per_machine_m2
  const value = area ?? sizing?.daily_capacity_per_machine_items
  return typeof value === 'number' ? `${value.toLocaleString('ru-RU', { maximumFractionDigits: 2 })} ${area != null ? 'м²/сут' : 'тележек/сут'} на машину` : ''
}
</script>

<template>
  <AssessmentNotice :report="report">
    <slot />
    <details v-if="report.blockers?.length"><summary>Ограничения расчёта · {{ report.blockers.length }}</summary>
      <ul><li v-for="(item, index) in report.blockers" :key="index">{{ processName(item.process_code) }}: {{ item.message }}</li></ul>
    </details>
    <details v-if="report.manual_processes?.length"><summary>Ручные процессы вне программы · {{ report.manual_processes.length }}</summary>
      <ul><li v-for="item in report.manual_processes" :key="item.process_code">{{ item.process_name }}</li></ul>
    </details>
    <details v-if="report.fleet.length"><summary>Расчётный парк · {{ report.robots }} машин</summary>
      <ul><li v-for="item in report.fleet" :key="item.process_code">{{ item.process_name }}: {{ item.name }} — {{ item.count_used }} шт.
        <span v-if="item.sizing?.model"> · {{ item.sizing.model }} · рабочие {{ item.sizing.working_count }}, резерв {{ item.sizing.reserve_count }}</span>
        <span v-if="item.uses_demo_synthetic"> · расчёт на синтетических входах</span>
        <details v-if="item.sizing?.inputs"><summary>Входы и производительность модели</summary>
          <p>{{ capacity(item.sizing) }}</p>
          <table class="table"><thead><tr><th>Параметр</th><th>Значение</th><th>Происхождение</th></tr></thead>
            <tbody><tr v-for="(value, key) in item.sizing.inputs" :key="key"><td>{{ inputMeta(item.sizing, key).label }}</td>
              <td>{{ value.toLocaleString('ru-RU') }} {{ inputMeta(item.sizing, key).unit }}</td><td>{{ formatOrigin(inputMeta(item.sizing, key).origin) }}</td></tr></tbody>
          </table>
        </details>
      </li></ul>
    </details>
    <details v-if="report.demo_synthetic?.length"><summary>Источники и синтетические входы</summary>
      <div v-for="(group, i) in report.demo_synthetic" :key="i"><strong>{{ group.process_name }} · {{ group.name }}</strong><DemoSyntheticNotice :values="group.fields" /></div>
    </details>
  </AssessmentNotice>
</template>
