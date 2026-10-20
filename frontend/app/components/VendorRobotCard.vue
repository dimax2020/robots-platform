<script setup lang="ts">
import { PhMapPin } from '@phosphor-icons/vue'
import { availabilityLabel, availabilityTone, formatRub, type Availability } from '~/data/catalog'
import { stateLabel, type AnalyticsRobot } from '~/data/analytics'
import { photoFor } from '~/data/placeholders'

const props = defineProps<{ robot: AnalyticsRobot; open?: boolean; compact?: boolean }>()
const emit = defineEmits<{ toggle: [] }>()

const known = computed(() => props.robot.availability && props.robot.availability in availabilityLabel)
const photo = computed(() => props.compact
  ? photoFor(props.robot.image_url, props.robot.name, props.robot.processes[0]?.code)
  : props.robot.image_url)
const tone = computed(() => (props.robot.state === 'in' ? 'ok' : props.robot.state === 'note' ? 'warn' : 'danger') as 'ok' | 'warn' | 'danger')
</script>

<template>
  <article class="card-r glass" :class="{ open, compact }" :id="`robot-${robot.slug}`">
    <button v-if="!open" type="button" class="media" :aria-expanded="false" :aria-label="robot.name" @click="emit('toggle')">
      <img v-if="photo" :src="photo" :alt="robot.name">
      <span class="badges">
        <UiBadge :tone="tone">{{ stateLabel[robot.state] }}</UiBadge>
        <UiBadge v-if="known" :tone="availabilityTone[robot.availability as Availability]">{{ availabilityLabel[robot.availability as Availability] }}</UiBadge>
        <UiBadge v-if="robot.trl" tone="neutral" mono size="sm">УГТ {{ robot.trl }}</UiBadge>
      </span>
    </button>
    <div class="body">
      <div v-if="robot.solution_type" class="label">{{ robot.solution_type }}</div>
      <button type="button" class="h3 name" @click="emit('toggle')">{{ robot.name }}</button>
      <div class="vendor body-sm muted">
        <span class="strong">{{ robot.manufacturer || 'Ваша компания' }}</span>
        <template v-if="robot.city"> <PhMapPin :size="12" /> {{ robot.city }}</template>
      </div>
      <p class="headline">{{ robot.headline }}</p>
      <dl v-if="robot.highlights.length" class="specs">
        <div v-for="item in robot.highlights" :key="item.label">
          <dt>{{ item.label }}</dt>
          <dd :class="{ dim: item.missing }">{{ item.value }}</dd>
        </div>
      </dl>
      <p v-if="robot.revision_comment" class="note">Администратор просит: {{ robot.revision_comment }}</p>
      <div class="foot">
        <div class="price">
          <span class="mono-lg">{{ formatRub(robot.price_rub ?? undefined) }}</span>
          <span class="caption">В подборе: {{ robot.offers }}</span>
        </div>
        <button type="button" class="cmp" @click="emit('toggle')">{{ open ? 'Свернуть' : 'Дополнить' }}</button>
      </div>
      <div v-if="open" class="editor">
        <slot />
      </div>
    </div>
  </article>
</template>

<style scoped>
.card-r { display: grid; grid-template-rows: auto 1fr; border-radius: var(--radius-xl); overflow: hidden; height: 100%; transition: transform var(--dur-mid) var(--ease), box-shadow var(--dur-mid) var(--ease); }
.card-r.open { grid-column: 1 / -1; height: auto; }
.card-r:hover { transform: translateY(-3px); box-shadow: inset 0 1px 0 var(--glass-stroke), 0 0 0 1px var(--glass-stroke-outer), var(--shadow-lg); }
.media { position: relative; display: block; width: 100%; aspect-ratio: 4 / 3; margin: 0; padding: 0; border: 0; border-radius: 18px; overflow: hidden; background: #e9eeec; cursor: pointer; }
.card-r .media { margin: 8px; width: calc(100% - 16px); }
/* Закрытая карточка показывает робота целиком. В раскрытой кадра нет. */
.media img { width: 100%; height: 100%; object-fit: contain; }
.badges { position: absolute; left: 10px; top: 10px; display: flex; gap: 6px; flex-wrap: wrap; }
.body { display: grid; gap: 8px; padding: 8px 16px 16px; align-content: start; text-align: left; }
.name { color: var(--ink-strong); text-align: left; background: none; border: 0; padding: 0; cursor: pointer; }
.vendor { display: flex; align-items: center; gap: 4px; }
.headline { margin: 0; font-size: 13px; line-height: 1.45; color: var(--ink-body); }
.specs { display: grid; grid-template-columns: 1fr 1fr; gap: 8px 12px; margin: 0; padding-top: 12px; border-top: 1px solid rgba(15, 20, 19, 0.08); }
.specs dt { font-size: 12px; color: var(--ink-muted); }
.specs dd { margin: 0; color: var(--ink-strong); font-variant-numeric: tabular-nums; }
.specs dd.dim { color: var(--state-warn); font-weight: 600; font-size: 13px; }
.note { margin: 0; padding: 8px 12px; border-radius: 10px; background: var(--state-warn-tint); color: var(--state-warn); font-size: 12px; line-height: 1.4; font-weight: 500; }
.foot { display: flex; align-items: flex-end; justify-content: space-between; gap: 12px; margin-top: 8px; }
.price { display: grid; }
.price .mono-lg { color: var(--ink-strong); }
.cmp { display: inline-flex; align-items: center; height: 36px; padding: 0 12px; border-radius: 10px; font-size: 13px; font-weight: 700; color: var(--ink-strong); background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); }
.cmp:hover { background: #fff; }
.editor { display: grid; gap: 10px; padding-top: 12px; border-top: 1px solid var(--border-hairline); }
</style>
