<script setup lang="ts">
import { PhScales, PhCheck, PhDownloadSimple, PhMapPin, PhArrowLeft, PhWarning } from '@phosphor-icons/vue'
import { attrGroups, availabilityLabel, availabilityTone, formatRub, sourceKindLabel, confidenceByKind, type AttrGroup, type AttrValue } from '~/data/catalog'

const route = useRoute()
const { product, sources, attributeDefs, pending } = useProduct(() => route.params.slug as string)
if (!pending.value && !product.value) throw createError({ statusCode: 404, statusMessage: 'Продукт не найден' })
useHead({ title: () => `${product.value?.name ?? 'Решение'} · Каталог` })

const { has, toggle } = useCompare()
const inCompare = computed(() => (product.value ? has(product.value.id) : false))

// Идентификация лежит в колонках product, а не в attrs: источник у неё тот же, что у региона
const catalogSourceId = computed(() => product.value?.attrs.find((a) => a.key === 'region')?.sourceId)
const idAttrs = computed<AttrValue[]>(() => {
  const p = product.value
  if (!p) return []
  const src = catalogSourceId.value
  const row = (key: string, label: string, value: string | number): AttrValue =>
    ({ group: 'identification', key, label, value, status: 'known', sourceId: src })
  return [
    row('name', 'Название', p.name),
    row('manufacturer', 'Производитель', p.manufacturer),
    row('legal', 'Юрлицо', p.legalEntity),
    row('country', 'Страна происхождения', p.country),
    row('status', 'Статус', availabilityLabel[p.availability]),
    row('trl', 'Уровень готовности технологии', `УГТ ${p.trl}`),
    row('mp', 'Рыночный потенциал', p.marketPotential ? `${p.marketPotential} из 5` : 'нет данных'),
  ]
})

/**
 * Таблица группы строится по справочнику характеристик, а не по тому, что уже заполнено:
 * пустая строка «нет данных» — это и есть запрос вендору, её не должно не быть видно.
 */
const byGroup = (code: AttrGroup): AttrValue[] => {
  if (code === 'identification') return idAttrs.value
  const p = product.value
  if (!p) return []
  return attributeDefs.value
    .filter((d) => d.group_code === code && (!d.required_for || d.required_for.includes(p.solutionTypeCode)))
    .map((d) => p.attrs.find((a) => a.key === d.key) ?? {
      group: code,
      key: d.key,
      label: d.unit ? `${d.label}, ${d.unit}` : d.label,
      status: 'unknown' as const,
    })
}

const usedSources = computed(() => sources.value)
const filled = computed(() => product.value?.attrs.filter((a) => a.status === 'known').length ?? 0)
const na = computed(() => product.value?.attrs.filter((a) => a.status === 'not_applicable').length ?? 0)
const unknown = computed(() => {
  const total = attributeDefs.value.filter(
    (d) => !d.required_for || d.required_for.includes(product.value?.solutionTypeCode ?? ''),
  ).length
  return Math.max(total - filled.value - na.value, 0)
})
const applicabilityText = computed(() => product.value?.attrs.filter((a) => a.group === 'applicability') ?? [])
</script>

<template>
  <section v-if="product" class="container product">
    <NuxtLink to="/catalog" class="back body-sm"><PhArrowLeft :size="14" weight="bold" /> Каталог</NuxtLink>

    <div class="head" v-reveal>
      <div class="media glass glass-xl">
        <img :src="product.image" :alt="product.name">
        <div class="media-badges">
          <UiBadge :tone="availabilityTone[product.availability]" :pulse="product.availability === 'operation'">{{ availabilityLabel[product.availability] }}</UiBadge>
          <UiBadge tone="neutral" mono>УГТ {{ product.trl }}</UiBadge>
          <UiBadge :tone="product.autoMatch ? 'ok' : 'warn'">{{ product.autoMatch ? 'В автоподборе' : 'Не в автоподборе' }}</UiBadge>
        </div>
      </div>
      <div class="info">
        <div class="label">{{ product.solutionType }}</div>
        <h1 class="hero-2">{{ product.name }}</h1>
        <div class="vendor body"><span class="strong">{{ product.manufacturer }}</span> <span class="muted"><PhMapPin :size="14" /> {{ product.city }}, {{ product.country }}</span></div>
        <p class="body-lg muted">{{ product.summary }}</p>
        <div class="hl">
          <div v-for="h in product.highlights" :key="h.label" class="hl-item">
            <span class="caption">{{ h.label }}</span>
            <span class="mono-lg">{{ h.value }}</span>
          </div>
        </div>
        <div class="price-row glass">
          <div>
            <div class="caption">Стоимость единицы</div>
            <div class="display-4">{{ formatRub(product.priceRub) }}</div>
            <div v-if="product.priceNote" class="caption">{{ product.priceNote }}</div>
          </div>
          <div class="actions">
            <UiButton :variant="inCompare ? 'secondary' : 'primary'" @click="toggle(product.id)">
              <template #icon><PhCheck v-if="inCompare" :size="16" weight="bold" /><PhScales v-else :size="16" weight="bold" /></template>
              {{ inCompare ? 'В сравнении' : 'Сравнить' }}
            </UiButton>
            <UiButton variant="secondary"><template #icon><PhDownloadSimple :size="16" weight="bold" /></template>Спецификация</UiButton>
          </div>
        </div>
      </div>
    </div>

    <div class="layout">
      <nav class="anchors glass" aria-label="Группы характеристик">
        <a v-for="(g, i) in attrGroups" :key="g.code" :href="`#${g.code}`" class="anchor"><span class="mono-sm">{{ i + 1 }}</span>{{ g.label }}</a>
      </nav>

      <div class="groups">
        <section v-for="(g, i) in attrGroups.slice(0, 4)" :id="g.code" :key="g.code" class="group glass" v-reveal>
          <div class="g-head">
            <div class="mono-sm num">{{ i + 1 }}</div>
            <div>
              <h2 class="h3">{{ g.label }}</h2>
              <div class="caption">{{ g.hint }}</div>
            </div>
          </div>
          <div class="rows">
            <div v-for="a in byGroup(g.code)" :key="a.key" class="rowl">
              <span class="body-sm k">{{ a.label }}</span>
              <UiValueCell :attr="a" align="right" />
            </div>
            <div v-if="!byGroup(g.code).length" class="rowl"><span class="body-sm k muted">Полей группы для этого типа решения в справочнике нет</span></div>
          </div>
        </section>

        <section id="applicability" class="group glass" v-reveal>
          <div class="g-head">
            <div class="mono-sm num">5</div>
            <div><h2 class="h3">Применимость</h2><div class="caption">Объекты, процессы, кейсы, риски</div></div>
          </div>
          <div class="apply">
            <div><div class="caption">Отрасли</div><div class="tags"><span v-for="o in product.industries" :key="o" class="tag">{{ o }}</span></div></div>
            <div><div class="caption">Объекты</div><div class="tags"><span v-for="o in product.objects" :key="o" class="tag">{{ o }}</span></div></div>
            <div><div class="caption">Процессы</div><div class="tags"><span v-for="o in product.processes" :key="o" class="tag">{{ o }}</span></div></div>
            <div v-if="product.cases.length" class="apply-text">
              <div class="caption">Кейсы внедрения</div>
              <div v-for="c in product.cases" :key="c.id" class="case">
                <p class="body-sm">{{ c.summary }}</p>
                <UiSourceTag v-if="c.sourceId" :source-id="c.sourceId" />
              </div>
            </div>
            <div v-for="a in applicabilityText" :key="a.key" class="apply-text">
              <div class="caption">{{ a.label }}</div>
              <div class="body-sm strong" :class="{ risk: a.key === 'risks' }"><PhWarning v-if="a.key === 'risks' && a.status === 'known'" :size="14" weight="fill" /> <template v-if="a.status === 'known'">{{ a.value }}</template><UiValueCell v-else :attr="a" /></div>
              <UiSourceTag v-if="a.sourceId" :source-id="a.sourceId" />
            </div>
          </div>
        </section>

        <section id="data_quality" class="group glass" v-reveal>
          <div class="g-head">
            <div class="mono-sm num">6</div>
            <div><h2 class="h3">Качество данных</h2><div class="caption">Достоверность выводится из типа источника и не редактируется вручную</div></div>
          </div>
          <div class="dq">
            <div class="dq-stats">
              <UiStat label="Заполнено" :value="`${Math.round(product.completeness * 100)}%`" :note="`${filled} полей с данными`" />
              <UiStat label="Нет данных" :value="String(unknown)" note="запрос вендору" />
              <UiStat label="Не применимо" :value="String(na)" note="поле не относится к типу" />
              <UiStat label="Автоподбор" :value="product.autoMatch ? 'Да' : 'Нет'" :note="product.autoMatch ? 'УГТ ≥ 5, не разработка' : 'УГТ < 5 или разработка'" />
            </div>
            <table class="table">
              <thead><tr><th>Источник</th><th>Тип</th><th>Достоверность</th><th>Получено</th><th>Проверено</th></tr></thead>
              <tbody>
                <tr v-for="s in usedSources" :key="s.id">
                  <td class="strong">{{ s.publisher }}</td>
                  <td>{{ sourceKindLabel[s.kind] }}</td>
                  <td><UiSourceTag :source-id="s.id" /> <span class="mono-sm muted">{{ confidenceByKind[s.kind] }}</span></td>
                  <td class="mono-sm">{{ new Date(s.fetchedAt).toLocaleDateString('ru-RU') }}</td>
                  <td class="mono-sm">{{ new Date(s.checkedAt).toLocaleDateString('ru-RU') }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  </section>
</template>

<style scoped>
.product { padding-top: var(--space-8); padding-bottom: var(--space-16); }
.back { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-muted); font-weight: 600; margin-bottom: var(--space-6); }
.back:hover { color: var(--ink-strong); }
.head { display: grid; grid-template-columns: minmax(0, 6fr) minmax(0, 6fr); gap: var(--space-10); margin-bottom: var(--space-12); align-items: start; }
.media { position: relative; padding: 10px; }
.media img { width: 100%; aspect-ratio: 4 / 3; object-fit: cover; border-radius: 18px; position: relative; z-index: 1; }
.media-badges { position: absolute; left: 22px; top: 22px; display: flex; gap: 6px; z-index: 2; }
.info { display: grid; gap: var(--space-4); }
.vendor { display: flex; gap: 10px; align-items: center; }
.vendor .muted { display: inline-flex; align-items: center; gap: 4px; }
.hl { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-4); padding: var(--space-4) 0; border-top: 1px solid var(--border-hairline); border-bottom: 1px solid var(--border-hairline); }
.hl-item { display: grid; gap: 4px; }
.hl-item .mono-lg { color: var(--ink-strong); }
.price-row { display: flex; justify-content: space-between; align-items: center; gap: var(--space-4); padding: var(--space-5) var(--space-6); }
.price-row > * { position: relative; z-index: 1; }
.actions { display: flex; gap: 8px; }

.layout { display: grid; grid-template-columns: clamp(240px, 15vw, 280px) minmax(0, 1fr); gap: var(--space-8); align-items: start; }
.anchors { position: sticky; top: 96px; display: grid; gap: 2px; padding: 8px; }
.anchor { position: relative; z-index: 1; display: flex; align-items: center; gap: 10px; min-height: 38px; padding: 0 10px; border-radius: 10px; font-size: 14px; font-weight: 600; color: var(--ink-body); transition: background var(--dur-fast) var(--ease); }
.anchor:hover { background: rgba(15, 20, 19, 0.05); color: var(--ink-strong); }
.anchor .mono-sm { color: var(--ink-faint); width: 14px; }
.groups { display: grid; gap: var(--space-4); min-width: 0; }
.group { padding: var(--space-6); scroll-margin-top: 100px; }
.group > * { position: relative; z-index: 1; }
.g-head { display: flex; gap: 14px; align-items: flex-start; margin-bottom: var(--space-5); }
.num { width: 28px; height: 28px; border-radius: 8px; background: var(--surface-graphite); color: var(--brand-300); display: inline-flex; align-items: center; justify-content: center; flex: none; }
.rows { display: grid; }
.rowl { display: flex; justify-content: space-between; align-items: center; gap: var(--space-4); padding: 10px 0; border-top: 1px solid rgba(15, 20, 19, 0.06); }
.rowl:first-child { border-top: 0; }
.k { color: var(--ink-body); }
.apply { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-5); }
.apply-text { grid-column: span 2; display: grid; grid-template-columns: 160px 1fr auto; gap: 12px; align-items: start; }
.apply-text .caption { padding-top: 2px; }
.case { display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: start; }
.case + .case { margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--border-hairline); }
.risk { color: var(--state-warn); display: inline-flex; gap: 6px; align-items: flex-start; }
.tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.tag { font-size: 13px; font-weight: 600; padding: 5px 10px; border-radius: var(--radius-pill); background: rgba(15, 20, 19, 0.06); color: var(--ink-body); }
.dq { display: grid; gap: var(--space-6); }
.dq-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-6); }
@media (max-width: 1100px) { .head { grid-template-columns: 1fr; } .layout { grid-template-columns: 1fr; } .anchors { position: static; grid-template-columns: repeat(3, 1fr); } }
</style>
