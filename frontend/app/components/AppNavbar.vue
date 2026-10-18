<script setup lang="ts">
import { PhUserCircle, PhSignOut, PhCaretDown, PhList, PhX } from '@phosphor-icons/vue'
import { roleLabel } from '~/composables/useRole'
import type { MenuId } from '~/components/AppMegaMenu.vue'

const { role } = useRole()
const { logout } = useAuth()
const router = useRouter()
const signOut = async () => {
  await logout()
  await router.push('/login')
}
const { ids } = useCompare()
const route = useRoute()
const isActive = (p: string) => route.path === p || (p !== '/' && route.path.startsWith(p))

const items = computed(() => {
  const list: { id: MenuId; to: string; label: string; count?: number; active: boolean; plain?: boolean }[] = [
    /* Обычная страница, без выпадающего списка: схема платформы и путь подбора. */
    { id: 'how', to: '/how', label: 'Как это работает', active: isActive('/how'), plain: true },
    { id: 'catalog', to: '/catalog', label: 'Каталог', active: isActive('/catalog') && !isActive('/catalog/compare') },
    { id: 'projects', to: '/projects', label: 'Проекты', active: isActive('/projects') },
    { id: 'compare', to: '/catalog/compare', label: 'Сравнение', count: ids.value.length, active: isActive('/catalog/compare') },
    /* Обычная страница, без выпадающего списка. */
    { id: 'coop', to: '/cooperation', label: 'Сотрудничество', active: isActive('/cooperation'), plain: true },
  ]
  if (role.value === 'admin') list.push({ id: 'admin', to: '/admin', label: 'Админка', active: isActive('/admin') })
  if (role.value === 'vendor') list.push({ id: 'vendor', to: '/vendor', label: 'Вендор', active: isActive('/vendor') })
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

/* Узкий экран: ссылки уезжают в бургер, иначе подписи наползают друг на друга. */
const sheet = ref(false)
const sheetMenu = ref<MenuId | null>(null)
const toggleSheet = () => {
  sheet.value = !sheet.value
  if (!sheet.value) sheetMenu.value = null
}
const toggleSheetMenu = (id: MenuId) => {
  sheetMenu.value = sheetMenu.value === id ? null : id
}

watch(() => route.fullPath, () => { close(); sheet.value = false; sheetMenu.value = null })
onMounted(() => {
  const onKey = (e: KeyboardEvent) => {
    if (e.key !== 'Escape') return
    close()
    sheet.value = false
    sheetMenu.value = null
  }
  window.addEventListener('keydown', onKey)
  onBeforeUnmount(() => window.removeEventListener('keydown', onKey))
})
</script>

<template>
  <header class="nav-wrap no-print" :class="{ 'is-open': open }">
    <div class="nav-inner" @mouseleave="hide">
      <nav class="nav glass" aria-label="Основная навигация">
        <Logo :size="40" />

        <ul class="links">
          <li v-for="i in items" :key="i.id" @mouseenter="i.plain ? close() : show(i.id)">
            <NuxtLink :to="i.to" :class="{ on: i.active, open: open === i.id }" class="lnk" :aria-expanded="i.plain ? undefined : open === i.id" :aria-haspopup="i.plain ? undefined : 'true'" @focus="i.plain ? close() : show(i.id)" @keydown.down.prevent="i.plain ? undefined : (open = i.id)">
              {{ i.label }}<span v-if="i.count" class="count">{{ i.count }}</span>
            </NuxtLink>
            <button v-if="!i.plain" type="button" class="caret" :aria-label="`${open === i.id ? 'Скрыть' : 'Показать'} меню «${i.label}»`" :aria-expanded="open === i.id" @click="toggle(i.id)" @focus="keep">
              <PhCaretDown :size="12" weight="bold" />
            </button>
          </li>
        </ul>

        <div class="right">
          <div class="role" :title="`Текущая роль: ${roleLabel[role]}`">
            <PhUserCircle :size="18" weight="duotone" />
            <span>{{ roleLabel[role] }}</span>
          </div>
          <UiButton v-if="role === 'guest'" to="/login" size="sm">Войти</UiButton>
          <button v-else type="button" class="icon-btn" aria-label="Выйти" @click="signOut"><PhSignOut :size="18" /></button>
          <button type="button" class="burger" :aria-expanded="sheet" :aria-label="sheet ? 'Закрыть меню' : 'Открыть меню'" @click="toggleSheet">
            <PhX v-if="sheet" :size="20" weight="bold" />
            <PhList v-else :size="20" weight="bold" />
          </button>
        </div>
      </nav>

      <div v-if="sheet" class="sheet glass glass-strong glass-xl">
        <ul class="sheet-list">
          <li v-for="i in items" :key="i.id">
            <div class="sheet-row">
              <NuxtLink :to="i.to" class="sheet-link" :class="{ on: i.active }" @click="sheet = false">
                {{ i.label }}<span v-if="i.count" class="count">{{ i.count }}</span>
              </NuxtLink>
              <button v-if="!i.plain" type="button" class="sheet-more" :aria-expanded="sheetMenu === i.id" @click="toggleSheetMenu(i.id)">
                {{ sheetMenu === i.id ? 'Свернуть' : 'Разделы' }}
              </button>
            </div>
            <AppMegaMenu v-if="!i.plain && sheetMenu === i.id" :menu="i.id" />
          </li>
        </ul>
      </div>

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
/* Непрозрачный: под навбаром прокручивается контент. Блик и кромка от .glass остаются. */
.nav.glass { background: linear-gradient(135deg, #ffffff, var(--surface-raised)); }
/* Ряд пунктов слева, подпись внутри каждого пункта по центру. */
.links { display: flex; align-items: center; justify-content: flex-start; gap: 4px; position: relative; z-index: 1; }
.logo { justify-self: start; }
.links li { position: relative; display: inline-flex; align-items: center; justify-content: center; }
.lnk { display: inline-flex; align-items: center; justify-content: center; gap: 8px; height: 42px; min-width: 108px; padding: 0 28px; border-radius: 12px; font-weight: 600; font-size: 16px; line-height: 1; text-align: center; color: var(--ink-body); transition: background var(--dur-fast) var(--ease), color var(--dur-fast) var(--ease); }
.lnk:hover, .lnk.open { background: rgba(15, 20, 19, 0.05); color: var(--ink-strong); }
.lnk.on { background: var(--surface-graphite); color: var(--ink-on-graphite); box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.1); }
.caret { position: absolute; right: 6px; top: 50%; width: 18px; height: 18px; margin-top: -9px; border-radius: 6px; display: inline-flex; align-items: center; justify-content: center; color: var(--ink-faint); opacity: 0; transition: opacity var(--dur-fast) var(--ease), transform var(--dur-mid) var(--ease); }
.links li:hover .caret, .caret:focus-visible, .caret[aria-expanded="true"] { opacity: 1; }
.caret[aria-expanded="true"] { transform: rotate(180deg); }
.lnk.on + .caret { color: var(--ink-muted-graphite); }
.count { font-family: var(--font-mono); font-size: 11px; padding: 2px 6px; border-radius: 6px; background: var(--brand-400); color: var(--brand-900); }
.right { display: flex; align-items: center; justify-content: flex-end; gap: 8px; position: relative; z-index: 1; }
.role { display: inline-flex; align-items: center; justify-content: center; gap: 6px; height: 42px; padding: 0 12px; border-radius: 12px; font-size: 15px; font-weight: 600; line-height: 1; white-space: nowrap; color: var(--ink-body); }
.icon-btn { display: inline-flex; align-items: center; justify-content: center; width: 42px; height: 42px; border-radius: 12px; color: var(--ink-muted); transition: background var(--dur-fast) var(--ease); }
.icon-btn:hover { background: rgba(15, 20, 19, 0.05); color: var(--ink-strong); }
.burger { display: none; align-items: center; justify-content: center; width: 42px; height: 42px; border-radius: 12px; color: var(--ink-strong); background: rgba(255, 255, 255, 0.5); box-shadow: inset 0 0 0 1px rgba(15, 20, 19, 0.06); }
.sheet { position: absolute; left: 0; right: 0; top: calc(100% + 10px); z-index: 3; max-height: calc(100dvh - 96px); overflow: auto; padding: 8px; }
.sheet-list { display: grid; gap: 6px; }
.sheet-row { display: flex; align-items: center; gap: 8px; }
.sheet-link { flex: 1; min-width: 0; display: flex; align-items: center; gap: 8px; min-height: 44px; padding: 8px 14px; border-radius: 12px; font-weight: 700; line-height: 1.3; }
.sheet-link.on { background: var(--surface-graphite); color: var(--ink-on-graphite); }
.sheet-more { flex: none; min-height: 36px; padding: 0 12px; border-radius: 10px; font-size: 13px; font-weight: 700; color: var(--ink-body); background: rgba(15, 20, 19, 0.05); }

/* Панель */
.mega { position: absolute; left: 0; right: 0; top: calc(100% + 10px); z-index: 2; --glass-shadow: 0 30px 80px rgba(15, 20, 19, 0.18), 0 2px 6px rgba(15, 20, 19, 0.05); }
.mega-enter-active, .mega-leave-active { transition: opacity var(--dur-mid) var(--ease), transform var(--dur-mid) var(--ease); }
.mega-enter-from, .mega-leave-to { opacity: 0; transform: translateY(-8px) scale(0.995); }

/* Лёгкое затемнение страницы под панелью */
.dim { position: fixed; inset: 0; z-index: -1; background: rgba(15, 20, 19, 0.10); }
.dim-enter-active, .dim-leave-active { transition: opacity var(--dur-slow) var(--ease); }
.dim-enter-from, .dim-leave-to { opacity: 0; }

@media (min-width: 1101px) {
  .sheet { display: none; }
}
@media (max-width: 1100px) {
  .links, .mega, .dim, .caret, .role span { display: none; }
  .burger { display: inline-flex; }
  .nav { padding-right: 8px; }
}
</style>
