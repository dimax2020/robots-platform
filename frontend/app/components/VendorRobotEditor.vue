<script setup lang="ts">
import type { Gap } from '~/data/analytics'

const name = defineModel<string>('name', { required: true })
const summary = defineModel<string>('summary', { required: true })
const price = defineModel<string>('price', { required: true })
const processes = defineModel<string[]>('processes', { required: true })
const attrs = defineModel<{ key: string; label: string; value: string }[]>('attrs', { required: true })

const props = defineProps<{
  choices: { code: string; name: string }[]
  gaps: Gap[]
  busy?: boolean
}>()
const emit = defineEmits<{ submit: [] }>()

const hint = (key: string) => {
  const gap = props.gaps.find((item) => item.key === key)
  if (!gap) return ''
  return gap.used_in === 'условие'
    ? 'Без этого поля робот не участвует в подборе.'
    : 'Без этого поля робот попадает в подбор с пометкой.'
}
const priceHint = computed(() => hint('price_rub'))
const processHint = computed(() => (processes.value.length ? '' : 'Если работы не выбраны, робот в подбор не попадает.'))
</script>

<template>
  <div class="grid-2">
    <label class="a-fld">
      <span class="caption">Название</span>
      <input v-model="name" class="input">
    </label>
    <label class="a-fld">
      <span class="caption">Цена, руб.</span>
      <input v-model="price" class="input" inputmode="decimal" :class="{ 'is-error': priceHint && !price.trim() }">
      <span v-if="priceHint" class="field-hint">{{ priceHint }}</span>
    </label>
  </div>
  <label class="a-fld">
    <span class="caption">Коротко</span>
    <textarea v-model="summary" class="textarea" rows="3" placeholder="Например, возит паллеты по складу" />
  </label>
  <div class="a-fld">
    <span class="caption">Что умеет</span>
    <ProcessPicker v-model="processes" :processes="choices" />
    <span v-if="processHint" class="field-hint">{{ processHint }}</span>
  </div>
  <div v-if="attrs.length" class="attrs">
    <label v-for="item in attrs" :key="item.key" class="a-fld">
      <span class="caption">{{ item.label }}</span>
      <input v-model="item.value" class="input" :class="{ 'is-error': hint(item.key) && !item.value.trim() }" :placeholder="hint(item.key) ? 'Заполните, чтобы робот попал в подбор' : ''">
      <span v-if="hint(item.key)" class="field-hint">{{ hint(item.key) }}</span>
    </label>
  </div>
  <UiButton :disabled="busy || !name.trim()" @click="emit('submit')">Отправить на проверку</UiButton>
</template>

<style scoped>
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.attrs { display: grid; gap: 10px; }
@media (max-width: 800px) {
  .grid-2 { grid-template-columns: 1fr; }
}
</style>
