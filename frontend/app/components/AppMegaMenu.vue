<script setup lang="ts">
import {
  PhArrowRight, PhArrowUpRight, PhX, PhScales, PhPlus, PhPlay, PhLockSimple,
  PhSquaresFour, PhPackage, PhTray, PhBookOpenText, PhCalculator, PhLinkSimple, PhUploadSimple, PhRocketLaunch,
} from '@phosphor-icons/vue'
import { countNode, availabilityLabel, availabilityTone, formatRub } from '~/data/catalog'
import { projects, objectTypeLabel, objectTypeImage, steps, isFullPath, proposals, fullPathSteps, shortPathSteps, type ObjectType } from '~/data/projects'

export type MenuId = 'catalog' | 'projects' | 'compare' | 'admin'
defineProps<{ menu: MenuId }>()

const { role } = useRole()
const { ids, toggle, clear } = useCompare()
const { products, catalogTree, sources } = useCatalog()
const byId = (id: string) => products.value.find((p) => p.id === id)

/* Каталог */
const objectsList = computed(() =>
  catalogTree.value.flatMap((ind) => (ind.children ?? []).map((obj) => ({ industry: ind.label, label: obj.label, count: countNode(obj) })))
    .sort((a, b) => b.count - a.count)
    .slice(0, 8),
)
const uniq = (level: 'process' | 'solution') => {
  const map = new Map<string, Set<string>>()
  const walk = (n: { label: string; children?: any[]; productIds?: string[] }, depth: number) => {
    const target = level === 'process' ? 2 : 3
    if (depth === target) {
      const s = map.get(n.label) ?? new Set<string>()
      const collect = (x: any) => { x.productIds?.forEach((id: string) => s.add(id)); x.children?.forEach(collect) }
      collect(n)
      map.set(n.label, s)
      return
    }
    n.children?.forEach((c) => walk(c, depth + 1))
  }
  catalogTree.value.forEach((n) => walk(n, 0))
  return [...map.entries()].map(([label, s]) => ({ label, count: s.size })).sort((a, b) => b.count - a.count)
}
const processes = computed(() => uniq('process').slice(0, 8))
const solutions = computed(() => uniq('solution').slice(0, 8))
// Витрина меню — самые полные карточки каталога, а не фиксированный список id
const featured = computed(() =>
  [...products.value].sort((a, b) => b.completeness - a.completeness || b.trl - a.trl).slice(0, 2),
)
const autoCount = computed(() => products.value.filter((p) => p.autoMatch).length)

/* Проекты */
const objectMeta: Record<ObjectType, { text: string; full: boolean }> = {
  warehouse: { text: 'Полный путь до отчёта и 2D-плана', full: true },
  airport: { text: 'Параметры площадки и подбор', full: false },
  hospital: { text: 'Параметры корпуса и подбор', full: false },
}
const objectTypes = Object.keys(objectTypeLabel) as ObjectType[]
const demos = projects.filter((p) => p.isDemo)
const mine = computed(() => (role.value === 'guest' ? [] : projects.filter((p) => !p.isDemo)))
const stepOf = (p: (typeof projects)[number]) => steps[Math.min(p.step, steps.length) - 1]?.label ?? 'Параметры'
const total = (p: (typeof projects)[number]) => (isFullPath(p) ? fullPathSteps : shortPathSteps)
const fmtDate = (d: string) => new Date(d).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })

/* Сравнение */
const compareItems = computed(() => ids.value.map(byId).filter(Boolean) as NonNullable<ReturnType<typeof byId>>[])

/* Админка */
const pending = proposals.filter((p) => p.status === 'pending').length
const adminItems = computed(() => [
  { to: '/admin', label: 'Обзор', icon: PhSquaresFour, note: 'Состояние каталога' },
  { to: '/admin/products', label: 'Продукты', icon: PhPackage, note: `${products.value.length} карточек` },
  { to: '/admin/proposals', label: 'Очередь правок', icon: PhTray, note: `${pending} ждут решения`, hot: pending > 0 },
  { to: '/admin/refs', label: 'Справочники', icon: PhBookOpenText, note: 'Отрасли, объекты, процессы' },
  { to: '/admin/norms', label: 'Нормативы', icon: PhCalculator, note: 'Коэффициенты расчёта' },
  { to: '/admin/sources', label: 'Источники', icon: PhLinkSimple, note: `${sources.value.length} в реестре` },
  { to: '/admin/import', label: 'Импорт', icon: PhUploadSimple, note: 'XLS и парсер по URL' },
  { to: '/admin/publish', label: 'Публикация', icon: PhRocketLaunch, note: 'v2026.09.3 · черновик' },
])
</script>

<template>
  <div class="mm" :class="`mm-${menu}`">
    <!-- ================= Каталог ================= -->
    <template v-if="menu === 'catalog'">
      <div class="col">
        <div class="col-head"><span class="label">Отрасль и объект</span></div>
        <NuxtLink v-for="o in objectsList" :key="o.industry + o.label" to="/catalog" class="row">
          <span class="row-main"><span class="row-t">{{ o.label }}</span><span class="row-s">{{ o.industry }}</span></span>
          <span class="row-n mono-sm">{{ o.count }}</span>
        </NuxtLink>
      </div>
      <div class="col">
        <div class="col-head"><span class="label">Процесс</span></div>
        <NuxtLink v-for="p in processes" :key="p.label" to="/catalog" class="row slim">
          <span class="row-t">{{ p.label }}</span><span class="row-n mono-sm">{{ p.count }}</span>
        </NuxtLink>
      </div>
      <div class="col">
        <div class="col-head"><span class="label">Тип решения</span></div>
        <NuxtLink v-for="s in solutions" :key="s.label" to="/catalog" class="row slim">
          <span class="row-t">{{ s.label }}</span><span class="row-n mono-sm">{{ s.count }}</span>
        </NuxtLink>
      </div>
      <div class="col feat">
        <div class="col-head"><span class="label">Часто открывают</span></div>
        <NuxtLink v-for="p in featured" :key="p.id" :to="`/catalog/${p.slug}`" class="prod">
          <img :src="p.image" :alt="p.name">
          <span class="prod-body">
            <span class="row-t">{{ p.name }}</span>
            <span class="row-s">{{ p.solutionType }} · {{ p.manufacturer }}</span>
            <span class="prod-foot"><UiBadge :tone="availabilityTone[p.availability]" size="sm">{{ availabilityLabel[p.availability] }}</UiBadge><span class="mono-sm">{{ formatRub(p.priceRub) }}</span></span>
          </span>
          <PhArrowUpRight :size="16" weight="bold" class="prod-go" />
        </NuxtLink>
        <NuxtLink to="/catalog" class="cta glass-graphite glass-graphite-solid">
          <span class="cta-in">
            <span class="cta-n display-4">{{ products.length }}</span>
            <span class="cta-t">решений в каталоге<span class="cta-s">{{ autoCount }} готовы к автоподбору · УГТ ≥ 7</span></span>
            <PhArrowRight :size="18" weight="bold" />
          </span>
        </NuxtLink>
      </div>
      <div class="foot">
        <span class="caption">Дерево: отрасль → объект → процесс → тип решения → продукт. Продукт может стоять в нескольких ветках без дублей.</span>
        <span class="foot-links">
          <NuxtLink to="/catalog/compare" class="fl"><PhScales :size="14" weight="bold" /> Сравнение <span class="mono-sm">{{ ids.length }}</span></NuxtLink>
          <NuxtLink to="/admin/sources" class="fl">Достоверность A–D</NuxtLink>
        </span>
      </div>
    </template>

    <!-- ================= Проекты ================= -->
    <template v-else-if="menu === 'projects'">
      <div class="col">
        <div class="col-head"><span class="label">Новый проект</span><NuxtLink to="/projects/new" class="col-link">Мастер <PhArrowRight :size="12" weight="bold" /></NuxtLink></div>
        <NuxtLink v-for="k in objectTypes" :key="k" :to="`/projects/new?type=${k}`" class="tile">
          <img :src="objectTypeImage[k]" :alt="objectTypeLabel[k]">
          <span class="tile-body">
            <span class="row-t">{{ objectTypeLabel[k] }}</span>
            <span class="row-s">{{ objectMeta[k].text }}</span>
          </span>
          <UiBadge :tone="objectMeta[k].full ? 'ok' : 'info'" size="sm">{{ objectMeta[k].full ? 'Полный' : 'Подбор' }}</UiBadge>
        </NuxtLink>
      </div>
      <div class="col">
        <div class="col-head"><span class="label">Демо-площадки</span><span class="caption">без входа</span></div>
        <NuxtLink v-for="d in demos" :key="d.id" :to="`/projects/${d.id}`" class="row">
          <span class="row-main">
            <span class="row-t">{{ d.name }}</span>
            <span class="row-s">{{ objectTypeLabel[d.objectType] }} · {{ d.area?.toLocaleString('ru-RU') }} м² · {{ d.shifts }} смены</span>
          </span>
          <span class="prog" :title="`Шаг ${d.step} из ${total(d)}`"><i v-for="i in total(d)" :key="i" :class="{ on: i <= d.step }" /></span>
        </NuxtLink>
      </div>
      <div class="col">
        <div class="col-head"><span class="label">Мои проекты</span><NuxtLink v-if="mine.length" to="/projects" class="col-link">Все <PhArrowRight :size="12" weight="bold" /></NuxtLink></div>
        <template v-if="mine.length">
          <NuxtLink v-for="p in mine" :key="p.id" :to="`/projects/${p.id}`" class="row">
            <span class="row-main"><span class="row-t">{{ p.name }}</span><span class="row-s">{{ stepOf(p) }} · {{ fmtDate(p.updatedAt) }}</span></span>
            <span class="row-n mono-sm">{{ p.step }}/{{ total(p) }}</span>
          </NuxtLink>
          <NuxtLink to="/projects/new" class="row add"><PhPlus :size="16" weight="bold" /><span class="row-t">Создать проект</span></NuxtLink>
        </template>
        <NuxtLink v-else to="/login" class="cta glass-graphite glass-graphite-solid tall">
          <span class="cta-in col-in">
            <PhLockSimple :size="22" weight="duotone" class="cta-ic" />
            <span class="cta-t">Войдите, чтобы сохранять проекты<span class="cta-s">Гость проходит демо без сохранения. Пользователь ведёт свои площадки и возвращается к расчёту на той же версии каталога.</span></span>
            <span class="cta-btn">Войти под ролью <PhArrowRight :size="14" weight="bold" /></span>
          </span>
        </NuxtLink>
      </div>
      <div class="foot">
        <span class="flow mono-sm"><template v-for="(s, i) in steps" :key="s.code"><span>{{ s.label }}</span><i v-if="i < steps.length - 1" /></template></span>
        <NuxtLink to="/projects/demo-warehouse/report" class="fl"><PhPlay :size="14" weight="fill" /> Демо-отчёт склада</NuxtLink>
      </div>
    </template>

    <!-- ================= Сравнение ================= -->
    <template v-else-if="menu === 'compare'">
      <div class="col wide">
        <div class="col-head"><span class="label">В сравнении</span><span class="caption">{{ compareItems.length }} из 6</span></div>
        <div v-if="compareItems.length" class="cmp-list">
          <div v-for="p in compareItems" :key="p.id" class="cmp">
            <NuxtLink :to="`/catalog/${p.slug}`" class="cmp-link">
              <img :src="p.image" :alt="p.name">
              <span class="row-main"><span class="row-t">{{ p.name }}</span><span class="row-s">{{ p.solutionType }} · {{ p.manufacturer }}</span></span>
            </NuxtLink>
            <button type="button" class="rm" :aria-label="`Убрать ${p.name}`" @click="toggle(p.id)"><PhX :size="12" weight="bold" /></button>
          </div>
        </div>
        <div v-else class="empty">
          <span class="row-t">Список пуст</span>
          <span class="row-s">Добавьте модели из каталога кнопкой «Сравнить» на карточке.</span>
          <NuxtLink to="/catalog" class="fl">Открыть каталог <PhArrowRight :size="12" weight="bold" /></NuxtLink>
        </div>
      </div>
      <div class="col">
        <div class="cta glass-graphite glass-graphite-solid tall static">
          <span class="cta-in col-in">
            <span class="cta-n display-3">{{ compareItems.length }}</span>
            <span class="cta-t">{{ compareItems.length === 1 ? 'модель' : compareItems.length < 5 ? 'модели' : 'моделей' }} к сравнению<span class="cta-s">Таблица по одним и тем же полям справочника. Пустые значения показаны как «нет данных», не как ноль.</span></span>
            <span class="cta-actions">
              <UiButton to="/catalog/compare" size="sm" :disabled="compareItems.length < 2"><template #icon><PhScales :size="14" weight="bold" /></template>Открыть таблицу</UiButton>
              <UiButton v-if="compareItems.length" variant="onGraphite" size="sm" @click="clear">Очистить</UiButton>
            </span>
          </span>
        </div>
      </div>
    </template>

    <!-- ================= Админка ================= -->
    <template v-else>
      <NuxtLink v-for="a in adminItems" :key="a.to" :to="a.to" class="adm">
        <component :is="a.icon" :size="22" weight="duotone" class="adm-ic" />
        <span class="row-t">{{ a.label }}</span>
        <span class="row-s" :class="{ hot: a.hot }">{{ a.note }}</span>
      </NuxtLink>
      <div class="foot">
        <span class="caption">Парсер и импорт пишут в очередь правок. В каталог попадает только опубликованная версия.</span>
        <NuxtLink to="/admin/publish" class="fl"><PhRocketLaunch :size="14" weight="fill" /> К публикации v2026.09.3</NuxtLink>
      </div>
    </template>
  </div>
</template>

<style scoped>
.mm { position: relative; z-index: 1; display: grid; gap: var(--space-6) var(--space-8); padding: var(--space-6) var(--space-7, 28px) var(--space-5); }
.mm-catalog { grid-template-columns: 1.1fr 1fr 1fr 1.4fr; }
.mm-projects { grid-template-columns: 1.2fr 1.2fr 1fr; }
.mm-compare { grid-template-columns: 1.6fr 1fr; }
.mm-admin { grid-template-columns: repeat(4, 1fr); gap: var(--space-3); }
.mm-admin .foot { grid-column: 1 / -1; }

.col { display: grid; gap: 4px; align-content: start; min-width: 0; }
.col-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; padding: 0 10px 8px; }
.col-link { display: inline-flex; align-items: center; gap: 4px; font-size: 13px; font-weight: 700; color: var(--link); }

.row { display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: center; padding: 8px 10px; border-radius: 12px; transition: background var(--dur-fast) var(--ease); }
.row:hover { background: rgba(15, 20, 19, 0.05); }
.row.slim { padding: 7px 10px; }
.row.add { grid-template-columns: auto 1fr; color: var(--link); }
.row-main { display: grid; gap: 2px; min-width: 0; }
.row-t { font-size: 15px; font-weight: 700; color: var(--ink-strong); line-height: 1.3; }
.row-s { font-size: 13px; color: var(--ink-muted); line-height: 1.4; }
.row-s.hot { color: var(--state-warn); font-weight: 600; }
.row-n { color: var(--ink-muted); padding: 2px 7px; border-radius: 6px; background: rgba(15, 20, 19, 0.05); }
.row:hover .row-n { background: var(--surface-brand-tint); color: var(--brand-ink); }

.prog { display: inline-flex; gap: 3px; }
.prog i { width: 10px; height: 4px; border-radius: 2px; background: rgba(15, 20, 19, 0.1); }
.prog i.on { background: var(--brand-500); }

/* Товарные мини-карточки */
.prod { display: grid; grid-template-columns: 64px 1fr auto; gap: 12px; align-items: center; padding: 8px; border-radius: 14px; transition: background var(--dur-fast) var(--ease); }
.prod:hover { background: rgba(255, 255, 255, 0.7); }
.prod img { width: 64px; height: 64px; border-radius: 12px; object-fit: cover; background: #fff; }
.prod-body { display: grid; gap: 3px; min-width: 0; }
.prod-foot { display: flex; align-items: center; gap: 8px; margin-top: 2px; color: var(--ink-strong); }
.prod-go { color: var(--ink-faint); transition: transform var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease); }
.prod:hover .prod-go { color: var(--ink-strong); transform: translate(2px, -2px); }

/* Плитки объектов */
.tile { display: grid; grid-template-columns: 56px 1fr auto; gap: 12px; align-items: center; padding: 8px; border-radius: 14px; transition: background var(--dur-fast) var(--ease); }
.tile:hover { background: rgba(15, 20, 19, 0.05); }
.tile img { width: 56px; height: 56px; border-radius: 12px; object-fit: cover; }
.tile-body { display: grid; gap: 2px; min-width: 0; }

/* Графитовые CTA */
.cta { display: block; margin-top: 6px; border-radius: 16px; transition: transform var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease); }
.cta:not(.static):hover { transform: translateY(-2px); box-shadow: inset 0 1px 0 var(--glass-g-highlight), 0 0 0 1px var(--glass-g-stroke), var(--glow-brand); }
.cta.tall { height: 100%; margin-top: 0; }
.cta-in { position: relative; z-index: 1; display: grid; grid-template-columns: auto 1fr auto; gap: 14px; align-items: center; padding: 16px 18px; color: var(--ink-on-graphite); }
.cta-in.col-in { grid-template-columns: 1fr; align-content: start; gap: 12px; padding: 20px; }
.cta-n { color: var(--brand-300); }
.cta-t { display: grid; gap: 3px; font-size: 15px; font-weight: 700; }
.cta-s { font-size: 13px; font-weight: 500; color: var(--ink-muted-graphite); line-height: 1.45; }
.cta-ic { color: var(--brand-300); }
.cta-btn { display: inline-flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 700; color: var(--brand-300); margin-top: 4px; }
.cta-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 4px; }

/* Сравнение */
.cmp-list { display: grid; grid-template-columns: repeat(2, 1fr); gap: 4px; }
.cmp { display: grid; grid-template-columns: 1fr auto; align-items: center; gap: 6px; padding-right: 6px; border-radius: 14px; transition: background var(--dur-fast) var(--ease); }
.cmp:hover { background: rgba(15, 20, 19, 0.05); }
.cmp-link { display: grid; grid-template-columns: 52px 1fr; gap: 12px; align-items: center; padding: 8px; min-width: 0; }
.cmp-link img { width: 52px; height: 52px; border-radius: 12px; object-fit: cover; background: #fff; }
.rm { width: 28px; height: 28px; border-radius: 8px; display: inline-flex; align-items: center; justify-content: center; color: var(--ink-muted); }
.rm:hover { background: var(--state-danger-tint); color: var(--state-danger); }
.empty { display: grid; gap: 6px; padding: 20px 10px; justify-items: start; }

/* Админка */
.adm { display: grid; gap: 4px; padding: 16px; border-radius: 16px; background: rgba(255, 255, 255, 0.45); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.05); transition: background var(--dur-fast) var(--ease), transform var(--dur-fast) var(--ease); }
.adm:hover { background: #fff; transform: translateY(-2px); }
.adm-ic { color: var(--brand-700); margin-bottom: 8px; }

/* Подвал панели */
.foot { grid-column: 1 / -1; display: flex; justify-content: space-between; align-items: center; gap: var(--space-6); padding-top: var(--space-4); border-top: 1px solid rgba(15, 20, 19, 0.08); }
.foot-links { display: flex; gap: 18px; flex: none; }
.fl { display: inline-flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 700; color: var(--ink-strong); }
.fl:hover { color: var(--link); }
.fl .mono-sm { padding: 1px 6px; border-radius: 5px; background: var(--brand-400); color: var(--brand-900); }
.flow { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; color: var(--ink-muted); }
.flow span { padding: 4px 8px; border-radius: 6px; background: rgba(15, 20, 19, 0.05); color: var(--ink-body); }
.flow i { width: 14px; height: 1px; background: var(--brand-500); opacity: 0.7; }
</style>
