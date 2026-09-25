<script setup lang="ts">
import { PhArrowRight } from '@phosphor-icons/vue'
import { projects } from '~/data/projects'
import { fetchErrorMessage } from '~/composables/useCalc'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { photoFor } from '~/data/placeholders'

const route = useRoute()
const router = useRouter()
const id = computed(() => route.params.id as string)
const { project, detail, pending, error, calculate } = useCalc(id)
const demoProject = computed(() => projects.find((p) => p.id === id.value))
const shell = computed(() => project.value ?? demoProject.value)
useHead({ title: () => `Подбор · ${shell.value?.name ?? 'проект'}` })

interface Hit { product_id: string; name: string; slug: string; verdict: string; notes: string[]; image_url?: string | null; count?: number | null; count_note?: string }
interface Group { process_code: string; process_name: string; best_product_id?: string | null; hits: Hit[] }
interface PlatformProject {
  id: string
  object_code: string
  processes: { code: string; enabled: boolean }[]
}

const groups = ref<Group[]>([])
const basket = ref<Record<string, string>>({})
const statusTab = ref('pass')
const showFinal = ref(false)
const statusOrder = ['pass', 'conditional', 'unknown', 'fail'] as const
const loadingMatch = ref(true)
const matchError = ref('')
const startedAt = ref(0)
const now = ref(0)
let clock: ReturnType<typeof setInterval> | undefined
const ranFor = ref('')

const live = computed(() => Boolean(project.value))
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
const statusTabs = computed(() => {
  const tabs: { id: string; label: string; count: number }[] = [
    { id: 'pass', label: 'Подходит', count: counts.value.pass },
    { id: 'conditional', label: 'С условием', count: counts.value.conditional },
    { id: 'unknown', label: 'Уточнить', count: counts.value.unknown },
    { id: 'fail', label: 'Не подходит', count: counts.value.fail },
  ]
  if (showFinal.value) tabs.push({ id: 'final', label: 'Итоговый выбор', count: groups.value.length })
  return tabs
})
const visibleHits = computed(() => (activeGroup.value?.hits ?? []).filter((hit) => hit.verdict === statusTab.value))
const revealFinal = () => {
  showFinal.value = true
  statusTab.value = 'final'
}
const buttonLabel = computed(() => {
  if (loadingMatch.value) return 'Считаем…'
  if (matchError.value || !nextGroup.value) return 'К сравнению'
  return 'Следующий процесс'
})

const acceptable = (hit: Hit) => hit.verdict === 'pass' || hit.verdict === 'conditional'
const chosenOf = (group: Group) => {
  const saved = basket.value[group.process_code]
  const picked = group.hits.find((hit) => hit.product_id === saved && acceptable(hit))
  if (picked) return picked
  return group.hits.find((hit) => hit.product_id === group.best_product_id) ?? group.hits.find(acceptable) ?? null
}
const chosen = computed(() => (activeGroup.value ? chosenOf(activeGroup.value) : null))
const countText = (hit: Hit | null) => {
  if (!hit || hit.count == null) return hit?.count_note || 'количество не задано'
  const value = Number(hit.count)
  const text = Number.isInteger(value) ? value.toLocaleString('ru-RU') : value.toLocaleString('ru-RU', { maximumFractionDigits: 1 })
  return `${text} шт.`
}
const pick = (group: Group, productId: string) => {
  basket.value = { ...basket.value, [group.process_code]: productId }
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

const ensureProject = async () => {
  const code = project.value?.objectType ?? 'warehouse'
  const key = `platform-project:${id.value}`
  const saved = localStorage.getItem(key)
    if (saved) {
      try {
        const current = await platformGet<PlatformProject>(`/projects/${saved}`)
        if (current.object_code === code) return current.id
      } catch {
        localStorage.removeItem(key)
      }
    }
  const created = await platformSend<PlatformProject>('/projects', 'POST', { name: shell.value?.name ?? code, object_code: code, site: {} })
  localStorage.setItem(key, created.id)
  return created.id
}

const runMatch = async () => {
  if (!project.value || ranFor.value === project.value.id) return
  ranFor.value = project.value.id
  loadingMatch.value = true
  matchError.value = ''
  groups.value = []
  startClock()
  try {
    const projectId = await ensureProject()
    const result = await platformSend<{ groups: Group[] }>(`/projects/${projectId}/match`, 'POST', { site: detail.value?.site ?? {} })
    groups.value = result.groups
    const requested = typeof route.query.process === 'string' ? route.query.process : ''
    const first = result.groups[0]?.process_code
    if (first && !result.groups.some((group) => group.process_code === requested)) {
      await router.replace({ query: { process: first } })
    }
    void calculate().catch(() => {})
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
  if (statusTab.value === 'final') return
  const hits = activeGroup.value?.hits ?? []
  if (hits.some((hit) => hit.verdict === statusTab.value)) return
  const next = statusOrder.find((id) => hits.some((hit) => hit.verdict === id))
  statusTab.value = next || 'pass'
})
watch(() => project.value?.id, () => { void runMatch() }, { immediate: true })
onMounted(() => {
  try { basket.value = JSON.parse(localStorage.getItem(`platform-basket:${id.value}`) || '{}') } catch { basket.value = {} }
})
watch(basket, (value) => localStorage.setItem(`platform-basket:${id.value}`, JSON.stringify(value)), { deep: true })
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
    :lead="loadingMatch ? 'Считаем решения по включённым процессам. Время на экране — сколько уже идёт расчёт.' : 'Роботы текущего процесса. Та же кнопка справа открывает следующий процесс.'"
  >
    <template #actions>
      <UiButton v-if="live" size="lg" :disabled="loadingMatch" @click="goNext">
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
        <UiButton v-if="!showFinal" size="sm" variant="secondary" @click="revealFinal">Итоговый выбор</UiButton>
      </div>

      <div v-if="statusTab === 'final'" class="baskets">
        <button v-for="group in groups" :key="group.process_code" type="button" class="basket" :class="{ on: group.process_code === activeCode }" @click="router.push({ query: { process: group.process_code } })">
          <img :src="photoFor(chosenOf(group)?.image_url, chosenOf(group)?.name || group.process_name, group.process_code)" alt="">
          <span class="copy">
            <span class="caption">{{ group.process_name }}</span>
            <span class="body-sm strong">{{ chosenOf(group)?.name || 'нет подходящего' }}</span>
            <span class="mono-sm">{{ chosenOf(group) ? countText(chosenOf(group)) : '—' }}</span>
          </span>
        </button>
      </div>

      <section v-else-if="visibleHits.length" class="glass sheet">
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
          <UiButton v-if="hit.product_id !== chosen?.product_id && (hit.verdict === 'pass' || hit.verdict === 'conditional')" size="sm" variant="secondary" @click="pick(activeGroup, hit.product_id)">В корзину</UiButton>
          <span v-else-if="hit.product_id === chosen?.product_id" class="caption in">в корзине</span>
        </article>
      </section>
      <section v-else-if="!activeGroup.hits.length" class="empty glass">
        <div class="h3">На этот процесс роботов не назначено</div>
        <p class="body muted">В списке подбора его нет. Следующий процесс открывается той же кнопкой справа.</p>
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
.in { color: var(--brand-ink); font-weight: 700; }
.baskets { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 10px; }
.basket { display: grid; grid-template-columns: 72px minmax(0, 1fr); gap: 10px; align-items: center; text-align: left; padding: 10px; border-radius: 16px; background: rgba(255, 255, 255, 0.55); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.basket.on { background: #fff; box-shadow: inset 0 0 0 1px var(--brand-400); }
.basket img { width: 72px; height: 56px; object-fit: contain; border-radius: 12px; background: #e9eeec; }
.copy { display: grid; gap: 2px; min-width: 0; }
.copy .body-sm { color: var(--ink-strong); }
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
