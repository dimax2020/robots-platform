<script setup lang="ts">
import { PhUploadSimple, PhFileXls, PhCheckCircle, PhWarningCircle, PhArrowRight, PhLinkSimple } from '@phosphor-icons/vue'

definePageMeta({ layout: 'admin' })
useHead({ title: 'Админка · Импорт' })

const step = ref(2)
const columns = [
  { src: 'Наименование продукта', dst: 'name', ok: true },
  { src: 'Производитель', dst: 'manufacturer', ok: true },
  { src: 'Юр. лицо', dst: 'legal_entity', ok: true },
  { src: 'Статус (эксплуатация/пилот/разработка)', dst: 'availability', ok: true },
  { src: 'УГТ', dst: 'trl', ok: true },
  { src: 'Грузоподъемность, кг', dst: 'payload_kg', ok: true },
  { src: 'Макс. скорость', dst: 'speed_ms', ok: true, note: 'км/ч → м/с' },
  { src: 'Автономность (часов)', dst: 'autonomy_h', ok: true },
  { src: 'Стоимость (руб.)', dst: 'price_rub', ok: true },
  { src: 'Комментарий эксперта', dst: '', ok: false },
]
const files = [
  { name: 'Каталог категории 1-2.xlsx', rows: 22, at: '2 сен', status: 'done' },
  { name: 'Каталог категории 7-9.xlsx', rows: 41, at: '2 сен', status: 'done' },
  { name: 'Каталог категории 7-9 v2.xlsx', rows: 44, at: '18 сен', status: 'done' },
]
const drag = ref(false)
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Импорт" title="Импорт каталога из XLS" lead="Загрузка файла, сопоставление колонок со справочником, проверка и отправка в очередь правок. Импорт никогда не пишет в каталог напрямую." />

    <ol class="steps" v-reveal>
      <li v-for="(s, i) in ['Файл', 'Сопоставление колонок', 'Проверка', 'В очередь']" :key="s" :class="{ on: i + 1 === step, done: i + 1 < step }"><span class="mono-sm n">{{ i + 1 }}</span><span class="body-sm strong">{{ s }}</span></li>
    </ol>

    <div class="grid">
      <div class="main-col">
        <div class="drop glass" :class="{ drag }" @dragover.prevent="drag = true" @dragleave="drag = false" @drop.prevent="drag = false" v-reveal>
          <div class="d-in">
            <div class="d-ic"><PhFileXls :size="28" weight="duotone" /></div>
            <div class="h3">Каталог категории 7-9 v2.xlsx</div>
            <div class="body-sm muted">44 строки · 31 колонка · лист «Каталог» · 1,2 МБ</div>
            <div class="d-actions"><UiButton size="sm" variant="secondary"><template #icon><PhUploadSimple :size="14" weight="bold" /></template>Заменить файл</UiButton><span class="caption">XLS, XLSX или CSV до 20 МБ</span></div>
          </div>
        </div>

        <section class="map glass glass-xl" v-reveal="1">
          <div class="m-in">
            <div class="m-head"><div><div class="h3">Сопоставление колонок</div><div class="caption">9 из 10 колонок распознаны автоматически. Нераспознанные попадут в примечание к продукту.</div></div><UiBadge tone="ok" size="sm">9 / 10</UiBadge></div>
            <div class="mrow head caption"><span>Колонка файла</span><span /><span>Поле справочника</span><span>Статус</span></div>
            <div v-for="c in columns" :key="c.src" class="mrow">
              <span class="body-sm strong">{{ c.src }}</span>
              <PhArrowRight :size="14" class="arr" />
              <select class="select"><option v-if="c.dst" selected>{{ c.dst }}</option><option :selected="!c.dst">Не импортировать</option><option>name</option><option>manufacturer</option><option>payload_kg</option><option>price_rub</option></select>
              <span v-if="c.ok" class="st ok"><PhCheckCircle :size="14" weight="fill" /> {{ c.note ?? 'Готово' }}</span><span v-else class="st warn"><PhWarningCircle :size="14" weight="fill" /> Без соответствия</span>
            </div>
            <div class="m-actions"><UiButton variant="secondary" @click="step = 1">Назад</UiButton><UiButton @click="step = 3">Проверить 44 строки<template #after><PhArrowRight :size="16" weight="bold" /></template></UiButton></div>
          </div>
        </section>
      </div>

      <aside class="side-col">
        <div class="hist glass-graphite glass-graphite-solid" v-reveal="2">
          <div class="hs-in">
            <div class="label">Загружено ранее</div>
            <div v-for="f in files" :key="f.name" class="frow"><PhFileXls :size="16" weight="duotone" /><span><span class="body-sm strong">{{ f.name }}</span><span class="caption block">{{ f.rows }} строк · {{ f.at }}</span></span><PhCheckCircle :size="16" weight="fill" class="okic" /></div>
          </div>
        </div>
        <div class="url glass" v-reveal="3">
          <div class="u-in">
            <div class="h4"><PhLinkSimple :size="16" /> Парсер по URL</div>
            <p class="body-sm muted">Ссылка на страницу производителя или дилера. Результат тоже уйдёт в очередь с цитатами и адресом.</p>
            <input class="input" placeholder="https://vendor.ru/product">
            <UiButton size="sm" variant="secondary">Запустить парсер</UiButton>
          </div>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.steps { display: flex; gap: 6px; }
.steps li { display: inline-flex; gap: 10px; align-items: center; padding: 8px 14px 8px 8px; border-radius: 999px; background: rgba(255, 255, 255, 0.5); box-shadow: inset 0 0 0 1px var(--border-hairline); color: var(--ink-muted); }
.steps li.on { background: var(--surface-graphite); color: var(--ink-on-graphite); }
.steps li.done { color: var(--ink-body); }
.n { width: 24px; height: 24px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; background: rgba(15, 20, 19, 0.06); }
.on .n { background: var(--brand-400); color: var(--brand-900); }
.done .n { background: var(--surface-brand-tint); color: var(--brand-ink); }
.grid { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: var(--space-5); align-items: start; }
.main-col, .side-col { display: grid; gap: var(--space-5); }
.drop { border: 1.5px dashed var(--border-strong); transition: border-color var(--dur-fast) var(--ease), background var(--dur-fast) var(--ease); }
.drop.drag { border-color: var(--brand-500); }
.d-in { position: relative; z-index: 1; padding: var(--space-6); display: grid; gap: 6px; justify-items: center; text-align: center; }
.d-ic { width: 56px; height: 56px; border-radius: 16px; background: var(--surface-brand-tint); color: var(--brand-700); display: grid; place-items: center; margin-bottom: 6px; }
.d-actions { display: flex; gap: 12px; align-items: center; margin-top: 8px; }
.m-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: 8px; }
.m-head { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--space-4); padding-bottom: 8px; }
.mrow { display: grid; grid-template-columns: 1.4fr auto 1fr 150px; gap: 12px; align-items: center; }
.mrow.head { padding-top: 6px; }
.arr { color: var(--ink-faint); }
.st { display: inline-flex; gap: 6px; align-items: center; font-size: 13px; font-weight: 600; }
.st.ok { color: var(--state-ok); }
.st.warn { color: var(--state-warn); }
.m-actions { display: flex; justify-content: space-between; padding-top: var(--space-4); margin-top: 4px; border-top: 1px solid var(--border-hairline); }
.hs-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: 12px; }
.hs-in .label { color: var(--brand-300); }
.frow { display: grid; grid-template-columns: auto 1fr auto; gap: 10px; align-items: center; color: var(--ink-on-graphite); }
.frow .caption { color: var(--ink-muted-graphite); }
.frow > svg:first-child { color: var(--brand-300); }
.okic { color: var(--brand-400); }
.block { display: block; }
.u-in { position: relative; z-index: 1; padding: var(--space-5); display: grid; gap: 10px; justify-items: start; }
.h4 { display: inline-flex; gap: 8px; align-items: center; }
.u-in .input { width: 100%; }
@media (max-width: 1100px) { .grid { grid-template-columns: 1fr; } }
</style>
