<script setup lang="ts">
import { PhCaretLeft, PhCaretRight, PhCaretDown, PhArrowLeft, PhArrowRight, PhArrowUpRight, PhCheck, PhCheckCircle } from '@phosphor-icons/vue'
import { fetchErrorMessage } from '~/utils/errors'
import { platformSend } from '~/composables/usePlatform'
import { useLiveProject } from '~/composables/useLiveProject'
import { photoFor } from '~/data/placeholders'
import { usePlatformCompare, type MatchGroup, type MatchHit, type RobotSpec } from '~/composables/usePlatformCompare'

const route = useRoute()
const id = computed(() => route.params.id as string)
const live = useLiveProject(id)
const project = live.shell
const shell = live.shell
const pending = live.pending
const error = live.error
useHead({ title: () => `Сравнение · ${shell.value?.name ?? 'проект'}` })

const groups = ref<MatchGroup[]>([])
const loadingMatch = ref(true)
const matchError = ref('')
const viewIndex = ref(0)
const { includedHits, chosenId, remainingHit, skipReason, choose } = usePlatformCompare(id)

const canEdit = computed(() => Boolean(project.value))
const readyGroups = computed(() => groups.value.filter((group) => includedHits(group).length > 0))
const skipped = computed(() => groups.value.flatMap((group) => {
  const reason = skipReason(group)
  return reason ? [{ code: group.process_code, name: group.process_name, reason }] : []
}))
const activeCode = computed(() => {
  const query = typeof route.query.process === 'string' ? route.query.process : ''
  if (readyGroups.value.some((group) => group.process_code === query)) return query
  return readyGroups.value[0]?.process_code ?? ''
})
const activeGroup = computed(() => readyGroups.value.find((group) => group.process_code === activeCode.value) ?? null)
const nextGroup = computed(() => {
  const index = readyGroups.value.findIndex((group) => group.process_code === activeCode.value)
  return index >= 0 ? readyGroups.value[index + 1] : undefined
})
const lineupOpen = ref(false)
const pool = computed(() => (activeGroup.value ? includedHits(activeGroup.value) : []))
const chosen = computed(() => pool.value.find((hit) => hit.product_id === (activeGroup.value ? chosenId(activeGroup.value) : '')) ?? null)
const optimal = computed(() => {
  const best = activeGroup.value?.best_product_id
  if (!best) return null
  return activeGroup.value?.hits.find((hit) => hit.product_id === best) ?? null
})
const selectedIsOptimal = computed(() => Boolean(chosen.value && optimal.value && chosen.value.product_id === optimal.value.product_id))
const viewed = computed(() => pool.value[viewIndex.value] ?? null)
const substages = computed(() => readyGroups.value.map((group) => ({
  id: group.process_code,
  label: group.process_name,
  to: `/projects/${id.value}/compare?process=${group.process_code}`,
})))
const lineup = computed(() => readyGroups.value.map((group) => ({
  code: group.process_code,
  name: group.process_name,
  robot: remainingHit(group),
  open: group.hits.length > 0,
})))
const readyCount = computed(() => lineup.value.filter((row) => row.robot).length)
const canEconomy = computed(() => lineup.value.some((row) => row.robot) && lineup.value.every((row) => row.robot || !row.open))

const isImmature = (hit: MatchHit) => hit.notes.some((note) => note.startsWith('Готовность:'))
const specsOf = (hit: MatchHit | null) => {
  const rows = [...(hit?.specs ?? [])]
  if (hit?.count != null) rows.push({ key: 'count', label: 'Роботов нужно', unit: 'шт', direction: 'low', value: hit.count })
  return rows
}

const formatValue = (value: number, unit: string) => {
  const digits = unit === '₽' || unit === 'шт' ? 0 : 1
  const text = value.toLocaleString('ru-RU', { maximumFractionDigits: digits })
  return unit ? `${text} ${unit}` : text
}

const bars = computed(() => {
  const base = chosen.value
  const current = viewed.value
  if (!base || !current) return []
  const keys = new Map<string, RobotSpec>()
  for (const row of [...specsOf(base), ...specsOf(current)]) keys.set(row.key, row)
  return [...keys.values()].map((meta) => {
    const baseRow = specsOf(base).find((row) => row.key === meta.key)
    const viewRow = specsOf(current).find((row) => row.key === meta.key)
    const sameRobot = base.product_id === current.product_id
    if (!baseRow || !viewRow || baseRow.value === 0) {
      return { ...meta, fill: sameRobot ? 50 : 8, text: viewRow ? formatValue(viewRow.value, meta.unit) : 'нет данных', delta: 'нет у выбранного', tone: 'missing' as const }
    }
    if (sameRobot) {
      return { ...meta, fill: 50, text: formatValue(baseRow.value, meta.unit), delta: 'выбранный', tone: 'same' as const }
    }
    const ratio = viewRow.value / baseRow.value
    const fill = Math.min(100, Math.max(8, 50 * ratio))
    const pct = Math.round((ratio - 1) * 100)
    const better = meta.direction === 'high' ? viewRow.value > baseRow.value : viewRow.value < baseRow.value
    const worse = meta.direction === 'high' ? viewRow.value < baseRow.value : viewRow.value > baseRow.value
    const sign = pct > 0 ? '+' : '−'
    return {
      ...meta,
      fill,
      text: formatValue(viewRow.value, meta.unit),
      delta: pct === 0 ? 'как у выбранного' : `${sign}${Math.abs(pct)}%`,
      tone: better ? 'better' as const : worse ? 'worse' as const : 'same' as const,
    }
  })
})

const step = (dir: -1 | 1) => {
  if (pool.value.length < 2) return
  viewIndex.value = (viewIndex.value + dir + pool.value.length) % pool.value.length
}

const onKeys = (event: KeyboardEvent) => {
  if (event.key === 'ArrowLeft') {
    event.preventDefault()
    step(-1)
  } else if (event.key === 'ArrowRight') {
    event.preventDefault()
    step(1)
  }
}

const takeViewed = () => {
  if (!activeGroup.value || !viewed.value) return
  choose(activeGroup.value.process_code, viewed.value.product_id)
}

const forwardLabel = computed(() => {
  if (loadingMatch.value) return 'Считаем…'
  if (matchError.value || !nextGroup.value) return 'К экономике'
  return 'Следующий процесс'
})
const goForward = () => {
  if (loadingMatch.value) return
  if (!matchError.value && nextGroup.value) {
    void navigateTo({ query: { process: nextGroup.value.process_code } })
    return
  }
  void navigateTo(`/projects/${id.value}/economics`)
}

const load = async () => {
  if (live.pending.value || !shell.value) return
  loadingMatch.value = true
  matchError.value = ''
  try {
    const site = live.site.value
    const result = await platformSend<{ groups: MatchGroup[] }>(`/projects/${id.value}/match`, 'POST', { site })
    groups.value = result.groups
    const ready = result.groups.filter((group) => includedHits(group).length > 0)
    const requested = typeof route.query.process === 'string' ? route.query.process : ''
    const first = ready[0]?.process_code
    if (first && !ready.some((group) => group.process_code === requested)) {
      await navigateTo({ query: { process: first } })
    }
  } catch (err: unknown) {
    matchError.value = fetchErrorMessage(err, 'Не удалось открыть сравнение')
  } finally {
    loadingMatch.value = false
  }
}

watch([() => shell.value?.id, () => live.pending.value], () => { void load() }, { immediate: true })
watch([activeCode, () => pool.value.map((hit) => hit.product_id).join(',')], () => {
  const current = chosen.value?.product_id
  const index = pool.value.findIndex((hit) => hit.product_id === current)
  viewIndex.value = index >= 0 ? index : 0
})
</script>

<template>
  <ProjectShell
    v-if="shell"
    :project="shell"
    current="compare"
    :substages="substages"
    :current-sub="activeCode"
    :title="activeGroup?.process_name || 'Сравнение'"
    lead="Слева выбранный робот. Его полоски стоят на 50%. Стрелки листают остальных из сравнения и показывают разницу уже от этого выбора."
  >
    <template #actions>
      <UiButton v-if="shell" :to="`/projects/${shell.id}/match`" size="lg" variant="secondary">
        <template #icon><PhArrowLeft :size="16" weight="bold" /></template>
        К подбору
      </UiButton>
      <UiButton v-if="shell" size="lg" :disabled="loadingMatch || (!nextGroup && !canEconomy)" @click="goForward">
        {{ forwardLabel }}<template v-if="!loadingMatch" #after><PhArrowRight :size="18" weight="bold" /></template>
      </UiButton>
    </template>

    <UiCallout v-if="!live && !pending" tone="warn" title="Это демонстрационный макет">
      Сравнение строится из подбора сохранённого проекта.
      <div class="call-actions"><UiButton to="/projects/new" size="sm">Создать проект</UiButton></div>
    </UiCallout>
    <UiCallout v-else-if="error" tone="danger" title="Не удалось загрузить проект">
      {{ fetchErrorMessage(error, 'Сервер не ответил.') }}
    </UiCallout>
    <section v-else-if="loadingMatch || pending" class="waiting glass">
      <div class="h3">Собираем сравнение</div>
    </section>
    <UiCallout v-else-if="matchError" tone="danger" title="Сравнение не открылось">{{ matchError }}</UiCallout>
    <section v-else-if="!activeGroup" class="empty glass">
      <div class="h3">Процессов для сравнения нет</div>
    </section>
    <section v-else-if="!pool.length" class="empty glass">
      <div class="h3">В сравнение никто не попал</div>
      <p class="body muted">На подборе включите роботов этого процесса. Прошедшие все фильтры уже включены.</p>
      <UiButton :to="`/projects/${shell.id}/match?process=${activeGroup.process_code}`" size="sm" variant="secondary">К подбору</UiButton>
    </section>

    <SkippedProcesses v-if="!loadingMatch && !pending" :rows="skipped" />

    <template v-if="!loadingMatch && !pending && !matchError && activeGroup && pool.length">
      <section class="lineup glass">
        <div class="line-in">
          <button type="button" class="line-head" :aria-expanded="lineupOpen" @click="lineupOpen = !lineupOpen">
            <span>
              <span class="h3">По одному роботу на процесс</span>
              <span class="caption">Этот состав уходит в экономику. Робот выбран для {{ readyCount }} из {{ lineup.length }} процессов.</span>
            </span>
            <PhCaretDown :size="16" weight="bold" class="caret" :class="{ up: lineupOpen }" />
          </button>
          <ul v-show="lineupOpen">
            <li v-for="row in lineup" :key="row.code">
              <span class="body-sm">{{ row.name }}</span>
              <span v-if="row.robot" class="strong">{{ row.robot.name }}<span class="caption"> · {{ row.robot.count != null ? `${row.robot.count.toLocaleString('ru-RU')} шт.` : 'количество не задано' }}</span></span>
              <span v-else class="caption">нет робота в сравнении</span>
            </li>
          </ul>
        </div>
      </section>
      <section class="arena" tabindex="0" @keydown="onKeys">
        <article class="base glass">
          <div class="in">
            <div class="picked-tag"><PhCheckCircle :size="16" weight="fill" /> Выбран для процесса</div>
            <img class="portrait" :src="photoFor(chosen?.image_url, chosen?.name || '', activeGroup.process_code)" :alt="chosen?.name || ''">
            <NuxtLink v-if="chosen" :to="`/catalog/card/${chosen.slug}`" target="_blank" rel="noopener" class="h3 card-link" title="Карточка робота в новой вкладке">{{ chosen.name }}<PhArrowUpRight :size="16" weight="bold" /></NuxtLink>
            <RobotReadiness v-if="chosen" :trl="chosen.trl" :stage="chosen.stage" :flagged="isImmature(chosen)" />
            <UiBadge v-if="selectedIsOptimal" tone="ok" size="sm">Оптимальный по версии платформы</UiBadge>
            <div class="mono-sm">{{ chosen?.count != null ? `${chosen.count.toLocaleString('ru-RU')} шт.` : (chosen?.count_note || 'количество не задано') }}</div>
            <div v-if="optimal && !selectedIsOptimal" class="optimal">
              <img :src="photoFor(optimal.image_url, optimal.name, activeGroup.process_code)" :alt="optimal.name">
              <span>
                <span class="caption">Оптимальный по версии платформы</span>
                <span class="body-sm strong">{{ optimal.name }}</span>
              </span>
            </div>
          </div>
        </article>

        <article class="stats glass">
          <div class="in">
            <div class="stat-head">
              <button type="button" class="arrow" aria-label="Предыдущий робот" :disabled="pool.length < 2" @click="step(-1)"><PhCaretLeft :size="18" weight="bold" /></button>
              <div class="stage">
                <img class="portrait" :src="photoFor(viewed?.image_url, viewed?.name || '', activeGroup.process_code)" :alt="viewed?.name || ''">
                <div class="who">
                  <div class="caption">{{ viewIndex + 1 }} из {{ pool.length }}<template v-if="viewed?.product_id === optimal?.product_id"> · оптимальный</template></div>
                  <NuxtLink v-if="viewed" :to="`/catalog/card/${viewed.slug}`" target="_blank" rel="noopener" class="h4 card-link" title="Карточка робота в новой вкладке">{{ viewed.name }}<PhArrowUpRight :size="14" weight="bold" /></NuxtLink>
                  <RobotReadiness v-if="viewed" :trl="viewed.trl" :stage="viewed.stage" :flagged="isImmature(viewed)" />
                </div>
              </div>
              <button type="button" class="arrow" aria-label="Следующий робот" :disabled="pool.length < 2" @click="step(1)"><PhCaretRight :size="18" weight="bold" /></button>
            </div>
            <div class="film" role="listbox" aria-label="Роботы в сравнении">
              <button
                v-for="(hit, index) in pool"
                :key="hit.product_id"
                type="button"
                class="frame"
                :class="{ on: index === viewIndex, picked: hit.product_id === chosen?.product_id }"
                role="option"
                :aria-selected="index === viewIndex"
                @click="viewIndex = index"
              >
                <img :src="photoFor(hit.image_url, hit.name, activeGroup.process_code)" :alt="hit.name">
                <span v-if="hit.product_id === chosen?.product_id" class="frame-check" aria-label="Выбран для процесса"><PhCheck :size="10" weight="bold" /></span>
              </button>
            </div>

            <div v-if="!bars.length" class="caption">У этих роботов нет числовых характеристик для полосок.</div>
            <div v-for="bar in bars" :key="bar.key" class="meter">
              <div class="meter-top">
                <span class="body-sm strong">{{ bar.label }}</span>
                <span class="mono-sm" :class="bar.tone">{{ bar.text }} · {{ bar.delta }}</span>
              </div>
              <div class="track">
                <span class="fill" :class="bar.tone" :style="{ width: `${bar.fill}%` }" />
                <span class="mid" aria-hidden="true" />
              </div>
            </div>

            <div v-if="viewed?.product_id === chosen?.product_id" class="picked-note" role="status">
              <PhCheckCircle :size="18" weight="fill" />
              <span>
                <span class="body-sm strong">Выбран для процесса «{{ activeGroup.process_name }}»</span>
                <span class="caption">Этот робот уходит в экономику. Стрелками можно посмотреть других.</span>
              </span>
            </div>
            <UiButton v-else size="sm" @click="takeViewed">Выбрать для процесса «{{ activeGroup.process_name }}»</UiButton>
          </div>
        </article>
      </section>
    </template>
  </ProjectShell>

  <section v-else class="container gone">
    <UiCallout tone="danger" title="Проект не найден">Нет ни сохранённого расчёта, ни демо-макета с таким адресом.</UiCallout>
    <UiButton to="/projects">К списку проектов</UiButton>
  </section>
</template>

<style scoped>
.waiting, .empty { padding: var(--space-10); display: grid; gap: 8px; justify-items: center; text-align: center; }
.waiting > *, .empty > * { position: relative; z-index: 1; }
.lineup .line-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: 12px; }
.line-head { display: flex; justify-content: space-between; align-items: center; gap: 12px; width: 100%; text-align: left; }
.line-head span { display: grid; gap: 4px; }
.caret { color: var(--ink-muted); transition: transform var(--dur-fast) var(--ease); flex: none; }
.caret.up { transform: rotate(180deg); }
.lineup ul { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
.lineup li { display: flex; justify-content: space-between; gap: 16px; align-items: baseline; }
.lineup .strong { color: var(--ink-strong); text-align: right; }
.arena { display: grid; grid-template-columns: minmax(240px, 320px) minmax(0, 1fr); gap: var(--space-4); align-items: start; outline: none; }
.arena:focus-visible { box-shadow: 0 0 0 2px var(--brand-400); border-radius: 18px; }
.in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: 12px; }
.portrait { width: 100%; height: 200px; object-fit: contain; border-radius: 18px; background:
  radial-gradient(120% 80% at 50% 100%, rgba(255, 255, 255, 0.9), transparent 55%),
  linear-gradient(180deg, #f4f7f5 0%, #e4ebe7 100%);
  box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06);
}
.base .h3 { margin: 0; }
.card-link { display: inline-flex; align-items: baseline; gap: 6px; color: var(--ink-strong); justify-self: start; }
.card-link svg { flex: none; color: var(--ink-faint); transition: color var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease); }
.card-link:hover { color: var(--link); }
.card-link:hover svg { color: var(--link); transform: translate(1px, -1px); }
.optimal { display: grid; grid-template-columns: 56px minmax(0, 1fr); gap: 10px; align-items: center; padding-top: 8px; border-top: 1px solid var(--border-hairline); }
.optimal img { width: 56px; height: 44px; object-fit: contain; border-radius: 10px; background: #e9eeec; }
.optimal span { display: grid; gap: 2px; min-width: 0; }
.optimal .body-sm { color: var(--ink-strong); }
.stat-head { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 12px; align-items: center; }
.stage { display: grid; gap: 10px; min-width: 0; }
.stage .portrait { height: 220px; }
.who { display: grid; gap: 2px; min-width: 0; }
.who .h4 { margin: 0; }
.film { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 2px; }
.picked-tag { display: inline-flex; align-items: center; gap: 6px; justify-self: start; padding: 4px 10px 4px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; background: var(--state-ok-tint); color: var(--state-ok); }
.picked-note { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 10px; align-items: start; padding: 12px 14px; border-radius: 14px; background: var(--state-ok-tint); color: var(--state-ok); }
.picked-note > span { display: grid; gap: 2px; }
.picked-note .strong { color: var(--brand-ink); }
.frame-check { position: absolute; top: 4px; right: 4px; width: 16px; height: 16px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; background: var(--state-ok); color: #fff; }
.frame { position: relative; flex: 0 0 auto; width: 84px; height: 64px; padding: 6px; border-radius: 14px; background: rgba(255, 255, 255, 0.55); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.08); }
.frame img { width: 100%; height: 100%; object-fit: contain; }
.frame.on { background: #fff; box-shadow: inset 0 0 0 2px var(--brand-400); }
.frame.picked:not(.on) { box-shadow: inset 0 0 0 1px var(--brand-700); }
.arrow { width: 40px; height: 40px; border-radius: 12px; background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); }
.arrow:disabled { opacity: 0.4; }
.meter { display: grid; gap: 6px; }
.meter-top { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
.track { position: relative; height: 12px; border-radius: 99px; background: rgba(15, 20, 19, 0.08); overflow: hidden; }
.fill { display: block; height: 100%; border-radius: inherit; background: var(--ink-muted); }
.fill.better { background: var(--state-ok); }
.fill.worse { background: var(--state-danger); }
.fill.same { background: var(--brand-400); }
.mid { position: absolute; left: 50%; top: 0; bottom: 0; width: 2px; background: var(--ink-strong); }
.better { color: var(--state-ok); }
.worse { color: var(--state-danger); }
.missing, .same { color: var(--ink-muted); }
.call-actions { margin-top: 10px; }
.gone { padding-top: var(--space-12); display: grid; gap: var(--space-4); justify-items: start; }
@media (max-width: 900px) { .arena { grid-template-columns: 1fr; } }
</style>
