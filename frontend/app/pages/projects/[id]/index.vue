<script setup lang="ts">
import { PhArrowRight, PhArrowLeft, PhCheckCircle, PhCircleDashed, PhClockCounterClockwise, PhCopy, PhEye, PhEyeSlash, PhGearSix, PhWarningCircle } from '@phosphor-icons/vue'
import { objectTypeLabel, objectTypeImage, steps } from '~/data/projects'
import { useLiveProject } from '~/composables/useLiveProject'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { fetchErrorMessage } from '~/utils/errors'
import { useDemoProjects } from '~/composables/useDemoProjects'
import { usePlatformCompare, type MatchGroup } from '~/composables/usePlatformCompare'
import { photoFor } from '~/data/placeholders'
import { millions, signedMillions, usePlatformEconomy, withPlan, yearsText } from '~/composables/usePlatformEconomy'
import type { Layout } from '~/sim/types'

const route = useRoute()
const router = useRouter()
const doc = useLiveProject(computed(() => route.params.id as string))
const project = computed(() => doc.shell.value)
const record = doc.record
const { role } = useRole()
const demos = useDemoProjects()
useHead({ title: () => `${project.value?.name ?? 'Проект'} · Кабинет проекта` })
const { remainingHit, includedHits, chosenId } = usePlatformCompare(computed(() => record.value?.id ?? ''))
/* Экономика тем же движком, что и шаг «Экономика»: те же люди на процессах, выбор роботов и правки платформы. */
const econ = usePlatformEconomy(computed(() => route.params.id as string))
const economy = econ.report
const groups = econ.groups
const layout = ref<Layout | null>(null)
const summaryPending = computed(() => econ.loading.value && !economy.value)

const fleet = computed(() => groups.value.flatMap((group) => {
  const hit = remainingHit(group)
  if (!hit) return []
  return [{
    code: group.process_code,
    process: group.process_name,
    name: hit.name,
    count: hit.count,
    image: photoFor(hit.image_url, hit.name, group.process_code),
    /* В итоге экономики или убран из него — по расчёту экономики. */
    out: Boolean(economy.value?.processes?.find((item) => item.process_code === group.process_code)?.off),
  }]
}))

/* Правки платформы ещё не внесены (демо или экономику не открывали) — показываем итог с ними, как на шаге «Экономика». */
let planned = false
watch(economy, (report) => {
  if (!report || planned || report.saved_overrides.auto || !report.plan?.changes.length) return
  planned = true
  void econ.load(withPlan(report.saved_overrides, report.plan.changes))
})
const loadSummary = async () => {
  if (!record.value) return
  if (!planned) await econ.load()
  try {
    const result = await platformGet<{ layout: Partial<Layout> | null }>(`/projects/${record.value.id}/layout`)
    layout.value = (result.layout as Layout | null) ?? null
  } catch {
    layout.value = null
  }
}
watch(() => [record.value?.id, econ.source.value ? 1 : 0], () => { void loadSummary() }, { immediate: true })

/* Сводка шагов: статус, одна главная строка и короткие подробности. Только факты проекта, без общих описаний. */
type Tone = 'ok' | 'warn' | 'todo'
interface StepCard { code: string; label: string; path: string; tone: Tone; headline: string; lines: string[]; issues: string[] }
const plural = (n: number, one: string, few: string, many: string) => {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few
  return many
}
const listOf = (names: string[], limit = 3) => names.length <= limit ? names.join(', ') : `${names.slice(0, limit).join(', ')} и ещё ${names.length - limit}`
const num = (value: unknown) => typeof value === 'number' ? value : typeof value === 'string' && value.trim() !== '' && Number.isFinite(Number(value)) ? Number(value) : null

const cards = computed<StepCard[]>(() => {
  const rec = record.value
  if (!rec) return []
  const site = rec.site
  const on = rec.processes.filter((item) => item.enabled)
  const off = rec.processes.filter((item) => !item.enabled)
  const area = num(site.area_m2)
  const shiftsN = num(site.shifts_per_day)
  const hours = num(site.shift_hours)
  const days = num(site.days_year)
  const regime = [area != null ? `${area.toLocaleString('ru-RU')} м²` : '', shiftsN != null ? `${shiftsN} ${plural(shiftsN, 'смена', 'смены', 'смен')}${hours != null ? ` по ${hours} ч` : ''}` : '', days != null ? `${days} дн. в году` : ''].filter(Boolean).join(' · ')
  const params: StepCard = {
    code: 'params', label: 'Параметры', path: 'params',
    tone: on.length ? 'ok' : 'todo',
    headline: on.length ? `Выбрано ${on.length} из ${rec.processes.length} ${plural(rec.processes.length, 'процесса', 'процессов', 'процессов')} объекта` : 'Процессы не выбраны',
    lines: regime ? [regime] : [],
    issues: [
      ...(off.length ? [`Не выбраны: ${listOf(off.map((item) => item.name))}`] : []),
      ...(shiftsN == null || hours == null || days == null ? ['Не задан режим работы: смены, часы или дни в году — без него не считаются роботы и экономия'] : []),
    ],
  }

  const gs = groups.value
  const passOf = (group: MatchGroup) => group.hits.filter((hit) => hit.verdict === 'pass').length
  const covered = gs.filter((group) => passOf(group) > 0)
  const empty = gs.filter((group) => !group.hits.length)
  const failed = gs.filter((group) => group.hits.length && !passOf(group))
  const passTotal = gs.reduce((sum, group) => sum + passOf(group), 0)
  const condTotal = gs.reduce((sum, group) => sum + group.hits.filter((hit) => hit.verdict === 'conditional').length, 0)
  const match: StepCard = {
    code: 'match', label: 'Подбор', path: 'match',
    tone: !gs.length ? 'todo' : covered.length === gs.length ? 'ok' : 'warn',
    headline: gs.length ? `Подобрано под ${covered.length} из ${gs.length} ${plural(gs.length, 'процесса', 'процессов', 'процессов')}` : 'Подбор ещё не запускался',
    lines: gs.length ? [`${passTotal} ${plural(passTotal, 'подходящий робот', 'подходящих робота', 'подходящих роботов')}${condTotal ? `, ещё ${condTotal} — с условием` : ''}`] : [],
    issues: [
      ...(empty.length ? [`В каталоге нет роботов: ${listOf(empty.map((group) => group.process_name))}`] : []),
      ...(failed.length ? [`Ни один робот не подошёл: ${listOf(failed.map((group) => group.process_name))}`] : []),
    ],
  }

  const chosen = gs.filter((group) => remainingHit(group))
  const recommended = chosen.filter((group) => group.best_product_id && chosenId(group) === group.best_product_id).length
  const skipped = gs.filter((group) => !includedHits(group).length)
  const noMatch = new Set([...empty, ...failed].map((group) => group.process_code))
  const removed = skipped.filter((group) => !noMatch.has(group.process_code))
  const compare: StepCard = {
    code: 'compare', label: 'Сравнение', path: 'compare',
    tone: !chosen.length ? 'todo' : removed.length ? 'warn' : 'ok',
    headline: chosen.length ? `Робот выбран на ${chosen.length} из ${gs.length} ${plural(gs.length, 'процесса', 'процессов', 'процессов')}` : 'Роботы не выбраны',
    lines: chosen.length ? [
      recommended === chosen.length ? (chosen.length === 1 ? 'Рекомендованный платформой' : 'Все — рекомендованные платформой') : `${recommended} — рекомендованные платформой, ${chosen.length - recommended} — свой выбор`,
      ...(skipped.length - removed.length ? [`Остальным ${skipped.length - removed.length} не нашлось робота на подборе`] : []),
    ] : [],
    issues: removed.length ? [`Убраны из сравнения: ${listOf(removed.map((group) => group.process_name))}`] : [],
  }

  const report = economy.value
  const buy = report?.scenarios.find((item) => item.key === 'purchase')
  const views = (report?.processes ?? []).filter((item) => item.included)
  const inTotal = views.filter((item) => !item.off)
  const noStaff = views.filter((item) => item.story?.needs_staff)
  const payback = buy?.payback.value ?? null
  const npv = buy?.npv?.value ?? null
  const net = buy?.cashflow?.at(-1)?.cumulative ?? null
  const horizon = report?.horizon_years ?? 5
  const pays = payback != null && payback <= horizon && (npv ?? 0) >= 0
  const economics: StepCard = {
    code: 'economics', label: 'Экономика', path: 'economics',
    tone: !buy || !inTotal.length ? 'todo' : pays ? 'ok' : 'warn',
    headline: !buy || !inTotal.length ? 'Нет процессов, которые окупаются' : pays ? `Окупится за ${yearsText(payback)} · ${signedMillions(net)} за ${horizon} лет` : `Не окупается за ${horizon} лет`,
    lines: buy && inTotal.length
      ? [`Вложения ${millions(buy.capex.value)} · экономия ${millions(buy.effect.value)} в год`, `Выгодно роботизировать ${inTotal.length} из ${views.length}: ${listOf(inTotal.map((item) => item.process_name))}`]
      : [],
    issues: noStaff.length ? [`Нет данных о людях или затратах — экономия не считается: ${listOf(noStaff.map((item) => item.process_name))}`] : [],
  }

  const own = (report?.params ?? []).filter((item) => item.source === 'project' && item.key !== 'horizon_years')
  const subsidies = (report?.subsidies ?? []).filter((item) => item.enabled)
  const whatIf: StepCard = {
    code: 'what-if', label: 'What-if', path: 'what-if',
    tone: report ? 'ok' : 'todo',
    headline: own.length ? `Изменено ${own.length} ${plural(own.length, 'допущение', 'допущения', 'допущений')} платформы` : 'Все допущения — стандарт платформы',
    lines: [
      own.length ? listOf(own.map((item) => `${item.label.toLowerCase()} ${item.value.toLocaleString('ru-RU')} ${item.unit}`), 3) : '',
      report ? `Горизонт ${yearsText(horizon)}${subsidies.length ? ` · господдержка: ${listOf(subsidies.map((item) => item.label), 2)}` : ' · без господдержки'}` : '',
    ].filter(Boolean),
    issues: [],
  }

  const floors = layout.value?.floors ?? []
  const placed = new Set(floors.flatMap((floor) => [...floor.stations, ...floor.zones, ...floor.blocks].map((item) => (item as { process?: string }).process).filter(Boolean)))
  /* Считаем только процессы с выбранным роботом: на плане могут остаться и те, что в парк не вошли. */
  const onPlan = fleet.value.filter((row) => placed.has(row.code))
  const unplaced = fleet.value.filter((row) => !placed.has(row.code))
  const plan: StepCard = {
    code: 'plan', label: 'Визуализация', path: 'plan',
    tone: !onPlan.length ? 'todo' : unplaced.length ? 'warn' : 'ok',
    headline: onPlan.length ? `На плане ${onPlan.length} из ${fleet.value.length} ${plural(fleet.value.length, 'процесса', 'процессов', 'процессов')} парка${floors.length > 1 ? ` · ${floors.length} ${plural(floors.length, 'этаж', 'этажа', 'этажей')}` : ''}` : 'План ещё не нарисован',
    lines: [],
    issues: onPlan.length && unplaced.length ? [`Не размещены: ${listOf(unplaced.map((row) => row.process))}`] : [],
  }

  const ready = Boolean(fleet.value.length && report)
  const reportCard: StepCard = {
    code: 'report', label: 'Отчёт', path: 'report',
    tone: ready ? 'ok' : 'todo',
    headline: ready ? 'Готов к выгрузке: PDF и Excel' : 'Появится после подбора роботов',
    lines: ready ? [`Войдут ${fleet.value.length} ${plural(fleet.value.length, 'процесс', 'процесса', 'процессов')} с роботами, экономика и допущения${onPlan.length ? ', план' : ''}`] : [],
    issues: [],
  }
  return [params, match, compare, economics, whatIf, plan, reportCard]
})
/* Главная кнопка ведёт к первому шагу, где есть что доделать. */
const nextCard = computed(() => cards.value.find((card) => card.tone !== 'ok') ?? cards.value.at(-1) ?? { code: 'params', label: 'Параметры', path: 'params' })
const pending = computed(() => !groups.value.length && (summaryPending.value || econ.pending.value))


const STEP_TONE = { ok: PhCheckCircle, warn: PhWarningCircle, todo: PhCircleDashed } as const

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
        <div v-if="project.readonly" class="versions">
          <PhClockCounterClockwise :size="16" />
          <span v-if="role === 'integrator'" class="body-sm">Проект заказчика только для просмотра.</span>
          <span v-else class="body-sm">Демо только для просмотра. Чтобы менять, скопируйте к себе.</span>
        </div>
        <UiCallout v-if="note" tone="danger">{{ note }}</UiCallout>
      </div>
      <div class="hero-cta">
        <UiButton :to="`/projects/${project.id}/${nextCard.path}`" size="lg">{{ nextCard.code === 'params' ? (project.readonly ? 'Смотреть параметры' : 'К параметрам') : `Дальше: ${nextCard.label}` }}<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
        <UiButton v-if="role === 'guest'" to="/login" variant="secondary"><template #icon><PhCopy :size="16" /></template>Войти, чтобы скопировать</UiButton>
        <UiButton v-else-if="role !== 'integrator'" variant="secondary" :disabled="busy === 'copy'" @click="copyProject"><template #icon><PhCopy :size="16" /></template>{{ project.readonly ? 'Скопировать в мои проекты' : 'Копировать проект' }}</UiButton>
        <template v-if="project.isDemo && role === 'admin'">
          <UiButton :variant="project.published ? 'ghost' : 'secondary'" :disabled="busy === 'publish'" @click="togglePublish">
            <template #icon><component :is="project.published ? PhEyeSlash : PhEye" :size="16" weight="bold" /></template>{{ project.published ? 'Снять с публикации' : 'Опубликовать демо' }}
          </UiButton>
          <UiButton to="/admin/demo" variant="ghost"><template #icon><PhGearSix :size="16" /></template>Все демо</UiButton>
        </template>
      </div>
    </div>

    <div class="grid grid-12 main">
      <div class="span-7 steps-col" v-reveal="1">
        <div class="h3">Шаги расчёта</div>
        <ol class="steps">
          <li v-for="(card, i) in cards" :key="card.code">
            <NuxtLink :to="`/projects/${project.id}/${card.path}`" class="st glass" :class="card.tone">
              <span class="st-n"><span class="mono-sm">{{ i + 1 }}</span></span>
              <div class="st-body">
                <div class="st-head">
                  <span class="h4">{{ card.label }}</span>
                  <component :is="STEP_TONE[card.tone]" :size="16" weight="fill" class="st-ico" />
                </div>
                <div v-if="pending && i > 0" class="caption">Считаем…</div>
                <template v-else>
                  <div class="body-sm strong">{{ card.headline }}</div>
                  <div v-for="line in card.lines" :key="line" class="caption">{{ line }}</div>
                  <UiHint v-for="issue in card.issues" :key="issue" compact class="issue">{{ issue }}</UiHint>
                </template>
              </div>
              <span class="st-go"><PhArrowRight :size="16" weight="bold" /></span>
            </NuxtLink>
          </li>
        </ol>
      </div>

      <aside class="span-5 side" v-reveal="2">
        <div class="result glass-graphite glass-graphite-solid">
          <div class="label">Состав парка</div>
          <div class="h3">Выбранные роботы</div>
          <p v-if="summaryPending" class="caption">Считаем роботов этого проекта…</p>
          <template v-else-if="fleet.length">
            <p class="caption">{{ fleet.length }} {{ plural(fleet.length, 'процесс', 'процесса', 'процессов') }} с выбранным роботом<template v-if="economy">, в итоге экономики — {{ fleet.filter((row) => !row.out).length }}</template>.</p>
            <ul class="fleet">
              <li v-for="row in fleet" :key="row.code" :class="{ out: row.out }">
                <img :src="row.image" :alt="row.name">
                <span class="who"><span class="body-sm">{{ row.name }}</span><span class="caption">{{ row.process }}{{ row.out ? ' · не в итоге экономики' : '' }}</span></span>
                <span class="mono-md">{{ row.count != null ? `× ${row.count.toLocaleString('ru-RU')}` : '—' }}</span>
              </li>
            </ul>
            <p v-if="fleet.some((row) => row.count == null)" class="caption">— количество не посчитано: формуле подбора не хватает данных площадки.</p>
          </template>
          <p v-else class="caption">Роботы появятся после подбора. Пока ни один процесс не закрыт подходящим решением.</p>
          <UiButton :to="`/projects/${project.id}/${fleet.length ? 'economics' : 'match'}`" variant="onGraphite" block>{{ fleet.length ? 'Открыть экономику' : 'Открыть подбор' }}</UiButton>
        </div>
      </aside>
    </div>
  </section>
  <section v-else-if="doc.pending.value" class="container cab"><StepLoading label="Проект" title="Открываем проект" :timer="false" /></section>
  <section v-else class="container cab">
    <UiCallout tone="danger" title="Проект не найден">Нет сохранённого расчёта с таким адресом.</UiCallout>
    <UiButton to="/projects">К списку проектов</UiButton>
  </section>
</template>

<style scoped>
.cab { padding-top: var(--space-8); padding-bottom: var(--space-16); display: grid; gap: var(--space-8); }
.back { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-muted); font-weight: 600; }
.hero { display: grid; grid-template-columns: 260px 1fr auto; gap: var(--space-8); align-items: center; padding: 12px; }
.hero > * { position: relative; z-index: 1; }
.hero-img { width: 260px; height: 220px; object-fit: cover; border-radius: 22px; }
.hero-body { display: grid; gap: 14px; padding: 8px 0; }
.versions { display: flex; gap: 8px; align-items: flex-start; color: var(--ink-muted); max-width: 64ch; }
.hero-cta { display: grid; gap: 8px; padding-right: 12px; align-self: start; padding-top: 8px; }
.main { align-items: start; }
.steps-col { display: grid; gap: var(--space-4); }
.steps { display: grid; gap: 8px; }
.steps { margin: 0; padding: 0; list-style: none; }
.st { display: grid; grid-template-columns: auto 1fr auto; gap: 14px; align-items: center; padding: 14px 16px; border-radius: 16px; color: inherit; transition: box-shadow var(--dur-fast) var(--ease); }
.st:hover { box-shadow: inset 0 1px 0 var(--glass-stroke), 0 0 0 1.5px var(--brand-400), var(--glass-shadow); }
.st-body { display: grid; gap: 3px; min-width: 0; }
.st-head { display: flex; align-items: center; gap: 8px; }
.st-head .h4 { margin: 0; }
.st-ico { flex: none; }
.st.ok .st-ico { color: var(--brand-600); }
.st.warn .st-ico { color: #d69a2d; }
.st.todo .st-ico { color: var(--ink-faint); }
.st.ok .st-n { background: var(--surface-brand-tint); color: var(--brand-700); }
.st.warn .st-n { background: #fdf4e3; color: #9a5b00; }
.issue { margin-top: 4px; }
.st > * { position: relative; z-index: 1; }
.st-n { width: 32px; height: 32px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; background: rgba(15, 20, 19, 0.06); color: var(--ink-muted); }
.done .st-n { background: var(--surface-brand-tint); color: var(--brand-700); }
.cur .st-n { background: var(--surface-graphite); color: var(--brand-300); }
.cur { box-shadow: inset 0 1px 0 var(--glass-stroke), 0 0 0 2px var(--brand-500), var(--glass-shadow); }
.locked { opacity: 0.6; }
.st-go { width: 36px; height: 36px; border-radius: 10px; display: inline-flex; align-items: center; justify-content: center; color: var(--ink-strong); background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); transition: all var(--dur-fast) var(--ease); }
.st:hover .st-go { background: var(--surface-graphite); color: #fff; }
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
.who .body-sm { line-height: 1.35; }
.fleet .mono-md { color: var(--brand-300); }
.fleet li.out { opacity: 0.5; }
@media (max-width: 1100px) { .hero { grid-template-columns: 1fr; } .hero-img { width: 100%; height: 200px; } .span-7, .span-5 { grid-column: span 12; } .side { position: static; } }
</style>
