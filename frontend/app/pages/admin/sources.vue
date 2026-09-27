<script setup lang="ts">
import { PhArrowSquareOut, PhMagnifyingGlass } from '@phosphor-icons/vue'
import { platformGet } from '~/composables/usePlatform'
import { fetchErrorMessage } from '~/utils/errors'
import { confidenceOf, platformSourceKinds, sourceKindName } from '~/data/adminLabels'

definePageMeta({ layout: 'admin', middleware: 'admin', pageTransition: false })
useHead({ title: 'Админка · Источники' })

interface Source { id: number; kind: string; publisher: string; url: string | null; title: string | null; parser_code: string | null; values: number; products: number; updated_at: string | null }

const items = ref<Source[]>([])
const notice = ref('')
const q = ref('')
const kind = ref('')
const noUrl = ref(false)
const unused = ref(false)
const limit = ref(100)

onMounted(async () => {
  try {
    items.value = await platformGet<Source[]>('/admin/sources')
  } catch (err) {
    notice.value = fetchErrorMessage(err, 'Реестр не загрузился')
  }
})

const shown = computed(() => {
  const text = q.value.trim().toLowerCase()
  return items.value
    .filter((item) => (!kind.value || item.kind === kind.value)
      && (!noUrl.value || !item.url)
      && (!unused.value || !item.values)
      && (!text || `${item.publisher} ${item.url ?? ''} ${item.title ?? ''}`.toLowerCase().includes(text)))
    .sort((a, b) => b.values - a.values)
})
const counts = computed(() => {
  const out: Record<string, number> = {}
  for (const item of items.value) out[item.kind] = (out[item.kind] ?? 0) + 1
  return out
})
watch([q, kind, noUrl, unused], () => { limit.value = 100 })
const when = (iso: string | null) => (iso ? new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' }) : '—')
const manual = (item: Source) => item.parser_code === 'manual'
</script>

<template>
  <div class="admin-page">
    <AdminHead label="Импорт данных" title="Реестр источников" lead="Откуда пришло каждое значение каталога (ТЗ 3.3.4): тип источника, издатель, ссылка, сколько значений и карточек на него ссылается и когда эти карточки обновлялись. Буква достоверности выводится из типа." />
    <UiCallout v-if="notice" tone="danger">{{ notice }}</UiCallout>

    <div class="legend">
      <button v-for="item in platformSourceKinds" :key="item.code" type="button" class="glass lg" :class="{ on: kind === item.code }" @click="kind = kind === item.code ? '' : item.code">
        <span class="lg-in"><span class="a-letter" :class="`c-${item.confidence}`">{{ item.confidence }}</span><span class="body-sm">{{ item.label }}</span><span class="mono-sm muted">{{ counts[item.code] ?? 0 }}</span></span>
      </button>
    </div>

    <section class="glass a-panel filters">
      <label class="search"><PhMagnifyingGlass :size="16" weight="bold" /><input v-model="q" class="s-in" placeholder="Издатель, домен или документ"></label>
      <label class="tg"><input v-model="noUrl" type="checkbox"> <span class="body-sm">только без ссылки</span></label>
      <label class="tg"><input v-model="unused" type="checkbox"> <span class="body-sm">ни на что не ссылаются</span></label>
    </section>

    <section class="glass glass-xl a-panel">
      <div class="caption">Найдено {{ shown.length }} из {{ items.length }}. Ручные правки из карточек помечены «вручную».</div>
      <div class="a-tbl">
        <table class="table">
          <thead><tr><th>Источник</th><th>Тип</th><th>Ссылка</th><th class="num">Значений</th><th class="num">Карточек</th><th class="num">Обновлено</th></tr></thead>
          <tbody>
            <tr v-for="item in shown.slice(0, limit)" :key="item.id">
              <td>
                <span class="strong">{{ item.publisher }}</span>
                <span v-if="item.title && item.title !== item.publisher" class="caption block">{{ item.title }}</span>
                <span class="caption block">{{ manual(item) ? 'вручную' : item.parser_code ? `парсер ${item.parser_code}` : 'импорт таблицы' }}</span>
              </td>
              <td><span class="kind"><span class="a-letter" :class="`c-${confidenceOf(item.kind)}`">{{ confidenceOf(item.kind) }}</span><span class="body-sm">{{ sourceKindName(item.kind) }}</span></span></td>
              <td>
                <a v-if="item.url" :href="item.url" target="_blank" rel="noreferrer" class="link mono-sm url">{{ item.url.replace(/^https?:\/\//, '') }} <PhArrowSquareOut :size="12" /></a>
                <span v-else class="a-pill warn">без ссылки</span>
              </td>
              <td class="num mono-sm">{{ item.values }}</td>
              <td class="num mono-sm">{{ item.products }}</td>
              <td class="num mono-sm">{{ when(item.updated_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <UiButton v-if="shown.length > limit" size="sm" variant="secondary" @click="limit += 100">Показать ещё {{ Math.min(100, shown.length - limit) }}</UiButton>
    </section>
  </div>
</template>

<style scoped>
.legend { display: grid; grid-template-columns: repeat(7, 1fr); gap: 8px; }
.lg { text-align: left; border-radius: var(--radius-md); }
.lg.on { box-shadow: inset 0 0 0 2px var(--brand-400); }
.lg-in { position: relative; z-index: 1; display: flex; gap: 8px; align-items: center; padding: 10px 12px; }
.lg-in .mono-sm { margin-left: auto; }
.filters { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; padding: 10px; }
.search { flex: 1; min-width: 260px; display: flex; align-items: center; gap: 10px; padding: 0 14px; border-radius: var(--radius-sm); background: rgba(255, 255, 255, 0.7); box-shadow: inset 0 0 0 1px var(--border-hairline); color: var(--ink-muted); }
.s-in { flex: 1; background: none; border: 0; outline: none; min-height: 42px; font-weight: 600; color: var(--ink-strong); }
.tg { display: inline-flex; gap: 8px; align-items: center; }
.block { display: block; }
.kind { display: inline-flex; gap: 8px; align-items: center; }
.url { word-break: break-all; }
@media (max-width: 1100px) { .legend { grid-template-columns: repeat(2, 1fr); } }
</style>
