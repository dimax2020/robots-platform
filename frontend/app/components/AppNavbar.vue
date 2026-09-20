<script setup lang="ts">
import { PhMagnifyingGlass, PhUserCircle, PhSignOut, PhCaretDown } from '@phosphor-icons/vue'
import { roleLabel } from '~/composables/useRole'
import type { MenuId } from '~/components/AppMegaMenu.vue'

const { role, setRole } = useRole()
const { ids } = useCompare()
const route = useRoute()
const isActive = (p: string) => route.path === p || (p !== '/' && route.path.startsWith(p))

const items = computed(() => {
  const list: { id: MenuId; to: string; label: string; count?: number; active: boolean }[] = [
    { id: 'catalog', to: '/catalog', label: 'Каталог', active: isActive('/catalog') && !isActive('/catalog/compare') },
    { id: 'projects', to: '/projects', label: 'Проекты', active: isActive('/projects') },
    { id: 'compare', to: '/catalog/compare', label: 'Сравнение', count: ids.value.length, active: isActive('/catalog/compare') },
  ]
  if (role.value === 'admin') list.push({ id: 'admin', to: '/admin', label: 'Админка', active: isActive('/admin') })
  return list
})

/* Mega menu: hover intent + клавиатура */
const open = ref<MenuId | null>(null)
let openT: ReturnType<typeof setTimeout> | undefined
let closeT: ReturnType<typeof setTimeout> | undefined
const show = (id: MenuId) => {
  clearTimeout(closeT)
  clearTimeout(openT)
  openT = setTimeout(() => { open.value = id }, open.value ? 40 : 110)
}
const hide = () => {
  clearTimeout(openT)
  clearTimeout(closeT)
  closeT = setTimeout(() => { open.value = null }, 180)
}
const keep = () => { clearTimeout(closeT); clearTimeout(openT) }
const toggle = (id: MenuId) => { keep(); open.value = open.value === id ? null : id }
const close = () => { keep(); open.value = null }

watch(() => route.fullPath, close)
onMounted(() => {
  const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') close() }
  window.addEventListener('keydown', onKey)
  onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
})
</script>

<template>
  <header class="nav-wrap no-print" :class="{ 'is-open': open }">
    <div class="nav-inner" @mouseleave="hide">
      <nav class="nav glass glass-sheen" aria-label="Основная навигация">
        <span class="sheen" aria-hidden="true" />
        <Logo :size="40" />

        <ul class="links">
          <li v-for="i in items" :key="i.id" @mouseenter="show(i.id)">
            <NuxtLink :to="i.to" :class="{ on: i.active, open: open === i.id }" class="lnk" :aria-expanded="open === i.id" aria-haspopup="true" @focus="show(i.id)" @keydown.down.prevent="open = i.id">
              {{ i.label }}<span v-if="i.count" class="count">{{ i.count }}</span>
            </NuxtLink>
            <button type="button" class="caret" :aria-label="`${open === i.id ? 'Скрыть' : 'Показать'} меню «${i.label}»`" :aria-expanded="open === i.id" @click="toggle(i.id)" @focus="keep">
              <PhCaretDown :size="12" weight="bold" />
            </button>
          </li>
        </ul>

        <div class="right">
          <button type="button" class="search" aria-label="Поиск по каталогу">
            <PhMagnifyingGlass :size="16" weight="bold" />
            <span>Поиск</span>
            <span class="kbd">/</span>
          </button>
          <div class="role" :title="`Текущая роль: ${roleLabel[role]}`">
            <PhUserCircle :size="18" weight="duotone" />
            <span>{{ roleLabel[role] }}</span>
          </div>
          <UiButton v-if="role === 'guest'" to="/login" size="sm">Войти</UiButton>
          <button v-else type="button" class="icon-btn" aria-label="Выйти" @click="setRole('guest')"><PhSignOut :size="18" /></button>
        </div>
      </nav>

      <Transition name="mega">
        <div v-if="open" class="mega glass glass-strong glass-xl" role="region" :aria-label="`Меню: ${items.find(i => i.id === open)?.label}`" @mouseenter="keep" @focusin="keep">
          <AppMegaMenu :key="open" :menu="open" />
        </div>
      </Transition>
    </div>

    <Transition name="dim">
      <div v-if="open" class="dim" aria-hidden="true" @mouseenter="hide" @click="close" />
    </Transition>
  </header>
</template>

<style scoped>
.nav-wrap { position: sticky; top: 12px; z-index: var(--z-sticky); padding: 0 var(--container-pad); margin-top: 12px; }
.nav-inner { position: relative; max-width: var(--container); margin: 0 auto; }
.nav {
  height: 68px;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: var(--space-8);
  padding: 0 12px 0 16px;
  border-radius: 20px;
}
.links { display: flex; align-items: center; gap: 4px; position: relative; z-index: 1; }
.links li { position: relative; display: inline-flex; align-items: center; }
.lnk { display: inline-flex; align-items: center; gap: 8px; height: 42px; padding: 0 14px 0 16px; border-radius: 12px; font-weight: 600; font-size: 16px; color: var(--ink-body); transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease); }
.lnk:hover, .lnk.open { background: rgba(15, 20, 19, 0.05); color: var(--ink-strong); }
.lnk.on { background: var(--surface-graphite); color: var(--ink-on-graphite); box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1); }
.caret { position: absolute; right: 2px; top: 50%; width: 22px; height: 22px; margin-top: -11px; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center; color: var(--ink-faint); opacity: 0; transition: opacity var(--dur-fast) var(--ease), transform var(--dur-mid) var(--ease); }
.links li:hover .caret, .caret:focus-visible, .caret[aria-expanded="true"] { opacity: 1; }
.caret[aria-expanded="true"] { transform: rotate(180deg); }
.lnk.on + .caret { color: var(--ink-muted-graphite); }
.count { font-family: var(--font-mono); font-size: 11px; padding: 2px 6px; border-radius: 6px; background: var(--brand-400); color: var(--brand-900); }
.right { display: flex; align-items: center; gap: 8px; position: relative; z-index: 1; }
.search { display: inline-flex; align-items: center; gap: 8px; height: 42px; padding: 0 12px; border-radius: 12px; color: var(--ink-muted); font-size: 15px; font-weight: 600; background: rgba(255, 255, 255, 0.5); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease); }
.search:hover { background: #fff; color: var(--ink-strong); }
.role { display: inline-flex; align-items: center; gap: 6px; height: 42px; padding: 0 12px; border-radius: 12px; font-size: 15px; font-weight: 600; color: var(--ink-body); }
.icon-btn { display: inline-flex; align-items: center; justify-content: center; width: 42px; height: 42px; border-radius: 12px; color: var(--ink-muted); transition: background var(--dur-fast) var(--ease); }
.icon-btn:hover { background: rgba(15, 20, 19, 0.05); color: var(--ink-strong); }

/* Панель */
.mega { position: absolute; left: 0; right: 0; top: calc(100% + 10px); z-index: 2; --glass-blur: 28px; --glass-shadow: 0 30px 80px rgba(15, 20, 19, 0.18), 0 2px 6px rgba(15, 20, 19, 0.05); }
.mega-enter-active, .mega-leave-active { transition: opacity var(--dur-mid) var(--ease), transform var(--dur-mid) var(--ease); }
.mega-enter-from, .mega-leave-to { opacity: 0; transform: translateY(-8px) scale(0.995); }

/* Лёгкое затемнение страницы под панелью */
.dim { position: fixed; inset: 0; z-index: -1; background: rgba(15, 20, 19, 0.10); -webkit-backdrop-filter: blur(3px); backdrop-filter: blur(3px); }
.dim-enter-active, .dim-leave-active { transition: opacity var(--dur-slow) var(--ease); }
.dim-enter-from, .dim-leave-to { opacity: 0; }

@media (max-width: 1100px) {
  .mega, .dim, .caret { display: none; }
}
</style>
