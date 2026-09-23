<script setup lang="ts">
import {
  PhCaretLeft,
  PhCaretRight,
  PhPushPin,
  PhPushPinSlash,
  PhScales,
  PhArrowLeft,
} from '@phosphor-icons/vue'
import { projects } from '~/data/projects'
import { fetchErrorMessage } from '~/composables/useCalc'
import type {
  CompareCarouselItem,
  CompareDeltaRow,
  CompareParamValue,
  CompareSubrow,
} from '~/composables/useCompareGrid'

const route = useRoute()
const id = computed(() => route.params.id as string)
const {
  products,
  compareSpec,
  pending: catalogPending,
  attrsPending,
  attrsError,
  ensureCompareData,
} = useCatalog()
void ensureCompareData()
const { project, detail, run, pending, error } = useCalc(id)
const demoProject = computed(() => projects.find((p) => p.id === id.value))
const shell = computed(() => project.value ?? demoProject.value)
useHead({ title: () => `Сравнение · ${shell.value?.name ?? 'проект'}` })

const { groups, summary, pinBaseline, clearPin, setActive } = useCompareGrid({
  detail,
  run,
  products,
  compareSpec,
})

const live = computed(() => Boolean(project.value))
const loading = computed(() => pending.value || catalogPending.value || attrsPending.value)
const noRun = computed(() => live.value && !loading.value && !error.value && !attrsError.value && !run.value)
const loadError = computed(() => error.value || attrsError.value)

/** Есть прогон, но ни в одной группе нет кандидатов со вердиктом «подходит». */
const nothingToCompare = computed(() => {
  if (!run.value || loading.value || loadError.value) return false
  return groups.value.every((g) => !g.subrows.some((s) => s.carousel.length > 0))
})

const formatMoney = (n: number) =>
  n.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' ₽'

const scorePct = (score: number | null) =>
  score == null ? '—' : String(Math.round(score * 100))

const subrowDomId = (s: CompareSubrow) =>
  `carousel-${s.processCode}-${s.solutionTypeCode}`

const activeIndex = (s: CompareSubrow) =>
  Math.max(0, s.carousel.findIndex((c) => c.productId === s.activeProductId))

const scrollActiveIntoView = (s: CompareSubrow) => {
  if (!import.meta.client) return
  const root = document.getElementById(subrowDomId(s))
  const card = root?.querySelector<HTMLElement>('.card.active')
  card?.scrollIntoView({ behavior: 'smooth', inline: 'nearest', block: 'nearest' })
}

const selectCard = (s: CompareSubrow, productId: string) => {
  setActive(s.processCode, s.solutionTypeCode, productId)
  nextTick(() => scrollActiveIntoView(s))
}

const stepCarousel = (s: CompareSubrow, dir: -1 | 1) => {
  if (!s.carousel.length) return
  const i = activeIndex(s)
  const next = s.carousel[(i + dir + s.carousel.length) % s.carousel.length]
  if (next) selectCard(s, next.productId)
}

const onCarouselKey = (e: KeyboardEvent, s: CompareSubrow) => {
  if (e.key === 'ArrowLeft') {
    e.preventDefault()
    stepCarousel(s, -1)
  } else if (e.key === 'ArrowRight') {
    e.preventDefault()
    stepCarousel(s, 1)
  }
}

const onPin = (s: CompareSubrow, item: CompareCarouselItem) => {
  if (s.isPinned && s.baselineProductId === item.productId) {
    void clearPin(s.processCode, s.solutionTypeCode)
  } else {
    void pinBaseline(s.processCode, s.solutionTypeCode, item.productId)
    setActive(s.processCode, s.solutionTypeCode, item.productId)
  }
}

const toneClass = (tone: CompareDeltaRow['tone']) => {
  if (tone === 'better') return 'tone-better'
  if (tone === 'worse') return 'tone-worse'
  if (tone === 'neutral') return 'tone-neutral'
  return ''
}

const provenanceLabel = (v: CompareParamValue) => {
  const p = v.provenance
  if (!p) return ''
  if (p.kind === 'engine') return p.note ? `расчёт движка · ${p.note}` : 'расчёт движка'
  if (p.kind === 'derived') return p.note ?? 'производное значение'
  return p.note ?? ''
}

const valueUnit = (v: CompareParamValue) => {
  if (!v.known) return ''
  return v.unit ? ` ${v.unit}` : ''
}
</script>

<template>
  <ProjectShell
    v-if="shell"
    :project="shell"
    current="compare"
    title="Сравнение кандидатов"
    lead="По каждому направлению — карусель подходящих решений и панель прироста к эталону. Эталон по умолчанию — лучший счёт; его можно закрепить, и ссылка сохранит выбор."
  >
    <template #actions>
      <UiButton v-if="live" :to="`/projects/${shell.id}/match`" size="lg" variant="secondary">
        <template #icon><PhArrowLeft :size="16" weight="bold" /></template>
        К подбору
      </UiButton>
      <UiButton v-if="live && run && !nothingToCompare" :to="`/projects/${shell.id}/economics`" size="lg">
        <template #icon><PhScales :size="16" weight="bold" /></template>
        К экономике
      </UiButton>
    </template>

    <UiCallout v-if="!live" tone="warn" title="Это демонстрационный макет">
      Живое сравнение строится из прогона подбора на сервере. Создайте проект и запустите подбор — тогда здесь появятся кандидаты и дельты.
      <div class="call-actions">
        <UiButton to="/projects/new" size="sm">Создать проект</UiButton>
      </div>
    </UiCallout>

    <UiCallout v-else-if="loadError" tone="danger" title="Не удалось загрузить данные сравнения">
      {{ fetchErrorMessage(loadError, 'Сервер не ответил. Проверьте, что API запущен.') }}
    </UiCallout>

    <div v-else-if="loading" class="summary" v-reveal>
      <div v-for="i in 4" :key="i" class="sum glass"><UiSkeleton h="56px" /></div>
    </div>

    <template v-else-if="noRun">
      <UiCallout tone="info" title="Расчёт ещё не запускался">
        Сравнивать нечего: сначала нужен прогон на шаге подбора — корзины, количество и счёт. Вернитесь туда и запустите подбор.
        <div class="call-actions">
          <UiButton :to="`/projects/${shell.id}/match`">
            <template #icon><PhArrowLeft :size="16" weight="bold" /></template>
            Вернуться к подбору
          </UiButton>
        </div>
      </UiCallout>
    </template>

    <template v-else-if="nothingToCompare">
      <UiCallout tone="warn" title="Сравнивать нечего">
        Прогон есть, но ни одно направление не дало кандидатов со вердиктом «подходит».
        <template v-if="summary.openLabels.length">
          Не закрыты: {{ summary.openLabels.join(', ') }}.
        </template>
        Откройте подбор: там видно, кто в «требует проверки» и кто исключён.
        <div class="call-actions">
          <UiButton :to="`/projects/${shell.id}/match`" variant="secondary" size="sm">Открыть подбор</UiButton>
        </div>
      </UiCallout>
      <div v-if="groups.length" class="grid">
        <section v-for="g in groups" :key="g.processCode" class="group glass">
          <header class="group-head">
            <h2 class="h3">{{ g.label }}</h2>
            <p v-if="g.emptyMessage" class="body-sm muted">{{ g.emptyMessage }}</p>
          </header>
        </section>
      </div>
    </template>

    <template v-else-if="run">
      <div class="grid">
        <section v-for="g in groups" :key="g.processCode" class="group glass">
          <header class="group-head">
            <h2 class="h3">{{ g.label }}</h2>
            <p v-if="g.emptyMessage && !g.subrows.length" class="body-sm muted">{{ g.emptyMessage }}</p>
            <UiChip v-else-if="g.subrows.length" :count="g.subrows.length">типов решений</UiChip>
          </header>

          <div v-if="!g.subrows.length && g.emptyMessage" class="empty-row">
            <p class="body-sm">{{ g.emptyMessage }}</p>
          </div>

          <div
            v-for="s in g.subrows"
            :key="`${s.processCode}:${s.solutionTypeCode}`"
            class="subrow"
          >
            <aside class="stype">
              <div class="h4">{{ s.solutionTypeLabel }}</div>
              <div v-if="s.carousel.length" class="caption">лучший счёт {{ scorePct(s.bestScore) }}</div>
              <div v-else class="caption">подходящих решений нет — все кандидаты требуют проверки</div>
              <UiBadge v-if="s.isPinned" tone="ok" size="sm">эталон закреплён</UiBadge>
            </aside>

            <div class="mid">
              <div
                :id="subrowDomId(s)"
                class="carousel"
                tabindex="0"
                role="listbox"
                :aria-label="`Кандидаты: ${s.solutionTypeLabel}`"
                @keydown="onCarouselKey($event, s)"
              >
                <button
                  type="button"
                  class="nav prev"
                  :disabled="s.carousel.length < 2"
                  aria-label="Предыдущий кандидат"
                  @click="stepCarousel(s, -1)"
                >
                  <PhCaretLeft :size="18" weight="bold" />
                </button>

                <div class="track">
                  <article
                    v-for="item in s.carousel"
                    :key="item.productId"
                    class="card"
                    :class="{
                      active: item.productId === s.activeProductId,
                      baseline: item.productId === s.baselineProductId,
                    }"
                    role="option"
                    :aria-selected="item.productId === s.activeProductId"
                    @click="selectCard(s, item.productId)"
                  >
                    <div class="card-who">
                      <NuxtLink
                        v-if="item.product"
                        :to="`/catalog/${item.product.slug}`"
                        class="h4"
                        @click.stop
                      >{{ item.product.name }}</NuxtLink>
                      <span v-else class="h4">{{ item.productId }}</span>
                      <div class="caption">{{ item.product?.manufacturer ?? 'производитель не указан' }}</div>
                    </div>
                    <dl class="card-nums">
                      <div>
                        <dt class="caption">Счёт</dt>
                        <dd class="mono-md">{{ scorePct(item.score) }}</dd>
                      </div>
                      <div>
                        <dt class="caption">Количество</dt>
                        <dd class="mono-md">
                          <template v-if="item.count != null">{{ item.count.toLocaleString('ru-RU') }} шт.</template>
                          <template v-else>нет данных</template>
                        </dd>
                      </div>
                    </dl>
                    <code v-if="item.formula" class="formula">{{ item.formula }}</code>
                    <div class="card-actions">
                      <button
                        v-if="s.isPinned && item.productId === s.baselineProductId"
                        type="button"
                        class="pin-btn unpin"
                        @click.stop="onPin(s, item)"
                      >
                        <PhPushPinSlash :size="14" weight="bold" /> Снять закрепление
                      </button>
                      <button
                        v-else-if="item.productId !== s.activeProductId"
                        type="button"
                        class="pin-btn"
                        @click.stop="onPin(s, item)"
                      >
                        <PhPushPin :size="14" weight="bold" /> Закрепить эталоном
                      </button>
                      <span v-else-if="item.productId === s.baselineProductId" class="caption pin-hint">это эталон</span>
                    </div>
                  </article>
                </div>

                <button
                  type="button"
                  class="nav next"
                  :disabled="s.carousel.length < 2"
                  aria-label="Следующий кандидат"
                  @click="stepCarousel(s, 1)"
                >
                  <PhCaretRight :size="18" weight="bold" />
                </button>
              </div>

              <div v-if="s.needsReview.length" class="review">
                <div class="h4">Требуют проверки</div>
                <p class="caption">
                  В сравнение не входят: часть жёстких условий не проверена, сравнивать позицию с неизвестными полями нельзя.
                </p>
                <ul class="review-list">
                  <li v-for="r in s.needsReview" :key="r.productId" class="review-item">
                    <span class="body-sm">{{ r.product?.name ?? r.productId }}</span>
                    <span class="caption">{{ r.product?.manufacturer }}</span>
                  </li>
                </ul>
              </div>
            </div>

            <aside class="panel">
              <div class="panel-title h4">Прирост и падение</div>
              <p v-if="s.panel.isBaseline || s.panel.message" class="panel-msg body-sm">
                {{ s.panel.message }}
              </p>
              <template v-else>
                <div v-for="pg in s.panel.groups" :key="pg.group" class="pgroup">
                  <div class="label">{{ pg.label }}</div>
                  <div v-for="row in pg.rows" :key="row.key" class="prow" :class="toneClass(row.tone)">
                    <div class="prow-head">
                      <span class="body-sm strong" :title="row.rationale">{{ row.label }}</span>
                      <span class="caption why" :title="row.rationale">{{ row.rationale }}</span>
                    </div>
                    <div class="prow-vals">
                      <div class="pval">
                        <span class="caption">активная</span>
                        <span class="mono-md">
                          <template v-if="row.active.known">{{ row.active.display }}{{ valueUnit(row.active) }}</template>
                          <template v-else>нет данных</template>
                        </span>
                        <span v-if="row.active.approximate" class="approx caption">приблизительно: середина диапазона</span>
                        <span v-if="row.active.provenance?.kind === 'catalog'" class="prov">
                          <UiSourceTag
                            :source-id="row.active.provenance.sourceId"
                            :quote="row.active.provenance.quote"
                          />
                        </span>
                        <span v-else-if="row.active.known && row.active.provenance" class="caption eng">
                          {{ provenanceLabel(row.active) }}
                        </span>
                      </div>
                      <div class="pval">
                        <span class="caption">эталон</span>
                        <span class="mono-md">
                          <template v-if="row.baseline.known">{{ row.baseline.display }}{{ valueUnit(row.baseline) }}</template>
                          <template v-else>нет данных</template>
                        </span>
                        <span v-if="row.baseline.approximate" class="approx caption">приблизительно: середина диапазона</span>
                        <span v-if="row.baseline.provenance?.kind === 'catalog'" class="prov">
                          <UiSourceTag
                            :source-id="row.baseline.provenance.sourceId"
                            :quote="row.baseline.provenance.quote"
                          />
                        </span>
                        <span v-else-if="row.baseline.known && row.baseline.provenance" class="caption eng">
                          {{ provenanceLabel(row.baseline) }}
                        </span>
                      </div>
                      <div class="pdelta">
                        <span class="caption">дельта</span>
                        <span v-if="row.kind === 'no_data'" class="no-data body-sm">{{ row.message }}</span>
                        <span v-else class="delta-msg mono-md">{{ row.message }}</span>
                        <span v-if="row.approximate && row.kind === 'numeric'" class="approx caption">приблизительно</span>
                      </div>
                    </div>
                  </div>
                </div>
              </template>
            </aside>
          </div>
        </section>
      </div>

      <section class="summary-block glass" v-reveal="1">
        <div class="h3">Сводка по эталонам</div>
        <p class="caption">Считается по закреплённым эталонам всех подстрок. Окупаемость здесь не считается.</p>

        <div class="summary">
          <UiStat
            label="Закрыто направлений"
            :value="String(summary.closedCount)"
            :note="summary.openCount ? `не закрыто: ${summary.openCount}` : 'все направления закрыты'"
          />
          <UiStat
            label="Суммарный парк"
            :value="String(summary.totalPark)"
            note="единиц по эталонам"
          />
          <UiStat
            label="Стоимость оборудования"
            :value="summary.equipmentCost == null ? 'нет данных' : formatMoney(summary.equipmentCost)"
            :note="summary.equipmentCostPartial
              ? `неполная сумма · цена известна у ${summary.priceKnown} из ${summary.priceTotal}`
              : summary.equipmentCost == null
                ? 'ни у одной позиции нет цены'
                : `цена известна у ${summary.priceKnown} из ${summary.priceTotal}`"
          />
          <UiStat
            label="Худшая достоверность"
            :value="summary.worstReliability ?? '—'"
            :note="summary.worstReliabilityLabel
              ? `у решения «${summary.worstReliabilityLabel}»`
              : 'по эталонам буквы нет'"
          />
        </div>

        <div v-if="summary.openLabels.length" class="open-list">
          <span class="caption">Не закрыты:</span>
          <UiChip v-for="label in summary.openLabels" :key="label">{{ label }}</UiChip>
        </div>

        <div v-if="summary.parkByProcess.length" class="park-break">
          <div class="caption">Парк по направлениям</div>
          <ul>
            <li v-for="p in summary.parkByProcess" :key="p.processCode" class="body-sm">
              {{ p.label }} — <span class="mono-md">{{ p.count.toLocaleString('ru-RU') }}</span> шт.
            </li>
          </ul>
        </div>

        <p class="body-sm vendor">
          Полей ждут ответа вендора:
          <strong>{{ summary.vendorFieldsWaiting }}</strong>.
          <NuxtLink :to="`/projects/${shell.id}/match`" class="link">Открыть корзину «требует проверки» на шаге подбора</NuxtLink>
        </p>

        <UiCallout tone="info" title="Экономика ещё впереди">
          {{ summary.economicsStub }}
        </UiCallout>
      </section>
    </template>
  </ProjectShell>

  <section v-else class="container missing">
    <UiCallout tone="danger" title="Проект не найден">Нет ни сохранённого расчёта, ни демо-макета с таким адресом.</UiCallout>
    <UiButton to="/projects">К списку проектов</UiButton>
  </section>
</template>

<style scoped>
.call-actions { margin-top: 10px; }
.missing { padding-top: var(--space-12); display: grid; gap: var(--space-4); justify-items: start; }

.grid { display: grid; gap: var(--space-5); }
.group { padding: 18px 20px; display: grid; gap: var(--space-5); }
.group > * { position: relative; z-index: 1; }
.group-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 12px; justify-content: space-between; }
.empty-row { padding: 14px 16px; border-radius: 12px; background: rgba(15, 20, 19, 0.04); }

.subrow {
  display: grid;
  grid-template-columns: minmax(140px, 180px) minmax(280px, 1.2fr) minmax(260px, 1fr);
  gap: var(--space-4);
  align-items: start;
  padding-top: var(--space-4);
  border-top: 1px solid rgba(15, 20, 19, 0.08);
}
.stype { display: grid; gap: 8px; align-content: start; }

.mid { display: grid; gap: 12px; min-width: 0; }
.carousel {
  display: grid;
  grid-template-columns: 36px 1fr 36px;
  gap: 8px;
  align-items: center;
  outline: none;
  border-radius: 14px;
}
.carousel:focus-visible { box-shadow: 0 0 0 2px var(--brand-400); }
.nav {
  display: inline-flex; align-items: center; justify-content: center;
  width: 36px; height: 36px; border-radius: 10px;
  background: rgba(255, 255, 255, 0.75);
  box-shadow: inset 0 0 0 1px var(--border-hairline);
  color: var(--ink-strong);
  transition: background var(--dur-fast) var(--ease);
}
.nav:hover:not(:disabled) { background: #fff; }
.nav:disabled { opacity: 0.35; cursor: default; }

.track {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  padding: 4px 2px 10px;
  scrollbar-width: thin;
}
.card {
  flex: 0 0 min(260px, 78%);
  scroll-snap-align: start;
  display: grid;
  gap: 10px;
  padding: 14px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.7);
  box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.08);
  cursor: pointer;
  transition: box-shadow var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease);
}
.card:hover { transform: translateY(-1px); }
.card.active {
  box-shadow: inset 0 0 0 2px var(--brand-500), 0 8px 24px rgba(15, 20, 19, 0.08);
  background: #fff;
}
.card.baseline:not(.active) { box-shadow: inset 0 0 0 1px rgba(10, 107, 69, 0.35); }
.card-who .h4 { color: var(--ink-strong); }
.card-nums { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin: 0; }
.card-nums dd { margin: 0; color: var(--ink-strong); }
.formula {
  display: block; padding: 8px 10px; border-radius: 10px;
  background: var(--surface-graphite); color: var(--brand-300);
  font-family: var(--font-mono); font-size: 11.5px; line-height: 1.45;
  white-space: pre-wrap; word-break: break-word;
}
.card-actions { min-height: 28px; }
.pin-btn {
  display: inline-flex; align-items: center; gap: 6px;
  height: 32px; padding: 0 10px; border-radius: 8px;
  font-size: 12.5px; font-weight: 700; color: var(--brand-ink);
  background: var(--surface-brand-tint);
  box-shadow: inset 0 0 0 1px rgba(10, 107, 69, 0.16);
}
.pin-btn.unpin { background: rgba(15, 20, 19, 0.06); color: var(--ink-strong); box-shadow: none; }
.pin-hint { color: var(--ink-muted); }

.review {
  padding: 12px 14px; border-radius: 12px;
  background: var(--state-warn-tint); display: grid; gap: 8px;
}
.review-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.review-item { display: flex; justify-content: space-between; gap: 8px; flex-wrap: wrap; }

.panel {
  display: grid; gap: 12px; align-content: start;
  padding: 14px; border-radius: 14px;
  background: rgba(255, 255, 255, 0.55);
  box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06);
  max-height: 520px; overflow-y: auto; overflow-x: hidden;
}
.panel-msg { padding: 10px 12px; border-radius: 10px; background: var(--surface-brand-tint); color: var(--brand-ink); font-weight: 600; }
.pgroup { display: grid; gap: 8px; }
.prow {
  display: grid; gap: 8px; padding: 10px 12px; border-radius: 10px;
  background: rgba(255, 255, 255, 0.7);
  box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.05);
}
.prow-head { display: grid; gap: 2px; }
.why {
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; cursor: help;
}
.prow-vals { display: grid; grid-template-columns: repeat(auto-fit, minmax(84px, 1fr)); gap: 8px; }
.pval, .pdelta { display: grid; gap: 4px; align-content: start; min-width: 0; overflow-wrap: anywhere; }
.approx { color: var(--state-warn); }
.no-data {
  font-weight: 600; padding: 4px 8px; border-radius: 6px;
  background: var(--state-warn-tint); color: var(--state-warn);
  min-width: 0; overflow-wrap: anywhere;
}
.eng { color: var(--ink-muted); }
.prov { display: inline-flex; }
.tone-better { box-shadow: inset 0 0 0 1px rgba(10, 107, 69, 0.28); }
.tone-better .delta-msg { color: var(--state-ok); font-weight: 700; }
.tone-worse { box-shadow: inset 0 0 0 1px rgba(180, 50, 45, 0.22); }
.tone-worse .delta-msg { color: var(--state-danger); font-weight: 700; }
.tone-neutral .delta-msg { color: var(--ink-muted); }

.summary-block { padding: 18px 20px; display: grid; gap: var(--space-5); }
.summary-block > * { position: relative; z-index: 1; }
.summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-4); }
.sum { display: grid; padding: 16px 18px; }
.open-list { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.park-break ul { margin: 6px 0 0; padding-left: 18px; display: grid; gap: 4px; }
.vendor .link { color: var(--link); font-weight: 600; margin-left: 4px; }
.strong { font-weight: 700; color: var(--ink-strong); }

@media (max-width: 1100px) {
  .subrow { grid-template-columns: 1fr; }
  .summary { grid-template-columns: 1fr 1fr; }
  .prow-vals { grid-template-columns: 1fr; }
}
</style>
