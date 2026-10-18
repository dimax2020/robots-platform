<script setup lang="ts">
import { fetchErrorMessage } from '~/utils/errors'
import { platformGet, platformSend, usePlatformBase } from '~/composables/usePlatform'

definePageMeta({ middleware: 'vendor' })
useHead({ title: 'Кабинет вендора' })

interface Profile {
  manufacturer: string
  company_name: string
  about: string
  website: string
  email: string
  phone: string
  city: string
  logo_url: string | null
  documents: { kind: string; title: string; filename?: string; url?: string; note?: string }[]
}
interface Attr { key: string; label: string; value: unknown; unit?: string | null }
interface Robot {
  slug: string
  name: string
  summary: string | null
  price_rub: number | null
  processes: string[]
  attrs: Attr[]
}
interface RequestRow {
  id: string
  kind: string
  title: string
  summary: string
  status: string
  catalog_applied: boolean
  admin_comment: string
  created_at: string | null
  subject_slug: string
  facts: { label: string; value: string }[]
}
interface ProcessChoice { code: string; name: string }
interface ParserChoice { code: string; title: string; summary: string }
interface ModelStat { name: string; offers: number; processes: string[]; objects: string[] }
interface VendorStats {
  cards: number
  processes: number
  objects: number
  offers: number
  process_names: string[]
  object_names: string[]
  models: ModelStat[]
}
interface DraftRobot { name: string; summary: string; price_rub: number | null; processes: string[]; attrs: { key: string; label: string; value: unknown }[] }

const route = useRoute()
const tab = ref(typeof route.query.tab === 'string' ? route.query.tab : 'profile')
watch(() => route.query.tab, (value) => { if (typeof value === 'string') tab.value = value })

const profile = ref<Profile | null>(null)
const products = ref<Robot[]>([])
const requests = ref<RequestRow[]>([])
const stats = ref<VendorStats | null>(null)
const processes = ref<ProcessChoice[]>([])
const parsers = ref<ParserChoice[]>([])
const notice = ref('')
const error = ref('')
const busy = ref(false)

const form = reactive({
  company_name: '',
  about: '',
  website: '',
  email: '',
  phone: '',
  city: '',
  logo: '',
  documents: [] as { kind: string; title: string; filename: string; note: string }[],
})
const docKind = ref('card')
const docTitle = ref('')
const selectedSlug = ref('')
const editName = ref('')
const editSummary = ref('')
const editPrice = ref('')
const editProcesses = ref<string[]>([])
const editAttrs = ref<{ key: string; label: string; value: string }[]>([])
const fresh = reactive({ name: '', summary: '', price: '', processes: [] as string[], attrs: [] as { label: string; value: string }[] })
const importUrl = ref('')
const parserCode = ref('')
const preview = ref<DraftRobot[]>([])
/* Одна открытая карточка. Остальные остаются короткими, пока с ними не начали работать. */
const openRequest = ref('')
/* Один способ за раз. Четыре формы сразу человек не разбирает. */
const robotView = ref<'add' | 'edit'>('edit')
const addMode = ref<'one' | 'file' | 'site'>('one')
const openRobot = ref('')
const modeReady = ref(false)

const statusLabel: Record<string, string> = {
  pending: 'На проверке',
  approved: 'Принято',
  rejected: 'Отклонено',
  revision: 'Нужна доработка',
  withdraw_pending: 'Отзыв на проверке',
  withdrawn: 'Отозвана',
}
const docKinds = [
  { id: 'card', label: 'Карточка предприятия' },
  { id: 'permit', label: 'Разрешительный документ' },
  { id: 'certificate', label: 'Сертификат' },
  { id: 'other', label: 'Другой документ' },
]
const attention = computed(() => requests.value.filter((item) => item.status === 'pending' || item.status === 'revision' || item.status === 'withdraw_pending'))
const tabs = computed(() => [
  { id: 'profile', label: 'Компания' },
  { id: 'robots', label: 'Роботы', count: products.value.length },
  { id: 'stats', label: 'Статистика' },
  { id: 'requests', label: 'Заявки', count: attention.value.length },
])
const parserPlain: Record<string, string> = {
  robob2b: 'Сайт robob2b.ru. Возьмём только карточки вашей компании.',
  robort: 'Сайт robort.ru. Возьмём только карточки вашей компании.',
  robot_moscow: 'Сайт robot.moscow. Возьмём только карточки вашей компании.',
}
const requestGroups = computed(() => {
  const order = [
    { id: 'revision', title: 'Нужно исправить', statuses: ['revision'] },
    { id: 'pending', title: 'Ждут ответа', statuses: ['pending', 'withdraw_pending'] },
    { id: 'done', title: 'Уже решено', statuses: ['approved', 'rejected', 'withdrawn'] },
  ]
  return order
    .map((group) => ({ ...group, items: requests.value.filter((item) => group.statuses.includes(item.status)) }))
    .filter((group) => group.items.length)
})
const statusHint: Record<string, string> = {
  pending: 'Администратор ещё не ответил. В каталоге пока прежние данные.',
  approved: 'Администратор принял заявку. В каталог она попадёт, когда он нажмёт «Внести в каталог».',
  rejected: 'В каталог это не попало.',
  revision: 'Поправьте по комментарию и отправьте ещё раз.',
  withdraw_pending: 'Просьба отозвать ушла администратору. Пока он не подтвердит, заявка ещё жива.',
  withdrawn: 'Заявку отозвали. В каталог она не попала.',
}
const hintFor = (item: RequestRow) => {
  if (item.status === 'approved' && item.catalog_applied) return 'Изменение уже видно в каталоге.'
  if (item.status === 'approved') return 'Администратор принял заявку. В каталог она попадёт, когда он нажмёт «Внести в каталог».'
  return statusHint[item.status] || ''
}
const robotsWord = (count: number) => {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return 'робот'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'робота'
  return 'роботов'
}
/* «2 раза», «5 раз», «21 раз». Человеку так понятнее, чем голое число. */
const timesWord = (count: number) => {
  const mod10 = count % 10
  const mod100 = count % 100
  const word = mod10 === 1 && mod100 !== 11 ? 'раз' : mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14) ? 'раза' : 'раз'
  return `${count} ${word}`
}
const asList = (items: string[], empty: string) => items.length ? items.join(', ') : empty
const when = (iso: string | null) => iso
  ? new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' })
  : ''

const fillProfile = (row: Profile) => {
  form.company_name = row.company_name
  form.about = row.about
  form.website = row.website
  form.email = row.email
  form.phone = row.phone
  form.city = row.city
  form.logo = ''
  form.documents = row.documents.map((item) => ({
    kind: item.kind,
    title: item.title,
    filename: item.filename || '',
    note: item.note || '',
  }))
}

const load = async () => {
  const [me, robots, queue, processPage, parserPage, summary] = await Promise.all([
    platformGet<{ profile: Profile }>('/vendor/me'),
    platformGet<Robot[]>('/vendor/products'),
    platformGet<RequestRow[]>('/vendor/requests'),
    platformGet<ProcessChoice[]>('/vendor/processes'),
    platformGet<ParserChoice[]>('/vendor/parsers'),
    platformGet<VendorStats>('/vendor/stats'),
  ])
  profile.value = me.profile
  fillProfile(me.profile)
  products.value = robots
  requests.value = queue
  processes.value = processPage
  parsers.value = parserPage
  stats.value = summary
  if (!parserCode.value && parserPage[0]) parserCode.value = parserPage[0].code
  if (!selectedSlug.value && robots[0]) pickRobot(robots[0].slug)
  if (!modeReady.value) {
    robotView.value = robots.length ? 'edit' : 'add'
    modeReady.value = true
  }
}

const pickRobot = (slug: string) => {
  selectedSlug.value = slug
  const robot = products.value.find((item) => item.slug === slug)
  if (!robot) return
  editName.value = robot.name
  editSummary.value = robot.summary || ''
  editPrice.value = robot.price_rub == null ? '' : String(robot.price_rub)
  editProcesses.value = [...robot.processes]
  editAttrs.value = robot.attrs.map((item) => ({ key: item.key, label: item.label, value: item.value == null ? '' : String(item.value) }))
}

/* Карточка робота раскрывается отдельно, чтобы не держать все формы сразу. */
const showRobot = (slug: string) => {
  if (openRobot.value === slug) {
    openRobot.value = ''
    return
  }
  openRobot.value = slug
  pickRobot(slug)
}

const money = (value: number | null) => value == null ? 'Цена не указана' : `${Math.round(value).toLocaleString('ru-RU')} руб.`

const run = async (action: () => Promise<string | void>, ok: string) => {
  error.value = ''
  notice.value = ''
  busy.value = true
  try {
    const extra = await action()
    notice.value = extra || ok
    await load()
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Не получилось отправить')
  } finally {
    busy.value = false
  }
}

const upload = async (file: File, kind: 'logo' | 'doc') => {
  const body = new FormData()
  body.append('file', file)
  body.append('kind', kind)
  return await $fetch<{ filename: string }>(`${usePlatformBase()}/vendor/files`, { method: 'POST', body, credentials: 'include' })
}

const onLogo = async (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  error.value = ''
  notice.value = ''
  busy.value = true
  try {
    const saved = await upload(file, 'logo')
    form.logo = saved.filename
    notice.value = 'Логотип прикреплён. Нажмите «Отправить на проверку», чтобы его увидел администратор.'
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Логотип не загрузился')
  } finally {
    busy.value = false
  }
}

const onDoc = async (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  error.value = ''
  notice.value = ''
  busy.value = true
  try {
    const saved = await upload(file, 'doc')
    form.documents.push({
      kind: docKind.value,
      title: docTitle.value.trim() || file.name,
      filename: saved.filename,
      note: '',
    })
    docTitle.value = ''
    notice.value = 'Документ прикреплён. Отправьте карточку на проверку, чтобы его увидел администратор.'
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Документ не загрузился')
  } finally {
    busy.value = false
  }
}

const sendProfile = () => run(async () => {
  await platformSend('/vendor/requests', 'POST', {
    kind: 'profile',
    payload: { ...form, documents: form.documents },
  })
}, 'Карточка компании отправлена. Пока её не подтвердят, заказчик видит прежнюю. Статус во вкладке «Заявки».')

const sendUpdate = () => run(async () => {
  await platformSend('/vendor/requests', 'POST', {
    kind: 'product_update',
    payload: {
      slug: selectedSlug.value,
      name: editName.value,
      summary: editSummary.value,
      price_rub: editPrice.value === '' ? null : Number(editPrice.value.replace(',', '.')),
      processes: editProcesses.value,
      attrs: editAttrs.value.filter((item) => item.value !== '').map((item) => ({ key: item.key, label: item.label, value: item.value })),
    },
  })
}, 'Правка отправлена. В каталоге пока старые цифры. Статус во вкладке «Заявки».')

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
  error.value = ''
  notice.value = ''
  busy.value = true
  try {
    const body = new FormData()
    body.append('file', file)
    const page = await $fetch<{ robots: DraftRobot[] }>(`${usePlatformBase()}/vendor/preview-file`, { method: 'POST', body, credentials: 'include' })
    preview.value = page.robots
    notice.value = `В файле ${page.robots.length} ${robotsWord(page.robots.length)}. Проверьте названия и отправьте список.`
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Файл не разобрался')
  } finally {
    busy.value = false
  }
}

const readUrl = () => run(async () => {
  const page = await platformSend<{ robots: DraftRobot[] }>('/vendor/preview-url', 'POST', { url: importUrl.value })
  preview.value = page.robots
  return `По ссылке нашлось ${page.robots.length} ${robotsWord(page.robots.length)}. Если это ваши модели, отправьте список.`
}, '')

// Отзыв не стирает строку сразу: сначала её смотрит администратор.
const withdrawRequest = (id: string) => run(async () => {
  await platformSend(`/vendor/requests/${id}/withdraw`, 'POST')
}, 'Просьба отозвать отправлена. Пока администратор её не подтвердит, заявка остаётся.')

const hideRequest = (id: string) => run(async () => {
  await platformSend(`/vendor/requests/${id}/hide`, 'POST')
}, 'Заявка убрана из вашего списка. В каталоге из-за этого ничего не меняется.')

const fixRobot = (slug: string) => {
  tab.value = 'robots'
  robotView.value = 'edit'
  if (slug) showRobot(slug)
}

const sendParse = () => run(async () => {
  await platformSend('/vendor/requests', 'POST', { kind: 'parse', payload: { parser: parserCode.value } })
}, 'Заявка отправлена. После подтверждения в каталог попадут только роботы вашей компании.')

onMounted(() => { void load().catch((err) => { error.value = fetchErrorMessage(err, 'Кабинет не открылся') }) })
/* После подбора в другом окне цифры обновляются, когда человек снова открывает вкладку. */
watch(tab, (value) => {
  if (value !== 'stats') return
  platformGet<VendorStats>('/vendor/stats').then((summary) => { stats.value = summary }).catch(() => {})
})
</script>

<template>
  <section class="container vendor">
    <div class="head">
      <div>
        <div class="label">Кабинет производителя</div>
        <h1 class="hero-2">{{ profile?.company_name || 'Компания' }}</h1>
        <p class="body muted">Сначала карточка компании, потом роботы. Заказчик увидит изменения только после проверки.</p>
      </div>
    </div>

    <UiTabs :tabs="tabs" :model-value="tab" @update:model-value="tab = $event" />
    <UiCallout v-if="requests.some((item) => item.status === 'revision')" tone="warn">
      Необходимо внести правки в заявке. Комментарий лежит во вкладке «Заявки».
      <button type="button" class="jump" @click="tab = 'requests'">Открыть заявки</button>
    </UiCallout>
    <UiCallout v-if="error" tone="danger">{{ error }}</UiCallout>
    <UiCallout v-else-if="notice" tone="ok">
      {{ notice }}
      <button type="button" class="jump" @click="tab = 'requests'">Смотреть статус</button>
    </UiCallout>

    <form v-if="tab === 'profile' && profile" class="glass glass-xl panel" @submit.prevent="sendProfile">
      <div class="panel-in">
        <div class="h3">Как вас увидит заказчик</div>
        <p class="body-sm muted">В каталоге роботы подписаны так: {{ profile.manufacturer }}. Это название не меняется, иначе уже загруженные модели оторвутся от компании.</p>
        <div class="grid-2">
          <label class="field field-line"><span class="field-label">Название компании</span><input v-model="form.company_name" class="input" required></label>
          <label class="field field-line"><span class="field-label">Город</span><input v-model="form.city" class="input"></label>
          <label class="field field-line"><span class="field-label">Сайт</span><input v-model="form.website" class="input" placeholder="https://"></label>
          <label class="field field-line"><span class="field-label">Почта</span><input v-model="form.email" class="input" type="email"></label>
          <label class="field field-line"><span class="field-label">Телефон</span><input v-model="form.phone" class="input"></label>
          <label class="field field-line">
            <span class="field-label">Логотип</span>
            <span>
              <input class="input" type="file" accept="image/png,image/jpeg,image/webp" @change="onLogo">
              <span class="field-hint">{{ form.logo ? 'Новая картинка прикреплена' : (profile.logo_url ? 'Логотип уже есть, можно заменить' : 'Картинка до 2 МБ') }}</span>
            </span>
          </label>
        </div>
        <label class="field field-line"><span class="field-label">О компании</span><textarea v-model="form.about" class="textarea" rows="3" placeholder="Чем занимаетесь и каких роботов выпускаете" /></label>

        <div class="h4">Документы</div>
        <p class="body-sm muted">Карточка предприятия, разрешение или сертификат. Их видит администратор, когда проверяет заявку.</p>
        <ul v-if="form.documents.length" class="docs">
          <li v-for="(doc, index) in form.documents" :key="doc.filename || doc.title">
            <span>{{ docKinds.find((item) => item.id === doc.kind)?.label }}: {{ doc.title }}</span>
            <button type="button" class="text-btn" @click="form.documents.splice(index, 1)">Убрать</button>
          </li>
        </ul>
        <div class="grid-2">
          <label class="field field-line">
            <span class="field-label">Тип документа</span>
            <select v-model="docKind" class="select">
              <option v-for="item in docKinds" :key="item.id" :value="item.id">{{ item.label }}</option>
            </select>
          </label>
          <label class="field field-line"><span class="field-label">Название</span><input v-model="docTitle" class="input" placeholder="Например, декларация соответствия"></label>
        </div>
        <label class="field field-line"><span class="field-label">Файл</span><input class="input" type="file" accept="application/pdf,image/png,image/jpeg,image/webp" @change="onDoc"></label>
        <UiButton type="submit" size="lg" :disabled="busy">Отправить на проверку</UiButton>
      </div>
    </form>

    <div v-else-if="tab === 'robots'" class="stack">
      <div class="mode-row">
        <button type="button" class="mode" :class="{ on: robotView === 'add' }" @click="robotView = 'add'">Добавить</button>
        <button type="button" class="mode" :class="{ on: robotView === 'edit' }" @click="robotView = 'edit'">Изменить</button>
      </div>

      <template v-if="robotView === 'add'">
        <div class="mode-row sub">
          <button type="button" class="mode" :class="{ on: addMode === 'one' }" @click="addMode = 'one'">Один робот</button>
          <button type="button" class="mode" :class="{ on: addMode === 'file' }" @click="addMode = 'file'">Списком</button>
          <button type="button" class="mode" :class="{ on: addMode === 'site' }" @click="addMode = 'site'">С сайта</button>
        </div>

        <section v-if="addMode === 'one'" class="glass glass-xl panel">
        <div class="panel-in">
          <div class="h3">Новый робот</div>
          <p class="body-sm muted">Одна модель. Если их много, удобнее пункт «Списком».</p>
          <div class="grid-2">
            <label class="field field-line"><span class="field-label">Название</span><input v-model="fresh.name" class="input" placeholder="Как модель называется у вас"></label>
            <label class="field field-line"><span class="field-label">Цена, руб.</span><input v-model="fresh.price" class="input" inputmode="decimal" placeholder="Если цены нет, оставьте пустым"></label>
          </div>
          <label class="field field-line"><span class="field-label">Коротко</span><textarea v-model="fresh.summary" class="textarea" rows="3" placeholder="Одним предложением, что робот делает" /></label>
          <div class="field">
            <span class="field-label">Что умеет</span>
            <ProcessPicker v-model="fresh.processes" :processes="processes" />
          </div>
          <div class="attrs">
            <div v-for="(item, index) in fresh.attrs" :key="index" class="grid-2">
              <label class="field field-line"><span class="field-label">Характеристика</span><input v-model="item.label" class="input" placeholder="Грузоподъёмность"></label>
              <label class="field field-line"><span class="field-label">Значение</span><input v-model="item.value" class="input" placeholder="1500 кг"></label>
            </div>
          </div>
          <div class="row">
            <UiButton variant="secondary" @click="fresh.attrs.push({ label: '', value: '' })">Добавить характеристику</UiButton>
            <UiButton :disabled="busy || !fresh.name.trim()" @click="sendFresh">Отправить на проверку</UiButton>
          </div>
        </div>
      </section>

      <section v-else-if="addMode === 'file'" class="glass glass-xl panel">
        <div class="panel-in">
          <div class="h3">Несколько роботов сразу</div>
          <p class="body-sm muted">Таблица CSV или файл JSON. В первой строке таблицы: название, описание, цена, процессы. Процессы пишите как здесь, через запятую: Перевозка паллет, Уборка помещений. Остальные колонки станут характеристиками. Чужие компании в файл класть не нужно.</p>
          <label class="field field-line"><span class="field-label">Файл</span><input class="input" type="file" accept=".json,.csv,application/json,text/csv" @change="readFile"></label>
          <label class="field field-line">
            <span class="field-label">Или ссылка</span>
            <span>
              <span class="field-hint">Адрес файла со списком на вашем сайте. Тот же состав, что у таблицы.</span>
              <span class="row">
                <input v-model="importUrl" class="input" placeholder="https://ваша-компания.ru/robots.json">
                <UiButton variant="secondary" :disabled="busy || !importUrl" @click="readUrl">Прочитать</UiButton>
              </span>
            </span>
          </label>
          <div v-if="preview.length" class="preview">
            <div class="body-sm strong">К отправке: {{ preview.length }}</div>
            <ul class="names">
              <li v-for="(item, index) in preview.slice(0, 8)" :key="`${item.name}-${index}`">{{ item.name }}</li>
            </ul>
            <p v-if="preview.length > 8" class="caption">И ещё {{ preview.length - 8 }}</p>
            <UiButton :disabled="busy" @click="sendBatch(preview, importUrl ? 'api' : 'file')">Отправить список</UiButton>
          </div>
        </div>
      </section>

      <section v-else class="glass glass-xl panel">
        <div class="panel-in">
          <div class="h3">Найти модели на открытом сайте</div>
          <p class="body-sm muted">Платформа посмотрит выбранный каталог и оставит только роботов вашей компании. Поиск начнётся после подтверждения заявки.</p>
          <label class="field field-line">
            <span class="field-label">Сайт</span>
            <span>
              <select v-model="parserCode" class="select">
                <option v-for="item in parsers" :key="item.code" :value="item.code">{{ item.title }}</option>
              </select>
              <span class="field-hint">{{ parserPlain[parserCode] || parsers.find((item) => item.code === parserCode)?.summary }}</span>
            </span>
          </label>
          <UiButton :disabled="busy || !parserCode" @click="sendParse">Отправить на проверку</UiButton>
        </div>
      </section>
      </template>

      <section v-else class="stack">
        <p class="body-sm muted">Нажмите модель. Внутри можно поменять название, цену и характеристики. Заказчик увидит новое только после проверки.</p>
        <p v-if="!products.length" class="body-sm muted">Своих роботов пока нет. Нажмите «Добавить».</p>
        <div v-else class="cards">
          <article v-for="robot in products" :key="robot.slug" class="glass card" :class="{ open: openRobot === robot.slug }">
            <button type="button" class="card-hit" :aria-expanded="openRobot === robot.slug" @click="showRobot(robot.slug)">
              <span class="card-title">{{ robot.name }}</span>
              <span class="caption">{{ money(robot.price_rub) }}</span>
              <span v-if="robot.summary" class="card-sum">{{ robot.summary }}</span>
            </button>
            <div v-if="openRobot === robot.slug" class="card-body">
              <div class="grid-2">
                <label class="field field-line"><span class="field-label">Название</span><input v-model="editName" class="input"></label>
                <label class="field field-line"><span class="field-label">Цена, руб.</span><input v-model="editPrice" class="input" inputmode="decimal"></label>
              </div>
              <label class="field field-line"><span class="field-label">Коротко</span><textarea v-model="editSummary" class="textarea" rows="3" placeholder="Например, возит паллеты по складу" /></label>
              <div class="field">
                <span class="field-label">Что умеет</span>
                <ProcessPicker v-model="editProcesses" :processes="processes" />
              </div>
              <div v-if="editAttrs.length" class="attrs">
                <label v-for="item in editAttrs" :key="item.key" class="field field-line">
                  <span class="field-label">{{ item.label }}</span>
                  <input v-model="item.value" class="input">
                </label>
              </div>
              <UiButton :disabled="busy" @click="sendUpdate">Отправить на проверку</UiButton>
            </div>
          </article>
        </div>
      </section>
    </div>

    <section v-else-if="tab === 'stats'" class="stack">
      <div>
        <div class="h3">Как ваши роботы попадают в подбор</div>
        <p class="body-sm muted">Здесь только общие цифры. Имён заказчиков и адресов площадок нет.</p>
      </div>
      <div v-if="stats" class="stats glass glass-xl">
        <UiStat label="Карточек в каталоге" :value="String(stats.cards)" note="Столько ваших моделей уже видит заказчик" />
        <UiStat label="Процессов" :value="String(stats.processes)" :note="asList(stats.process_names, 'К роботам ещё не привязаны работы, поэтому в подбор они не попадают')" />
        <UiStat label="Объектов в подборе" :value="String(stats.objects)" :note="asList(stats.object_names, 'Эти процессы пока не стоят ни на одном типе площадки')" />
        <UiStat label="Показов в подборе" :value="String(stats.offers)" note="Сколько раз модель попала в «Подходит», «С условием» или «Уточнить». «Не подходит» сюда не входит." />
      </div>
      <p v-else class="body-sm muted">Считаем сводку.</p>
      <div class="h4">По моделям</div>
      <p v-if="stats && !stats.models.length" class="body-sm muted">Своих карточек в каталоге пока нет. Добавьте робота, и здесь появится его строка.</p>
      <div v-else class="cards">
        <article v-for="model in stats?.models || []" :key="model.name" class="glass card">
          <div class="card-title">{{ model.name }}</div>
          <p class="model-line">Показали в подборе: {{ timesWord(model.offers) }}</p>
          <p class="model-line">Процессы: {{ asList(model.processes, 'не отмечены, в подбор модель не попадает') }}</p>
          <p class="model-line">Объекты: {{ asList(model.objects, 'пока ни один тип площадки') }}</p>
        </article>
      </div>
    </section>

    <section v-else class="requests">
      <div class="h3">Заявки</div>
      <p v-if="!requests.length" class="body-sm muted">Пока пусто. Измените компанию или робота, и здесь появится ответ администратора.</p>
      <template v-for="group in requestGroups" :key="group.id">
        <div class="h4">{{ group.title }}</div>
        <div class="cards">
          <article v-for="item in group.items" :key="item.id" class="glass card" :class="{ open: openRequest === item.id }">
            <button type="button" class="card-hit" :aria-expanded="openRequest === item.id" @click="openRequest = openRequest === item.id ? '' : item.id">
              <span class="between">
                <span class="card-title">{{ item.title }}</span>
                <UiBadge :tone="item.status === 'approved' ? 'ok' : item.status === 'rejected' ? 'danger' : item.status === 'revision' ? 'warn' : 'info'">{{ statusLabel[item.status] || item.status }}</UiBadge>
              </span>
              <span v-if="item.summary" class="card-sum">{{ item.summary }}</span>
              <span class="caption">{{ hintFor(item) }}</span>
              <span class="caption">{{ when(item.created_at) }}</span>
            </button>
            <div v-if="openRequest === item.id" class="card-body">
              <VendorRequestFacts :facts="item.facts || []" />
              <p class="caption">{{ hintFor(item) }}</p>
              <p v-if="item.admin_comment" class="note">Комментарий: {{ item.admin_comment }}</p>
              <div class="row">
                <UiButton v-if="item.status === 'revision' && item.subject_slug" size="sm" variant="secondary" @click="fixRobot(item.subject_slug)">Исправить эту модель</UiButton>
                <UiButton v-if="item.status === 'pending' || item.status === 'revision'" size="sm" variant="ghost" :disabled="busy" @click="withdrawRequest(item.id)">Отозвать</UiButton>
                <UiButton v-if="item.status === 'approved' || item.status === 'rejected' || item.status === 'withdrawn'" size="sm" variant="ghost" :disabled="busy" @click="hideRequest(item.id)">Удалить из списка</UiButton>
              </div>
            </div>
          </article>
        </div>
      </template>
    </section>
  </section>
</template>

<style scoped>
.vendor { display: grid; gap: var(--space-5); padding-top: var(--space-8); padding-bottom: var(--space-16); }
.head { display: grid; gap: 8px; }
.panel-in, .stack { display: grid; gap: var(--space-4); }
.panel-in > * { position: relative; z-index: 1; }
.panel { padding: var(--space-6); }
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-4); }
.row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.row .input { flex: 1; min-width: 220px; }
.attrs { display: grid; gap: 10px; }
.docs { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.docs li { display: flex; justify-content: space-between; gap: 12px; }
.text-btn { color: var(--state-danger); font-weight: 700; }
.request { display: grid; gap: 6px; padding-top: 14px; border-top: 1px solid var(--border-hairline); }
.requests { display: grid; gap: var(--space-4); min-width: 0; }
.mode-row { display: flex; flex-wrap: wrap; gap: 8px; }
.mode { min-height: 40px; padding: 8px 16px; border-radius: 12px; font-weight: 700; color: var(--ink-body); background: rgba(15, 20, 19, 0.05); }
.mode.on { background: var(--surface-graphite); color: var(--ink-on-graphite); }
.mode-row.sub .mode { font-weight: 600; background: transparent; box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.12); }
.mode-row.sub .mode.on { background: rgba(15, 20, 19, 0.06); color: var(--ink-strong); }
.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.card { min-width: 0; padding: 12px 14px; display: grid; gap: 10px; align-content: start; overflow: hidden; }
.card.open { grid-column: 1 / -1; }
.card-hit { display: grid; gap: 6px; width: 100%; min-width: 0; text-align: left; }
.card-title { min-width: 0; font-size: 16px; font-weight: 700; line-height: 1.35; overflow-wrap: anywhere; }
.card-sum { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; color: var(--ink-muted); font-size: 13px; line-height: 1.4; overflow-wrap: anywhere; }
.card-body { display: grid; gap: 10px; min-width: 0; }
.between { min-width: 0; flex-wrap: wrap; align-items: flex-start; }
.between .card-title { flex: 1; }
.preview { display: grid; gap: 8px; }
.names { margin: 0; padding-left: 18px; display: grid; gap: 4px; }
.jump { margin-left: 8px; font-weight: 700; text-decoration: underline; text-underline-offset: 3px; }
.stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; padding: 20px 22px; }
.model-line { margin: 0; color: var(--ink-body); font-size: 14px; line-height: 1.45; overflow-wrap: anywhere; }
.specs { display: grid; gap: 10px; }
.specs summary { font-weight: 700; color: var(--ink-strong); cursor: pointer; }
.note { margin: 0; padding: 8px 12px; border-radius: 10px; background: var(--state-warn-tint); color: var(--state-warn); font-weight: 600; }
@media (max-width: 900px) {
  .stats { grid-template-columns: 1fr 1fr; }
}
@media (max-width: 800px) {
  .grid-2 { grid-template-columns: 1fr; }
  .stats { grid-template-columns: 1fr; }
}
</style>
