<script setup lang="ts">
import { PhUser, PhUserGear, PhEye, PhArrowRight } from '@phosphor-icons/vue'
import { fetchErrorMessage } from '~/utils/errors'
import { roleLabel, type Role } from '~/composables/useRole'

useHead({ title: 'Вход по роли' })
const { login: signIn } = useAuth()
const router = useRouter()

const accounts: { role: Role; login: string; icon: any; text: string; goes: string }[] = [
  { role: 'guest', login: 'guest', icon: PhEye, text: 'Демо-наборы, каталог, проход по складу без сохранения.', goes: 'Остаётся на демо-складе' },
  { role: 'user', login: 'user', icon: PhUser, text: 'Свои проекты и полный путь по складу. Аэропорт и медучреждение до подбора.', goes: 'Попадает в список проектов' },
  { role: 'admin', login: 'admin', icon: PhUserGear, text: 'Всё пользовательское плюс каталог, справочники, нормативы, источники.', goes: 'Проекты и админка' },
]

const login = ref('user')
const password = ref('demo-2026')
const error = ref('')

const submit = async () => {
  error.value = ''
  try {
    const user = await signIn(login.value.trim(), password.value)
    const role = user?.role ?? 'guest'
    await router.push(role === 'guest' ? '/projects' : role === 'admin' ? '/admin' : '/projects')
  } catch (err) {
    error.value = fetchErrorMessage(err, 'Не удалось войти')
  }
}
const pick = (a: typeof accounts[number]) => { login.value = a.login; error.value = '' }
</script>

<template>
  <section class="container login">
    <div class="wrap">
      <div class="intro" v-reveal>
        <div class="label">Вход по роли</div>
        <h1 class="hero-2">Сменить роль. Регистрации нет</h1>
        <p class="body-lg muted">Три демонстрационные учётки с одним паролем. Почты и восстановления пароля в MVP нет: вход нужен только для разделения проектов и админки.</p>
        <div class="accounts">
          <button v-for="a in accounts" :key="a.role" type="button" class="acc glass" :class="{ on: login === a.login }" @click="pick(a)">
            <component :is="a.icon" :size="22" weight="duotone" class="acc-ic" />
            <div class="acc-body">
              <div class="between"><span class="h4">{{ roleLabel[a.role] }}</span><span class="mono-sm muted">{{ a.login }}</span></div>
              <p class="body-sm muted">{{ a.text }}</p>
              <span class="caption goes"><PhArrowRight :size="12" /> {{ a.goes }}</span>
            </div>
          </button>
        </div>
      </div>

      <form class="form glass glass-strong glass-xl" v-reveal="1" @submit.prevent="submit">
        <div class="form-inner">
          <Logo :size="44" :wordmark="false" />
          <div>
            <div class="h2">Войти</div>
            <div class="caption">Сессия хранится в cookie браузера. Сид-аккаунты одинаковы для всех стендов.</div>
          </div>
          <label class="field">
            <span class="field-label">Логин</span>
            <input v-model="login" class="input input-mono" :class="{ 'is-error': error }" autocomplete="username" spellcheck="false">
            <span v-if="error" class="field-error">{{ error }}</span>
            <span v-else class="field-hint">guest, user или admin</span>
          </label>
          <label class="field">
            <span class="field-label">Пароль</span>
            <input v-model="password" type="password" class="input input-mono" autocomplete="current-password">
            <span class="field-hint">Одинаковый для трёх учёток: demo-2026</span>
          </label>
          <UiButton type="submit" size="lg" block>Войти как {{ roleLabel[accounts.find(a => a.login === login)?.role ?? 'user'] }}</UiButton>
          <UiCallout tone="info">Почты и восстановления пароля нет. Это осознанное ограничение MVP, а не недоработка.</UiCallout>
        </div>
      </form>
    </div>
  </section>
</template>

<style scoped>
.login { padding-top: var(--space-16); padding-bottom: var(--space-16); }
.wrap { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 0.85fr); gap: var(--space-16); align-items: start; }
.intro { display: grid; gap: var(--space-5); }
.intro p { max-width: 58ch; }
.accounts { display: grid; gap: var(--space-3); margin-top: var(--space-4); }
.acc { display: grid; grid-template-columns: auto 1fr; gap: 14px; padding: 16px 18px; text-align: left; border-radius: 18px; transition: transform var(--dur-fast) var(--ease), box-shadow var(--dur-fast) var(--ease); }
.acc:hover { transform: translateY(-1px); }
.acc.on { box-shadow: inset 0 1px 0 var(--glass-stroke), 0 0 0 2px var(--brand-500), var(--glass-shadow); }
.acc-ic { color: var(--brand-700); margin-top: 2px; position: relative; z-index: 1; }
.acc-body { display: grid; gap: 4px; position: relative; z-index: 1; }
.goes { display: inline-flex; align-items: center; gap: 6px; color: var(--brand-700); }
.form { position: sticky; top: 100px; }
.form-inner { position: relative; z-index: 1; display: grid; gap: var(--space-5); padding: var(--space-8); }
</style>
