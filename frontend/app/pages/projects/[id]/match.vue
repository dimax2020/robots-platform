<script setup lang="ts">
import { PhArrowRight, PhArrowUpRight, PhCheck, PhPlus, PhRobot, PhX } from '@phosphor-icons/vue'
import { assessmentLabel, assessmentTone } from '~/utils/assessmentPresentation'
import { pluralRu } from '~/data/adminLabels'
import { fetchErrorMessage } from '~/utils/errors'
import { platformSend } from '~/composables/usePlatform'
import { useLiveProject } from '~/composables/useLiveProject'
import { photoFor } from '~/data/placeholders'
import { usePlatformCompare, type MatchGroup, type MatchHit } from '~/composables/usePlatformCompare'
import { STEP_SUMMARY, useProcessFocus, useStepPass, type SummaryRow } from '~/composables/useStepPass'

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
const statusOrder = ['pass', 'conditional', 'unknown', 'fail'] as const
const { inCompare, toggleCompare } = usePlatformCompare(id)
const loadingMatch = ref(true)
const matchError = ref('')
const clarificationDialog = ref<HTMLDialogElement | null>(null)
const vendorNotify = useVendorNotify()
const requestClarification = (productId: string) => {
  vendorNotify.request(productId)
  clarificationDialog.value?.showModal()
}
const ranFor = ref('')

const canRun = computed(() => Boolean(project.value))
/* Первый проход — по процессам, в конце итог. Пройденный шаг открывается сразу с итога. */
const pass = useStepPass(id, 'match')
const focus = useProcessFocus(id)
const activeCode = computed(() => {
  const query = typeof route.query.process === 'string' ? route.query.process : ''
  if (query === STEP_SUMMARY || groups.value.some((group) => group.process_code === query)) return query
  return groups.value.length ? focus.pick(groups.value.map((group) => group.process_code), pass.done.value, STEP_SUMMARY) : ''
})
watch(activeCode, (code) => { if (code) focus.set(code) })
watch([activeCode, () => groups.value.length], ([code, count]) => { if (code === STEP_SUMMARY && count) pass.markDone() }, { immediate: true })
const activeGroup = computed(() => groups.value.find((group) => group.process_code === activeCode.value) ?? null)
const nextGroup = computed(() => {
  const index = groups.value.findIndex((group) => group.process_code === activeCode.value)
  return index >= 0 ? groups.value[index + 1] : undefined
})
const onSummary = computed(() => activeCode.value === STEP_SUMMARY)
/* Процессы слева: у каждого — сколько роботов подошло. */
const rail = computed(() => groups.value.length ? {
  summary: { id: STEP_SUMMARY, label: 'Итог подбора', to: `/projects/${id.value}/match?process=${STEP_SUMMARY}`, meta: `подобрано ${groups.value.filter((group) => passOf(group) > 0).length} из ${groups.value.length}` },
  items: groups.value.map((group) => ({
    id: group.process_code,
    label: group.process_name,
    to: `/projects/${id.value}/match?process=${group.process_code}`,
    tone: passOf(group) ? 'ok' : group.hits.length ? 'warn' : 'off',
    meta: passOf(group) ? `подходят ${passOf(group)} из ${group.hits.length}` : group.hits.length ? 'нет подходящих' : 'нет роботов в каталоге',
  })),
} : null)
/* Итог подбора: все процессы разом — сколько роботов подошло, лучший и сколько в сравнении. */
/* Подписи итога — те же слова, что у оценки робота на подборе. */
const SUMMARY_LABEL: Record<string, string> = { pass: 'подходят', check: 'уточнить', fail: 'не подходят' }
/* «С условием» и «нужны данные» для человека — одно: «уточнить». */
const verdictGroup = (verdict: string) => verdict === 'pass' || verdict === 'fail' ? verdict : 'check'
const passOf = (group: MatchGroup) => group.hits.filter((hit) => hit.verdict === 'pass').length
const summaryRows = computed<SummaryRow[]>(() => groups.value.map((group) => {
  const counts = (['pass', 'check', 'fail'] as const).map((key) => [key, group.hits.filter((hit) => verdictGroup(hit.verdict) === key).length] as const).filter(([, n]) => n > 0)
  const best = group.hits.find((hit) => hit.product_id === group.best_product_id) ?? group.hits.find((hit) => hit.verdict === 'pass') ?? null
  const inside = group.hits.filter((hit) => inCompare(group.process_code, hit, group)).length
  return {
    code: group.process_code,
    name: group.process_name,
    to: `/projects/${id.value}/match?process=${group.process_code}`,
    tone: passOf(group) ? 'ok' : group.hits.length ? 'warn' : 'todo',
    image: best ? photoFor(best.image_url, best.name, group.process_code) : null,
    robot: best ? best.name : group.hits.length ? 'подходящего робота нет' : 'в каталоге нет роботов',
    detail: counts.map(([verdict, n]) => `${SUMMARY_LABEL[verdict]} ${n}`).join(' · '),
    aside: group.hits.length ? `в сравнении ${inside}` : '',
  }
}))
const summaryStats = computed(() => {
  const covered = groups.value.filter((group) => passOf(group) > 0).length
  const total = groups.value.reduce((sum, group) => sum + passOf(group), 0)
  const inside = groups.value.reduce((sum, group) => sum + group.hits.filter((hit) => inCompare(group.process_code, hit, group)).length, 0)
  return [
    { label: 'Процессов', value: String(groups.value.length) },
    { label: 'Подобрано', value: `${covered} из ${groups.value.length}` },
    { label: 'Подходящих роботов', value: String(total) },
    { label: 'В сравнении', value: robots(inside) },
  ]
})
const summaryHint = computed(() => {
  const empty = groups.value.filter((group) => group.hits.length && !group.hits.some((hit) => inCompare(group.process_code, hit, group)))
  if (!empty.length) return ''
  if (empty.length === 1) return `У процесса «${empty[0]!.process_name}» нет робота в сравнении — в экономику он не попадёт. Откройте его и добавьте робота.`
  return `У ${empty.length} ${pluralRu(empty.length, 'процесса', 'процессов', 'процессов')} нет робота в сравнении — в экономику они не попадут. Откройте процесс и добавьте робота.`
})
const robots = (n: number) => `${n.toLocaleString('ru-RU')} ${pluralRu(n, 'робот', 'робота', 'роботов')}`
const compared = computed(() => {
  const group = activeGroup.value
  return group ? group.hits.filter((hit) => inCompare(group.process_code, hit, group)).length : 0
})
const statusRank = (verdict: string) => {
  const index = statusOrder.indexOf(verdict as (typeof statusOrder)[number])
  return index < 0 ? statusOrder.length : index
}
/* Все роботы процесса одним списком: сначала подходящие, затем с условием, уточнить и не подходит. */
const visibleHits = computed(() => [...(activeGroup.value?.hits ?? [])].sort((a, b) => statusRank(a.verdict) - statusRank(b.verdict)))
const buttonLabel = computed(() => {
  if (loadingMatch.value) return 'Считаем…'
  if (matchError.value || onSummary.value) return 'К сравнению'
  return nextGroup.value ? 'Следующий процесс' : 'Итог подбора'
})

const isImmature = (hit: MatchHit) => hit.notes.some((note) => note.startsWith('Готовность:'))
const countText = (hit: MatchHit | null) => {
  if (!hit || hit.count == null) return 'количество уточняется'
  const value = Number(hit.count)
  const text = Number.isInteger(value) ? value.toLocaleString('ru-RU') : value.toLocaleString('ru-RU', { maximumFractionDigits: 1 })
  return `${text} шт.`
}

const runMatch = async () => {
  if (live.pending.value || !shell.value || ranFor.value === shell.value.id) return
  ranFor.value = shell.value.id
  loadingMatch.value = true
  matchError.value = ''
  groups.value = []
  try {
    const site = live.site.value
    const result = await platformSend<{ groups: MatchGroup[] }>(`/projects/${id.value}/match`, 'POST', { site, tasks: live.tasks.value })
    groups.value = result.groups
    const requested = typeof route.query.process === 'string' ? route.query.process : ''
    const first = focus.pick(result.groups.map((group) => group.process_code), pass.done.value, STEP_SUMMARY)
    if (first && requested !== STEP_SUMMARY && !result.groups.some((group) => group.process_code === requested)) {
      await router.replace({ query: { process: first } })
    }
  } catch (err: unknown) {
    matchError.value = fetchErrorMessage(err, 'Не удалось посчитать подбор')
  } finally {
    loadingMatch.value = false
  }
}

const goNext = () => {
  if (loadingMatch.value) return
  if (!matchError.value && !onSummary.value) {
    void router.push({ query: { process: nextGroup.value?.process_code ?? STEP_SUMMARY } })
    return
  }
  void router.push(`/projects/${id.value}/compare`)
}

watch([() => shell.value?.id, () => live.pending.value], () => { void runMatch() }, { immediate: true })
</script>

<template>
  <ProjectShell
    v-if="shell"
    :project="shell"
    current="match"
    :rail="rail"
    :current-sub="activeCode"
    title="Подобранные решения"
    :subtitle="onSummary ? 'итог по всем процессам' : activeGroup ? `по процессу «${activeGroup.process_name}»` : undefined"
    :lead="loadingMatch ? 'Проверяем роботов каталога по требованиям процессов.' : onSummary ? 'Сколько роботов подошло по каждому процессу. Нажмите на процесс, чтобы открыть его.' : 'Сверху — подходящие роботы. Отметьте, кого сравнить на следующем шаге.'"
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

    <StepLoading
      v-else-if="loadingMatch || pending"
      label="Подбор"
      title="Подбираем роботов"
      :stages="['Загружаем параметры объекта', 'Проверяем роботов каталога по требованиям процессов', 'Считаем, сколько роботов нужно', 'Сортируем: подходит, уточнить, не подходит']"
      hint="Когда расчёт закончится, откроются роботы первого процесса."
    />

    <UiCallout v-else-if="matchError" tone="danger" title="Подбор не посчитался">{{ matchError }}</UiCallout>

    <StepSummary v-else-if="onSummary" :stats="summaryStats" :rows="summaryRows" :hint="summaryHint" />

    <section v-else-if="!activeGroup" class="empty glass">
      <div class="h3">Процессов для подбора нет</div>
      <p class="body muted">Включите хотя бы один процесс на шаге параметров.</p>
    </section>

    <template v-else>
      <OperationContext :operation="activeGroup.operation" />
      <div class="tally glass" :class="{ empty: !compared }">
        <span class="tally-ico"><PhRobot :size="22" weight="duotone" /></span>
        <span class="tally-text">
          <template v-if="compared">В сравнении <b>{{ robots(compared) }}</b> · подходят {{ activeGroup.hits.filter((hit) => hit.verdict === 'pass').length }} из {{ activeGroup.hits.length }}</template>
          <template v-else>Пока никого в сравнении — нажмите «Добавить в сравнение» у робота</template>
        </span>
      </div>
      <p v-if="visibleHits.some(isImmature)" class="caption tab-note">Роботы в разработке или с низким УГТ — в «Уточнить», но их можно добавить в сравнение.</p>
      <section v-if="visibleHits.length" class="glass sheet">
        <article v-for="hit in visibleHits" :key="hit.product_id" class="hit" :class="{ picked: inCompare(activeGroup.process_code, hit, activeGroup) }">
          <NuxtLink :to="`/catalog/card/${hit.slug}`" target="_blank" rel="noopener" class="thumb" :aria-label="`${hit.name}: карточка в новой вкладке`">
            <img :src="photoFor(hit.image_url, hit.name, activeGroup.process_code)" :alt="hit.name" loading="lazy">
          </NuxtLink>
          <div class="who">
            <NuxtLink :to="`/catalog/card/${hit.slug}`" target="_blank" rel="noopener" class="h4 card-link">{{ hit.name }}<PhArrowUpRight :size="14" weight="bold" /></NuxtLink>
            <span class="mono-sm">{{ countText(hit) }}</span>
            <RobotReadiness :trl="hit.trl" :stage="hit.stage" :flagged="isImmature(hit)" />
          </div>
          <!-- Статус, одна причина и запрос вендору — одной колонкой. -->
          <div class="hit-status">
            <div class="status-row">
              <UiBadge :tone="assessmentTone(hit)" size="sm">{{ assessmentLabel(hit) }}</UiBadge>
              <template v-if="hit.verdict !== 'pass' && hit.verdict !== 'fail'">
                <UiBadge v-if="vendorNotify.isRequested(hit.product_id)" tone="neutral" size="sm">Уведомим о данных</UiBadge>
                <button v-else type="button" class="ask" @click="requestClarification(hit.product_id)">Уведомить, когда появятся данные</button>
              </template>
            </div>
            <AssessmentStatus :hit="hit" />
          </div>
          <button
            type="button"
            class="pick"
            :class="{ on: inCompare(activeGroup.process_code, hit, activeGroup) }"
            :aria-pressed="inCompare(activeGroup.process_code, hit, activeGroup)"
            @click="toggleCompare(activeGroup.process_code, hit, activeGroup)"
          >
            <template v-if="inCompare(activeGroup.process_code, hit, activeGroup)">
              <span class="pick-ico"><PhCheck :size="14" weight="bold" /></span>
              <span class="pick-text">В сравнении</span>
              <span class="pick-ico pick-drop"><PhX :size="14" weight="bold" /></span>
              <span class="pick-text pick-drop">Убрать</span>
            </template>
            <template v-else>
              <span class="pick-ico"><PhPlus :size="14" weight="bold" /></span>
              <span class="pick-text">Добавить в сравнение</span>
            </template>
          </button>
        </article>
      </section>
      <section v-else-if="!activeGroup.hits.length" class="empty glass">
        <div class="h3">Для этого процесса роботов в каталоге нет</div>
        <p class="body muted">Он не попадёт в экономику. Переходите к следующему процессу.</p>
      </section>
    </template>

    <dialog ref="clarificationDialog" class="clarification-dialog" aria-labelledby="clarification-message">
      <p id="clarification-message" class="body">Ждём пополнения данных от вендора. Сообщим, когда робота можно будет взять в расчёт.</p>
      <form method="dialog">
        <UiButton type="submit" autofocus>Понятно</UiButton>
      </form>
    </dialog>
  </ProjectShell>

  <!-- Пока проект грузится — загрузка, а не «не найден»: на первом показе данных ещё нет всегда. -->
  <section v-else-if="pending" class="container opening"><StepLoading label="Проект" title="Открываем проект" :timer="false" /></section>
  <section v-else class="container gone">
    <UiCallout tone="danger" title="Проект не найден">Нет ни сохранённого расчёта, ни демо-макета с таким адресом.</UiCallout>
    <UiButton to="/projects">К списку проектов</UiButton>
  </section>

</template>

<style scoped>
.tally { display: flex; align-items: center; gap: 14px; padding: 14px 20px; border-radius: 16px; }
.tally > * { position: relative; z-index: 1; }
.tally-ico { width: 40px; height: 40px; border-radius: 12px; display: inline-flex; align-items: center; justify-content: center; background: var(--surface-brand-tint); color: var(--brand-700); flex: none; }
.tally-text { font-size: 16px; line-height: 1.45; color: var(--ink-body); }
.tally-text b { font-weight: 800; color: var(--ink-strong); }
/* Никого в сравнении: процесс выпадет из экономики, поэтому плашка предупреждающего цвета. */
.tally.empty { background: var(--state-warn-tint); box-shadow: inset 0 0 0 1.5px rgba(138, 82, 0, 0.35); }
.tally.empty .tally-ico { background: rgba(138, 82, 0, 0.12); color: var(--state-warn); }
.tally.empty .tally-text { color: var(--state-warn); font-weight: 600; }
.sheet { padding: 8px; display: grid; gap: 8px; }
.sheet > * { position: relative; z-index: 1; }
.hit { display: grid; grid-template-columns: 132px minmax(180px, 1fr) minmax(220px, 1.2fr) 210px; gap: 20px; align-items: center; min-height: 120px; padding: 14px 16px; border-radius: 14px; background: rgba(255, 255, 255, 0.65); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.who { display: grid; gap: 4px; min-width: 0; }
.hit-status { display: grid; gap: 6px; align-content: center; min-width: 0; }
.status-row { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }
.ask { font-size: 13px; font-weight: 700; color: var(--link); }
.ask:hover { text-decoration: underline; }
.clarification-dialog { margin: auto; width: 440px; max-width: calc(100vw - 32px); padding: 24px; border: 0; border-radius: 20px; background: #fff; color: var(--ink-strong); box-shadow: var(--shadow-lg); }
.clarification-dialog::backdrop { background: rgba(15, 20, 19, 0.45); }
.clarification-dialog form { margin-top: 20px; display: flex; justify-content: flex-end; }
.thumb { display: block; width: 132px; height: 96px; border-radius: 14px; overflow: hidden; background: #e9eeec; }
.thumb img { width: 100%; height: 100%; object-fit: contain; }
.hit .h4 { color: var(--ink-strong); }
/* Робот в сравнении: зелёная кромка слева и сплошная зелёная кнопка с галочкой. На наведении — «Убрать». */
.hit { position: relative; transition: background var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease); }
.hit.picked { background: #fff; box-shadow: inset 0 0 0 1.5px var(--brand-400); }
.hit.picked::before { content: ''; position: absolute; left: 0; top: 14px; bottom: 14px; width: 4px; border-radius: 0 4px 4px 0; background: var(--brand-500); }
.pick {
  display: inline-flex; align-items: center; justify-content: center; gap: 8px; min-width: 210px; height: 44px; padding: 0 16px;
  border-radius: 12px; font-size: 14px; font-weight: 700; white-space: nowrap;
  color: var(--brand-700); background: #fff; box-shadow: inset 0 0 0 1.5px var(--brand-400);
  transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease);
}
.pick:hover { background: var(--surface-brand-tint); }
.pick-ico { width: 22px; height: 22px; border-radius: 7px; display: inline-flex; align-items: center; justify-content: center; background: var(--surface-brand-tint); }
.pick.on { color: #fff; background: var(--brand-600); box-shadow: none; }
.pick.on .pick-ico { background: rgba(255, 255, 255, 0.22); }
.pick-drop { display: none; }
.pick.on:hover { background: var(--state-danger); }
.pick.on:hover > :not(.pick-drop) { display: none; }
.pick.on:hover .pick-drop { display: inline-flex; }
.card-link { display: inline-flex; align-items: baseline; gap: 4px; }
.card-link svg { flex: none; color: var(--ink-faint); transition: color var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease); }
.card-link:hover { color: var(--link); }
.card-link:hover svg { color: var(--link); transform: translate(1px, -1px); }
.tab-note { margin: 0; }
.empty { padding: var(--space-10); text-align: center; display: grid; gap: 8px; justify-items: center; }
.empty > * { position: relative; z-index: 1; }
.call-actions { margin-top: 10px; }
.gone { padding-top: var(--space-12); display: grid; gap: var(--space-4); justify-items: start; }
@media (max-width: 1100px) {
  .hit { grid-template-columns: 96px minmax(0, 1fr); min-height: 108px; }
  .hit-status, .pick { grid-column: 2; }
  .thumb { width: 96px; height: 72px; }
}
.opening { padding-top: var(--space-8); padding-bottom: var(--space-8); }
</style>
