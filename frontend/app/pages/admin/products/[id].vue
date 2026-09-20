<script setup lang="ts">
import { PhArrowLeft, PhFloppyDisk, PhQuotes, PhLinkSimple } from '@phosphor-icons/vue'
import { productBySlug, products, attrGroups, sources, sourceKindLabel, availabilityLabel, type AttrValue } from '~/data/catalog'

definePageMeta({ layout: 'admin' })
const route = useRoute()
const isNew = computed(() => route.params.id === 'new')
const product = computed(() => (isNew.value ? undefined : productBySlug(route.params.id as string)) ?? products[0]!)
useHead({ title: () => `Админка · ${isNew.value ? 'Новый продукт' : product.value.name}` })

const groups = attrGroups.filter((g) => g.code !== 'identification' && g.code !== 'data_quality')
const attrsOf = (code: AttrValue['group']) => product.value.attrs.filter((a) => a.group === code)
const statusLabel: Record<AttrValue['status'], string> = { known: 'Есть данные', unknown: 'Нет данных', not_applicable: 'Не применимо' }
</script>

<template>
  <div class="admin-page">
    <NuxtLink to="/admin/products" class="back body-sm"><PhArrowLeft :size="14" weight="bold" /> Продукты</NuxtLink>
    <AdminHead :label="isNew ? 'Новый продукт' : 'Редактирование'" :title="isNew ? 'Новый продукт' : product.name" lead="Форма собирается из справочника характеристик. Для каждого значения: само значение, статус, цитата и источник. Буква достоверности не редактируется: она выводится из типа источника.">
      <UiButton variant="secondary">Отменить</UiButton>
      <UiButton><template #icon><PhFloppyDisk :size="16" weight="bold" /></template>Сохранить в очередь</UiButton>
    </AdminHead>

    <UiCallout tone="info">Ручная правка тоже идёт через очередь модерации и попадает в каталог только после публикации версии.</UiCallout>

    <section class="grp glass" v-reveal>
      <div class="g-in">
        <div class="g-head"><span class="mono-sm n">1</span><div><div class="h3">Идентификация</div><div class="caption">Название, производитель, юрлицо, страна, статус, УГТ, рыночный потенциал</div></div></div>
        <div class="id-grid">
          <label class="field"><span class="field-label">Название</span><input class="input" :value="isNew ? '' : product.name"></label>
          <label class="field"><span class="field-label">Производитель</span><input class="input" :value="isNew ? '' : product.manufacturer"></label>
          <label class="field"><span class="field-label">Юрлицо</span><input class="input" :value="isNew ? '' : product.legalEntity"><span class="field-hint">Из справочника вендоров, нормализованное</span></label>
          <label class="field"><span class="field-label">Страна</span><input class="input" :value="isNew ? '' : product.country"></label>
          <label class="field"><span class="field-label">Статус</span><select class="select"><option v-for="(l, k) in availabilityLabel" :key="k" :selected="!isNew && product.availability === k">{{ l }}</option></select></label>
          <label class="field"><span class="field-label">УГТ</span><input class="input input-mono" :value="isNew ? '' : product.trl"><span class="field-hint">1–9. Ниже 7 не участвует в автоподборе</span></label>
          <label class="field"><span class="field-label">Рыночный потенциал</span><input class="input input-mono" :value="isNew ? '' : product.marketPotential"><span class="field-hint">1–5 по каталогу организатора</span></label>
          <label class="field"><span class="field-label">Тип решения</span><input class="input" :value="isNew ? '' : product.solutionType"><span class="field-hint">Определяет семейство формул расчёта количества</span></label>
        </div>
      </div>
    </section>

    <section v-for="(g, gi) in groups" :key="g.code" class="grp glass" v-reveal="Math.min(gi + 1, 5)">
      <div class="g-in">
        <div class="g-head"><span class="mono-sm n">{{ gi + 2 }}</span><div><div class="h3">{{ g.label }}</div><div class="caption">{{ g.hint }}</div></div></div>
        <div class="attrs">
          <div class="attr attr-head caption"><span>Поле</span><span>Значение</span><span>Статус</span><span>Цитата</span><span>Источник</span></div>
          <div v-for="a in attrsOf(g.code)" :key="a.key" class="attr">
            <span class="body-sm strong">{{ a.label }}<span v-if="a.unit" class="caption block">{{ a.unit }}</span></span>
            <input class="input input-mono" :value="a.status === 'known' ? a.value : ''" :disabled="a.status !== 'known'" :placeholder="a.status === 'known' ? '' : statusLabel[a.status]">
            <select class="select"><option v-for="(l, k) in statusLabel" :key="k" :selected="a.status === k">{{ l }}</option></select>
            <span class="quote"><PhQuotes :size="14" weight="fill" /><input class="input" :value="a.quote ?? ''" placeholder="Цитата из источника"></span>
            <span class="src-sel">
              <select class="select"><option v-if="!a.sourceId" selected>Без источника</option><option v-for="s in sources" :key="s.id" :selected="a.sourceId === s.id">{{ s.publisher }} · {{ sourceKindLabel[s.kind] }}</option></select>
              <UiSourceTag v-if="a.sourceId" :source-id="a.sourceId" align="right" />
            </span>
          </div>
          <div v-if="!attrsOf(g.code).length" class="caption empty">Для этого типа решения в справочнике нет полей группы</div>
        </div>
      </div>
    </section>

    <section class="grp glass" v-reveal="5">
      <div class="g-in">
        <div class="g-head"><span class="mono-sm n">6</span><div><div class="h3">Качество данных</div><div class="caption">Выводится автоматически, не редактируется</div></div></div>
        <div class="dq">
          <UiStat label="Заполнено" :value="`${Math.round(product.completeness * 100)}%`" />
          <UiStat label="Автоподбор" :value="product.autoMatch ? 'Да' : 'Нет'" :note="product.autoMatch ? 'УГТ ≥ 7, не разработка' : 'УГТ < 7 или разработка'" />
          <UiStat label="Источников" :value="String(new Set(product.attrs.map(a => a.sourceId).filter(Boolean)).size)" />
          <div class="dq-link"><PhLinkSimple :size="16" /> <span class="body-sm">Достоверность каждого значения считается из типа источника в разделе <NuxtLink to="/admin/sources" class="link">Источники</NuxtLink>.</span></div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.back { display: inline-flex; align-items: center; gap: 6px; color: var(--ink-muted); font-weight: 600; }
.grp .g-in { position: relative; z-index: 1; padding: var(--space-6); display: grid; gap: var(--space-5); }
.g-head { display: flex; gap: 14px; align-items: flex-start; }
.n { width: 28px; height: 28px; border-radius: 8px; background: var(--surface-graphite); color: var(--brand-300); display: inline-flex; align-items: center; justify-content: center; flex: none; }
.id-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 14px 20px; align-items: start; }
.attrs { display: grid; gap: 8px; }
.attr { display: grid; grid-template-columns: 180px 1fr 150px 1.4fr 1.6fr; gap: 10px; align-items: center; }
.attr-head { padding: 0 2px; }
.block { display: block; }
.quote { position: relative; display: flex; align-items: center; }
.quote svg { position: absolute; left: 10px; color: var(--ink-faint); }
.quote .input { padding-left: 30px; }
.src-sel { display: grid; grid-template-columns: 1fr auto; gap: 8px; align-items: center; }
.empty { padding: 8px 2px; }
.dq { display: grid; grid-template-columns: repeat(3, auto) 1fr; gap: var(--space-8); align-items: center; }
.dq-link { display: flex; gap: 8px; align-items: center; color: var(--ink-muted); }
@media (max-width: 1100px) { .attr { grid-template-columns: 1fr 1fr; } .dq { grid-template-columns: 1fr 1fr; } }
</style>
