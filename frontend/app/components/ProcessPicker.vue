<script setup lang="ts">
/* Поиск процесса и короткий список. Уже выбранные живут отдельно, их можно снять, не листая весь справочник. */
const props = defineProps<{
  processes: { code: string; name: string }[]
  modelValue: string[]
}>()
const emit = defineEmits<{ 'update:modelValue': [string[]] }>()

const query = ref('')
const needle = computed(() => query.value.trim().toLocaleLowerCase('ru'))

const chosen = computed(() => props.modelValue
  .map((code) => props.processes.find((item) => item.code === code))
  .filter((item): item is { code: string; name: string } => Boolean(item)))

/* Пока человек не написал хотя бы две буквы, не показываем весь справочник. Там чужие отрасли. */
const hits = computed(() => {
  const taken = new Set(props.modelValue)
  if (needle.value.length < 2) return []
  return props.processes.filter((item) => {
    if (taken.has(item.code)) return false
    return item.name.toLocaleLowerCase('ru').includes(needle.value)
  })
})

const add = (code: string) => {
  if (props.modelValue.includes(code)) return
  emit('update:modelValue', [...props.modelValue, code])
}
const remove = (code: string) => {
  emit('update:modelValue', props.modelValue.filter((item) => item !== code))
}
const onEnter = () => {
  const first = hits.value[0]
  if (needle.value && first) add(first.code)
}
</script>

<template>
  <div class="picker">
    <input
      v-model="query"
      class="input"
      type="search"
      placeholder="Что делает робот: паллеты, уборка"
      @keydown.enter.prevent="onEnter"
    >
    <div class="hits" role="listbox" aria-label="Подходящие процессы">
      <p v-if="needle.length < 2" class="caption empty">Напишите хотя бы две буквы. Подходящие процессы появятся здесь, по три строки.</p>
      <p v-else-if="!hits.length" class="caption empty">Такого процесса нет. Попробуйте другое слово, например «паллет» или «уборка».</p>
      <div v-for="item in hits" :key="item.code" class="hit" role="option">
        <span>{{ item.name }}</span>
        <button type="button" class="add" @click="add(item.code)">Добавить</button>
      </div>
    </div>
    <div v-if="chosen.length" class="picked" aria-label="Выбранные процессы">
      <span v-for="item in chosen" :key="item.code" class="chip">
        {{ item.name }}
        <button type="button" class="rm" :aria-label="`Убрать ${item.name}`" @click="remove(item.code)">Убрать</button>
      </span>
    </div>
    <p v-else class="caption">Пока ничего не выбрано. Без процесса робота не предложат на объекте.</p>
  </div>
</template>

<style scoped>
.picker { display: grid; gap: 8px; min-width: 0; }
/* Три строки и прокрутка: страница не растёт вместе со справочником. */
.hits { max-height: 132px; overflow: auto; display: grid; gap: 4px; align-content: start; }
.hit { display: flex; align-items: center; justify-content: space-between; gap: 10px; min-height: 40px; padding: 6px 8px 6px 12px; border-radius: 10px; background: rgba(255, 255, 255, 0.62); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.hit span { min-width: 0; line-height: 1.35; font-weight: 600; color: var(--ink-strong); }
.add, .rm { flex: none; font-size: 13px; font-weight: 700; color: var(--link); }
.rm { color: var(--state-danger); }
.empty { padding: 8px 4px; }
.picked { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { display: inline-flex; align-items: center; gap: 8px; max-width: 100%; padding: 6px 8px 6px 12px; border-radius: 999px; background: var(--surface-brand-tint); color: var(--brand-ink); font-weight: 600; line-height: 1.35; }
</style>
