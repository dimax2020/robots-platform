<script setup lang="ts">
import { PhPrinter, PhFileXls, PhFileCsv, PhImage, PhEnvelopeSimple, PhWarning } from '@phosphor-icons/vue'
import { scenarios, objectTypeLabel } from '~/data/projects'
import { useLiveProject } from '~/composables/useLiveProject'
import { demoProducts as products } from '~/data/demo'
import { PRELIMINARY } from '~/composables/usePlatformEconomy'

const route = useRoute()
const doc = useLiveProject(computed(() => route.params.id as string))
const project = computed(() => doc.shell.value)
useHead({ title: () => `Отчёт · ${project.value?.name ?? 'проект'}` })
const { role } = useRole()
const p = (id: string) => products.find((x) => x.id === id)!
const best = scenarios[2]!
const f = (n: number) => n.toLocaleString('ru-RU')
const f1 = (n: number) => n.toLocaleString('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const requests = [
  { product: p('p-03'), missing: ['Автономность', 'Точность позиционирования', 'Требования к полу'] },
  { product: p('p-06'), missing: ['Класс защиты'] },
  { product: p('p-08'), missing: ['Производительность', 'Класс защиты'] },
]
const limits = [
  'Производительность трёх позиций взята по аналогу класса (достоверность C), паспортных данных нет.',
  'Ровность пола 3 мм на 2 м проходит по допуску Weibot G2P-600 впритык, нужен замер на площадке.',
  'Интеграция с WMS учтена оценкой 9,8 млн ₽ без обследования ИТ-ландшафта.',
  'Дополнительный доход от роста пропускной способности показан интервалом 0–9,4 млн ₽ и не включён в центральную оценку.',
]
const print = () => { if (import.meta.client) window.print() }
const today = new Date().toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
</script>

<template>
  <ProjectShell v-if="project" :project="project" current="report" title="Отчёт" lead="Сводка сценариев, интервал окупаемости, запросы вендорам и ограничения расчёта. Печать из браузера, выгрузка таблиц в Excel или CSV.">
    <template #actions>
      <UiButton variant="secondary" @click="print"><template #icon><PhPrinter :size="16" weight="bold" /></template>Печать в PDF</UiButton>
      <UiButton variant="secondary" disabled title="Заглушка: выгрузка ещё не реализована"><template #icon><PhFileXls :size="16" weight="duotone" /></template>Excel · заглушка</UiButton>
      <UiButton variant="secondary" disabled title="Заглушка: выгрузка ещё не реализована"><template #icon><PhFileCsv :size="16" weight="duotone" /></template>CSV · заглушка</UiButton>
      <UiButton variant="secondary"><template #icon><PhImage :size="16" weight="duotone" /></template>План</UiButton>
    </template>

    <UiCallout v-if="role === 'guest'" tone="info">Это демо-отчёт. Гость может открыть и распечатать его, сохранения собственного проекта у гостя нет.</UiCallout>

    <article class="report glass glass-xl" v-reveal>
      <div class="r-in">
        <header class="r-head">
          <div>
            <div class="label">Предварительная экспресс-оценка</div>
            <h2 class="h1">{{ project.name }}</h2>
            <div class="body-sm muted">{{ objectTypeLabel[project.objectType] }} · {{ project.industry }} · {{ today }}</div>
          </div>
          <div class="r-meta mono-sm">
            <span>каталог {{ project.catalogVersion }}</span>
            <span>модель {{ project.modelVersion }}</span>
            <span>прогон #{{ project.id.replace(/\D/g, '') || '0917' }}</span>
          </div>
        </header>

        <div class="disclaimer">
          <PhWarning :size="18" weight="fill" />
          <p class="body-sm"><span class="strong">{{ PRELIMINARY }}</span> Числа опираются на каталог вендоров, параметры площадки и стандартные коэффициенты. Это гипотеза для перехода к полноценному ТЭО, не акт обследования.</p>
        </div>

        <section class="r-sec">
          <h3 class="h3">Сводка сценариев</h3>
          <table class="table">
            <thead><tr><th>Сценарий</th><th>Состав парка</th><th class="num">CAPEX, млн ₽</th><th class="num">OPEX в год</th><th class="num">Эффект в год</th><th class="num">Окупаемость, лет</th></tr></thead>
            <tbody>
              <tr v-for="s in scenarios" :key="s.id" :class="{ best: s.id === best.id }">
                <td><span class="strong">{{ s.title }}</span><div class="caption">{{ s.subtitle }}</div></td>
                <td><span v-if="s.fleet.length" class="body-sm">{{ s.fleet.map(fl => `${p(fl.productId).name} × ${fl.count}`).join(', ') }}</span><span v-else class="caption">38 сотрудников, 9 погрузчиков</span></td>
                <td class="num">{{ s.capex[1] ? `${f(s.capex[0])}–${f(s.capex[2])}` : '0' }}</td>
                <td class="num">{{ f(s.opex[0]) }}–{{ f(s.opex[2]) }}</td>
                <td class="num">{{ s.effect[1] ? `${f(s.effect[0])}–${f(s.effect[2])}` : 'не применимо' }}</td>
                <td class="num">{{ s.payback[1] ? `${f1(s.payback[0])} · ${f1(s.payback[1])} · ${f1(s.payback[2])}` : 'база' }}</td>
              </tr>
            </tbody>
          </table>
          <div class="caption">Окупаемость: нижняя · центральная · верхняя оценка. Выделен рекомендуемый сценарий. Все значения предварительные и требуют верификации при обследовании объекта.</div>
        </section>

        <section class="r-sec two">
          <div>
            <h3 class="h3">Интервал окупаемости</h3>
            <UiInterval :low="best.payback[0]" :mid="best.payback[1]" :high="best.payback[2]" :min="0" :max="6" unit="лет" />
            <p class="body-sm muted">61% ширины интервала даёт производительность Ronavi H1500, взятая по аналогу класса. Паспортное значение сузит интервал примерно до 2,7–3,6 года.</p>
          </div>
          <div>
            <h3 class="h3">Запросы вендорам</h3>
            <ul class="req">
              <li v-for="r in requests" :key="r.product.id">
                <PhEnvelopeSimple :size="16" weight="duotone" />
                <span><span class="strong body-sm">{{ r.product.manufacturer }}</span> · {{ r.product.name }}<span class="caption block">Не хватает: {{ r.missing.join(', ') }}</span></span>
              </li>
              <li><PhEnvelopeSimple :size="16" weight="duotone" /><span><span class="strong body-sm">Ronavi Robotics</span> · Ronavi H1500<span class="caption block">Паспортная производительность на палете 1 200 × 800 при маршруте 85 м</span></span></li>
            </ul>
          </div>
        </section>

        <section class="r-sec">
          <h3 class="h3">Ограничения расчёта</h3>
          <ol class="limits">
            <li v-for="(l, i) in limits" :key="i"><span class="mono-sm n">{{ i + 1 }}</span><span class="body-sm">{{ l }}</span></li>
          </ol>
        </section>

        <footer class="r-foot caption">
          <span class="strong block">{{ PRELIMINARY }}</span>
          Отчёт сформирован платформой подбора роботизированных решений. Кейс ФЦ БАС, хакатон «Лидеры цифровой трансформации», 2026. Версия каталога {{ project.catalogVersion }}, версия расчётной модели {{ project.modelVersion }}.
        </footer>
      </div>
    </article>
  </ProjectShell>
</template>

<style scoped>
.report { max-width: 1160px; }
.r-in { position: relative; z-index: 1; padding: var(--space-10); display: grid; gap: var(--space-8); }
.r-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-6); }
.r-head > div:first-child { display: grid; gap: 6px; }
.r-meta { display: grid; gap: 4px; text-align: right; color: var(--ink-muted); }
.disclaimer { display: flex; gap: 12px; align-items: flex-start; padding: 16px 18px; border-radius: 14px; background: var(--state-warn-tint); color: #5c3700; }
.disclaimer svg { flex: none; color: var(--state-warn); margin-top: 1px; }
.r-sec { display: grid; gap: var(--space-4); }
.r-sec.two { grid-template-columns: 1fr 1fr; gap: var(--space-10); align-items: start; }
.r-sec.two > div { display: grid; gap: var(--space-4); }
.table td.num, .table th.num { white-space: nowrap; }
tr.best td { background: var(--surface-brand-tint); }
tr.best td:first-child { border-radius: 10px 0 0 10px; }
tr.best td:last-child { border-radius: 0 10px 10px 0; }
.req { display: grid; gap: 10px; }
.req li { display: grid; grid-template-columns: auto 1fr; gap: 10px; align-items: start; }
.req svg { color: var(--brand-700); margin-top: 2px; }
.block { display: block; }
.limits { display: grid; gap: 10px; }
.limits li { display: grid; grid-template-columns: auto 1fr; gap: 12px; align-items: start; }
.n { width: 24px; height: 24px; border-radius: 7px; background: var(--surface-graphite); color: var(--brand-300); display: inline-flex; align-items: center; justify-content: center; }
.r-foot { padding-top: var(--space-4); border-top: 1px solid var(--border-hairline); }
@media (max-width: 1100px) { .r-sec.two { grid-template-columns: 1fr; } }
@media print { .report { max-width: none; } .r-in { padding: 0; } }
</style>
