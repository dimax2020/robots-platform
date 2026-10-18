<script setup lang="ts">
import { PhArrowRight, PhBuildings, PhFirstAid, PhAirplaneTilt, PhWarehouse, PhRobot } from '@phosphor-icons/vue'
import type { Component } from 'vue'
import { processIcon } from '~/data/processIcons'

/** Инфографика главной: объект → процессы → фильтры → роботы. Объекты и процессы — из справочника платформы. */
interface Tree {
  objects: { code: string; name: string; in_match?: boolean; processes: string[] }[]
  processes: { code: string; name: string; product_count: number }[]
}
const props = defineProps<{ tree: Tree | null }>()

const objectIcons: Record<string, Component> = { warehouse: PhWarehouse, airport: PhAirplaneTilt, hospital: PhFirstAid }
const fallback = [
  { code: 'warehouse', name: 'Склад' },
  { code: 'airport', name: 'Аэропорт' },
  { code: 'hospital', name: 'Медучреждение' },
]
const objects = computed(() => {
  const rows = props.tree?.objects.filter((item) => item.in_match) ?? []
  return rows.length ? rows.map((item) => ({ code: item.code, name: item.name })) : fallback
})
const objectCode = ref('warehouse')
watch(objects, (rows) => { if (!rows.some((item) => item.code === objectCode.value)) objectCode.value = rows[0]?.code ?? '' }, { immediate: true })

const processes = computed(() => {
  const tree = props.tree
  const object = tree?.objects.find((item) => item.code === objectCode.value)
  if (!tree || !object) return []
  const byCode = new Map(tree.processes.map((item) => [item.code, item]))
  return object.processes
    .map((code) => byCode.get(code))
    .filter((item): item is Tree['processes'][number] => Boolean(item))
    .sort((a, b) => b.product_count - a.product_count)
})
const shown = computed(() => processes.value.slice(0, 6))
const processCode = ref('')
watch(shown, (rows) => { if (!rows.some((item) => item.code === processCode.value)) processCode.value = rows[0]?.code ?? '' }, { immediate: true })
const process = computed(() => processes.value.find((item) => item.code === processCode.value) ?? null)

/* Примеры фильтров: так администратор настраивает процесс — поле объекта против характеристики робота. */
const filters = [
  { site: 'Ширина проходов', op: '≥', robot: 'Ширина робота' },
  { site: 'Масса груза', op: '≤', robot: 'Грузоподъёмность' },
  { site: 'Длительность смены', op: '≤', robot: 'Время работы' },
  { site: 'Лимит шума', op: '≥', robot: 'Уровень шума' },
]
const verdicts = [
  { label: 'Подходит', tone: 'ok', text: 'прошёл все фильтры' },
  { label: 'С условием', tone: 'warn', text: 'подойдёт с оговоркой' },
  { label: 'Уточнить', tone: 'info', text: 'не хватает данных' },
  { label: 'Не подходит', tone: 'danger', text: 'не прошёл фильтр' },
]
const robots = (n: number) => {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return 'робот'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'робота'
  return 'роботов'
}
</script>

<template>
  <div class="model">
    <div class="col" v-reveal="0">
      <div class="col-head"><span class="n">1</span>Объект</div>
      <div class="list">
        <button v-for="o in objects" :key="o.code" type="button" class="item" :class="{ on: o.code === objectCode }" @click="objectCode = o.code">
          <component :is="objectIcons[o.code] ?? PhBuildings" :size="20" weight="duotone" />
          <span>{{ o.name }}</span>
        </button>
      </div>
      <p class="note">У каждого объекта свой набор процессов и свои параметры площадки.</p>
    </div>

    <span class="link" aria-hidden="true"><PhArrowRight :size="16" weight="bold" /></span>

    <div class="col" v-reveal="1">
      <div class="col-head"><span class="n">2</span>Процессы объекта</div>
      <div class="list">
        <button v-for="p in shown" :key="p.code" type="button" class="item" :class="{ on: p.code === processCode }" @click="processCode = p.code">
          <component :is="processIcon(p.code)" :size="20" weight="duotone" />
          <span class="clip">{{ p.name }}</span>
        </button>
        <span v-if="processes.length > shown.length" class="more">и ещё {{ processes.length - shown.length }}</span>
        <span v-if="!shown.length" class="more">Справочник загружается…</span>
      </div>
      <p class="note">Каталог роботов разложен по процессам: уборка, доставка, перевозка паллет и другие.</p>
    </div>

    <span class="link" aria-hidden="true"><PhArrowRight :size="16" weight="bold" /></span>

    <div class="col" v-reveal="2">
      <div class="col-head"><span class="n">3</span>Фильтры процесса</div>
      <div class="list">
        <div v-for="f in filters" :key="f.site" class="rule">
          <span class="chip site">{{ f.site }}</span>
          <span class="op">{{ f.op }}</span>
          <span class="chip bot">{{ f.robot }}</span>
        </div>
      </div>
      <p class="note"><span class="dot site" /> из параметров объекта · <span class="dot bot" /> из карточки робота</p>
    </div>

    <span class="link" aria-hidden="true"><PhArrowRight :size="16" weight="bold" /></span>

    <div class="col" v-reveal="3">
      <div class="col-head"><span class="n">4</span>Роботы каталога</div>
      <div class="count">
        <PhRobot :size="26" weight="duotone" />
        <span class="count-n">{{ process?.product_count ?? '—' }}</span>
        <span class="count-t">{{ process ? `${robots(process.product_count)} для процесса «${process.name}»` : 'роботов для процесса' }}</span>
      </div>
      <div class="list">
        <div v-for="v in verdicts" :key="v.label" class="verdict" :class="v.tone">
          <span class="v-dot" /><span class="v-label">{{ v.label }}</span><span class="v-text">{{ v.text }}</span>
        </div>
      </div>
      <p class="note">Каждый робот получает вердикт с причиной. Подходящие идут в сравнение и экономику.</p>
    </div>
  </div>
</template>

<style scoped>
.model { position: relative; z-index: 1; display: grid; grid-template-columns: minmax(0, 1fr) 28px minmax(0, 1fr) 28px minmax(0, 1fr) 28px minmax(0, 1fr); gap: 12px; align-items: stretch; }
.col { display: grid; grid-template-rows: auto 1fr auto; gap: 14px; padding: 20px; border-radius: 20px; background: rgba(255, 255, 255, 0.05); box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.1); }
.col-head { display: flex; align-items: center; gap: 10px; font-size: 15px; font-weight: 700; color: var(--ink-on-graphite); }
.n { width: 26px; height: 26px; border-radius: 8px; display: inline-flex; align-items: center; justify-content: center; font-family: var(--font-mono); font-size: 13px; background: var(--brand-400); color: var(--brand-900); }
.list { display: grid; gap: 8px; align-content: start; }
.item { display: flex; align-items: center; gap: 10px; min-width: 0; padding: 10px 12px; border-radius: 12px; text-align: left; font-size: 14px; font-weight: 600; color: rgba(241, 245, 243, 0.8); background: rgba(255, 255, 255, 0.04); box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08); transition: background var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease); }
.item svg { flex: none; color: rgba(241, 245, 243, 0.55); }
.item:hover { background: rgba(255, 255, 255, 0.08); color: #fff; }
.item.on { color: #fff; background: rgba(43, 209, 141, 0.16); box-shadow: inset 0 0 0 1.5px var(--brand-400); }
.item.on svg { color: var(--brand-300); }
.clip { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.more { font-size: 13px; color: rgba(241, 245, 243, 0.55); padding: 2px 4px; }
.rule { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; padding: 10px 12px; border-radius: 12px; background: rgba(255, 255, 255, 0.04); box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.08); }
.chip { padding: 3px 8px; border-radius: 8px; font-size: 12px; font-weight: 700; }
.chip.site { background: rgba(43, 209, 141, 0.16); color: var(--brand-200); }
.chip.bot { background: rgba(120, 170, 255, 0.16); color: #b9d3ff; }
.op { font-family: var(--font-mono); font-weight: 700; color: #fff; }
.dot { display: inline-block; width: 8px; height: 8px; border-radius: 3px; vertical-align: middle; }
.dot.site { background: var(--brand-300); }
.dot.bot { background: #8fb6ff; }
.count { display: grid; grid-template-columns: auto 1fr; column-gap: 10px; align-items: center; padding: 12px 14px; border-radius: 14px; background: rgba(43, 209, 141, 0.12); color: var(--brand-300); }
.count-n { font-family: var(--font-display); font-size: 34px; line-height: 1; color: #fff; }
.count-t { grid-column: 1 / -1; margin-top: 6px; font-size: 13px; color: rgba(241, 245, 243, 0.75); }
.verdict { display: grid; grid-template-columns: auto auto 1fr; gap: 8px; align-items: center; font-size: 13px; color: rgba(241, 245, 243, 0.7); }
.v-dot { width: 10px; height: 10px; border-radius: 50%; }
.v-label { font-weight: 700; color: #fff; }
.ok .v-dot { background: #36c98a; }
.warn .v-dot { background: #f0b14a; }
.info .v-dot { background: #6ea8ff; }
.danger .v-dot { background: #f06a5f; }
.note { margin: 0; font-size: 13px; line-height: 1.5; color: rgba(241, 245, 243, 0.6); }
.link { align-self: center; width: 28px; height: 28px; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center; background: var(--brand-400); color: var(--brand-900); }
@media (max-width: 1100px) {
  .model { grid-template-columns: 1fr; }
  .link { justify-self: center; transform: rotate(90deg); }
}
</style>
