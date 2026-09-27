<script setup lang="ts">
import { PhPlus, PhTrash, PhCheckSquare, PhSquare } from '@phosphor-icons/vue'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { fetchErrorMessage } from '~/utils/errors'

definePageMeta({ layout: 'admin', middleware: 'admin', pageTransition: false })
useHead({ title: 'Админка · Отрасли' })

interface Industry { code: string; name: string; objects: string[] }
interface Draft { code: string | null; name: string; objects: string[] }

const list = ref<Industry[]>([])
const objects = ref<{ code: string; name: string }[]>([])
const draft = ref<Draft | null>(null)
const notice = ref<{ ok: boolean; text: string } | null>(null)
const saving = ref(false)

const load = async () => {
  const [items, tree] = await Promise.all([
    platformGet<Industry[]>('/admin/industries'),
    platformGet<{ objects: { code: string; name: string }[] }>('/catalog/tree'),
  ])
  list.value = items
  objects.value = tree.objects
}
onMounted(() => { void load().catch((err) => { notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось загрузить отрасли') } }) })

const objectName = (code: string) => objects.value.find((item) => item.code === code)?.name ?? code
const edit = (item: Industry) => { draft.value = { code: item.code, name: item.name, objects: [...item.objects] } }
const create = () => { draft.value = { code: null, name: '', objects: [] } }
const toggleObject = (code: string) => {
  if (!draft.value) return
  const set = new Set(draft.value.objects)
  if (set.has(code)) set.delete(code); else set.add(code)
  draft.value.objects = [...set]
}

const save = async () => {
  if (!draft.value || saving.value) return
  saving.value = true
  notice.value = null
  try {
    await platformSend('/admin/industries', 'POST', draft.value)
    notice.value = { ok: true, text: `Отрасль «${draft.value.name}» сохранена` }
    draft.value = null
    await load()
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось сохранить') }
  } finally {
    saving.value = false
  }
}

const remove = async (item: Industry) => {
  if (!confirm(`Удалить отрасль «${item.name}»? Объекты останутся, пропадёт только связь с отраслью.`)) return
  try {
    await platformSend(`/admin/industries/${item.code}`, 'DELETE')
    if (draft.value?.code === item.code) draft.value = null
    await load()
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось удалить') }
  }
}
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Каталог" title="Отрасли" lead="Верхний уровень дерева. Один объект может входить в несколько отраслей: склад — и в логистику, и в ритейл.">
      <UiButton @click="create"><template #icon><PhPlus :size="16" weight="bold" /></template>Новая отрасль</UiButton>
    </AdminHead>
    <UiCallout v-if="notice" :tone="notice.ok ? 'ok' : 'danger'">{{ notice.text }}</UiCallout>

    <section v-if="draft" class="glass glass-xl a-panel">
      <div class="h3">{{ draft.code ? 'Изменить отрасль' : 'Новая отрасль' }}</div>
      <label class="a-fld"><span class="caption">Название</span><input v-model="draft.name" class="input" placeholder="Например, Ритейл"></label>
      <div class="a-fld">
        <span class="caption">Объекты отрасли</span>
        <div class="checks">
          <button v-for="obj in objects" :key="obj.code" type="button" class="check" :class="{ on: draft.objects.includes(obj.code) }" @click="toggleObject(obj.code)">
            <PhCheckSquare v-if="draft.objects.includes(obj.code)" :size="18" weight="fill" /><PhSquare v-else :size="18" />
            <span>{{ obj.name }}</span>
          </button>
        </div>
        <span class="caption">Новый объект заводится на странице <NuxtLink to="/admin/objects" class="link">Объекты</NuxtLink>.</span>
      </div>
      <div class="a-row">
        <UiButton :disabled="saving || !draft.name.trim()" @click="save">{{ saving ? 'Сохраняем…' : 'Сохранить' }}</UiButton>
        <UiButton variant="secondary" @click="draft = null">Отмена</UiButton>
      </div>
    </section>

    <section class="glass glass-xl a-panel">
      <div class="a-tbl">
        <table class="table">
          <thead><tr><th>Отрасль</th><th>Объекты</th><th /></tr></thead>
          <tbody>
            <tr v-for="item in list" :key="item.code">
              <td><button type="button" class="strong nm" @click="edit(item)">{{ item.name }}</button><span class="caption block mono-sm">{{ item.code }}</span></td>
              <td>
                <div class="a-chips">
                  <NuxtLink v-for="code in item.objects" :key="code" :to="`/admin/objects?code=${code}`" class="a-pill ok">{{ objectName(code) }}</NuxtLink>
                  <span v-if="!item.objects.length" class="a-pill warn">нет объектов</span>
                </div>
              </td>
              <td class="num">
                <span class="acts">
                  <UiButton size="sm" variant="secondary" @click="edit(item)">Изменить</UiButton>
                  <button type="button" class="a-x" :aria-label="`Удалить ${item.name}`" @click="remove(item)"><PhTrash :size="16" /></button>
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.checks { display: flex; flex-wrap: wrap; gap: 8px; }
.check { display: inline-flex; align-items: center; gap: 8px; min-height: 38px; padding: 0 12px; border-radius: 10px; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px var(--border-hairline); font-weight: 600; font-size: 14px; }
.check svg { color: var(--ink-faint); }
.check.on { box-shadow: inset 0 0 0 1px var(--brand-400); background: #fff; }
.check.on svg { color: var(--brand-600); }
.nm { text-align: left; }
.nm:hover { color: var(--link); }
.block { display: block; }
.acts { display: inline-flex; gap: 6px; align-items: center; }
</style>
