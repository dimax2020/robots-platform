<script setup lang="ts">
import { PhArrowRight, PhCheckCircle, PhStar } from '@phosphor-icons/vue'
import { fetchErrorMessage } from '~/utils/errors'
import { platformSend } from '~/composables/usePlatform'
import { useLiveProject } from '~/composables/useLiveProject'
import { photoFor } from '~/data/placeholders'
import { eligibleForEconomy } from '~/utils/fleetSelection'
import { skippedAlerts, usePlatformCompare, type MatchGroup, type MatchHit, type RobotSpec } from '~/composables/usePlatformCompare'

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
const { includedHits, chosenId, remainingHit, skipReason, choose } = usePlatformCompare(id)

const canEdit = computed(() => Boolean(project.value))
const readyGroups = computed(() => groups.value.filter((group) => includedHits(group).length > 0))
const skipped = computed(() => groups.value.flatMap((group) => {
  const reason = skipReason(group)
  return reason ? [{ code: group.process_code, name: group.process_name, reason }] : []
}))
const stepAlerts = computed(() => skippedAlerts(skipped.value))
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
const pool = computed(() => (activeGroup.value ? includedHits(activeGroup.value) : []))
const chosen = computed(() => pool.value.find((hit) => hit.product_id === (activeGroup.value ? chosenId(activeGroup.value) : '')) ?? null)
/* Колонки таблицы: выбранный робот всегда первым, он закреплён слева, остальные прокручиваются. */
const columns = computed(() => {
  const picked = chosen.value
  return picked ? [picked, ...pool.value.filter((hit) => hit.product_id !== picked.product_id)] : pool.value
})
const optimal = computed(() => {
  const best = activeGroup.value?.best_product_id
  if (!best) return null
  return activeGroup.value?.hits.find((hit) => hit.product_id === best) ?? null
})
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

const verdictLabel: Record<string, string> = { pass: 'Подходит', conditional: 'С условием', unknown: 'Уточнить', fail: 'Не подходит' }
const verdictTone: Record<string, 'ok' | 'warn' | 'info' | 'danger' | 'neutral'> = { pass: 'ok', conditional: 'warn', unknown: 'info', fail: 'danger' }

/* Строки таблицы: все характеристики роботов сравнения. Лучшее значение подсвечивается, если оно отличается у разных роботов. */
const rows = computed(() => {
  const keys = new Map<string, RobotSpec>()
  for (const hit of columns.value) for (const row of specsOf(hit)) if (!keys.has(row.key)) keys.set(row.key, row)
  return [...keys.values()].map((meta) => {
    const values = columns.value.map((hit) => specsOf(hit).find((row) => row.key === meta.key)?.value ?? null)
    const known = values.filter((value): value is number => value != null)
    const best = known.length > 1 && new Set(known).size > 1 ? (meta.direction === 'high' ? Math.max(...known) : Math.min(...known)) : null
    return {
      ...meta,
      cells: values.map((value) => ({ text: value == null ? '—' : formatValue(value, meta.unit), best: best != null && value === best, empty: value == null })),
    }
  })
})

const take = (hit: MatchHit) => {
  if (!activeGroup.value || !eligibleForEconomy(hit)) return
  choose(activeGroup.value.process_code, hit.product_id)
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
    const result = await platformSend<{ groups: MatchGroup[] }>(`/projects/${id.value}/match`, 'POST', { site, tasks: live.tasks.value })
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
</script>

<template>
  <ProjectShell
    v-if="shell"
    :project="shell"
    current="compare"
    :substages="substages"
    :current-sub="activeCode"
    title="Сравнение роботов"
    :alerts="stepAlerts"
    :subtitle="activeGroup ? `по процессу «${activeGroup.process_name}»` : undefined"
    lead="На этом шаге вы можете сравнить подобранные решения и выбрать одно для расчёта экономики. По умолчанию выбран оптимальный робот — его рекомендует платформа."
  >
    <UiCallout v-if="skipped.length" tone="warn" title="Часть решений нельзя включить в расчёт">
      <ul><li v-for="item in skipped" :key="item.code">{{ item.name }}: {{ item.reason }}</li></ul>
    </UiCallout>
    <template #actions>
      <UiButton v-if="shell" size="lg" :disabled="loadingMatch" @click="goForward">
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


    <template v-if="!loadingMatch && !pending && !matchError && activeGroup && pool.length">
      <div class="table-wrap glass">
        <table class="cmp" :class="{ multi: columns.length > 1 }" :style="{ '--cols': columns.length }" :aria-label="`Сравнение роботов по процессу «${activeGroup.process_name}»`">
          <colgroup>
            <col class="c-label">
            <col v-for="hit in columns" :key="`c-${hit.product_id}`" class="c-robot">
            <col class="c-fill">
          </colgroup>
          <thead>
            <tr>
              <th class="label-col corner" scope="col">
                <span class="pool-n">{{ pool.length }}</span>
                <span class="caption">{{ pool.length === 1 ? 'робот в сравнении' : pool.length < 5 ? 'робота в сравнении' : 'роботов в сравнении' }}</span>
                <span class="caption hint">Нажмите «Выбрать», чтобы взять робота в расчёт экономики.</span>
              </th>
              <th v-for="hit in columns" :key="`h-${hit.product_id}`" class="head" :class="{ sel: hit.product_id === chosen?.product_id }" scope="col">
                <div class="head-in">
                  <div class="tags">
                    <span v-if="hit.product_id === optimal?.product_id" class="tag opt"><PhStar :size="12" weight="fill" /> Оптимальный</span>
                    <UiBadge :tone="verdictTone[hit.verdict] || 'neutral'" size="sm">{{ verdictLabel[hit.verdict] || hit.verdict }}</UiBadge>
                  </div>
                  <span class="photo"><img :src="photoFor(hit.image_url, hit.name, activeGroup.process_code)" :alt="hit.name"></span>
                  <NuxtLink :to="`/catalog/card/${hit.slug}`" target="_blank" rel="noopener" class="name" :title="`${hit.name}: карточка робота в новой вкладке`">{{ hit.name }}</NuxtLink>
                  <div class="ready"><RobotReadiness :trl="hit.trl" :stage="hit.stage" :flagged="isImmature(hit)" /></div>
                  <AssessmentStatus :hit="hit" />
                  <button
                    type="button"
                    class="take"
                    :class="{ on: hit.product_id === chosen?.product_id }"
                    :aria-pressed="hit.product_id === chosen?.product_id"
                    :disabled="!eligibleForEconomy(hit)"
                    :title="hit.economic_reasons?.map((item) => item.message).join('; ')"
                    @click="take(hit)"
                  >
                    <template v-if="hit.product_id === chosen?.product_id"><PhCheckCircle :size="18" weight="fill" /> Выбран для расчёта</template>
                    <template v-else>Выбрать этого робота</template>
                  </button>
                  <p v-if="!eligibleForEconomy(hit)" class="caption">{{ hit.economic_reasons?.map((item) => item.message).join('; ') || 'Не допущен к экономическому расчёту' }}</p>
                </div>
              </th>
              <th class="fill" aria-hidden="true" />
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.key">
              <th class="label-col" scope="row">{{ row.label }}</th>
              <td v-for="(cell, i) in row.cells" :key="`${row.key}-${i}`" class="val" :class="{ sel: columns[i]?.product_id === chosen?.product_id, best: cell.best, none: cell.empty }">
                <span>{{ cell.text }}</span>
                <span v-if="cell.best" class="best-tag">лучше всех</span>
              </td>
              <td class="fill" aria-hidden="true" />
            </tr>
            <tr v-if="!rows.length">
              <th class="label-col" scope="row">Характеристики</th>
              <td v-for="hit in columns" :key="`e-${hit.product_id}`" class="val none" :class="{ sel: hit.product_id === chosen?.product_id }">нет числовых данных</td>
              <td class="fill" aria-hidden="true" />
            </tr>
          </tbody>
        </table>
      </div>
      <p class="caption legend"><span class="dot" /> Зелёным отмечено лучшее значение в строке. Выбранный робот уходит в расчёт экономики.</p>
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

/* Таблица сравнения: колонка на робота, строка на характеристику.
   Подписи и выбранный робот закреплены слева (sticky в настоящей таблице), остальные роботы прокручиваются. */
.table-wrap { min-width: 0; max-width: 100%; padding: 8px 0; overflow-x: auto; }
/* Ширина колонки робота одна и та же при любом их числе. Таблица всегда во всю ширину:
   если роботов мало, справа пустая колонка продолжает строки; если много — таблица прокручивается. */
.cmp { --label-w: 200px; --col-w: 280px; position: relative; z-index: 1; width: 100%; min-width: calc(var(--label-w) + var(--cols) * var(--col-w)); border-collapse: separate; border-spacing: 0; table-layout: fixed; }
.c-label { width: var(--label-w); }
.c-robot { width: var(--col-w); }
.cmp .fill { padding: 0; }
.cmp th, .cmp td { padding: 12px 16px; border-bottom: 1px solid var(--border-hairline); text-align: left; vertical-align: middle; font-weight: inherit; }
.cmp tbody tr:last-child > * { border-bottom: 0; }
.cmp .label-col { position: sticky; left: 0; z-index: 3; width: var(--label-w); background: #fafbfb; font-size: 14px; font-weight: 600; color: var(--ink-muted); }
.cmp .corner { vertical-align: top; }
.corner > * { display: block; }
.pool-n { font-family: var(--font-display); font-size: 40px; line-height: 1; color: var(--ink-strong); }
.hint { margin-top: 10px; color: var(--ink-faint); font-weight: 500; }
.sel { position: sticky; left: var(--label-w); z-index: 2; background: #f1faf6; box-shadow: inset 1.5px 0 0 var(--brand-400), inset -1.5px 0 0 var(--brand-400); }
.multi .sel::after { content: ''; position: absolute; top: 0; bottom: 0; right: -12px; width: 12px; background: linear-gradient(90deg, rgba(15, 20, 19, 0.07), transparent); pointer-events: none; }
th.head.sel { border-radius: 16px 16px 0 0; box-shadow: inset 1.5px 0 0 var(--brand-400), inset -1.5px 0 0 var(--brand-400), inset 0 1.5px 0 var(--brand-400); }
.cmp tbody tr:last-child .sel { border-radius: 0 0 16px 16px; box-shadow: inset 1.5px 0 0 var(--brand-400), inset -1.5px 0 0 var(--brand-400), inset 0 -1.5px 0 var(--brand-400); }
.cmp .head { vertical-align: top; padding-top: 16px; padding-bottom: 16px; }
/* Шапка робота: у каждой строки своя высота, поэтому кнопки всех роботов стоят на одной линии. */
.head-in { display: grid; grid-template-rows: 22px 170px 2.6em 24px auto; gap: 10px; }
.tags { display: flex; flex-wrap: wrap; gap: 6px; overflow: hidden; }
.tag { display: inline-flex; align-items: center; gap: 4px; padding: 2px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; }
.tag.opt { background: var(--brand-500); color: #fff; }
/* Фото целиком, без обрезки: у высоких роботов иначе остаётся одна стойка. */
.photo { display: block; border-radius: 14px; overflow: hidden; background: #eef2f0; box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.photo img { width: 100%; height: 100%; object-fit: contain; display: block; }
.name { font-size: 17px; font-weight: 700; line-height: 1.3; color: var(--ink-strong); display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.name:hover { color: var(--link); }
.ready { overflow: hidden; }
.take { display: inline-flex; align-items: center; justify-content: center; gap: 8px; height: 42px; padding: 0 14px; border-radius: 12px; font-size: 14px; font-weight: 700; color: var(--brand-700); background: #fff; box-shadow: inset 0 0 0 1.5px var(--brand-400); transition: background var(--dur-fast) var(--ease); }
.take:hover { background: var(--surface-brand-tint); }
.take.on { color: #fff; background: var(--brand-600); box-shadow: none; cursor: default; }
.val { font-family: var(--font-mono); font-size: 14px; color: var(--ink-strong); }
.val > span { vertical-align: middle; }
.val.none { color: var(--ink-faint); font-family: inherit; }
.val.best { color: var(--state-ok); font-weight: 700; }
.best-tag { display: inline-block; margin-left: 8px; font-family: var(--font-sans); font-size: 11px; font-weight: 700; padding: 1px 6px; border-radius: 999px; background: var(--state-ok-tint); color: var(--state-ok); }
.legend { display: flex; align-items: center; gap: 8px; margin: -8px 0 0; }
.legend .dot { width: 10px; height: 10px; border-radius: 3px; background: var(--state-ok); }
.call-actions { margin-top: 10px; }
.gone { padding-top: var(--space-12); display: grid; gap: var(--space-4); justify-items: start; }
</style>
