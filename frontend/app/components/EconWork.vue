<script setup lang="ts">
import type { EconWork } from '~/composables/usePlatformEconomy'

/** Работа процесса в операциях: сколько её, сколько делает человек и робот, сколько забирают роботы. */
const props = defineProps<{ work: EconWork; byCost?: boolean; manualNote?: string; fteHours?: number; busy?: boolean; editable?: boolean }>()
const emit = defineEmits<{ rate: [number | null] }>()

/* Выработка робота: из карточки по формуле подбора или своя — по паспорту или опыту вендора. */
const editing = ref(false)
const typed = ref<number | null>(null)
const startEdit = () => {
  typed.value = props.work.robot_rate_raw ? Math.round(props.work.robot_rate_raw * 10) / 10 : null
  editing.value = true
}
const saveRate = () => {
  if (!typed.value || typed.value <= 0) return
  emit('rate', typed.value)
  editing.value = false
}

const fmt = (value: number | null | undefined, digits = 1) => value == null ? '—' : value.toLocaleString('ru-RU', { maximumFractionDigits: digits })
/* «1 паллета», «3 паллеты», «12 паллет». */
const unit = (value: number) => {
  const n = Math.abs(Math.round(value))
  const mod10 = n % 10
  const mod100 = n % 100
  if (!Number.isInteger(value) && Math.round(value) !== value) return props.work.unit[1]
  if (mod10 === 1 && mod100 !== 11) return props.work.unit[0]
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return props.work.unit[1]
  return props.work.unit[2]
}
const big = (value: number | null | undefined) => {
  if (value == null) return '—'
  if (value >= 1e6) return `${fmt(value / 1e6)} млн`
  if (value >= 1e4) return `${fmt(value / 1e3, 0)} тыс.`
  return fmt(value, 0)
}
const many = computed(() => props.work.unit[2])
/* Сравниваем за год: робот ненамного быстрее человека в час, но работает все часы площадки, а человек — норму по ТК РФ. */
const personHours = computed(() => props.fteHours ?? 1810)
const personYear = computed(() => props.work.person_rate != null ? props.work.person_rate * personHours.value : null)
const robotHours = computed(() => props.work.robot_rate && props.work.robot_year ? props.work.robot_year / props.work.robot_rate : null)
const coverage = computed(() => props.work.coverage ?? 0)
const manual = computed(() => Math.max(0, 1 - props.work.auto))
const idle = computed(() => Math.max(0, props.work.auto - coverage.value))
const extra = computed(() => props.work.robots_full != null && props.work.robots > props.work.robots_full ? props.work.robots - props.work.robots_full : 0)
const robotsWord = (n: number) => {
  const mod10 = n % 10
  const mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return 'робот'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'робота'
  return 'роботов'
}
</script>

<template>
  <section class="work">
    <span class="label">Работа процесса</span>
    <div class="flow">
      <div class="vol">
        <span class="big">{{ big(work.per_day) }} <small>{{ work.per_day != null ? unit(work.per_day) : '' }} в сутки</small></span>
        <span class="caption">{{ big(work.volume_year) }} в год · {{ work.volume_source }}</span>
      </div>
      <div class="rates">
        <div class="rate person">
          <span class="caption">Человек за год</span>
          <template v-if="personYear != null">
            <span class="mono-md">{{ big(personYear) }} {{ many }}</span>
            <span class="caption">{{ fmt(work.person_rate) }} в час × {{ fmt(personHours, 0) }} ч — норма по ТК РФ</span>
          </template>
          <span class="caption" v-else>{{ byCost ? 'людей не считали — по затратам' : 'укажите людей, чтобы узнать' }}</span>
        </div>
        <div class="rate robot">
          <span class="caption">Робот за год{{ work.robot_rate_own ? ' · указано вручную' : '' }}</span>
          <form v-if="editing" class="r-form" @submit.prevent="saveRate">
            <input v-model.number="typed" class="input input-mono" type="number" min="0" step="0.1" :aria-label="`${many} в час на одного робота`">
            <span class="caption">{{ many }}/ч</span>
            <UiButton type="submit" size="sm" :disabled="busy || !typed">ОК</UiButton>
          </form>
          <template v-else-if="work.robot_rate != null">
            <span class="mono-md">{{ big(work.robot_year) }} {{ many }}</span>
            <span class="caption">{{ fmt(work.robot_rate) }} в час × {{ fmt(robotHours, 0) }} ч — все часы площадки</span>
            <span v-if="editable" class="r-links">
              <button type="button" class="link" :disabled="busy" @click="startEdit">изменить</button>
              <button v-if="work.robot_rate_own" type="button" class="link" :disabled="busy" @click="emit('rate', null)">как в карточке</button>
            </span>
          </template>
          <span v-else class="caption">нет данных о скорости и производительности</span>
        </div>
        <div v-if="work.replaces != null" class="rate swap">
          <span class="caption">Один робот заменяет</span>
          <span class="mono-md">≈ {{ fmt(work.replaces) }} чел.</span>
          <span class="caption">{{ big(work.robot_year) }} ÷ {{ big(personYear) }}</span>
        </div>
      </div>
    </div>
    <!-- Пользователь карточку не правит: ему — только факт. Выработку вручную задаёт администратор каталога. -->
    <p v-if="work.robot_rate == null" class="caption how">Нет данных о выработке робота: долю операций, которую он заберёт, не посчитать.
      <button v-if="editable && !editing" type="button" class="link" :disabled="busy" @click="startEdit">Указать вручную</button>
    </p>

    <div v-if="work.coverage != null" class="cover">
      <div class="c-text body-sm">
        <b>{{ fmt(work.robots, 0) }} {{ robotsWord(work.robots) }} закрывают {{ fmt(coverage * 100, 0) }}% операций</b>
        <template v-if="manual > 0.001"> · {{ manualNote || `${fmt(manual * 100, 0)}% остаётся людям` }}</template>
        <template v-if="idle > 0.001"> · ещё {{ fmt(idle * 100, 0) }}% роботы могли бы взять, но их не хватает — нужно {{ work.robots_full }}</template>
        <template v-else-if="extra === 1"> · ещё 1 — резерв на отказы, как в формуле подбора</template>
        <template v-else-if="extra > 1"> · всю работу закрывают {{ work.robots_full }} + 1 в резерве, {{ extra - 1 }} {{ robotsWord(extra - 1) }} сверх этого</template>
      </div>
      <span class="track">
        <i class="bots" :style="{ width: `${coverage * 100}%` }" />
        <i class="idle" :style="{ width: `${idle * 100}%` }" />
        <i class="manual" :style="{ width: `${manual * 100}%` }" />
      </span>
      <span class="legend caption"><i class="sw bots" />роботы <i v-if="idle > 0.001" class="sw idle" /><template v-if="idle > 0.001">не хватает роботов</template> <i v-if="manual > 0.001" class="sw manual" /><template v-if="manual > 0.001">только вручную</template></span>
    </div>
  </section>
</template>

<style scoped>
.work { display: grid; gap: 10px; padding: 14px 16px; border-radius: 16px; background: rgba(255, 255, 255, 0.65); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.label { color: var(--ink-muted); }
.flow { display: grid; grid-template-columns: minmax(200px, 1fr) minmax(0, 2fr); gap: 16px; align-items: center; }
.vol { display: grid; gap: 2px; }
.big { font-family: var(--font-mono); font-weight: 700; font-size: clamp(22px, 1.8vw, 28px); line-height: 1.1; color: var(--ink-strong); font-variant-numeric: tabular-nums; }
.big small { font-size: 0.5em; font-weight: 600; opacity: 0.7; }
.rates { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; }
.rate { display: grid; gap: 2px; padding: 10px 12px; border-radius: 12px; background: #fff; box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.07); }
.rate .mono-md { font-weight: 700; color: var(--ink-strong); }
.rate.robot .mono-md { color: var(--brand-700); }
.rate.swap { background: var(--surface-brand-tint); box-shadow: none; }
.rate.swap .mono-md { color: var(--brand-ink); }
.how { margin: 0; }
.r-form { display: flex; align-items: center; gap: 6px; }
.r-form .input { width: 90px; height: 30px; padding: 0 8px; }
.r-links { display: flex; gap: 10px; }
.link { font-size: 12px; font-weight: 700; color: var(--link); }
.cover { display: grid; gap: 6px; padding-top: 10px; border-top: 1px dashed rgba(15, 20, 19, 0.1); }
.c-text { color: var(--ink-body); }
.track { display: flex; height: 14px; border-radius: 7px; background: rgba(15, 20, 19, 0.05); overflow: hidden; }
.track i { display: block; height: 100%; }
.bots, .sw.bots { background: var(--brand-500); }
.idle, .sw.idle { background: repeating-linear-gradient(45deg, rgba(240, 177, 74, 0.55) 0 4px, rgba(240, 177, 74, 0.25) 4px 8px); }
.manual, .sw.manual { background: #b8c2be; }
.legend { display: flex; flex-wrap: wrap; gap: 4px 12px; align-items: center; }
.sw { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 4px; vertical-align: -1px; }
@media (max-width: 760px) { .flow { grid-template-columns: 1fr; } }
</style>
