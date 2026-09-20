<script setup lang="ts">
import { PhRocketLaunch, PhPlus, PhPencilSimple, PhMinus, PhCheckCircle, PhWarningCircle, PhClockCounterClockwise } from '@phosphor-icons/vue'

definePageMeta({ layout: 'admin' })
useHead({ title: 'Админка · Публикация' })

const changes = [
  { kind: 'edit', product: 'Weibot G2P-600', what: 'Класс защиты: нет данных → IP20', src: 'A' },
  { kind: 'edit', product: 'Ronavi H1500', what: 'Дата проверки источника обновлена', src: 'A' },
  { kind: 'add', product: 'Стриж-И', what: 'Новый продукт из каталога 7-9 v2', src: 'B' },
  { kind: 'edit', product: 'DMR 300 Carrier B', what: 'Цена: 3 200 000 → интервал 2 900 000–3 400 000 ₽', src: 'B' },
  { kind: 'edit', product: 'Легат Патрол', what: 'Скорость: 1,2 → 1,4 м/с', src: 'A' },
  { kind: 'remove', product: 'Ячейка Q', what: 'Снят с автоподбора: УГТ 6', src: '' },
]
const checks = [
  { ok: true, label: 'У всех значений в изменениях есть источник' },
  { ok: true, label: 'Обязательные поля идентификации заполнены' },
  { ok: true, label: 'Единицы измерения приведены к справочнику' },
  { ok: false, label: 'Очередь правок: 3 предложения не рассмотрены', to: '/admin/proposals' },
]
const releases = [
  { v: 'v2026.09.3', at: '20 сен 2026', by: 'черновик', n: 6, current: false },
  { v: 'v2026.09.2', at: '12 сен 2026', by: 'Д. Максимов', n: 14, current: true },
  { v: 'v2026.09.1', at: '2 сен 2026', by: 'А. Петрова', n: 63, current: false },
]
const icon = { add: PhPlus, edit: PhPencilSimple, remove: PhMinus }
const note = ref('Добавлен Стриж-И, уточнён класс защиты Weibot, цена DMR 300 переведена в интервал.')
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Публикация" title="Версия каталога v2026.09.3" lead="Каталог публикуется версиями. Каждый расчёт помнит номер версии, поэтому старые отчёты не меняются задним числом.">
      <UiButton variant="secondary">Предпросмотр</UiButton>
      <UiButton size="lg" :disabled="!checks.every(c => c.ok)"><template #icon><PhRocketLaunch :size="18" weight="fill" /></template>Опубликовать</UiButton>
    </AdminHead>

    <div class="grid">
      <div class="col">
        <section class="chg glass glass-xl" v-reveal>
          <div class="c-in">
            <div class="c-head"><div class="h3">Изменения к выпуску</div><span class="caption">{{ changes.length }} записей относительно v2026.09.2</span></div>
            <div v-for="(c, i) in changes" :key="i" class="crow">
              <span class="k" :class="c.kind"><component :is="icon[c.kind as keyof typeof icon]" :size="14" weight="bold" /></span>
              <span><span class="body-sm strong">{{ c.product }}</span><span class="caption block">{{ c.what }}</span></span>
              <span v-if="c.src" class="letter" :class="`c-${c.src}`">{{ c.src }}</span><span v-else />
            </div>
          </div>
        </section>

        <section class="note glass" v-reveal="1">
          <div class="n-in">
            <label class="field"><span class="field-label">Примечание к версии</span><textarea v-model="note" class="input ta" rows="3" /></label>
            <span class="field-hint">Показывается пользователям в списке версий и в отчётах</span>
          </div>
        </section>
      </div>

      <aside class="col">
        <section class="checks glass-graphite glass-graphite-solid" v-reveal="2">
          <div class="ck-in">
            <div class="label">Проверка перед выпуском</div>
            <div v-for="c in checks" :key="c.label" class="ck" :class="{ bad: !c.ok }">
              <PhCheckCircle v-if="c.ok" :size="18" weight="fill" /><PhWarningCircle v-else :size="18" weight="fill" />
              <span class="body-sm">{{ c.label }} <NuxtLink v-if="c.to" :to="c.to" class="ck-link">Открыть</NuxtLink></span>
            </div>
          </div>
        </section>

        <section class="rel glass" v-reveal="3">
          <div class="r-in">
            <div class="h4"><PhClockCounterClockwise :size="16" /> Версии</div>
            <div v-for="r in releases" :key="r.v" class="rrow" :class="{ cur: r.current }">
              <span class="mono-md">{{ r.v }}</span>
              <span class="caption">{{ r.at }} · {{ r.by }} · {{ r.n }} изм.</span>
              <UiBadge v-if="r.current" tone="ok" size="sm">Текущая</UiBadge>
              <UiBadge v-else-if="r.by === 'черновик'" tone="neutral" size="sm">Черновик</UiBadge>
            </div>
          </div>
        </section>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.grid { display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: var(--space-5); align-items: start; }
.col { display: grid; gap: var(--space-5); }
.c-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: 10px; }
.c-head { display: flex; justify-content: space-between; align-items: baseline; padding-bottom: 6px; }
.crow { display: grid; grid-template-columns: auto 1fr auto; gap: 12px; align-items: center; padding: 10px 0; border-top: 1px solid var(--border-hairline); }
.k { width: 28px; height: 28px; border-radius: 8px; display: inline-flex; align-items: center; justify-content: center; }
.k.add { background: var(--surface-brand-tint); color: var(--brand-ink); }
.k.edit { background: rgba(15, 20, 19, 0.06); color: var(--ink-body); }
.k.remove { background: var(--state-danger-tint); color: var(--state-danger); }
.block { display: block; }
.letter { width: 24px; height: 24px; border-radius: 7px; display: inline-flex; align-items: center; justify-content: center; font-family: var(--font-mono); font-weight: 700; font-size: 12px; }
.c-A { background: var(--surface-graphite); color: var(--brand-300); }
.c-B { background: var(--surface-brand-tint); color: var(--brand-ink); }
.n-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: 6px; }
.ta { resize: vertical; min-height: 84px; padding-top: 10px; line-height: 1.5; }
.ck-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: 12px; }
.ck-in .label { color: var(--brand-300); }
.ck { display: grid; grid-template-columns: auto 1fr; gap: 10px; align-items: start; color: var(--ink-on-graphite); }
.ck svg { color: var(--brand-400); margin-top: 1px; }
.ck.bad svg { color: var(--state-warn); }
.ck-link { color: var(--brand-300); text-decoration: underline; text-underline-offset: 3px; margin-left: 4px; }
.r-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: 10px; }
.h4 { display: inline-flex; gap: 8px; align-items: center; }
.rrow { display: grid; grid-template-columns: 1fr auto; gap: 2px 10px; align-items: center; padding: 10px 12px; border-radius: 10px; }
.rrow .caption { grid-column: 1; }
.rrow > :nth-child(3) { grid-column: 2; grid-row: 1 / span 2; }
.rrow.cur { background: var(--surface-brand-tint); }
@media (max-width: 1100px) { .grid { grid-template-columns: 1fr; } }
</style>
