<script setup lang="ts">
import { platformGet, platformSend } from '~/composables/usePlatform'
import { siteFieldMeta } from '~/data/siteFields'

definePageMeta({ layout: 'admin' })
useHead({ title: 'Админка · Объекты' })

interface Input { key: string; label: string; kind: string }
interface Proc {
  code: string
  name: string
  product_count: number
  enabled: boolean
  inputs: Input[]
  bindings: Record<string, string>
}
interface Setup { code: string; name: string; processes: Proc[] }
interface Obj { code: string; name: string }

const objects = ref<Obj[]>([])
const draft = ref<Setup | null>(null)
const selected = ref('')
const query = ref('')
const siteQuery = ref('')
const notice = ref('')
const saving = ref(false)

const fields = siteFieldMeta.map((field) => ({ key: field.key, label: field.plain || field.label, unit: field.unit || '' }))
const fieldText = (field: { label: string; unit: string }) => (field.unit ? `${field.label} · ${field.unit}` : field.label)
const shown = computed(() => {
  const text = query.value.trim().toLowerCase()
  const list = draft.value?.processes ?? []
  if (!text) return list
  return list.filter((item) => `${item.name} ${item.code}`.toLowerCase().includes(text))
})
const enabledCount = computed(() => draft.value?.processes.filter((item) => item.enabled).length ?? 0)
const shownFields = computed(() => {
  const text = siteQuery.value.trim().toLowerCase()
  const picked = new Set<string>()
  for (const process of draft.value?.processes ?? []) {
    for (const value of Object.values(process.bindings)) if (value) picked.add(value)
  }
  return fields.filter((field) => picked.has(field.key) || !text || `${field.label} ${field.key}`.toLowerCase().includes(text))
})

const loadList = async () => {
  const tree = await platformGet<{ objects: Obj[] }>('/catalog/tree')
  objects.value = tree.objects
  if (!selected.value && objects.value[0]) await open(objects.value[0].code)
}

const open = async (code: string) => {
  selected.value = code
  query.value = ''
  siteQuery.value = ''
  const setup = await platformGet<Setup>(`/admin/objects/${code}`)
  for (const process of setup.processes) {
    for (const input of process.inputs) {
      if (process.bindings[input.key] == null) process.bindings[input.key] = ''
    }
  }
  draft.value = setup
  notice.value = ''
}

const save = async () => {
  if (!draft.value) return
  saving.value = true
  notice.value = ''
  const bindings = []
  for (const process of draft.value.processes) {
    for (const input of process.inputs) {
      const siteKey = process.bindings[input.key]
      if (siteKey) bindings.push({ process_code: process.code, input_key: input.key, site_key: siteKey })
    }
  }
  try {
    draft.value = await platformSend<Setup>(`/admin/objects/${draft.value.code}/setup`, 'PUT', {
      processes: draft.value.processes.filter((item) => item.enabled).map((item) => item.code),
      bindings,
    })
    for (const process of draft.value.processes) {
      for (const input of process.inputs) {
        if (process.bindings[input.key] == null) process.bindings[input.key] = ''
      }
    }
    notice.value = 'Настройка сохранена'
  } catch (err) {
    notice.value = err instanceof Error ? err.message : 'Не удалось сохранить'
  } finally {
    saving.value = false
  }
}

onMounted(() => { void loadList().catch((err) => { notice.value = String(err) }) })
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Объекты" title="Настройка объектов" lead="У объекта включаются процессы. Для каждого фильтра и для формулы количества здесь выбирается, какое поле площадки подставить." />
    <UiCallout v-if="notice" :tone="notice === 'Настройка сохранена' ? 'ok' : 'danger'">{{ notice }}</UiCallout>

    <div class="split">
      <aside class="glass list">
        <button v-for="object in objects" :key="object.code" type="button" class="proc" :class="{ on: object.code === selected }" @click="open(object.code)">
          <span class="body-sm strong">{{ object.name }}</span>
        </button>
      </aside>

      <div v-if="draft" class="editor">
        <section class="glass glass-xl panel">
          <div class="in">
            <div class="head">
              <div>
                <div class="h3">{{ draft.name }}</div>
                <div class="caption">{{ enabledCount }} процессов в объекте. Уже созданные проекты этот список не переписывают.</div>
              </div>
              <UiButton size="sm" :disabled="saving" @click="save">{{ saving ? 'Сохраняем…' : 'Сохранить' }}</UiButton>
            </div>
            <div class="row">
              <label class="fld"><span class="caption">Поиск процессов</span><input v-model="query" class="input" placeholder="мойка, паллет, охрана"></label>
              <label class="fld"><span class="caption">Поле площадки</span><input v-model="siteQuery" class="input" placeholder="смена, площадь, шум"></label>
            </div>

            <article v-for="process in shown" :key="process.code" class="block">
              <div class="row">
                <div>
                  <div class="body-sm strong">{{ process.name }}</div>
                  <div class="caption">{{ process.product_count }} роботов</div>
                </div>
                <UiButton size="sm" :variant="process.enabled ? 'primary' : 'secondary'" @click="process.enabled = !process.enabled">
                  {{ process.enabled ? 'В объекте' : 'Добавить' }}
                </UiButton>
              </div>
              <template v-if="process.enabled">
                <p v-if="!process.inputs.length" class="caption">У процесса нет величин. Их задают в настройке процессов.</p>
                <div v-for="input in process.inputs" :key="input.key" class="row">
                  <div class="bind-name">
                    <span class="body-sm strong">{{ input.label }}</span>
                    <span class="caption">{{ input.kind === 'count' ? 'количество' : 'фильтр' }}</span>
                  </div>
                  <select v-model="process.bindings[input.key]" class="select">
                    <option value="">поле не задано</option>
                    <option v-for="field in shownFields" :key="field.key" :value="field.key">{{ fieldText(field) }}</option>
                  </select>
                </div>
              </template>
            </article>
          </div>
        </section>
      </div>
    </div>
  </div>
</template>

<style scoped>
.split { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: var(--space-5); align-items: start; }
.list { padding: 8px; display: grid; gap: 6px; }
.list > * { position: relative; z-index: 1; }
.proc { display: grid; gap: 2px; text-align: left; padding: 10px 12px; border-radius: 14px; background: rgba(255, 255, 255, 0.55); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.proc.on { background: #fff; box-shadow: inset 0 0 0 1px var(--brand-400); }
.proc .body-sm { color: var(--ink-strong); }
.panel { overflow: hidden; }
.in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: var(--space-4); }
.head, .row { display: flex; gap: 12px; align-items: end; justify-content: space-between; flex-wrap: wrap; }
.block { display: grid; gap: 10px; padding-top: 12px; border-top: 1px solid var(--border-hairline); }
.fld { display: grid; gap: 6px; flex: 1; min-width: 180px; }
.bind-name { display: grid; gap: 2px; min-width: 180px; }
.select, .input { width: 100%; }
@media (max-width: 1100px) { .split { grid-template-columns: 1fr; } }
</style>
