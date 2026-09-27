<script setup lang="ts">
import { PhCheck, PhArrowRight, PhSparkle } from '@phosphor-icons/vue'
import { objectTypeImage } from '~/data/projects'
import { fetchErrorMessage } from '~/utils/errors'
import { platformGet, platformSend } from '~/composables/usePlatform'
import { asObjectType } from '~/composables/useLiveProject'
import { useDemoProjects } from '~/composables/useDemoProjects'

interface IndustryRow { code: string; name: string; objects: { code: string; name: string }[] }

useHead({ title: 'Новый проект' })
const route = useRoute()
const router = useRouter()
const { role } = useRole()
const canSave = computed(() => role.value === 'user' || role.value === 'admin')
const demos = useDemoProjects()

/* Отрасли и их объекты приходят из справочника платформы: новая отрасль появляется здесь без правки экранов. */
const industries = ref<IndustryRow[]>([])
const loadError = ref('')
const loading = ref(true)
const industryCode = ref('')
const type = ref('')
const name = ref('')

/* Полный путь до отчёта пока собран только для склада; остальные объекты идут до подбора и сравнения. */
const fullPath = (code: string) => asObjectType(code) === 'warehouse'
const objectImage = (code: string) => objectTypeImage[asObjectType(code)]
const objectText = (code: string) => fullPath(code)
  ? 'Параметры, подбор, сравнение, экономика, what-if, визуализация, отчёт.'
  : 'Параметры, подбор и сравнение. Экономика и визуализация в MVP закрыты.'

const industry = computed(() => industries.value.find((row) => row.code === industryCode.value) ?? null)
const objects = computed(() => industry.value?.objects ?? [])
const picked = computed(() => objects.value.find((row) => row.code === type.value) ?? null)
const demoFor = computed(() => (type.value ? demos.byObject(type.value) : null))

const pickIndustry = (row: IndustryRow) => {
  industryCode.value = row.code
  if (!row.objects.some((obj) => obj.code === type.value)) type.value = row.objects[0]?.code ?? ''
}

onMounted(async () => {
  try {
    const page = await platformGet<{ items: IndustryRow[] }>('/catalog/industries')
    industries.value = page.items.filter((row) => row.objects.length)
    const wanted = typeof route.query.type === 'string' ? route.query.type : ''
    const start = industries.value.find((row) => row.objects.some((obj) => obj.code === wanted)) ?? industries.value[0]
    if (start) {
      industryCode.value = start.code
      type.value = wanted && start.objects.some((obj) => obj.code === wanted) ? wanted : (start.objects[0]?.code ?? '')
    }
  } catch (e: unknown) {
    loadError.value = fetchErrorMessage(e, 'Справочник отраслей не ответил. Проверьте, что платформа запущена.')
  } finally {
    loading.value = false
  }
})

const creating = ref(false)
const createError = ref('')
const submit = async () => {
  if (creating.value || !picked.value) return
  creating.value = true
  createError.value = ''
  try {
    if (!canSave.value) {
      await router.push('/login')
      return
    }
    const project = await platformSend<{ id: string }>('/projects', 'POST', {
      name: name.value.trim() || `${picked.value.name}: новый расчёт`,
      object_code: picked.value.code,
      site: {},
    })
    await router.push(`/projects/${project.id}/params`)
  } catch (e: unknown) {
    createError.value = fetchErrorMessage(e, 'Не удалось создать проект. Проверьте, что API запущен.')
  } finally {
    creating.value = false
  }
}
</script>

<template>
  <section class="container newp">
    <div class="intro" v-reveal>
      <div class="label">Новый проект</div>
      <h1 class="hero-2">Рамка расчёта</h1>
      <p class="body-lg muted">Имя, отрасль и объект внутри отрасли. Параметры площадки заполняются на следующем шаге — вручную или из демо-объекта.</p>
    </div>

    <UiCallout v-if="createError" tone="danger" title="Проект не создан">{{ createError }}</UiCallout>
    <UiCallout v-if="loadError" tone="danger" title="Справочник не загрузился">{{ loadError }}</UiCallout>

    <form class="wiz" @submit.prevent="submit">
      <div class="col" v-reveal="1">
        <div class="step glass">
          <div class="step-head"><span class="n mono-sm">1</span><span class="h3">Имя проекта</span></div>
          <label class="field">
            <span class="field-label">Как называть расчёт</span>
            <input v-model="name" class="input" placeholder="Например, РЦ Софьино, зона B">
            <span class="field-hint">Отображается в списке проектов и в шапке отчёта</span>
          </label>
        </div>

        <div class="step glass">
          <div class="step-head"><span class="n mono-sm">2</span><span class="h3">Отрасль</span></div>
          <div v-if="loading" class="opts"><UiSkeleton h="44px" w="180px" /><UiSkeleton h="44px" w="140px" /><UiSkeleton h="44px" w="160px" /></div>
          <div v-else class="opts">
            <button v-for="row in industries" :key="row.code" type="button" class="opt" :class="{ on: industryCode === row.code }" @click="pickIndustry(row)">
              <span class="chk"><PhCheck v-if="industryCode === row.code" :size="12" weight="bold" /></span>{{ row.name }}
              <span class="cnt mono-sm">{{ row.objects.length }}</span>
            </button>
          </div>
          <div class="caption">Отрасли и объекты ведутся в справочнике платформы (Админка → Каталог → Отрасли).</div>
        </div>

        <div class="step glass">
          <div class="step-head"><span class="n mono-sm">3</span><span class="h3">Объект отрасли{{ industry ? ` «${industry.name}»` : '' }}</span></div>
          <div v-if="loading" class="types"><UiSkeleton h="220px" /><UiSkeleton h="220px" /></div>
          <p v-else-if="!objects.length" class="body-sm muted">В этой отрасли пока нет объектов: добавьте их в справочнике.</p>
          <div v-else class="types" :class="{ single: objects.length === 1 }">
            <button v-for="obj in objects" :key="obj.code" type="button" class="type" :class="{ on: type === obj.code }" @click="type = obj.code">
              <img :src="objectImage(obj.code)" alt="">
              <span class="type-body">
                <span class="between"><span class="h4">{{ obj.name }}</span><UiBadge :tone="fullPath(obj.code) ? 'ok' : 'info'" size="sm">{{ fullPath(obj.code) ? 'Полный путь' : 'До подбора' }}</UiBadge></span>
                <span class="caption">{{ objectText(obj.code) }}</span>
              </span>
            </button>
          </div>
        </div>
      </div>

      <aside class="side" v-reveal="2">
        <div class="summary glass glass-strong glass-xl">
          <div class="s-in">
            <div class="label">Итог</div>
            <div class="s-row"><span class="caption">Имя</span><span class="strong">{{ name || 'Без названия' }}</span></div>
            <div class="s-row"><span class="caption">Отрасль</span><span class="strong">{{ industry?.name ?? '—' }}</span></div>
            <div class="s-row"><span class="caption">Объект</span><span class="strong">{{ picked?.name ?? '—' }}</span></div>
            <div class="s-row"><span class="caption">Путь</span><span class="strong">{{ picked ? (fullPath(picked.code) ? '7 шагов до отчёта' : '3 шага: параметры, подбор и сравнение') : '—' }}</span></div>
            <div class="hairline" />
            <div class="demo-note">
              <PhSparkle :size="18" weight="duotone" />
              <span>
                <span class="strong block">Демо-данные — на шаге параметров</span>
                <span class="caption block">{{ demoFor ? `Кнопка «Подставить демо-данные» возьмёт параметры из «${demoFor.name}».` : 'Кнопка «Подставить демо-данные» заполнит форму значениями по умолчанию.' }}</span>
              </span>
            </div>
            <UiButton v-if="canSave" type="submit" size="lg" block :disabled="creating || !picked">{{ creating ? 'Создаём…' : 'Создать и перейти к параметрам' }}<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
            <UiButton v-else to="/login" size="lg" block>Войти, чтобы создать проект<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
            <div class="caption">Проект сохраняется на текущей версии каталога и модели платформы.</div>
          </div>
        </div>
      </aside>
    </form>
  </section>
</template>

<style scoped>
.newp { padding-top: var(--space-12); padding-bottom: var(--space-16); display: grid; gap: var(--space-8); }
.intro { display: grid; gap: 10px; max-width: 64ch; }
.wiz { display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: var(--space-6); align-items: start; }
.col { display: grid; gap: var(--space-4); }
.step { padding: var(--space-6); display: grid; gap: var(--space-4); }
.step > * { position: relative; z-index: 1; }
.step-head { display: flex; align-items: center; gap: 12px; }
.n { width: 28px; height: 28px; border-radius: 8px; background: var(--surface-graphite); color: var(--brand-300); display: inline-flex; align-items: center; justify-content: center; }
.opts { display: flex; gap: 8px; flex-wrap: wrap; }
.opt { display: inline-flex; align-items: center; gap: 10px; min-height: 44px; padding: 0 12px 0 10px; border-radius: 12px; font-weight: 600; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px var(--border-hairline); transition: all var(--dur-fast) var(--ease); }
.opt.on { background: var(--surface-graphite); color: var(--ink-on-graphite); box-shadow: none; }
.chk { width: 20px; height: 20px; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center; background: rgba(15, 20, 19, 0.06); }
.opt.on .chk { background: var(--brand-400); color: var(--brand-900); }
.cnt { padding: 2px 7px; border-radius: 999px; background: rgba(15, 20, 19, 0.06); color: var(--ink-muted); }
.opt.on .cnt { background: rgba(255, 255, 255, 0.12); color: var(--ink-on-graphite); }
.types { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; }
.types.single { grid-template-columns: minmax(0, 420px); }
.type { display: grid; gap: 10px; padding: 8px; border-radius: 16px; text-align: left; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px var(--border-hairline); transition: all var(--dur-fast) var(--ease); }
.type:hover { background: #fff; }
.type.on { box-shadow: inset 0 0 0 2px var(--brand-500); background: #fff; }
.type img { width: 100%; aspect-ratio: 16 / 9; object-fit: cover; border-radius: 12px; }
.type-body { display: grid; gap: 6px; padding: 0 6px 6px; }
.side { position: sticky; top: 96px; }
.s-in { position: relative; z-index: 1; padding: var(--space-6); display: grid; gap: var(--space-4); }
.s-row { display: grid; gap: 2px; }
.demo-note { display: grid; grid-template-columns: auto 1fr; gap: 12px; align-items: start; padding: 12px 14px; border-radius: 14px; background: var(--surface-brand-tint); color: var(--brand-700); }
.block { display: block; }
@media (max-width: 1100px) { .wiz { grid-template-columns: 1fr; } .side { position: static; } .types { grid-template-columns: 1fr; } }
</style>
