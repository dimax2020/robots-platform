<script setup lang="ts">
import { PhCaretDown, PhCaretRight, PhMapPin } from '@phosphor-icons/vue'
import type { AnalyticsRobot, MatchTotals, ReasonStat } from '~/data/analytics'
import { stateLabel } from '~/data/analytics'
import { photoFor } from '~/data/placeholders'
import { fetchErrorMessage } from '~/utils/errors'
import { platformGet, platformSend } from '~/composables/usePlatform'

definePageMeta({ layout: 'admin', middleware: 'admin', pageTransition: false })
useHead({ title: 'Админка · Аналитика' })

interface VendorCard {
  company: string
  manufacturer: string
  city: string
  logo_url: string | null
  has_cabinet: boolean
  ok: boolean
  rating: number
  robots_total: number
  robots_in: number
  robots_out: number
  robots_note: number
  matches: MatchTotals
  reasons: ReasonStat[]
  robots: AnalyticsRobot[]
}
interface Board {
  matches: MatchTotals
  reasons: ReasonStat[]
  vendor_pie: { ok: number; fix: number }
  robot_pie: { in: number; out: number; note: number }
  vendors: VendorCard[]
  problems: AnalyticsRobot[]
}

const data = ref<Board | null>(null)
const failure = ref('')
const notice = ref('')
const error = ref('')
const busy = ref('')
const query = ref('')
const vendorQuery = ref('')
const onlyFix = ref(true)
const vendorSort = ref<'more' | 'less'>('more')
const openReasons = ref(false)
const openProblems = ref(false)
const openVendors = ref(false)
const openVendor = ref('')
const openProblem = ref('')
const comments = reactive<Record<string, string>>({})

const needle = computed(() => query.value.trim().toLocaleLowerCase('ru'))
const vendorNeedle = computed(() => vendorQuery.value.trim().toLocaleLowerCase('ru'))
const problems = computed(() => (data.value?.problems || []).filter((item) => {
  if (!needle.value) return true
  return `${item.name} ${item.manufacturer} ${item.headline}`.toLocaleLowerCase('ru').includes(needle.value)
}))
const reasonSum = computed(() => (data.value?.reasons || []).reduce((sum, item) => sum + item.count, 0))
const vendors = computed(() => {
  const rows = (data.value?.vendors || []).filter((item) => {
    if (onlyFix.value && item.ok) return false
    if (!vendorNeedle.value) return true
    return `${item.company} ${item.manufacturer} ${item.city}`.toLocaleLowerCase('ru').includes(vendorNeedle.value)
  })
  const sign = vendorSort.value === 'more' ? -1 : 1
  return [...rows].sort((left, right) => {
    const gap = (left.robots_out + left.robots_note) - (right.robots_out + right.robots_note)
    if (gap) return gap * sign
    return left.company.localeCompare(right.company, 'ru')
  })
})
const robotNote = computed(() => {
  const note = data.value?.robot_pie.note || 0
  if (!note) return 'Зелёные участвуют в подборе. Красные из него выпадают.'
  return `Зелёные участвуют в подборе. Из них ${note} с пометкой: карточки не хватает для чистого результата. Красные в подбор не попадают.`
})
const shareOf = (count: number) => {
  if (!reasonSum.value) return '0%'
  return `${Math.round((100 * count) / reasonSum.value)}%`
}
const gapsOf = (vendor: VendorCard) => vendor.robots.filter((item) => item.state !== 'in')

watch(query, (value) => { if (value.trim()) openProblems.value = true })
watch(vendorQuery, (value) => { if (value.trim()) openVendors.value = true })

const load = async () => {
  data.value = await platformGet<Board>('/admin/analytics')
}
const sendFix = async (robot: AnalyticsRobot) => {
  error.value = ''
  notice.value = ''
  const comment = (comments[robot.slug] || '').trim()
  if (!comment) {
    error.value = 'Напишите, что исправить. Производитель увидит этот текст в заявке.'
    return
  }
  busy.value = robot.slug
  try {
    await platformSend('/admin/analytics/fix', 'POST', { slug: robot.slug, comment })
    notice.value = `Просьба по «${robot.name}» ушла производителю. Он дополнит карточку и отправит её на проверку.`
    comments[robot.slug] = ''
    await load()
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Не удалось отправить просьбу')
  } finally {
    busy.value = ''
  }
}
const sendVendor = async (vendor: VendorCard) => {
  error.value = ''
  notice.value = ''
  if (!vendor.has_cabinet) {
    error.value = 'У этого вендора нет кабинета, заявку отправить некому.'
    return
  }
  const items = gapsOf(vendor).map((robot) => ({
    slug: robot.slug,
    comment: (comments[robot.slug] || '').trim() || robot.headline,
  }))
  if (!items.length) return
  busy.value = vendor.manufacturer
  try {
    const saved = await platformSend<{ sent: number }>('/admin/analytics/fix-vendor', 'POST', { items })
    notice.value = `Вендору «${vendor.company}» ушло заявок: ${saved.sent}. Каждая модель с пробелом появится у него в заявках.`
    for (const robot of gapsOf(vendor)) comments[robot.slug] = ''
    await load()
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Не удалось отправить на доработку')
  } finally {
    busy.value = ''
  }
}
const tone = (state: AnalyticsRobot['state']) => (state === 'in' ? 'ok' : state === 'note' ? 'warn' : 'danger') as 'ok' | 'warn' | 'danger'

onMounted(() => { void load().catch((err) => { failure.value = fetchErrorMessage(err, 'Аналитика не открылась') }) })
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Сводка" title="Аналитика подбора" lead="Сколько подборов прошло, у каких вендоров роботы выпадают из подбора и что попросить их дополнить." />
    <UiCallout v-if="failure" tone="danger">{{ failure }}</UiCallout>
    <UiCallout v-else-if="error" tone="danger">{{ error }}</UiCallout>
    <UiCallout v-else-if="notice" tone="ok">{{ notice }}</UiCallout>

    <template v-if="data">
      <div class="stats">
        <UiStat label="Всего подборов" :value="String(data.matches.total)" note="Каждое открытие подбора заказчиком" />
        <UiStat label="Удачных" :value="String(data.matches.success)" note="Нашёлся хотя бы один робот со статусом «Подходит»" />
        <UiStat label="Неудачных" :value="String(data.matches.empty)" note="Подходящего робота не было" />
      </div>

      <div class="pies">
        <section class="glass glass-xl a-panel">
          <div class="h3">Вендоры</div>
          <MatchPie :green="data.vendor_pie.ok" :red="data.vendor_pie.fix" green-label="Всё заполнено" red-label="Нужны правки" note="Зелёные: у всех роботов хватает данных. Красные: есть пустые поля или роботов нет." />
        </section>
        <section class="glass glass-xl a-panel">
          <div class="h3">Роботы</div>
          <MatchPie :green="data.robot_pie.in" :red="data.robot_pie.out" green-label="Участвуют" red-label="Исключены" :note="robotNote" />
        </section>
      </div>

      <section class="fold">
        <div class="bar">
          <button type="button" class="fold-btn" :aria-expanded="openReasons" @click="openReasons = !openReasons">
            <component :is="openReasons ? PhCaretDown : PhCaretRight" :size="14" weight="bold" />
            <span class="h3">Почему подбор оставался пустым</span>
            <span class="count">{{ data.reasons.length }}</span>
          </button>
        </div>
        <div v-if="openReasons" class="scroller short">
          <p v-if="!data.reasons.length" class="body-sm muted">Пустых подборов пока не было.</p>
          <div v-else class="grid grid-cards">
            <article v-for="item in data.reasons" :key="item.text" class="card-r glass reason-card">
              <div class="body">
                <div class="label">Причина</div>
                <p class="reason-title">{{ item.text }}</p>
                <dl class="specs">
                  <div><dt>Сколько раз</dt><dd>{{ item.count }}</dd></div>
                  <div><dt>Доля причин</dt><dd>{{ shareOf(item.count) }}</dd></div>
                </dl>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section class="fold">
        <div class="bar">
          <button type="button" class="fold-btn" :aria-expanded="openProblems" @click="openProblems = !openProblems">
            <component :is="openProblems ? PhCaretDown : PhCaretRight" :size="14" weight="bold" />
            <span class="h3">Роботы с проблемой в подборе</span>
            <span class="count">{{ problems.length }}</span>
          </button>
          <input v-model="query" class="input seek" placeholder="Найти робота" aria-label="Поиск робота">
        </div>
        <div v-if="openProblems" class="scroller">
          <p v-if="!problems.length" class="body-sm muted">Таких роботов нет.</p>
          <div v-else class="grid grid-cards">
            <article v-for="robot in problems" :key="robot.slug" class="card-r glass" :class="{ open: openProblem === robot.slug }">
              <button type="button" class="media" :aria-expanded="openProblem === robot.slug" @click="openProblem = openProblem === robot.slug ? '' : robot.slug">
                <img :src="photoFor(robot.image_url, robot.name, robot.processes[0]?.code)" :alt="robot.name">
                <span class="badges"><UiBadge :tone="tone(robot.state)">{{ stateLabel[robot.state] }}</UiBadge></span>
              </button>
              <div class="body">
                <button type="button" class="h3 name" @click="openProblem = openProblem === robot.slug ? '' : robot.slug">{{ robot.name }}</button>
                <div class="vendor body-sm muted">{{ robot.manufacturer || 'Производитель не указан' }}</div>
                <p class="headline">{{ robot.headline }}</p>
                <div v-if="openProblem === robot.slug" class="editor">
                  <p v-if="!robot.has_cabinet" class="caption">У этого производителя нет кабинета, отправить правку некому.</p>
                  <div v-else class="a-row">
                    <label class="a-fld">
                      <span class="caption">Комментарий производителю</span>
                      <textarea v-model="comments[robot.slug]" class="textarea" rows="2" placeholder="Например, укажите грузоподъёмность, иначе робот не попадёт в подбор" />
                    </label>
                    <UiButton :disabled="busy === robot.slug" @click="sendFix(robot)">Отправить на исправление</UiButton>
                  </div>
                </div>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section class="fold">
        <div class="bar">
          <button type="button" class="fold-btn" :aria-expanded="openVendors" @click="openVendors = !openVendors">
            <component :is="openVendors ? PhCaretDown : PhCaretRight" :size="14" weight="bold" />
            <span class="h3">Вендоры</span>
            <span class="count">{{ vendors.length }}</span>
          </button>
          <input v-model="vendorQuery" class="input seek" placeholder="Найти вендора" aria-label="Поиск вендора">
          <div class="sorts">
            <button type="button" class="mode" :class="{ on: vendorSort === 'more' }" @click="vendorSort = 'more'; openVendors = true">Больше правок</button>
            <button type="button" class="mode" :class="{ on: vendorSort === 'less' }" @click="vendorSort = 'less'; openVendors = true">Меньше правок</button>
            <button type="button" class="mode" :class="{ on: onlyFix }" @click="onlyFix = !onlyFix; openVendors = true">{{ onlyFix ? 'Показать всех' : 'Только с правками' }}</button>
          </div>
        </div>
        <div v-if="openVendors" class="scroller">
          <p v-if="!vendors.length" class="body-sm muted">{{ onlyFix ? 'Сейчас у всех вендоров карточки заполнены.' : 'Вендоров пока нет.' }}</p>
          <div v-else class="grid grid-cards">
            <article v-for="vendor in vendors" :key="vendor.manufacturer" class="card-r glass" :class="{ open: openVendor === vendor.manufacturer }">
              <button type="button" class="media" :aria-expanded="openVendor === vendor.manufacturer" @click="openVendor = openVendor === vendor.manufacturer ? '' : vendor.manufacturer">
                <img v-if="vendor.logo_url" :src="vendor.logo_url" :alt="vendor.company">
                <span v-else class="letter">{{ vendor.company.slice(0, 1) }}</span>
                <span class="badges">
                  <UiBadge :tone="vendor.ok ? 'ok' : 'danger'">{{ vendor.ok ? 'Всё заполнено' : 'Нужны правки' }}</UiBadge>
                </span>
              </button>
              <div class="body">
                <button type="button" class="h3 name" @click="openVendor = openVendor === vendor.manufacturer ? '' : vendor.manufacturer">{{ vendor.company }}</button>
                <div class="vendor body-sm muted">
                  <span class="strong">{{ vendor.manufacturer }}</span>
                  <template v-if="vendor.city"> <PhMapPin :size="12" /> {{ vendor.city }}</template>
                </div>
                <p class="headline">Готовность {{ vendor.rating }}%. {{ vendor.has_cabinet ? 'Кабинет есть.' : 'Кабинета нет, правку отправить нельзя.' }}</p>
                <dl class="specs">
                  <div><dt>В подборе</dt><dd>{{ vendor.robots_in }}</dd></div>
                  <div><dt>Исключены</dt><dd :class="{ dim: vendor.robots_out }">{{ vendor.robots_out }}</dd></div>
                  <div><dt>Удачные подборы</dt><dd>{{ vendor.matches.success }}</dd></div>
                  <div><dt>Неудачные</dt><dd :class="{ dim: vendor.matches.empty }">{{ vendor.matches.empty }}</dd></div>
                </dl>
                <div v-if="openVendor === vendor.manufacturer" class="editor">
                  <p class="body-sm">Роботов: {{ vendor.robots_total }}. С пометкой: {{ vendor.robots_note }}. Подборов с этими моделями: {{ vendor.matches.total }}.</p>
                  <div v-if="vendor.reasons.length" class="reasons">
                    <div class="caption">Почему неудачные подборы</div>
                    <div v-for="item in vendor.reasons" :key="item.text" class="reason">
                      <span class="body-sm">{{ item.text }}</span>
                      <span class="mono-sm">{{ item.count }}</span>
                    </div>
                  </div>
                  <p v-else class="caption">Неудачных подборов по этим роботам пока нет.</p>
                  <div v-if="gapsOf(vendor).length" class="inner-scroll">
                    <article v-for="robot in gapsOf(vendor)" :key="robot.slug" class="problem inner">
                      <div class="a-head">
                        <div class="body-sm strong">{{ robot.name }}</div>
                        <UiBadge :tone="tone(robot.state)">{{ stateLabel[robot.state] }}</UiBadge>
                      </div>
                      <p class="body-sm">{{ robot.headline }}</p>
                      <div v-if="vendor.has_cabinet" class="a-row">
                        <label class="a-fld">
                          <span class="caption">Комментарий</span>
                          <textarea v-model="comments[robot.slug]" class="textarea" rows="2" placeholder="Что дополнить в карточке" />
                        </label>
                        <UiButton :disabled="busy === robot.slug" @click="sendFix(robot)">Отправить на исправление</UiButton>
                      </div>
                    </article>
                  </div>
                  <div v-if="vendor.has_cabinet && gapsOf(vendor).length" class="send-all">
                    <UiButton :disabled="busy === vendor.manufacturer" @click="sendVendor(vendor)">Отправить на доработку</UiButton>
                    <p class="caption">Вендор получит заявку по каждой модели с пробелом и увидит её у себя в кабинете.</p>
                  </div>
                  <p v-else-if="!vendor.has_cabinet" class="caption">Кабинета нет, отправить на доработку некому.</p>
                  <p v-else-if="vendor.ok" class="caption">Пробелов нет: все роботы этого вендора участвуют в подборе.</p>
                </div>
              </div>
            </article>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.stats { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; }
.pies { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.fold { display: grid; gap: 12px; }
.bar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.fold-btn { display: inline-flex; align-items: center; gap: 8px; padding: 0; border: 0; background: none; color: inherit; cursor: pointer; text-align: left; }
.fold-btn .h3 { margin: 0; }
.count { min-width: 28px; padding: 2px 8px; border-radius: 999px; background: rgba(15, 20, 19, 0.06); font-size: 12px; font-weight: 700; }
.seek { width: min(280px, 100%); }
.sorts { display: flex; gap: 8px; flex-wrap: wrap; margin-left: auto; }
.scroller { max-height: 920px; overflow: auto; padding-right: 4px; }
.scroller.short { max-height: 340px; }
.reason { display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: start; }
.reason-card { height: auto; }
.reason-title { margin: 0; font-size: 15px; font-weight: 700; line-height: 1.35; color: var(--ink-strong); }
.problem { display: grid; gap: 8px; padding-top: 14px; border-top: 1px solid var(--border-hairline); }
.problem.inner { padding: 12px; border: 0; border-radius: 14px; background: rgba(255, 255, 255, 0.45); }
.reasons { display: grid; gap: 6px; }
.inner-scroll { max-height: 420px; overflow: auto; display: grid; gap: 8px; padding-right: 4px; }
.send-all { display: grid; gap: 6px; justify-items: start; }
.mode { min-height: 40px; padding: 8px 16px; border-radius: 12px; font-weight: 700; color: var(--ink-body); background: rgba(15, 20, 19, 0.05); }
.mode.on { background: var(--surface-graphite); color: var(--ink-on-graphite); }
.card-r { display: grid; grid-template-rows: auto 1fr; border-radius: var(--radius-xl); overflow: hidden; height: 100%; }
.card-r.open { grid-column: 1 / -1; height: auto; }
.media { position: relative; display: grid; place-items: center; aspect-ratio: 4 / 3; margin: 8px; border: 0; border-radius: 18px; overflow: hidden; background: #e9eeec; cursor: pointer; }
.media img { width: 100%; height: 100%; object-fit: cover; }
.letter { font-size: 48px; font-weight: 700; color: var(--ink-muted); }
.badges { position: absolute; left: 10px; top: 10px; display: flex; gap: 6px; }
.body { display: grid; gap: 8px; padding: 8px 16px 16px; align-content: start; text-align: left; }
.name { color: var(--ink-strong); text-align: left; background: none; border: 0; padding: 0; cursor: pointer; }
.vendor { display: flex; align-items: center; gap: 4px; }
.headline { margin: 0; font-size: 13px; line-height: 1.45; color: var(--ink-body); }
.specs { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 12px; margin: 0; padding-top: 12px; border-top: 1px solid rgba(15, 20, 19, 0.08); }
.specs dt { font-size: 12px; color: var(--ink-muted); }
.specs dd { margin: 0; color: var(--ink-strong); font-weight: 700; }
.specs dd.dim { color: var(--state-danger); }
.editor { display: grid; gap: 10px; padding-top: 12px; border-top: 1px solid var(--border-hairline); }
@media (max-width: 900px) {
  .stats, .pies { grid-template-columns: 1fr; }
  .sorts { margin-left: 0; }
}
</style>
