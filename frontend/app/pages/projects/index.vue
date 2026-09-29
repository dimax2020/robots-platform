<script setup lang="ts">
import { PhPlus, PhCopy, PhTrash, PhArrowRight, PhEye, PhGearSix, PhSignIn } from '@phosphor-icons/vue'
import { objectTypeLabel, objectTypeImage, type ObjectType } from '~/data/projects'
import { fetchErrorMessage } from '~/utils/errors'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { demoPath, useDemoProjects } from '~/composables/useDemoProjects'

interface OwnProject {
  id: string
  slug: string | null
  name: string
  object_code: string
  object_name: string
  industry: string
  is_demo: boolean
  published: boolean
}

useHead({ title: 'Проекты' })
const { role } = useRole()
const own = ref<OwnProject[]>([])
const pending = ref(false)
const error = ref<unknown>(null)
const busy = ref('')
const demos = useDemoProjects()

const load = async () => {
  if (role.value === 'guest') { own.value = []; return }
  pending.value = true
  error.value = null
  try {
    const page = await platformGet<{ items: OwnProject[] }>('/projects')
    /* Демо-объекты администратора живут в отдельном разделе админки, здесь только обычные проекты. */
    own.value = page.items.filter((row) => !row.is_demo)
  } catch (err) {
    error.value = err
  } finally {
    pending.value = false
  }
}
watch(role, () => { void load() }, { immediate: true })

const demo = demos.items
const typeOf = (code: string): ObjectType => code === 'airport' || code === 'hospital' ? code : 'warehouse'
const labelOf = (row: { object_code: string; object_name: string }) => objectTypeLabel[typeOf(row.object_code)] ?? row.object_name
const imageOf = (row: { object_code: string }) => objectTypeImage[typeOf(row.object_code)] ?? objectTypeImage.warehouse

const copyProject = async (id: string) => {
  busy.value = id
  try {
    await platformSend(`/projects/${id}/copy`, 'POST')
    await load()
  } catch (err) {
    error.value = err
  } finally {
    busy.value = ''
  }
}
const removeProject = async (id: string) => {
  if (!window.confirm('Удалить проект? Файлы схемы этого проекта тоже будут удалены.')) return
  busy.value = id
  try {
    await platformSend(`/projects/${id}`, 'DELETE')
    await load()
  } catch (err) {
    error.value = err
  } finally {
    busy.value = ''
  }
}
</script>

<template>
  <section class="container projects">
    <div class="between head" v-reveal>
      <div>
        <div class="label">Проекты</div>
        <h1 class="hero-2">{{ role === 'guest' ? 'Демо-проекты' : 'Сохранённые расчёты' }}</h1>
        <p class="body muted">{{ role === 'guest' ? 'Опубликованные администратором демо-объекты. Открываются без входа, только для просмотра.' : 'Каждый прогон хранит версию каталога и модели: расчёт открывается снова с теми же исходными данными.' }}</p>
      </div>
      <UiButton v-if="role !== 'guest'" to="/projects/new" size="lg"><template #icon><PhPlus :size="18" weight="bold" /></template>Новый проект</UiButton>
      <UiButton v-else to="/login" size="lg"><template #icon><PhSignIn :size="18" weight="bold" /></template>Войти как пользователь</UiButton>
    </div>

    <UiCallout v-if="role === 'guest'" tone="info" title="Гостю доступны только демо-проекты">Чтобы создать свой проект, сохранять расчёты и копировать демо к себе, войдите как пользователь.</UiCallout>

    <div v-if="role !== 'guest'" class="block" v-reveal>
      <div class="h3 block-title">Мои проекты <span class="mono-sm muted">{{ own.length }}</span></div>
      <UiCallout v-if="error" tone="danger" title="Не удалось загрузить проекты">{{ fetchErrorMessage(error, 'Сервер не ответил.') }}</UiCallout>
      <div v-else-if="pending" class="list glass glass-xl"><UiSkeleton h="120px" /></div>
      <div v-else-if="!own.length" class="list glass glass-xl">
        <div class="empty-own">
          <div class="h4">Пока нет сохранённых расчётов</div>
          <div class="caption">Создайте проект — площадка и задачи предзаполнятся из профиля объекта.</div>
        </div>
      </div>
      <div v-else class="list glass glass-xl">
        <table class="table">
          <thead><tr><th>Название</th><th>Тип объекта</th><th>Отрасль</th><th class="num">Действия</th></tr></thead>
          <tbody>
            <tr v-for="p in own" :key="p.id">
              <td><NuxtLink :to="`/projects/${p.id}`" class="strong name">{{ p.name }}</NuxtLink></td>
              <td><span class="row"><img :src="imageOf(p)" class="thumb" alt="">{{ labelOf(p) }}</span></td>
              <td class="caption">{{ p.industry || '—' }}</td>
              <td class="num actions">
                <UiButton :to="`/projects/${p.id}`" size="sm" variant="secondary">Открыть <template #after><PhArrowRight :size="14" weight="bold" /></template></UiButton>
                <button type="button" class="ic" aria-label="Копировать" :disabled="busy === p.id" @click="copyProject(p.id)"><PhCopy :size="16" /></button>
                <button type="button" class="ic danger" aria-label="Удалить" :disabled="busy === p.id" @click="removeProject(p.id)"><PhTrash :size="16" /></button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div class="block" v-reveal="1">
      <div class="between">
        <div class="h3 block-title">Демо-объекты <span class="mono-sm muted">{{ demo.length }}</span></div>
        <UiButton v-if="role === 'admin'" to="/admin/demo" size="sm" variant="secondary"><template #icon><PhGearSix :size="14" weight="bold" /></template>Ведение демо</UiButton>
      </div>
      <UiCallout v-if="demos.loaded.value && !demo.length" tone="info" title="Опубликованных демо пока нет">{{ role === 'admin' ? 'Соберите демо-объект в админке и опубликуйте его.' : 'Администратор ещё не опубликовал ни одного демо-объекта.' }}</UiCallout>
      <div v-else class="demos">
        <NuxtLink v-for="p in demo" :key="p.id" :to="demoPath(p)" class="demo glass">
          <img :src="imageOf(p)" :alt="labelOf(p)">
          <div class="demo-body">
            <div class="label">{{ labelOf(p) }}</div>
            <div class="h4">{{ p.name }}</div>
            <div class="caption"><PhEye :size="12" /> Только просмотр · {{ p.industry || labelOf(p) }}{{ p.area_m2 ? ` · ${Number(p.area_m2).toLocaleString('ru-RU')} м²` : '' }}</div>
          </div>
        </NuxtLink>
      </div>
    </div>
  </section>
</template>

<style scoped>
.projects { padding-top: var(--space-12); padding-bottom: var(--space-16); display: grid; gap: var(--space-8); }
.head { align-items: flex-end; }
.head > div { display: grid; gap: 10px; max-width: 64ch; }
.block { display: grid; gap: var(--space-4); }
.block-title { display: flex; align-items: baseline; gap: 10px; }
.list { padding: var(--space-3); }
.list table { position: relative; z-index: 1; }
.empty-own { position: relative; z-index: 1; padding: var(--space-8); display: grid; gap: 6px; }
.name { color: var(--ink-strong); }
.thumb { width: 28px; height: 28px; border-radius: 8px; object-fit: cover; }
.progress { display: grid; gap: 4px; min-width: 140px; }
.bar { height: 4px; border-radius: 2px; background: rgba(15, 20, 19, 0.08); overflow: hidden; }
.bar span { display: block; height: 100%; border-radius: 2px; background: var(--brand-500); }
.actions { white-space: nowrap; }
.ic { display: inline-flex; align-items: center; justify-content: center; width: 32px; height: 32px; border-radius: 8px; color: var(--ink-muted); margin-left: 4px; transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease); vertical-align: middle; }
.ic:hover { background: rgba(15, 20, 19, 0.06); color: var(--ink-strong); }
.ic.danger:hover { background: var(--state-danger-tint); color: var(--state-danger); }
.demos { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-4); }
.demo { display: grid; grid-template-columns: 96px 1fr; gap: 12px; padding: 8px; align-items: center; transition: transform var(--dur-mid) var(--ease); }
.demo:hover { transform: translateY(-2px); }
.demo img { width: 96px; height: 96px; object-fit: cover; border-radius: 12px; position: relative; z-index: 1; }
.demo-body { display: grid; gap: 4px; padding-right: 8px; position: relative; z-index: 1; }
.demo-body .caption { display: inline-flex; align-items: center; gap: 4px; }
</style>
