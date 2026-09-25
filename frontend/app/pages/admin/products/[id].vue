<script setup lang="ts">
import { PhArrowLeft, PhFloppyDisk, PhQuotes, PhLinkSimple, PhCheckCircle, PhWarningCircle } from '@phosphor-icons/vue'
import { attrGroups, availabilityLabel, sourceKindLabel, type AttrGroup, type SourceKind, type ValueStatus } from '~/data/catalog'
import type { ApiAttrValue } from '~/types/api'

definePageMeta({ layout: 'admin' })
const route = useRoute()
const { product, sources, attributeDefs, refresh } = useProduct(() => route.params.id as string)
const { refresh: refreshCatalog } = useCatalog()
useHead({ title: () => `Админка · ${product.value?.name ?? 'Решение'}` })

const groups = attrGroups.filter((g) => g.code !== 'identification' && g.code !== 'data_quality')
const statusLabel: Record<ValueStatus, string> = {
  known: 'Есть данные',
  unknown: 'Нет данных',
  not_applicable: 'Не применимо',
}

interface Row {
  key: string
  label: string
  unit?: string
  datatype: string
  enumValues?: string[]
  status: ValueStatus
  value: string
  quote: string
  sourceId?: string
  initial: { status: ValueStatus; value: string; quote: string }
}

/**
 * Форма собирается из справочника характеристик, а не из того, что заполнено: в исходном CSV
 * ТТХ нет ни одной, поэтому пустые поля — это и есть рабочая поверхность (§6.2, §12.4).
 */
const rows = ref<Record<string, Row[]>>({})
const buildRows = () => {
  const p = product.value
  if (!p) return
  const next: Record<string, Row[]> = {}
  for (const g of groups) {
    next[g.code] = attributeDefs.value
      .filter((d) => d.group_code === g.code && (!d.required_for || d.required_for.includes(p.solutionTypeCode)))
      .map((d) => {
        const current = p.attrs.find((a) => a.key === d.key)
        const status = current?.status ?? 'unknown'
        const value = current?.value != null ? String(current.value) : ''
        const quote = current?.quote ?? ''
        return {
          key: d.key,
          label: d.label,
          unit: d.unit ?? undefined,
          datatype: d.datatype,
          enumValues: d.enum_values ?? undefined,
          status,
          value,
          quote,
          sourceId: current?.sourceId,
          initial: { status, value, quote },
        }
      })
  }
  rows.value = next
}
watch([product, attributeDefs], buildRows, { immediate: true })

const changed = computed(() =>
  Object.values(rows.value).flat().filter(
    (r) => r.status !== r.initial.status || r.value !== r.initial.value || r.quote !== r.initial.quote,
  ),
)

/* Источник правки: без него значение не принимается, достоверность выводится из его типа (§6.4) */
const sourceKind = ref<SourceKind>('vendor')
const sourceUrl = ref('')
const sourcePublisher = ref('')
const sourceTitle = ref('')
const rationale = ref('')
const needsRationale = computed(() => sourceKind.value === 'analogue' || sourceKind.value === 'assumption')

const saving = ref(false)
const result = ref<{ ok: boolean; text: string } | null>(null)

const cast = (row: Row): ApiAttrValue['value'] => {
  if (row.status !== 'known') return null
  if (row.datatype === 'number') {
    const n = Number(row.value.replace(',', '.').replace(/\s/g, ''))
    return Number.isFinite(n) ? n : row.value
  }
  if (row.datatype === 'bool') return /^(да|true|1)$/i.test(row.value.trim())
  return row.value
}

const save = async () => {
  const p = product.value
  if (!p || !changed.value.length || saving.value) return
  saving.value = true
  result.value = null
  const values: Record<string, ApiAttrValue> = {}
  for (const row of changed.value) {
    values[row.key] = {
      status: row.status,
      value: cast(row),
      unit: row.unit ?? null,
      quote: row.quote || null,
    }
  }
  try {
    await $fetch(`${useApiBase()}/admin/products/${p.id}/attrs`, {
      method: 'PATCH',
      body: {
        values,
        source_kind: sourceKind.value,
        source_url: sourceUrl.value || null,
        source_publisher: sourcePublisher.value || p.manufacturer,
        source_title: sourceTitle.value || null,
        rationale: rationale.value || null,
      },
    })
    await Promise.all([refresh(), refreshCatalog()])
    result.value = { ok: true, text: `Сохранено характеристик: ${Object.keys(values).length}` }
  } catch (e: any) {
    result.value = { ok: false, text: e?.data?.detail ?? 'Не удалось сохранить' }
  } finally {
    saving.value = false
  }
}

const reset = () => { buildRows(); result.value = null }
</script>

<template>
  <div v-if="product" class="admin-page">
    <NuxtLink to="/admin/products" class="back body-sm"><PhArrowLeft :size="14" weight="bold" /> Продукты</NuxtLink>
    <AdminHead label="Редактирование" :title="product.name" lead="Форма собирается из справочника характеристик. Для каждого значения: само значение, статус, цитата и источник. Буква достоверности не редактируется: она выводится из типа источника.">
      <UiButton variant="secondary" :disabled="!changed.length" @click="reset">Отменить</UiButton>
      <UiButton :disabled="!changed.length || saving" @click="save">
        <template #icon><PhFloppyDisk :size="16" weight="bold" /></template>
        {{ saving ? 'Сохранение…' : changed.length ? `Сохранить (${changed.length})` : 'Сохранить' }}
      </UiButton>
    </AdminHead>

    <UiCallout v-if="result" :tone="result.ok ? 'ok' : 'warn'">
      <PhCheckCircle v-if="result.ok" :size="18" weight="fill" />
      <PhWarningCircle v-else :size="18" weight="fill" />
      {{ result.text }}
    </UiCallout>
    <UiCallout v-else tone="info">
      Характеристик в исходном каталоге организатора нет: все технические поля заполняются здесь, каждое со своим источником.
    </UiCallout>

    <section class="grp glass" v-reveal>
      <div class="g-in">
        <div class="g-head"><span class="mono-sm n">1</span><div><div class="h3">Идентификация</div><div class="caption">Название, производитель, юрлицо, страна, статус, УГТ, рыночный потенциал</div></div></div>
        <div class="id-grid">
          <label class="field"><span class="field-label">Название</span><input class="input" :value="product.name" disabled></label>
          <label class="field"><span class="field-label">Производитель</span><input class="input" :value="product.manufacturer" disabled></label>
          <label class="field"><span class="field-label">Юрлицо</span><input class="input" :value="product.legalEntity" disabled><span class="field-hint">Из справочника вендоров, нормализованное</span></label>
          <label class="field"><span class="field-label">Регион</span><input class="input" :value="product.city" disabled></label>
          <label class="field"><span class="field-label">Статус</span><select class="select" disabled><option v-for="(l, k) in availabilityLabel" :key="k" :selected="product.availability === k">{{ l }}</option></select></label>
          <label class="field"><span class="field-label">УГТ</span><input class="input input-mono" :value="product.trl" disabled><span class="field-hint">1–9. Ниже 5 не участвует в автоподборе</span></label>
          <label class="field"><span class="field-label">Рыночный потенциал</span><input class="input input-mono" :value="product.marketPotential" disabled><span class="field-hint">1–5 по каталогу организатора</span></label>
          <label class="field"><span class="field-label">Тип решения</span><input class="input" :value="product.solutionType" disabled><span class="field-hint">Определяет семейство формул расчёта количества</span></label>
        </div>
      </div>
    </section>

    <section class="grp glass" v-reveal="1">
      <div class="g-in">
        <div class="g-head"><span class="mono-sm n">2</span><div><div class="h3">Источник правки</div><div class="caption">Один источник на все изменённые в этот раз значения. Достоверность выводится из его типа</div></div></div>
        <div class="id-grid">
          <label class="field">
            <span class="field-label">Тип источника</span>
            <select v-model="sourceKind" class="select"><option v-for="(l, k) in sourceKindLabel" :key="k" :value="k">{{ l }}</option></select>
          </label>
          <label class="field"><span class="field-label">Кто опубликовал</span><input v-model="sourcePublisher" class="input" :placeholder="product.manufacturer"></label>
          <label class="field"><span class="field-label">Ссылка</span><input v-model="sourceUrl" class="input" placeholder="https://"><span class="field-hint">Если источник — файл или бумага, оставьте пустым</span></label>
          <label class="field"><span class="field-label">Название документа</span><input v-model="sourceTitle" class="input" placeholder="Техническое описание"></label>
          <label v-if="needsRationale" class="field wide">
            <span class="field-label">Обоснование</span>
            <input v-model="rationale" class="input" placeholder="Почему это допущение или какой аналог взят">
            <span class="field-hint">Для оценки по аналогу и допущения команды обязательно</span>
          </label>
        </div>
      </div>
    </section>

    <section v-for="(g, gi) in groups" :key="g.code" class="grp glass" v-reveal="Math.min(gi + 1, 5)">
      <div class="g-in">
        <div class="g-head"><span class="mono-sm n">{{ gi + 3 }}</span><div><div class="h3">{{ g.label }}</div><div class="caption">{{ g.hint }}</div></div></div>
        <div class="attrs">
          <div class="attr attr-head caption"><span>Поле</span><span>Значение</span><span>Статус</span><span>Цитата</span><span>Источник</span></div>
          <div v-for="a in rows[g.code] ?? []" :key="a.key" class="attr">
            <span class="body-sm strong">{{ a.label }}<span v-if="a.unit" class="caption block">{{ a.unit }}</span></span>
            <select v-if="a.enumValues && a.status === 'known'" v-model="a.value" class="select">
              <option v-for="v in a.enumValues" :key="v" :value="v">{{ v }}</option>
            </select>
            <input
              v-else
              v-model="a.value"
              class="input input-mono"
              :disabled="a.status !== 'known'"
              :placeholder="a.status === 'known' ? '' : statusLabel[a.status]"
            >
            <select v-model="a.status" class="select"><option v-for="(l, k) in statusLabel" :key="k" :value="k">{{ l }}</option></select>
            <span class="quote"><PhQuotes :size="14" weight="fill" /><input v-model="a.quote" class="input" placeholder="Цитата из источника"></span>
            <span class="src-sel">
              <span class="caption">{{ a.sourceId ? (sources.find((s) => s.id === a.sourceId)?.publisher ?? 'источник') : 'будет источник правки' }}</span>
              <UiSourceTag v-if="a.sourceId" :source-id="a.sourceId" align="right" />
            </span>
          </div>
          <div v-if="!(rows[g.code] ?? []).length" class="caption empty">Для этого типа решения в справочнике нет полей группы</div>
        </div>
      </div>
    </section>

    <section class="grp glass" v-reveal="5">
      <div class="g-in">
        <div class="g-head"><span class="mono-sm n">{{ groups.length + 3 }}</span><div><div class="h3">Качество данных</div><div class="caption">Выводится автоматически, не редактируется</div></div></div>
        <div class="dq">
          <UiStat label="Заполнено" :value="`${Math.round(product.completeness * 100)}%`" />
          <UiStat label="Автоподбор" :value="product.autoMatch ? 'Да' : 'Нет'" :note="product.autoMatch ? 'УГТ ≥ 5, не разработка' : 'УГТ < 5 или разработка'" />
          <UiStat label="Источников" :value="String(sources.length)" />
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
.id-grid .wide { grid-column: span 2; }
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
