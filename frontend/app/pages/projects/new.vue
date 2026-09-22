<script setup lang="ts">
import { PhCheck, PhArrowRight, PhSparkle } from '@phosphor-icons/vue'
import { objectTypeLabel, objectTypeImage, type ObjectType, projects } from '~/data/projects'
import { fetchErrorMessage } from '~/composables/useCalc'

useHead({ title: 'Новый проект' })
const route = useRoute()
const router = useRouter()
const { create, refresh } = useProjects()

const industries = [
  { code: 'logistics', label: 'Логистика и торговля', objects: ['warehouse'] as ObjectType[] },
  { code: 'transport', label: 'Транспорт', objects: ['airport'] as ObjectType[] },
  { code: 'health', label: 'Здравоохранение', objects: ['hospital'] as ObjectType[] },
]
const objectMeta: Record<ObjectType, { text: string; full: boolean }> = {
  warehouse: { text: 'Параметры, подбор, три сценария, экономика, what-if, симуляция смены, 2D-план, отчёт.', full: true },
  airport: { text: 'Параметры площадки и список применимых решений. Экономика и план в MVP закрыты.', full: false },
  hospital: { text: 'Параметры корпуса и список применимых решений. Экономика и план в MVP закрыты.', full: false },
}

const type = ref<ObjectType>((route.query.type as ObjectType) || 'warehouse')
const industry = computed(() => industries.find((i) => i.objects.includes(type.value))!)
const name = ref('')
const useDemo = ref(false)
const demoFor = computed(() => projects.find((p) => p.isDemo && p.objectType === type.value)!)

const pickIndustry = (i: typeof industries[number]) => { type.value = i.objects[0]! }
const applyDemo = () => { useDemo.value = true; name.value = demoFor.value.name }
const creating = ref(false)
const createError = ref('')
const submit = async () => {
  if (creating.value) return
  creating.value = true
  createError.value = ''
  try {
    const project = await create({
      name: name.value.trim() || demoFor.value.name,
      object_type_code: type.value,
      industry_code: industry.value.code,
      use_demo: true,
    })
    await refresh()
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
      <p class="body-lg muted">Три поля: имя, отрасль и тип объекта. Параметры площадки и задачи собираются на следующем шаге.</p>
    </div>

    <UiCallout v-if="createError" tone="danger" title="Проект не создан">{{ createError }}</UiCallout>

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
          <div class="opts">
            <button v-for="i in industries" :key="i.code" type="button" class="opt" :class="{ on: industry.code === i.code }" @click="pickIndustry(i)">
              <span class="chk"><PhCheck v-if="industry.code === i.code" :size="12" weight="bold" /></span>{{ i.label }}
            </button>
          </div>
          <div class="caption">Новая отрасль появляется из справочника, не из кода экранов.</div>
        </div>

        <div class="step glass">
          <div class="step-head"><span class="n mono-sm">3</span><span class="h3">Тип объекта</span></div>
          <div class="types">
            <button v-for="t in (Object.keys(objectTypeLabel) as ObjectType[])" :key="t" type="button" class="type" :class="{ on: type === t, dim: !industry.objects.includes(t) }" @click="type = t">
              <img :src="objectTypeImage[t]" alt="">
              <span class="type-body">
                <span class="between"><span class="h4">{{ objectTypeLabel[t] }}</span><UiBadge :tone="objectMeta[t].full ? 'ok' : 'info'" size="sm">{{ objectMeta[t].full ? 'Полный путь' : 'До подбора' }}</UiBadge></span>
                <span class="caption">{{ objectMeta[t].text }}</span>
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
            <div class="s-row"><span class="caption">Отрасль</span><span class="strong">{{ industry.label }}</span></div>
            <div class="s-row"><span class="caption">Объект</span><span class="strong">{{ objectTypeLabel[type] }}</span></div>
            <div class="s-row"><span class="caption">Путь</span><span class="strong">{{ objectMeta[type].full ? '7 шагов до отчёта' : '2 шага: параметры и подбор' }}</span></div>
            <div class="hairline" />
            <button type="button" class="demo-btn" :class="{ on: useDemo }" @click="applyDemo">
              <PhSparkle :size="18" weight="duotone" />
              <span><span class="strong">Подставить демо-набор</span><span class="caption block">{{ demoFor.name }}: {{ demoFor.area?.toLocaleString('ru-RU') }} м², {{ demoFor.tasks }} задачи</span></span>
              <PhCheck v-if="useDemo" :size="16" weight="bold" class="ok" />
            </button>
            <UiButton type="submit" size="lg" block :disabled="creating">{{ creating ? 'Создаём…' : 'Создать и перейти к параметрам' }}<template #after><PhArrowRight :size="18" weight="bold" /></template></UiButton>
            <div class="caption">Проект сохраняется на версии каталога v2026.09.3 и модели m1.4.</div>
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
.opt { display: inline-flex; align-items: center; gap: 10px; min-height: 44px; padding: 0 16px 0 10px; border-radius: 12px; font-weight: 600; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px var(--border-hairline); transition: all var(--dur-fast) var(--ease); }
.opt.on { background: var(--surface-graphite); color: var(--ink-on-graphite); box-shadow: none; }
.chk { width: 20px; height: 20px; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center; background: rgba(15, 20, 19, 0.06); }
.opt.on .chk { background: var(--brand-400); color: var(--brand-900); }
.types { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.type { display: grid; gap: 10px; padding: 8px; border-radius: 16px; text-align: left; background: rgba(255, 255, 255, 0.6); box-shadow: inset 0 0 0 1px var(--border-hairline); transition: all var(--dur-fast) var(--ease); }
.type:hover { background: #fff; }
.type.on { box-shadow: inset 0 0 0 2px var(--brand-500); background: #fff; }
.type.dim:not(.on) { opacity: 0.7; }
.type img { width: 100%; aspect-ratio: 16 / 9; object-fit: cover; border-radius: 12px; }
.type-body { display: grid; gap: 6px; padding: 0 6px 6px; }
.side { position: sticky; top: 96px; }
.s-in { position: relative; z-index: 1; padding: var(--space-6); display: grid; gap: var(--space-4); }
.s-row { display: grid; gap: 2px; }
.demo-btn { display: grid; grid-template-columns: auto 1fr auto; gap: 12px; align-items: center; text-align: left; padding: 12px 14px; border-radius: 14px; background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); color: var(--brand-700); transition: all var(--dur-fast) var(--ease); }
.demo-btn:hover { background: #fff; }
.demo-btn.on { background: var(--surface-brand-tint); box-shadow: inset 0 0 0 1px rgba(10, 107, 69, 0.2); }
.demo-btn .strong { display: block; }
.block { display: block; }
.ok { color: var(--brand-700); }
@media (max-width: 1100px) { .wiz { grid-template-columns: 1fr; } .side { position: static; } }
</style>
