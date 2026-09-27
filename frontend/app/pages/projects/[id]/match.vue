<script setup lang="ts">
import { PhArrowRight } from '@phosphor-icons/vue'
import { fetchErrorMessage } from '~/utils/errors'
import { platformSend } from '~/composables/usePlatform'
import { useLiveProject } from '~/composables/useLiveProject'
import { photoFor } from '~/data/placeholders'
import { usePlatformCompare, type MatchGroup, type MatchHit } from '~/composables/usePlatformCompare'

const route = useRoute()
const router = useRouter()
const id = computed(() => route.params.id as string)
const live = useLiveProject(id)
const project = live.shell
const shell = live.shell
const pending = live.pending
const error = live.error
useHead({ title: () => `Подбор · ${shell.value?.name ?? 'проект'}` })

const groups = ref<MatchGroup[]>([])
const statusTab = ref('pass')
const statusOrder = ['pass', 'conditional', 'unknown', 'fail'] as const
const { inCompare, toggleCompare } = usePlatformCompare(id)
const loadingMatch = ref(true)
const matchError = ref('')
const startedAt = ref(0)
const now = ref(0)
let clock: ReturnType<typeof setInterval> | undefined
const ranFor = ref('')

const canRun = computed(() => Boolean(project.value))
const verdictLabel: Record<string, string> = {
  pass: 'Подходит',
  conditional: 'С условием',
  unknown: 'Уточнить',
  fail: 'Не подходит',
}
const verdictTone: Record<string, 'ok' | 'warn' | 'info' | 'danger' | 'neutral'> = {
  pass: 'ok',
  conditional: 'warn',
  unknown: 'info',
  fail: 'danger',
}

const elapsed = computed(() => {
  if (!startedAt.value) return '0,0 с'
  const sec = Math.max(0, now.value - startedAt.value) / 1000
  return `${sec.toLocaleString('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 })} с`
})

const activeCode = computed(() => {
  const query = typeof route.query.process === 'string' ? route.query.process : ''
  if (groups.value.some((group) => group.process_code === query)) return query
  return groups.value[0]?.process_code ?? ''
})
const activeGroup = computed(() => groups.value.find((group) => group.process_code === activeCode.value) ?? null)
const nextGroup = computed(() => {
  const index = groups.value.findIndex((group) => group.process_code === activeCode.value)
  return index >= 0 ? groups.value[index + 1] : undefined
})
const substages = computed(() => groups.value.map((group) => ({
  id: group.process_code,
  label: group.process_name,
  to: `/projects/${id.value}/match?process=${group.process_code}`,
})))
const counts = computed(() => {
  const tally = { pass: 0, conditional: 0, unknown: 0, fail: 0 }
  for (const hit of activeGroup.value?.hits ?? []) {
    if (hit.verdict in tally) tally[hit.verdict as keyof typeof tally] += 1
  }
  return tally
})
const statusTabs = computed(() => [
  { id: 'pass', label: 'Подходит', count: counts.value.pass },
  { id: 'conditional', label: 'С условием', count: counts.value.conditional },
  { id: 'unknown', label: 'Уточнить', count: counts.value.unknown },
  { id: 'fail', label: 'Не подходит', count: counts.value.fail },
])
const visibleHits = computed(() => (activeGroup.value?.hits ?? []).filter((hit) => hit.verdict === statusTab.value))
const buttonLabel = computed(() => {
  if (loadingMatch.value) return 'Считаем…'
  if (matchError.value || !nextGroup.value) return 'К сравнению'
  return 'Следующий процесс'
})

const countText = (hit: MatchHit | null) => {
  if (!hit || hit.count == null) return hit?.count_note || 'количество не задано'
  const value = Number(hit.count)
  const text = Number.isInteger(value) ? value.toLocaleString('ru-RU') : value.toLocaleString('ru-RU', { maximumFractionDigits: 1 })
  return `${text} шт.`
}
const startClock = () => {
  startedAt.value = Date.now()
  now.value = startedAt.value
  clock = setInterval(() => { now.value = Date.now() }, 100)
}
const stopClock = () => {
  if (clock) clearInterval(clock)
  clock = undefined
}

const runMatch = async () => {
  if (live.pending.value || !shell.value || ranFor.value === shell.value.id) return
  ranFor.value = shell.value.id
  loadingMatch.value = true
  matchError.value = ''
  groups.value = []
  startClock()
  try {
    const site = live.site.value
    const result = await platformSend<{ groups: MatchGroup[] }>(`/projects/${id.value}/match`, 'POST', { site })
    groups.value = result.groups
    const requested = typeof route.query.process === 'string' ? route.query.process : ''
    const first = result.groups[0]?.process_code
    if (first && !result.groups.some((group) => group.process_code === requested)) {
      await router.replace({ query: { process: first } })
    }
  } catch (err: unknown) {
    matchError.value = fetchErrorMessage(err, 'Не удалось посчитать подбор')
  } finally {
    stopClock()
    loadingMatch.value = false
  }
}

const goNext = () => {
  if (loadingMatch.value) return
  if (!matchError.value && nextGroup.value) {
    void router.push({ query: { process: nextGroup.value.process_code } })
    return
  }
  void router.push(`/projects/${id.value}/compare`)
}

watch([activeCode, () => activeGroup.value?.hits.length ?? 0], () => {
  const hits = activeGroup.value?.hits ?? []
  if (hits.some((hit) => hit.verdict === statusTab.value)) return
  const next = statusOrder.find((code) => hits.some((hit) => hit.verdict === code))
  statusTab.value = next || 'pass'
})
watch([() => shell.value?.id, () => live.pending.value], () => { void runMatch() }, { immediate: true })
onBeforeUnmount(stopClock)
</script>

<template>
  <ProjectShell
    v-if="shell"
    :project="shell"
    current="match"
    :substages="substages"
    :current-sub="activeCode"
    :title="activeGroup?.process_name || 'Подбор'"
    :lead="loadingMatch ? 'Считаем решения по включённым процессам. Время на экране — сколько уже идёт расчёт.' : 'Прошедшие все фильтры уже стоят в сравнении. Роботов с других вкладок можно добавить той же кнопкой.'"
  >
    <template #actions>
      <UiButton v-if="shell" size="lg" :disabled="loadingMatch" @click="goNext">
        {{ buttonLabel }}<template v-if="!loadingMatch" #after><PhArrowRight :size="18" weight="bold" /></template>
      </UiButton>
    </template>

    <UiCallout v-if="!live && !pending" tone="warn" title="Это демонстрационный макет">
      Живой подбор работает с проектом, сохранённым на сервере. Создайте проект — площадка и задачи предзаполнятся из профиля объекта.
      <div class="call-actions">
        <UiButton to="/projects/new" size="sm">Создать проект</UiButton>
      </div>
    </UiCallout>

    <UiCallout v-else-if="error" tone="danger" title="Не удалось загрузить проект">
      {{ fetchErrorMessage(error, 'Сервер не ответил. Проверьте, что API запущен.') }}
    </UiCallout>

    <section v-else-if="loadingMatch || pending" class="waiting glass">
      <div class="wait-copy">
        <div class="label">Подбор</div>
        <div class="h3">Считаем решения</div>
        <p class="body-sm muted">Когда расчёт закончится, откроются роботы первого процесса.</p>
      </div>
      <div class="timer">
        <span class="display-3">{{ elapsed }}</span>
        <span class="caption">идёт расчёт</span>
      </div>
    </section>

    <UiCallout v-else-if="matchError" tone="danger" title="Подбор не посчитался">{{ matchError }}</UiCallout>

    <section v-else-if="!activeGroup" class="empty glass">
      <div class="h3">Процессов для подбора нет</div>
      <p class="body muted">Включите хотя бы один процесс на шаге параметров.</p>
    </section>

    <template v-else>
      <div class="status-bar">
        <UiTabs v-model="statusTab" :tabs="statusTabs" />
      </div>

      <section v-if="visibleHits.length" class="glass sheet">
        <article v-for="hit in visibleHits" :key="hit.product_id" class="hit">
          <NuxtLink :to="`/catalog/card/${hit.slug}`" class="thumb" :aria-label="hit.name">
            <img :src="photoFor(hit.image_url, hit.name, activeGroup.process_code)" :alt="hit.name" loading="lazy">
          </NuxtLink>
          <div class="who">
            <NuxtLink :to="`/catalog/card/${hit.slug}`" class="h4">{{ hit.name }}</NuxtLink>
            <span class="mono-sm">{{ countText(hit) }}</span>
          </div>
          <UiBadge :tone="verdictTone[hit.verdict] || 'neutral'" size="sm">{{ verdictLabel[hit.verdict] || hit.verdict }}</UiBadge>
          <span class="caption">{{ hit.notes.join(' · ') || 'замечаний нет' }}</span>
          <UiButton size="sm" :variant="inCompare(activeGroup.process_code, hit) ? 'primary' : 'secondary'" @click="toggleCompare(activeGroup.process_code, hit)">
            {{ inCompare(activeGroup.process_code, hit) ? 'В сравнении' : 'В сравнение' }}
          </UiButton>
        </article>
      </section>
      <section v-else-if="!activeGroup.hits.length" class="empty glass">
        <div class="h3">На этот процесс роботов не назначено</div>
        <p class="body muted">Этот процесс не попадёт в сравнение, экономику и схему. Следующий процесс открывается той же кнопкой справа.</p>
      </section>
      <section v-else class="empty glass">
        <div class="h3">В этом статусе роботов нет</div>
      </section>
    </template>
  </ProjectShell>

  <section v-else class="container gone">
    <UiCallout tone="danger" title="Проект не найден">Нет ни сохранённого расчёта, ни демо-макета с таким адресом.</UiCallout>
    <UiButton to="/projects">К списку проектов</UiButton>
  </section>
</template>

<style scoped>
.waiting { display: flex; justify-content: space-between; align-items: center; gap: var(--space-6); padding: var(--space-6); }
.waiting > * { position: relative; z-index: 1; }
.wait-copy { display: grid; gap: 6px; max-width: 52ch; }
.timer { display: grid; justify-items: end; gap: 4px; }
.timer .display-3 { font-variant-numeric: tabular-nums; }
.status-bar { display: flex; align-items: center; gap: 12px; }
.status-bar :deep(.tabs) { flex: 1; min-width: 0; }
.sheet { padding: 8px; display: grid; gap: 8px; }
.sheet > * { position: relative; z-index: 1; }
.hit { display: grid; grid-template-columns: 132px minmax(180px, 1.4fr) auto minmax(140px, 1fr) auto; gap: 16px; align-items: center; min-height: 120px; padding: 14px 16px; border-radius: 14px; background: rgba(255, 255, 255, 0.65); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.who { display: grid; gap: 4px; min-width: 0; }
.thumb { display: block; width: 132px; height: 96px; border-radius: 14px; overflow: hidden; background: #e9eeec; }
.thumb img { width: 100%; height: 100%; object-fit: contain; }
.hit .h4 { color: var(--ink-strong); }
.empty { padding: var(--space-10); text-align: center; display: grid; gap: 8px; justify-items: center; }
.empty > * { position: relative; z-index: 1; }
.call-actions { margin-top: 10px; }
.gone { padding-top: var(--space-12); display: grid; gap: var(--space-4); justify-items: start; }
@media (max-width: 1100px) {
  .waiting { display: grid; }
  .status-bar { display: grid; }
  .hit { grid-template-columns: 96px minmax(0, 1fr); min-height: 108px; }
  .thumb { width: 96px; height: 72px; }
  .timer { justify-items: start; }
}
</style>
