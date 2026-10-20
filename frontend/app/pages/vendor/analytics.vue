<script setup lang="ts">
import type { AnalyticsRobot, MatchEvent, VendorBoard } from '~/data/analytics'
import type { RobotProduct } from '~/composables/useRobotDraft'
import { useRobotDraft } from '~/composables/useRobotDraft'
import { fetchErrorMessage } from '~/utils/errors'
import { platformGet } from '~/composables/usePlatform'
import { pluralRu } from '~/data/adminLabels'

definePageMeta({ layout: 'vendor', middleware: 'vendor', pageTransition: false })
useHead({ title: 'Кабинет вендора · Аналитика' })

const board = ref<VendorBoard | null>(null)
const products = ref<RobotProduct[]>([])
const processes = ref<{ code: string; name: string }[]>([])
const failure = ref('')
const onlyGaps = ref(true)

const draft = useRobotDraft(async () => { await load() })
const shown = computed(() => {
  const rows = board.value?.robots || []
  return onlyGaps.value ? rows.filter((item) => item.state !== 'in') : rows
})
const pieNote = computed(() => {
  const note = board.value?.pie.note || 0
  if (!note) return 'Зелёные участвуют в подборе. Красные из него выпадают.'
  return `Зелёные участвуют в подборе. Из них ${note} ${pluralRu(note, 'робот попадает', 'робота попадают', 'роботов попадают')} с пометкой: не хватает характеристик. Красные в подбор не попадают.`
})

const load = async () => {
  const [summary, robots, processPage] = await Promise.all([
    platformGet<VendorBoard>('/vendor/analytics'),
    platformGet<RobotProduct[]>('/vendor/products'),
    platformGet<{ code: string; name: string }[]>('/vendor/processes'),
  ])
  board.value = summary
  products.value = robots
  processes.value = processPage
}

const productOf = (slug: string) => products.value.find((item) => item.slug === slug)
const toggle = (robot: AnalyticsRobot) => draft.toggle(productOf(robot.slug), robot.gaps)
const targets = (event: MatchEvent) => {
  const map = new Map<string, string>()
  for (const item of [...event.noted, ...event.blocked]) {
    if (item.slug) map.set(item.slug, item.name)
  }
  return [...map.entries()].map(([slug, name]) => ({ slug, name }))
}
const follow = (slug: string) => {
  const card = board.value?.robots.find((item) => item.slug === slug)
  if (!card) return
  if (card.state === 'in') onlyGaps.value = false
  draft.open(productOf(slug), card.gaps)
}
const when = (iso: string | null) => iso
  ? new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })
  : ''

onMounted(() => { void load().catch((err) => { failure.value = fetchErrorMessage(err, 'Аналитика не открылась') }) })
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Аналитика" title="Как роботы попадают в подбор" />
    <UiCallout v-if="failure" tone="danger">{{ failure }}</UiCallout>
    <UiCallout v-else-if="draft.error" tone="danger">{{ draft.error }}</UiCallout>
    <UiCallout v-else-if="draft.notice" tone="ok">
      {{ draft.notice }}
      <NuxtLink to="/vendor/requests" class="jump">Смотреть статус</NuxtLink>
    </UiCallout>

    <template v-if="board">
      <section class="glass glass-xl a-panel">
        <div class="h3">Участие в подборе</div>
        <MatchPie :green="board.pie.in" :red="board.pie.out" green-label="Участвуют" red-label="Исключены" :note="pieNote" />
      </section>

      <div class="stats">
        <UiStat label="Подборов с вашими роботами" :value="String(board.matches.total)" note="Столько раз модели попали в чей-то расчёт" />
        <UiStat label="Удачных" :value="String(board.matches.success)" note="Хотя бы один ваш робот получил «Подходит»" />
        <UiStat label="Неудачных" :value="String(board.matches.empty)" note="Подходящим вашего робота признать не удалось" />
        <UiStat label="Показов" :value="String(board.offers)" note="Сколько раз модель была в «Подходит», «С условием» или «Уточнить»" />
      </div>

      <section v-if="board.reasons.length" class="glass glass-xl a-panel">
        <div class="h3">Почему подбор не сложился</div>
        <div v-for="item in board.reasons" :key="item.text" class="reason">
          <span class="body-sm">{{ item.text }}</span>
          <span class="mono-sm">{{ item.count }}</span>
        </div>
      </section>

      <section class="glass glass-xl a-panel">
        <div class="h3">Что вводил заказчик, когда робот не подошёл</div>
        <p v-if="!board.events.length" class="body-sm muted">Пока таких подборов нет. Строка появится, когда заказчик откроет подбор и ваша модель в нём поучаствует.</p>
        <article v-for="(event, index) in board.events" :key="`${index}-${event.at}`" class="event">
          <div class="a-head">
            <div>
              <div class="body-sm strong">{{ event.text }}</div>
              <div class="caption">{{ event.object_name }} · {{ when(event.at) }}</div>
            </div>
            <UiBadge :tone="event.outcome === 'success' ? 'ok' : 'danger'">{{ event.outcome === 'success' ? 'Подошёл' : 'Не подошёл' }}</UiBadge>
          </div>
          <p v-if="event.site.length" class="body-sm">Параметры площадки: {{ event.site.map((item) => `${item.label}: ${item.value}`).join(', ') }}</p>
          <ul v-if="event.reasons.length" class="reasons">
            <li v-for="text in event.reasons" :key="text">{{ text }}</li>
          </ul>
          <div v-if="targets(event).length" class="a-row">
            <UiButton v-for="item in targets(event)" :key="item.slug" size="sm" variant="secondary" @click="follow(item.slug)">Дополнить «{{ item.name }}»</UiButton>
          </div>
        </article>
      </section>

      <section class="stack">
        <div class="a-head">
          <div>
            <div class="h3">Карточки, которые стоит дополнить</div>
            <p class="body-sm muted">Откройте карточку, впишите пустые поля и отправьте на проверку.</p>
          </div>
          <button type="button" class="mode" :class="{ on: onlyGaps }" @click="onlyGaps = !onlyGaps">{{ onlyGaps ? 'Показать все' : 'Только с пробелами' }}</button>
        </div>
        <p v-if="!shown.length" class="body-sm muted">{{ onlyGaps ? 'Пробелов нет: все роботы могут участвовать в подборе.' : 'Своих карточек пока нет.' }}</p>
        <div v-else class="grid grid-cards">
          <VendorRobotCard v-for="robot in shown" :key="robot.slug" :robot="robot" :open="draft.openSlug === robot.slug" @toggle="toggle(robot)">
            <VendorRobotEditor
              v-if="productOf(robot.slug)"
              v-model:name="draft.editName"
              v-model:summary="draft.editSummary"
              v-model:price="draft.editPrice"
              v-model:processes="draft.editProcesses"
              v-model:attrs="draft.editAttrs"
              :choices="processes"
              :gaps="robot.gaps"
              :busy="draft.busy"
              @submit="draft.send()"
            />
          </VendorRobotCard>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
.reason, .event { display: grid; gap: 8px; padding-top: 12px; border-top: 1px solid var(--border-hairline); }
.reason { grid-template-columns: 1fr auto; align-items: start; }
.reasons { margin: 0; padding-left: 18px; display: grid; gap: 4px; }
.stack { display: grid; gap: 12px; }
.mode { min-height: 40px; padding: 8px 16px; border-radius: 12px; font-weight: 700; color: var(--ink-body); background: rgba(15, 20, 19, 0.05); }
.mode.on { background: var(--surface-graphite); color: var(--ink-on-graphite); }
.jump { margin-left: 8px; font-weight: 700; text-decoration: underline; text-underline-offset: 3px; }
@media (max-width: 900px) {
  .stats { grid-template-columns: 1fr 1fr; }
}
</style>
