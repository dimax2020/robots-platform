<script setup lang="ts">
import { PhArrowRight, PhArrowLeft, PhClockCounterClockwise, PhCopy, PhEye, PhEyeSlash, PhGearSix } from '@phosphor-icons/vue'
import { objectTypeLabel, objectTypeImage, steps } from '~/data/projects'
import { useLiveProject } from '~/composables/useLiveProject'
import { platformSend } from '~/composables/usePlatform'
import { fetchErrorMessage } from '~/utils/errors'
import { useDemoProjects } from '~/composables/useDemoProjects'
import { usePlatformCompare, type MatchGroup } from '~/composables/usePlatformCompare'
import { photoFor } from '~/data/placeholders'
import type { EconReport } from '~/composables/usePlatformEconomy'

const route = useRoute()
const router = useRouter()
const doc = useLiveProject(computed(() => route.params.id as string))
const project = computed(() => doc.shell.value)
const record = doc.record
const { role } = useRole()
const demos = useDemoProjects()
useHead({ title: () => `${project.value?.name ?? 'Проект'} · Кабинет проекта` })
const { remainingHit, picksFor } = usePlatformCompare(computed(() => record.value?.id ?? ''))
const groups = ref<MatchGroup[]>([])
const economy = ref<EconReport | null>(null)
const summaryPending = ref(false)

const fleet = computed(() => groups.value.flatMap((group) => {
  const hit = remainingHit(group)
  if (!hit) return []
  return [{
    code: group.process_code,
    process: group.process_name,
    name: hit.name,
    count: hit.count,
    image: photoFor(hit.image_url, hit.name, group.process_code),
  }]
}))
const purchase = computed(() => economy.value?.scenarios.find((item) => item.key === 'purchase') ?? null)
const paybackText = computed(() => {
  const value = purchase.value?.payback.value
  if (value == null) return ''
  return `${value.toLocaleString('ru-RU', { maximumFractionDigits: 1, minimumFractionDigits: 1 })} лет`
})

const loadSummary = async () => {
  const current = record.value
  if (!current?.can_edit) {
    groups.value = []
    economy.value = null
    return
  }
  summaryPending.value = true
  try {
    const match = await platformSend<{ groups: MatchGroup[] }>(`/projects/${current.id}/match`, 'POST', { site: current.site })
    groups.value = match.groups
    const picks = picksFor(match.groups)
    economy.value = Object.keys(picks).length
      ? await platformSend<EconReport>(`/projects/${current.id}/economy`, 'POST', { site: current.site, picks })
      : null
  } catch {
    groups.value = []
    economy.value = null
  } finally {
    summaryPending.value = false
  }
}
watch(() => record.value?.id, () => { void loadSummary() })
const fmtNum = (v: unknown) => (typeof v === 'number' ? v.toLocaleString('ru-RU') : v == null || v === '' ? '—' : String(v))
const area = computed(() => fmtNum(record.value?.site.area_m2))
const shifts = computed(() => fmtNum(record.value?.site.shifts_per_day))
const enabledCount = computed(() => record.value?.processes.filter((p) => p.enabled).length ?? 0)

/* Копия: владелец дублирует свой проект, пользователь забирает опубликованное демо к себе. */
const busy = ref('')
const note = ref('')
const copyProject = async () => {
  if (!record.value || busy.value) return
  busy.value = 'copy'
  note.value = ''
  try {
    const copy = await platformSend<{ id: string }>(`/projects/${record.value.id}/copy`, 'POST')
    await router.push(`/projects/${copy.id}`)
  } catch (e: unknown) {
    note.value = fetchErrorMessage(e, 'Не удалось скопировать проект')
  } finally {
    busy.value = ''
  }
}
/* Публикация демо: до неё объект видит только администратор, после — все, но для чтения. */
const togglePublish = async () => {
  if (!record.value || busy.value) return
  busy.value = 'publish'
  note.value = ''
  try {
    await platformSend(`/admin/projects/${record.value.id}/demo`, 'PUT', { published: !record.value.published })
    await doc.load()
    await demos.load(true)
  } catch (e: unknown) {
    note.value = fetchErrorMessage(e, 'Не удалось изменить публикацию')
  } finally {
    busy.value = ''
  }
}
const stepDesc: Record<string, string> = {
  params: 'Профиль площадки и список задач',
  match: 'Подходит, требует проверки, исключён',
  scenarios: 'Без роботизации, по задачам, оптимальный парк',
  economics: 'CAPEX, OPEX, эффект, интервал окупаемости',
  'what-if': 'Чувствительность к допущениям',
  plan: '2D-план и реплей смены',
  report: 'Печать, Excel, выгрузка плана',
}
</script>

<template>
  <section v-if="project" class="container cab">
    <NuxtLink to="/projects" class="back body-sm"><PhArrowLeft :size="14" weight="bold" /> Проекты</NuxtLink>

    <div class="hero glass glass-xl" v-reveal>
      <img :src="objectTypeImage[project.objectType]" alt="" class="hero-img">
      <div class="hero-body">
        <div class="row tags">
          <UiBadge tone="neutral">{{ project.industry && project.industry !== objectTypeLabel[project.objectType] ? `${project.industry} — ${objectTypeLabel[project.objectType]}` : objectTypeLabel[project.objectType] }}</UiBadge>
          <UiBadge v-if="project.isDemo && project.readonly" tone="info">Демо · только просмотр</UiBadge>
          <UiBadge v-else-if="project.isDemo" :tone="project.published ? 'ok' : 'warn'">{{ project.published ? 'Демо · опубликовано' : 'Демо · черновик' }}</UiBadge>
        </div>
        <h1 class="hero-2">{{ project.name }}</h1>
        <div class="facts">
          <div><span class="caption">Площадь</span><span class="mono-md">{{ area }} м²</span></div>
          <div><span class="caption">Смены</span><span class="mono-md">{{ shifts }}</span></div>
          <div><span class="caption">Процессов в подборе</span><span class="mono-md">{{ enabledCount }}</span></div>
          <div><span class="caption">Отрасль</span><span class="mono-md">{{ project.industry || '—' }}</span></div>
        </div>
        <div class="versions">
          <PhClockCounterClockwise :size="16" />
          <span class="body-sm">{{ project.readonly ? 'Демо-объект собрал администратор: параметры, подбор, коэффициенты и схема открываются для просмотра. Чтобы менять — скопируйте к себе.' : 'Расчёт идёт на текущей версии каталога и модели платформы и откроется снова с теми же исходными данными.' }}</span>
        </div>
        <UiCallout v-if="note" tone="danger">{{ note }}</UiCallout>
      </div>
      <div class="hero-cta">
        <UiButton :to="`/projects/${project.id}/params`" size="lg">{{ project.readonly ? 'Смотреть параметры' : 'К параметрам' }}<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
        <UiButton v-if="role !== 'guest'" variant="secondary" :disabled="busy === 'copy'" @click="copyProject"><template #icon><PhCopy :size="16" /></template>{{ project.readonly ? 'Скопировать в мои проекты' : 'Копировать проект' }}</UiButton>
        <UiButton v-else to="/login" variant="secondary"><template #icon><PhCopy :size="16" /></template>Войти, чтобы скопировать</UiButton>
        <template v-if="project.isDemo && role === 'admin'">
          <UiButton :variant="project.published ? 'ghost' : 'secondary'" :disabled="busy === 'publish'" @click="togglePublish">
            <template #icon><component :is="project.published ? PhEyeSlash : PhEye" :size="16" weight="bold" /></template>{{ project.published ? 'Снять с публикации' : 'Опубликовать демо' }}
          </UiButton>
          <UiButton to="/admin/demo" variant="ghost"><template #icon><PhGearSix :size="16" /></template>Все демо</UiButton>
        </template>
      </div>
    </div>

    <div class="grid-12 main">
      <div class="span-7 steps-col" v-reveal="1">
        <div class="h3">Шаги расчёта</div>
        <ol class="steps">
          <li v-for="(s, i) in steps" :key="s.code" class="st glass">
            <span class="st-n"><span class="mono-sm">{{ i + 1 }}</span></span>
            <div class="st-body">
              <div class="h4">{{ s.label }}</div>
              <div class="caption">{{ stepDesc[s.code] }}</div>
            </div>
            <NuxtLink :to="`/projects/${project.id}/${s.path}`" class="st-go"><PhArrowRight :size="16" weight="bold" /></NuxtLink>
          </li>
        </ol>
      </div>

      <aside class="span-5 side" v-reveal="2">
        <div class="result glass-graphite glass-graphite-solid">
          <div class="label">Состав парка</div>
          <div class="h3">Оптимальный состав парка</div>
          <p v-if="summaryPending" class="caption">Считаем роботов этого проекта…</p>
          <template v-else-if="fleet.length">
            <p class="caption">{{ fleet.length }} {{ fleet.length === 1 ? 'процесс' : 'процессов' }} с выбранным роботом. Процессы без робота в расчёт не входят.</p>
            <div v-if="paybackText" class="pay">
              <span class="caption">Окупаемость покупки</span>
              <span class="display-3">{{ paybackText }}</span>
              <span class="caption">по текущим параметрам площадки</span>
            </div>
            <ul class="fleet">
              <li v-for="row in fleet" :key="row.code">
                <img :src="row.image" :alt="row.name">
                <span class="who"><span class="body-sm">{{ row.name }}</span><span class="caption">{{ row.process }}</span></span>
                <span class="mono-md">{{ row.count != null ? `× ${row.count.toLocaleString('ru-RU')}` : '—' }}</span>
              </li>
            </ul>
          </template>
          <p v-else class="caption">Роботы появятся после подбора. Пока ни один процесс не закрыт подходящим решением.</p>
          <UiButton :to="`/projects/${project.id}/${fleet.length ? 'economics' : 'match'}`" variant="onGraphite" block>{{ fleet.length ? 'Открыть экономику' : 'Открыть подбор' }}</UiButton>
        </div>
      </aside>
    </div>
  </section>
</template>

<style scoped>
.cab { padding-top: var(--space-8); padding-bottom: var(--space-16); display: grid; gap: var(--space-8); }
.back { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-muted); font-weight: 600; }
.hero { display: grid; grid-template-columns: 260px 1fr auto; gap: var(--space-8); align-items: center; padding: 12px; }
.hero > * { position: relative; z-index: 1; }
.hero-img { width: 260px; height: 220px; object-fit: cover; border-radius: 22px; }
.hero-body { display: grid; gap: 14px; padding: 8px 0; }
.facts { display: flex; gap: var(--space-8); }
.facts > div { display: grid; gap: 2px; }
.facts .mono-md { color: var(--ink-strong); }
.versions { display: flex; gap: 8px; align-items: flex-start; color: var(--ink-muted); max-width: 64ch; }
.hero-cta { display: grid; gap: 8px; padding-right: 12px; align-self: start; padding-top: 8px; }
.main { align-items: start; }
.steps-col { display: grid; gap: var(--space-4); }
.steps { display: grid; gap: 8px; }
.st { display: grid; grid-template-columns: auto 1fr auto; gap: 14px; align-items: center; padding: 12px 14px; border-radius: 16px; }
.st > * { position: relative; z-index: 1; }
.st-n { width: 32px; height: 32px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; background: rgba(15, 20, 19, 0.06); color: var(--ink-muted); }
.done .st-n { background: var(--surface-brand-tint); color: var(--brand-700); }
.cur .st-n { background: var(--surface-graphite); color: var(--brand-300); }
.cur { box-shadow: inset 0 1px 0 var(--glass-stroke), 0 0 0 2px var(--brand-500), var(--glass-shadow); }
.locked { opacity: 0.6; }
.st-go { width: 36px; height: 36px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; color: var(--ink-strong); background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); transition: all var(--dur-fast) var(--ease); }
.st-go:hover { background: var(--surface-graphite); color: #fff; }
.side { position: sticky; top: 96px; }
.result { padding: var(--space-6); display: grid; gap: 12px; }
.result > * { position: relative; z-index: 1; }
.result .label { color: var(--brand-300); }
.result .h3,
.result .body-sm { color: var(--ink-on-graphite); }
.result .caption { color: rgba(241, 245, 243, 0.72); }
.pay { display: grid; gap: 4px; padding: 14px 0; border-top: 1px solid rgba(255, 255, 255, 0.1); border-bottom: 1px solid rgba(255, 255, 255, 0.1); }
.pay .display-3 { color: var(--brand-300); }
.fleet { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
.fleet li { display: grid; grid-template-columns: 36px minmax(0, 1fr) auto; gap: 10px; align-items: center; }
.fleet img { width: 36px; height: 36px; border-radius: 8px; object-fit: cover; background: rgba(255, 255, 255, 0.08); }
.who { display: grid; gap: 1px; min-width: 0; }
.who .body-sm { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fleet .mono-md { color: var(--brand-300); }
@media (max-width: 1100px) { .hero { grid-template-columns: 1fr; } .hero-img { width: 100%; height: 200px; } .span-7, .span-5 { grid-column: span 12; } .side { position: static; } }
</style>
