<script setup lang="ts">
import { PhPlus, PhTrash, PhEye, PhEyeSlash, PhArrowRight, PhCheckCircle, PhCircle } from '@phosphor-icons/vue'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { fetchErrorMessage } from '~/utils/errors'
import { demoPath, useDemoProjects, type DemoProject } from '~/composables/useDemoProjects'

definePageMeta({ layout: 'admin', middleware: 'admin', pageTransition: false })
useHead({ title: 'Админка · Демо-объекты' })

interface Draft { name: string; object_code: string; slug: string }

const list = ref<DemoProject[]>([])
const objects = ref<{ code: string; name: string; in_match?: boolean }[]>([])
const draft = ref<Draft | null>(null)
const notice = ref<{ ok: boolean; text: string } | null>(null)
const saving = ref(false)
const busy = ref('')
const slugEdit = reactive<Record<string, string>>({})
const published = useDemoProjects()

const load = async () => {
  const [page, tree] = await Promise.all([
    platformGet<{ items: DemoProject[] }>('/admin/projects/demo'),
    platformGet<{ objects: { code: string; name: string; in_match?: boolean }[] }>('/catalog/tree'),
  ])
  list.value = page.items
  objects.value = tree.objects.filter((item) => item.in_match !== false)
  for (const item of list.value) slugEdit[item.id] = item.slug ?? ''
}
onMounted(() => { void load().catch((err) => { notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось загрузить демо-объекты') } }) })

const create = () => { draft.value = { name: '', object_code: objects.value[0]?.code ?? '', slug: '' } }
const slugFrom = (name: string) => `demo-${name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'object'}`
const save = async () => {
  if (!draft.value || saving.value) return
  saving.value = true
  notice.value = null
  try {
    const created = await platformSend<{ id: string; name: string }>('/admin/projects/demo', 'POST', {
      name: draft.value.name.trim(),
      object_code: draft.value.object_code,
      slug: draft.value.slug.trim() || slugFrom(draft.value.object_code),
    })
    notice.value = { ok: true, text: `Демо «${created.name}» создано как черновик: пройдите шаги проекта и опубликуйте.` }
    draft.value = null
    await load()
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось создать демо') }
  } finally {
    saving.value = false
  }
}

const flags = async (item: DemoProject, body: Record<string, unknown>, done: string) => {
  busy.value = item.id
  notice.value = null
  try {
    await platformSend(`/admin/projects/${item.id}/demo`, 'PUT', body)
    notice.value = { ok: true, text: done }
    await load()
    await published.load(true)
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось сохранить') }
  } finally {
    busy.value = ''
  }
}
const togglePublish = (item: DemoProject) => flags(item, { published: !item.published }, item.published ? `«${item.name}» снято с публикации` : `«${item.name}» опубликовано: видно гостям и пользователям`)
const saveSlug = (item: DemoProject) => {
  const next = (slugEdit[item.id] ?? '').trim()
  if (next === (item.slug ?? '')) return
  void flags(item, { slug: next }, `Адрес «${item.name}» обновлён`)
}
const unmark = async (item: DemoProject) => {
  if (!confirm(`Убрать «${item.name}» из демо? Проект останется у администратора как обычный, публикация и адрес снимутся.`)) return
  await flags(item, { is_demo: false }, `«${item.name}» больше не демо`)
}
const remove = async (item: DemoProject) => {
  if (!confirm(`Удалить демо «${item.name}» со схемой и параметрами?`)) return
  busy.value = item.id
  try {
    await platformSend(`/projects/${item.id}`, 'DELETE')
    await load()
    await published.load(true)
  } catch (err) {
    notice.value = { ok: false, text: fetchErrorMessage(err, 'Не удалось удалить') }
  } finally {
    busy.value = ''
  }
}

/* Готовность к публикации: параметры площадки, хотя бы один процесс и собранная схема. */
const readiness = (item: DemoProject) => [
  { ok: item.area_m2 != null, label: 'параметры' },
  { ok: item.processes > 0, label: 'процессы' },
  { ok: item.has_layout, label: 'схема' },
]
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Проекты" title="Демо-объекты" lead="Демо — обычный проект администратора. Пройдите его шаги как пользователь: параметры, подбор, экономика, схема. Затем опубликуйте: гости и пользователи увидят его только для чтения и смогут скопировать к себе.">
      <UiButton @click="create"><template #icon><PhPlus :size="16" weight="bold" /></template>Новое демо</UiButton>
    </AdminHead>
    <UiCallout v-if="notice" :tone="notice.ok ? 'ok' : 'danger'">{{ notice.text }}</UiCallout>

    <section v-if="draft" class="glass glass-xl a-panel">
      <div class="h3">Новое демо</div>
      <div class="a-grid">
        <label class="a-fld"><span class="caption">Название</span><input v-model="draft.name" class="input" placeholder="Например, РЦ Софьино, зона B"></label>
        <label class="a-fld"><span class="caption">Тип объекта</span>
          <select v-model="draft.object_code" class="select"><option v-for="obj in objects" :key="obj.code" :value="obj.code">{{ obj.name }}</option></select>
        </label>
        <label class="a-fld"><span class="caption">Адрес (латиница)</span><input v-model="draft.slug" class="input input-mono" :placeholder="slugFrom(draft.object_code)"></label>
      </div>
      <span class="caption">Параметры площадки подставятся из значений по умолчанию объекта, дальше правятся на шаге «Параметры».</span>
      <div class="a-row">
        <UiButton :disabled="saving || !draft.name.trim() || !draft.object_code" @click="save">{{ saving ? 'Создаём…' : 'Создать черновик' }}</UiButton>
        <UiButton variant="secondary" @click="draft = null">Отмена</UiButton>
      </div>
    </section>

    <section class="glass glass-xl a-panel">
      <div class="a-tbl">
        <table class="table">
          <thead><tr><th>Демо</th><th>Адрес</th><th>Готовность</th><th>Статус</th><th /></tr></thead>
          <tbody>
            <tr v-for="item in list" :key="item.id">
              <td>
                <NuxtLink :to="demoPath(item)" class="strong nm">{{ item.name }}</NuxtLink>
                <span class="caption block">{{ item.object_name }}{{ item.industry ? ` · ${item.industry}` : '' }}</span>
              </td>
              <td>
                <span class="slug-row">
                  <span class="mono-sm muted">/projects/</span>
                  <input v-model="slugEdit[item.id]" class="input input-mono sm" :disabled="busy === item.id" @blur="saveSlug(item)" @keydown.enter.prevent="saveSlug(item)">
                </span>
              </td>
              <td>
                <span class="ready">
                  <span v-for="row in readiness(item)" :key="row.label" class="rd" :class="{ ok: row.ok }">
                    <component :is="row.ok ? PhCheckCircle : PhCircle" :size="14" :weight="row.ok ? 'fill' : 'regular'" />{{ row.label }}
                  </span>
                </span>
              </td>
              <td><UiBadge :tone="item.published ? 'ok' : 'warn'" size="sm">{{ item.published ? 'опубликовано' : 'черновик' }}</UiBadge></td>
              <td class="num">
                <span class="acts">
                  <UiButton size="sm" variant="secondary" :to="`${demoPath(item)}/params`">Открыть<template #after><PhArrowRight :size="14" weight="bold" /></template></UiButton>
                  <UiButton size="sm" :variant="item.published ? 'ghost' : 'primary'" :disabled="busy === item.id" @click="togglePublish(item)">
                    <template #icon><component :is="item.published ? PhEyeSlash : PhEye" :size="14" weight="bold" /></template>{{ item.published ? 'Снять' : 'Опубликовать' }}
                  </UiButton>
                  <button type="button" class="a-x" title="Сделать обычным проектом" :disabled="busy === item.id" @click="unmark(item)">не демо</button>
                  <button type="button" class="a-x" :aria-label="`Удалить ${item.name}`" :disabled="busy === item.id" @click="remove(item)"><PhTrash :size="16" /></button>
                </span>
              </td>
            </tr>
            <tr v-if="!list.length"><td colspan="5" class="caption">Демо-объектов пока нет. Создайте черновик, соберите его и опубликуйте.</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<style scoped>
.a-grid { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 12px; }
.nm { color: var(--ink-strong); }
.nm:hover { color: var(--link); }
.block { display: block; }
.slug-row { display: inline-flex; align-items: center; gap: 4px; }
.input.sm { height: 32px; min-height: 32px; font-size: 12px; width: 170px; }
.ready { display: inline-flex; flex-wrap: wrap; gap: 6px 10px; }
.rd { display: inline-flex; align-items: center; gap: 4px; font-size: 12px; color: var(--ink-faint); }
.rd.ok { color: var(--brand-700); }
.acts { display: inline-flex; gap: 6px; align-items: center; }
.a-x { font-size: 12px; font-weight: 600; }
@media (max-width: 1100px) { .a-grid { grid-template-columns: 1fr; } }
</style>
