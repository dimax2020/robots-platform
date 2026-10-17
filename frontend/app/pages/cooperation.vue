<script setup lang="ts">
import { platformGet } from '~/composables/usePlatform'

useHead({ title: 'Сотрудничество' })

const partners = ref<{ name: string; products: number }[]>([])
const partnerTotal = ref(0)
onMounted(() => {
  platformGet<{ total: number; items: { name: string; products: number }[] }>('/catalog/partners')
    .then((page) => { partners.value = page.items; partnerTotal.value = page.total })
    .catch(() => { partners.value = []; partnerTotal.value = 0 })
})
const leadPartners = computed(() => partners.value.slice(0, 8))
const restPartners = computed(() => partners.value.slice(8))
const steps = [
  { title: 'Рассказываете о компании', text: 'Название, логотип, сайт и документы: карточка предприятия, разрешения, сертификаты. Пока администратор не подтвердит, на витрине остаётся прежняя версия.' },
  { title: 'Передаёте своих роботов', text: 'Можно заполнить карточку вручную, приложить таблицу, дать ссылку на список или попросить найти модели на открытом сайте. Найдутся только роботы вашей компании.' },
  { title: 'Ждёте решение', text: 'У заявки есть статус: на проверке, принята, нужна доработка или отклонена. В каталог модель попадает, когда администратор сам нажмёт «Внести в каталог».' },
]
const gains = [
  { title: 'Те же форматы, что уже есть у вас', text: 'Таблица или файл со списком, можно дать ссылку. Отдельно подключаться к каждому расчёту не нужно: платформа сама читает список роботов.' },
  { title: 'Робот сразу связан с процессом', text: 'Вы отмечаете, что умеет модель: перевозка, уборка, инвентаризация и другие процессы каталога. По ним её и предлагают на объекте.' },
  { title: 'Характеристики с источником', text: 'Грузоподъёмность, скорость и остальные ТТХ видны заказчику вместе с тем, откуда цифра взялась. Следующий импорт чужого сайта ручную правку не затирает.' },
  { title: 'Публикация только после проверки', text: 'Ни профиль, ни новая модель, ни правка ТТХ не появляются в подборе сами. Администратор принимает заявку и отдельно вносит её в каталог.' },
]
const word = (count: number) => {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return 'модель'
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'модели'
  return 'моделей'
}
</script>

<template>
  <div>
    <section id="steps" class="container section coop">
      <SectionHead
        label="Для производителей"
        title="Подключите своих роботов к подбору"
        lead="Если вы выпускаете роботов, платформа может предлагать их заказчику склада, аэропорта или медучреждения. Карточка попадает в каталог, сравнение и расчёт только после проверки администратором."
        size="hero-2"
      />
      <div class="coop-steps">
        <article v-for="(step, i) in steps" :key="step.title" class="glass coop-step" v-reveal="i">
          <span class="mono-sm step-n">0{{ i + 1 }}</span>
          <h3 class="h3">{{ step.title }}</h3>
          <p class="body-sm muted">{{ step.text }}</p>
        </article>
      </div>
    </section>

    <section class="container section-tight">
      <div class="graphite graphite-section coop-why">
        <div class="how-head">
          <div class="label">Почему это просто</div>
          <h2 class="h2">Не нужно отдельно встраиваться в каждый расчёт</h2>
        </div>
        <div class="rules">
          <div v-for="item in gains" :key="item.title" class="rule glass-graphite">
            <h3 class="h3">{{ item.title }}</h3>
            <p class="body-sm muted">{{ item.text }}</p>
          </div>
        </div>
      </div>
    </section>

    <section id="makers" class="container section">
      <SectionHead
        title="Уже в каталоге"
        :lead="partnerTotal ? `С этими производителями платформа уже работает: их модели стоят в каталоге и участвуют в подборе. Сейчас таких компаний ${partnerTotal}.` : 'Список производителей загружается из каталога.'"
      />
      <div class="coop-leads">
        <article v-for="item in leadPartners" :key="item.name" class="glass coop-lead">
          <div class="h4">{{ item.name }}</div>
          <div class="caption">{{ item.products }} {{ word(item.products) }} в каталоге</div>
        </article>
      </div>
      <div v-if="restPartners.length" class="coop-rest">
        <span v-for="item in restPartners" :key="item.name" class="coop-name">{{ item.name }}</span>
      </div>
    </section>

    <section class="container section-tight">
      <div class="disclaimer glass glass-xl">
        <div>
          <div class="h2">Присоединиться как вендор</div>
          <p class="body muted">Дальше откроется вход. Выберите пункт «Вендор»: подставятся тестовые логин и пароль производителя из каталога. В кабинете можно заполнить профиль и передать своих роботов на проверку.</p>
        </div>
        <div class="row">
          <UiButton to="/login" size="lg">Присоединиться</UiButton>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.coop { padding-top: var(--space-8); }
.coop-steps, .coop-leads { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--space-4); }
.coop-leads { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.coop-step, .coop-lead { min-width: 0; padding: 20px 22px; display: grid; gap: 8px; overflow: hidden; }
.coop-step h3, .coop-lead .h4, .coop-step p, .coop-lead .caption { overflow-wrap: break-word; }
.step-n { color: var(--brand-700); }
.coop-why { padding: var(--space-8); display: grid; gap: var(--space-6); min-width: 0; }
.how-head { min-width: 0; max-width: 40rem; }
.how-head h2 { font-size: clamp(22px, 2vw, 30px); line-height: 1.25; overflow-wrap: break-word; }
.rules { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--space-4); position: relative; z-index: 1; }
.rule { min-width: 0; padding: 18px 20px; display: grid; gap: 8px; align-content: start; overflow: hidden; }
.rule h3 { font-size: 17px; line-height: 1.35; overflow-wrap: break-word; }
.rule p { overflow-wrap: break-word; }
.coop-rest { display: flex; flex-wrap: wrap; gap: 8px; margin-top: var(--space-5); }
.coop-name { padding: 6px 10px; border-radius: 999px; background: rgba(15, 20, 19, 0.05); font-size: 13px; font-weight: 600; color: var(--ink-body); }
.disclaimer { display: grid; grid-template-columns: 1fr auto; gap: var(--space-8); align-items: center; padding: clamp(32px, 3vw, 48px) clamp(32px, 3vw, 56px); }
.disclaimer > * { position: relative; z-index: 1; }
.disclaimer p { max-width: 62ch; margin-top: 8px; }
@media (max-width: 900px) {
  .coop-steps, .coop-leads, .rules, .disclaimer { grid-template-columns: 1fr; }
}
</style>
