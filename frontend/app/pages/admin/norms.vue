<script setup lang="ts">
import { PhLockSimple, PhFloppyDisk, PhClockCounterClockwise } from '@phosphor-icons/vue'
import { norms } from '~/data/projects'

definePageMeta({ layout: 'admin' })
useHead({ title: 'Админка · Нормативы' })

const history = [
  { at: '12 сен 2026', who: 'Д. Максимов', what: 'ФОТ комплектовщика: 3 600 000 → 3 900 000 ₽/год', why: 'Обновление по HeadHunter Q2 2026' },
  { at: '3 сен 2026', who: 'А. Петрова', what: 'Тариф на электроэнергию: 6,9 → 7,2 ₽/кВт·ч', why: 'Средний коммерческий тариф МО с 1 июля' },
  { at: '2 сен 2026', who: 'система', what: 'Инициализация 7 нормативов из каталога организатора', why: 'Импорт v2026.09.1' },
]
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Нормативы" title="Коэффициенты и допущения расчёта" lead="Каждый норматив с обоснованием и источником. Смена норматива меняет версию расчётной модели: старые отчёты остаются на старой версии.">
      <UiButton><template #icon><PhFloppyDisk :size="16" weight="bold" /></template>Сохранить как модель 1.4.0</UiButton>
    </AdminHead>

    <UiCallout tone="warn" title="Изменения затронут новые расчёты">Текущая модель 1.3.2 используется в 4 проектах. Сохранение создаст версию 1.4.0, проекты продолжат ссылаться на 1.3.2 до пересчёта.</UiCallout>

    <div class="tbl glass glass-xl" v-reveal>
      <div class="t-in">
        <div class="nrow head caption"><span>Норматив</span><span>Значение</span><span>Единица</span><span>Обоснование</span><span>Источник</span></div>
        <div v-for="n in norms" :key="n.key" class="nrow">
          <span class="nm"><span class="body strong">{{ n.label }}</span><span class="mono-sm code">{{ n.key }}</span></span>
          <span class="val"><input class="input input-mono" :value="n.value" :disabled="!n.editable"><PhLockSimple v-if="!n.editable" :size="14" class="lock" /></span>
          <span class="mono-sm">{{ n.unit }}</span>
          <span class="body-sm">{{ n.rationale }}</span>
          <span><UiSourceTag :source-id="n.sourceId" align="right" /></span>
        </div>
      </div>
    </div>

    <section class="hist glass" v-reveal="1">
      <div class="h-in">
        <div class="h4"><PhClockCounterClockwise :size="16" /> История изменений</div>
        <div v-for="h in history" :key="h.at + h.what" class="hrow">
          <span class="mono-sm muted">{{ h.at }}</span>
          <span class="body-sm strong">{{ h.who }}</span>
          <span class="body-sm">{{ h.what }}<span class="caption block">{{ h.why }}</span></span>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.tbl { padding: var(--space-3); }
.t-in { position: relative; z-index: 1; display: grid; gap: 4px; }
.nrow { display: grid; grid-template-columns: 1.4fr 150px 90px 2fr 60px; gap: var(--space-4); align-items: center; padding: 12px 14px; border-radius: 12px; }
.nrow.head { padding-bottom: 4px; }
.nrow:not(.head):hover { background: rgba(255, 255, 255, 0.55); }
.nm { display: grid; gap: 4px; justify-items: start; }
.code { color: var(--ink-muted); padding: 2px 6px; border-radius: 5px; background: rgba(15, 20, 19, 0.05); }
.val { position: relative; display: flex; align-items: center; }
.lock { position: absolute; right: 10px; color: var(--ink-faint); }
.hist .h-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: 12px; }
.h4 { display: inline-flex; gap: 8px; align-items: center; }
.hrow { display: grid; grid-template-columns: 110px 130px 1fr; gap: var(--space-4); align-items: start; padding-top: 12px; border-top: 1px solid var(--border-hairline); }
.block { display: block; }
</style>
