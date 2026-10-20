<script setup lang="ts">
import type { AnalyticsRobot } from '~/data/analytics'
import type { RobotProduct } from '~/composables/useRobotDraft'
import { useRobotDraft } from '~/composables/useRobotDraft'
import { fetchErrorMessage } from '~/utils/errors'
import { platformGet, platformSend, usePlatformBase } from '~/composables/usePlatform'

definePageMeta({ layout: 'vendor', middleware: 'vendor', pageTransition: false })
useHead({ title: 'Кабинет вендора · Роботы' })

interface ProcessChoice { code: string; name: string }
interface ParserChoice { code: string; title: string; summary: string }
interface DraftRobot { name: string; summary: string; price_rub: number | null; processes: string[]; attrs: { key: string; label: string; value: unknown }[] }

const route = useRoute()
const products = ref<RobotProduct[]>([])
const board = ref<AnalyticsRobot[]>([])
const processes = ref<ProcessChoice[]>([])
const parsers = ref<ParserChoice[]>([])
const robotView = ref<'add' | 'edit'>('edit')
const addMode = ref<'one' | 'file' | 'site'>('one')
const fresh = reactive({ name: '', summary: '', price: '', processes: [] as string[], attrs: [] as { label: string; value: string }[] })
const importUrl = ref('')
const parserCode = ref('')
const preview = ref<DraftRobot[]>([])
const pageError = ref('')
const pageNotice = ref('')
const pageBusy = ref(false)

const draft = useRobotDraft(async () => { await load() })
const cards = computed(() => board.value)
const parserPlain: Record<string, string> = {
  robob2b: 'Сайт robob2b.ru. Возьмём только карточки вашей компании.',
  robort: 'Сайт robort.ru. Возьмём только карточки вашей компании.',
  robot_moscow: 'Сайт robot.moscow. Возьмём только карточки вашей компании.',
}

const load = async () => {
  const [robots, processPage, parserPage] = await Promise.all([
    platformGet<RobotProduct[]>('/vendor/products'),
    platformGet<ProcessChoice[]>('/vendor/processes'),
    platformGet<ParserChoice[]>('/vendor/parsers'),
  ])
  products.value = robots
  processes.value = processPage
  parsers.value = parserPage
  if (!parserCode.value && parserPage[0]) parserCode.value = parserPage[0].code
  try {
    const summary = await platformGet<{ robots: AnalyticsRobot[] }>('/vendor/analytics')
    board.value = summary.robots
  } catch (err) {
    if (!board.value.length) {
      pageError.value = fetchErrorMessage(err, 'Сводка по подбору не загрузилась. Карточки всё равно можно править.')
      board.value = robots.map((robot) => ({
        slug: robot.slug,
        name: robot.name,
        summary: robot.summary,
        price_rub: robot.price_rub,
        image_url: null,
        trl: null,
        availability: null,
        solution_type: null,
        manufacturer: '',
        city: '',
        state: 'note' as const,
        headline: 'Откройте карточку, дополните поля и отправьте на проверку.',
        gaps: [],
        processes: robot.processes.map((code) => ({ code, name: processes.value.find((item) => item.code === code)?.name || code })),
        offers: 0,
        highlights: [],
        revision_comment: '',
      }))
    }
  }
}

const productOf = (slug: string) => products.value.find((item) => item.slug === slug)
const toggle = (slug: string) => {
  const card = board.value.find((item) => item.slug === slug)
  draft.toggle(productOf(slug), card?.gaps || [])
}

const run = async (action: () => Promise<string | void>, ok: string) => {
  pageError.value = ''
  pageNotice.value = ''
  pageBusy.value = true
  try {
    const extra = await action()
    pageNotice.value = extra || ok
    await load()
  } catch (err) {
    pageError.value = fetchErrorMessage(err, 'Не получилось отправить')
  } finally {
    pageBusy.value = false
  }
}

const robotsWord = (count: number) => {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return 'робот'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'робота'
  return 'роботов'
}

const sendFresh = () => run(async () => {
  await platformSend('/vendor/requests', 'POST', {
    kind: 'product_create',
    payload: {
      name: fresh.name,
      summary: fresh.summary,
      price_rub: fresh.price === '' ? null : Number(fresh.price.replace(',', '.')),
      processes: fresh.processes,
      attrs: Object.fromEntries(fresh.attrs.filter((item) => item.label && item.value).map((item) => [item.label, item.value])),
    },
  })
  fresh.name = ''
  fresh.summary = ''
  fresh.price = ''
  fresh.processes = []
  fresh.attrs = []
}, 'Робот отправлен на проверку. В каталоге он появится после подтверждения.')

const sendBatch = (robots: DraftRobot[], source: string) => run(async () => {
  await platformSend('/vendor/requests', 'POST', { kind: 'import_batch', payload: { robots, source } })
  preview.value = []
}, `Список из ${robots.length} роботов отправлен. В каталоге они появятся после подтверждения.`)

const readFile = async (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  pageError.value = ''
  pageNotice.value = ''
  pageBusy.value = true
  try {
    const body = new FormData()
    body.append('file', file)
    const page = await $fetch<{ robots: DraftRobot[] }>(`${usePlatformBase()}/vendor/preview-file`, { method: 'POST', body, credentials: 'include' })
    preview.value = page.robots
    pageNotice.value = `В файле ${page.robots.length} ${robotsWord(page.robots.length)}. Проверьте названия и отправьте список.`
  } catch (err) {
    pageError.value = fetchErrorMessage(err, 'Файл не разобрался')
  } finally {
    pageBusy.value = false
  }
}

const readUrl = () => run(async () => {
  const page = await platformSend<{ robots: DraftRobot[] }>('/vendor/preview-url', 'POST', { url: importUrl.value })
  preview.value = page.robots
  return `По ссылке нашлось ${page.robots.length} ${robotsWord(page.robots.length)}. Если это ваши модели, отправьте список.`
}, '')

const sendParse = () => run(async () => {
  await platformSend('/vendor/requests', 'POST', { kind: 'parse', payload: { parser: parserCode.value } })
}, 'Заявка отправлена. После подтверждения в каталог попадут только роботы вашей компании.')

onMounted(async () => {
  try {
    await load()
    const slug = typeof route.query.slug === 'string' ? route.query.slug : ''
    if (slug) {
      robotView.value = 'edit'
      draft.open(productOf(slug), board.value.find((item) => item.slug === slug)?.gaps || [])
    }
  } catch (err) {
    pageError.value = fetchErrorMessage(err, 'Кабинет не открылся')
  }
})
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Роботы" title="Ваши модели" lead="Нажмите карточку, дополните пустые поля и отправьте на проверку. Заказчик увидит новое только после подтверждения." />
    <UiCallout v-if="pageNotice || draft.notice" tone="ok">
      {{ pageNotice || draft.notice }}
      <NuxtLink to="/vendor/requests" class="jump">Смотреть статус</NuxtLink>
    </UiCallout>
    <UiCallout v-else-if="pageError || draft.error" tone="danger">{{ pageError || draft.error }}</UiCallout>

    <div class="mode-row">
      <button type="button" class="mode" :class="{ on: robotView === 'add' }" @click="robotView = 'add'">Добавить</button>
      <button type="button" class="mode" :class="{ on: robotView === 'edit' }" @click="robotView = 'edit'">Карточки</button>
    </div>

    <template v-if="robotView === 'add'">
      <div class="mode-row sub">
        <button type="button" class="mode" :class="{ on: addMode === 'one' }" @click="addMode = 'one'">Один робот</button>
        <button type="button" class="mode" :class="{ on: addMode === 'file' }" @click="addMode = 'file'">Списком</button>
        <button type="button" class="mode" :class="{ on: addMode === 'site' }" @click="addMode = 'site'">С сайта</button>
      </div>

      <section v-if="addMode === 'one'" class="glass glass-xl a-panel">
        <div class="h3">Новый робот</div>
        <p class="body-sm muted">Одна модель. Если их много, удобнее пункт «Списком».</p>
        <div class="grid-2">
          <label class="a-fld"><span class="caption">Название</span><input v-model="fresh.name" class="input" placeholder="Как модель называется у вас"></label>
          <label class="a-fld"><span class="caption">Цена, руб.</span><input v-model="fresh.price" class="input" inputmode="decimal" placeholder="Если цены нет, оставьте пустым"></label>
        </div>
        <label class="a-fld"><span class="caption">Коротко</span><textarea v-model="fresh.summary" class="textarea" rows="3" placeholder="Одним предложением, что робот делает" /></label>
        <div class="a-fld">
          <span class="caption">Что умеет</span>
          <ProcessPicker v-model="fresh.processes" :processes="processes" />
        </div>
        <div class="attrs">
          <div v-for="(item, index) in fresh.attrs" :key="index" class="grid-2">
            <label class="a-fld"><span class="caption">Характеристика</span><input v-model="item.label" class="input" placeholder="Грузоподъёмность"></label>
            <label class="a-fld"><span class="caption">Значение</span><input v-model="item.value" class="input" placeholder="1500 кг"></label>
          </div>
        </div>
        <div class="a-row">
          <UiButton variant="secondary" @click="fresh.attrs.push({ label: '', value: '' })">Добавить характеристику</UiButton>
          <UiButton :disabled="pageBusy || !fresh.name.trim()" @click="sendFresh">Отправить на проверку</UiButton>
        </div>
      </section>

      <section v-else-if="addMode === 'file'" class="glass glass-xl a-panel">
        <div class="h3">Несколько роботов сразу</div>
        <p class="body-sm muted">Таблица CSV или файл JSON. В первой строке таблицы: название, описание, цена, процессы. Процессы пишите как здесь, через запятую. Остальные колонки станут характеристиками.</p>
        <label class="a-fld"><span class="caption">Файл</span><input class="input" type="file" accept=".json,.csv,application/json,text/csv" @change="readFile"></label>
        <label class="a-fld">
          <span class="caption">Или ссылка</span>
          <span class="a-row">
            <input v-model="importUrl" class="input" placeholder="https://ваша-компания.ru/robots.json">
            <UiButton variant="secondary" :disabled="pageBusy || !importUrl" @click="readUrl">Прочитать</UiButton>
          </span>
        </label>
        <div v-if="preview.length" class="preview">
          <div class="body-sm strong">К отправке: {{ preview.length }}</div>
          <ul class="names">
            <li v-for="(item, index) in preview.slice(0, 8)" :key="`${item.name}-${index}`">{{ item.name }}</li>
          </ul>
          <p v-if="preview.length > 8" class="caption">И ещё {{ preview.length - 8 }}</p>
          <UiButton :disabled="pageBusy" @click="sendBatch(preview, importUrl ? 'api' : 'file')">Отправить список</UiButton>
        </div>
      </section>

      <section v-else class="glass glass-xl a-panel">
        <div class="h3">Найти модели на открытом сайте</div>
        <p class="body-sm muted">Платформа посмотрит выбранный каталог и оставит только роботов вашей компании. Поиск начнётся после подтверждения заявки.</p>
        <label class="a-fld">
          <span class="caption">Сайт</span>
          <select v-model="parserCode" class="select">
            <option v-for="item in parsers" :key="item.code" :value="item.code">{{ item.title }}</option>
          </select>
          <span class="caption">{{ parserPlain[parserCode] || parsers.find((item) => item.code === parserCode)?.summary }}</span>
        </label>
        <UiButton :disabled="pageBusy || !parserCode" @click="sendParse">Отправить на проверку</UiButton>
      </section>
    </template>

    <section v-else class="stack">
      <p v-if="!cards.length" class="body-sm muted">Своих роботов пока нет. Нажмите «Добавить».</p>
      <div v-else class="grid grid-cards">
        <VendorRobotCard v-for="robot in cards" :key="robot.slug" compact :robot="robot" :open="draft.openSlug === robot.slug" @toggle="toggle(robot.slug)">
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
  </div>
</template>

<style scoped>
.mode-row { display: flex; flex-wrap: wrap; gap: 8px; }
.mode { min-height: 40px; padding: 8px 16px; border-radius: 12px; font-weight: 700; color: var(--ink-body); background: rgba(15, 20, 19, 0.05); }
.mode.on { background: var(--surface-graphite); color: var(--ink-on-graphite); }
.mode-row.sub .mode { font-weight: 600; background: transparent; box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.12); }
.mode-row.sub .mode.on { background: rgba(15, 20, 19, 0.06); color: var(--ink-strong); }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.attrs { display: grid; gap: 10px; }
.stack { display: grid; gap: 12px; }
.preview { display: grid; gap: 8px; }
.names { margin: 0; padding-left: 18px; display: grid; gap: 4px; }
.jump { margin-left: 8px; font-weight: 700; text-decoration: underline; text-underline-offset: 3px; }
@media (max-width: 800px) {
  .grid-2 { grid-template-columns: 1fr; }
}
</style>
