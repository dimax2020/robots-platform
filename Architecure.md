# Платформа подбора роботизированных решений — архитектура и техническое задание

> Кейс ФЦ БАС (Федеральный центр беспилотных авиационных систем), хакатон «Лидеры цифровой трансформации», 2026.
> Этот файл — единственный источник правды по архитектуре. Он самодостаточен: для работы по нему
> не нужен ни исходный PDF организатора, ни история обсуждения.

## 0. Как пользоваться этим файлом

**Человеку.** Разделы 1–3 — рамка и границы. 4–9 — что и как строить. 10 — порядок работ. 11 — трассировка на пункты ТЗ организатора (нужна для сдачи и для питча).

**Агенту / разработчику.** Правила, которые нельзя нарушать молча:

1. Структура репозитория (§5) и модель данных (§6) — фиксированы. Отклонение допускается только с записью в §12 «Журнал решений».
2. `engine/` не импортирует ничего из `api/`. Ни БД, ни HTTP, ни настроек. Только pydantic-модели и стандартная библиотека + OR-Tools.
3. Любое число, попадающее в интерфейс, обязано иметь запись в `trace[]` с формулой и источником. Коэффициент без обоснования в БД физически не вставляется — см. `calc_norm.rationale NOT NULL`.
4. Ссылки вида «ТЗ 3.3.4» относятся к техническому заданию организатора; смысл пункта всегда пересказан рядом, лазить в оригинал не требуется.
5. Русский язык в интерфейсе, сообщениях об ошибках и названиях полей каталога. Код и имена таблиц — латиница.

---

## 1. Задача

Компании, рассматривающие роботизацию, не имеют единого источника данных о доступных решениях и не могут быстро оценить их применимость и экономику для конкретного объекта.

Платформа ведёт пользователя по одному сценарию: выбор отрасли и объекта → ввод параметров → подбор решений с объяснением → сравнение → расчёт экономики → what-if → 2D-визуализация, подтверждающая расчёт → сохранение и экспорт.

Приоритетный режим использования — **экспресс-прединвестиционная оценка**. Платформа не заменяет обследование объекта, а даёт обоснованную гипотезу о целесообразности и материалы для перехода к полноценному ТЭО.

**Аудитория:** руководители предприятий и подразделений, технические директора, руководители по автоматизации, логисты, операционные и финансовые аналитики.

### 1.1. Чем это решение отличается

Три вещи, вокруг которых построена вся архитектура. Если что-то придётся резать, режется не это.

| | Что | Где реализовано |
|---|---|---|
| 1 | **Каждое значение ссылается на свой источник.** Достоверность — свойство источника (сайт производителя, дилер, оценка по аналогу, допущение), а не подпись к числу: выводится, а не хранится. | §6.3, §6.4 |
| 2 | **Трёхзначная логика подбора.** `unknown` не выбрасывает решение, а превращается в список запросов вендору. | §7.2 |
| 3 | **Результат интервалом, а не точкой.** Достоверность исходных данных пробрасывается в разброс окупаемости, и платформа называет характеристику, которая даёт больше всего неопределённости. | §8.4 |

Первое и второе — следствие того, что каталог собран вручную и честно размечен. Третье — следствие первых двух.

---

## 2. Границы MVP

### 2.1. Что делаем полностью

- **Склад** — сквозной путь целиком: параметры, подбор, экономика, три сценария, симуляция смены, 2D, экспорт.
- Каталог всех собранных решений с иерархией, фильтрами, поиском, сравнением и админкой.
- Три сценария сравнения: без роботизации / подбор по задачам / оптимальный состав парка.
- Монте-Карло по достоверности данных.
- 2D-визуализация с проигрыванием реального прогона.

### 2.2. Что делаем в урезанном виде — и почему это разрешено

- **Аэропорт и медучреждение** — выбор типа объекта, набор входных параметров, подбор применимых решений. Без глубокой экономики и симуляции.
  *Основание: ТЗ раздел 2 требует полноценную работу «для одного из трёх базовых типов объектов»; ТЗ 5.5 требует показать три типа «хотя бы на уровне выбора, входных параметров и доступных решений».*
- **Авторизация** — три роли (гость / пользователь / администратор), JWT, сид-аккаунты. Без регистрации, восстановления пароля и почты.
  *Основание: ТЗ 3.1.1 требует роли, регистрацию не требует нигде; ТЗ 8.2.5 требует демонстрационные учётные записи.*
- **PDF-отчёт** — печать из браузера по шаблону `@media print`, без серверной генерации.
  *Основание: ТЗ 3.7.3 — «PDF и расчётных таблиц в Excel или CSV либо в эквивалентные открываемые форматы».*
- **Извлечение данных по ссылке** — прототип-ассистент ввода в админке, не продакшн-парсер. Помечается как прототип в презентации.
  *Основание: ТЗ 3.3.5 — «Автоматический парсинг является преимуществом, но не заменяет ручное управление»; ТЗ 5.7 требует указать, что реализовано полностью, частично или как прототип.*

### 2.3. Чего не делаем

3D-визуализация (ТЗ 3.6.1: «3D не требуется»). Чат с каталогом на LLM — подменяет детерминированный движок, за объяснимость которого дают 25% балла. Рекомендательная ML-модель вместо правил — на полусотне объектов учить нечего, а на вопрос «почему этот робот» ответить нельзя. Реальная маршрутизация с обходом препятствий. Мобильная вёрстка (ТЗ 4.5.5 требует от 1366×768). Интеграции с WMS/ERP/1С — только описание возможных (ТЗ 3.8.3).

---

## 3. Стек и инфраструктура

### 3.1. Компоненты

| Слой | Технология | Примечание |
|---|---|---|
| Прокси | Traefik v3.1 | TLS, один origin — CORS не нужен |
| Фронтенд | Nuxt 3 (SSR), Vue 3, TypeScript | 2D на инлайн-SVG без библиотек |
| Бэкенд | FastAPI, uvicorn, Python 3.12 | `--workers 4` |
| Модели | pydantic v2 | источник правды по типам |
| ORM | SQLAlchemy 2.0 + Alembic | |
| БД | PostgreSQL 16 | JSONB + GIN, `pg_trgm` для поиска |
| Кэш | Redis 7 | результаты расчёта по хэшу входа |
| Оптимизация | OR-Tools CP-SAT | состав парка |
| Пакеты | uv | |
| Запуск | Docker Compose | ТЗ 4.2.3 требует Dockerfile и compose |

### 3.2. Контур

```
        Ubuntu VPS, 2 vCPU / 4 GB
┌──────────────────────────────────────────────────────────┐
│  traefik:v3.1        :80 / :443, Let's Encrypt           │
│    ├─ PathPrefix(`/api`) → api      priority 10          │
│    └─ PathPrefix(`/`)    → web      priority 1           │
│                                                          │
│  web     node:22-alpine · Nuxt 3 SSR              :3000  │
│  api     python:3.12-slim · uvicorn --workers 4   :8000  │
│  db      postgres:16-alpine        volume pgdata         │
│  cache   redis:7-alpine                                  │
│                                                          │
│  ./data:ro → catalog_master.xlsx, rules/, snapshots/     │
└──────────────────────────────────────────────────────────┘
```

Пять контейнеров. Брокера сообщений и воркера нет намеренно:

| Задача | Как решается | Почему не воркер |
|---|---|---|
| Конвейер расчёта | в процессе `api` | бюджет ТЗ 4.3.2 — 10 с, реально сотни мс |
| Монте-Карло 2000 прогонов | там же | считается только экономика, не весь конвейер |
| Оптимизатор состава парка | там же, CP-SAT | доли секунды на полусотне продуктов |
| Обновление каталога по запросу | `BackgroundTasks` + таблица `refresh_run` | статус поллится фронтом |
| Плановая проверка источников | APScheduler в `lifespan` | 15 строк против брокера и контейнера |

Порог, за которым появляется воркер: один расчёт дольше 10 секунд. Проект туда не подходит.

### 3.3. Приоритеты роутеров Traefik — обязательны

Без `priority` правило `PathPrefix(`/`)` у фронтенда перехватывает `/api`. Это самая частая поломка этой связки.

### 3.4. Два режима запуска

ТЗ 8.2.2 требует ссылку на развёрнутый прототип, ТЗ 8.2.8 — готовность поднять сборку по запросу жюри, ТЗ 6.10 — чтобы сторонний специалист развернул и воспроизвёл демо-расчёт. Значит `git clone && make up` должен подниматься с засеянными данными и без единого секрета в руках.

```make
up:      ## локально (для жюри): поднять и засеять
	docker compose up -d --build
	docker compose exec -T api alembic upgrade head
	docker compose exec -T api python -m scripts.seed --demo
	@echo "→ http://localhost"

deploy:  ## прод
	docker compose -f compose.yml -f compose.prod.yml up -d --build

gen:     ## перегенерировать типы фронта из OpenAPI
	npx openapi-typescript http://localhost/api/v1/openapi.json -o web/types/api.ts
```

---

## 4. Ядро: конвейер расчёта

```
Профиль объекта + Задачи
  │
  ├─ 1. MATCH     каталог → Candidate[]        жёсткие ограничения, трёхзначно
  ├─ 2. SIZE      → SizedOption[]              сколько штук и по какой формуле
  ├─ 3. COST      → Economics                  CAPEX / OPEX / эффект / окупаемость / ROI / TCO
  ├─ 4. RANK      → Scenario[]                 три сценария, объяснимый скоринг
  ├─ 5. LAYOUT    → Plan                       зоны, маршруты, расстановка
  └─ 6. SIM       → ShiftRun                   прогон смены, загрузка, events[]
```

Каждый шаг — чистая функция `(input, catalog, norms) -> (result, list[TraceStep])`. Без обращений к БД, без сайд-эффектов, без чтения настроек.

### 4.1. Контракт шага

```python
# engine/models.py
class TraceStep(BaseModel):
    step: Literal["match", "size", "cost", "rank", "layout", "sim"]
    product_id: UUID | None = None
    verdict: Literal["pass", "fail", "unknown"] | None = None
    formula: str | None = None    # "ceil(120 / (3600/48 * 0.82))" — с подставленными числами
    value: float | None = None
    unit: str | None = None
    source: str | None = None     # "[A] ronavi-robotics.ru/catalogue/h1500"
    message: str                  # человеческая формулировка для интерфейса
```

`trace[]` уезжает в ответе API целиком и показывается пользователю. Это выполнение ТЗ 3.4.2 (причины соответствия, ограничения и недостающие данные), ТЗ 3.4.5 (объяснимое ранжирование) и ТЗ 3.5.8 (все формулы, единицы, источники и допущения доступны).

### 4.2. Правила — данные, а не код

Логика подбора и расчёта количества хранится в БД как `RuleSpec`, по одной на тип решения. Добавление продукта не требует правки кода; добавление типа решения — тоже, пока он попадает в одно из пяти семейств формул (§7.3).

```json
{
  "solution_type": "transport_amr",
  "hard": [
    {"field": "Грузоподъёмность_кг",  "op": ">=", "ref": "task.max_load_kg"},
    {"field": "Мин_ширина_прохода_м", "op": "<=", "ref": "site.aisle_width_m"},
    {"field": "Темп_мин_C",           "op": "<=", "ref": "site.temp_min_c"},
    {"field": "Габариты_тары_мм",     "op": "in", "ref": "task.container_types"}
  ],
  "soft": [
    {"field": "УГТ", "weight": 0.20, "dir": "max"},
    {"field": "Достоверность_общая", "weight": 0.15, "map": {"A": 1.0, "B": 0.6, "C": 0.3}},
    {"field": "Доля_локализации", "weight": 0.10, "dir": "max"},
    {"field": "has_case_for_object_type", "weight": 0.15, "dir": "max"}
  ],
  "sizing": {
    "family": "flow_cycle",
    "vars": {
      "t_cycle": "2 * task.route_len_m / robot.Скорость_с_грузом_мс + task.t_load_s + task.t_unload_s",
      "uptime":  "robot.Время_работы_ч / (robot.Время_работы_ч + robot.Время_зарядки_ч)"
    },
    "formula": "ceil(task.flow_per_hour / (3600 / t_cycle * uptime * norm.k_util))"
  }
}
```

Вычислитель выражений — **безопасный**: разбор через `ast.parse(mode="eval")` с белым списком узлов (`BinOp`, `Compare`, `Name`, `Constant`, `Call` только для `ceil`/`floor`/`min`/`max`/`abs`). Никакого `eval()` от строки из БД.

---

## 5. Структура репозитория

```
robots/
├─ ARCHITECTURE.md              # этот файл
├─ Makefile
├─ compose.yml
├─ compose.prod.yml
│
├─ engine/                      # чистый python-пакет: uv pip install -e ./engine
│  ├─ models.py                 # pydantic: вход, выход, TraceStep, AttrValue
│  │                            # ЕДИНСТВЕННАЯ точка связи между всеми четырьмя людьми
│  ├─ rules.py                  # RuleSpec + безопасный вычислитель выражений
│  ├─ match.py                  # шаг 1
│  ├─ size.py                   # шаг 2, пять семейств формул
│  ├─ cost.py                   # шаг 3, экономическая модель
│  ├─ rank.py                   # шаг 4, скоринг и сборка сценариев
│  ├─ layout.py                 # шаг 5, расстановка и трассировка маршрутов
│  ├─ sim.py                    # шаг 6, прогон смены тиками
│  ├─ mc.py                     # Монте-Карло по достоверности
│  ├─ optimize.py               # CP-SAT, оптимальный состав парка
│  ├─ pipeline.py               # run_pipeline(req, catalog, norms) -> CalcResponse
│  └─ tests/
│     ├─ golden/                # эталонные входы и выходы
│     └─ test_*.py
│
├─ api/
│  ├─ main.py                   # lifespan: каталог, правила и нормативы в app.state
│  ├─ deps.py
│  ├─ routers/
│  │  ├─ catalog.py  projects.py  calc.py  admin.py  auth.py
│  ├─ services/
│  │  ├─ cache.py  catalog.py  enrich.py  importer.py  export.py
│  ├─ db/
│  │  ├─ models.py  session.py
│  ├─ alembic/
│  └─ Dockerfile
│
├─ web/                         # Nuxt 3
│  ├─ types/api.ts              # СГЕНЕРИРОВАН из OpenAPI — правки затрутся
│  ├─ pages/
│  │  ├─ index.vue  catalog/  project/[id]/  admin/
│  ├─ components/
│  │  ├─ wizard/                # мастер ввода объекта
│  │  ├─ compare/               # таблица сравнения решений и сценариев
│  │  ├─ trace/                 # раскрытие формул и источников
│  │  └─ plan/                  # 2D: зоны, маршруты, реплей events[]
│  └─ Dockerfile
│
├─ data/
│  ├─ catalog_master.xlsx       # нормализованный каталог, схема §6.7
│  ├─ rules/*.json              # RuleSpec по типам решений
│  ├─ norms/*.json              # расчётные нормативы с обоснованиями
│  ├─ sites/*.json              # демо-наборы: склад, аэропорт, медучреждение
│  └─ snapshots/*.html          # закэшированные страницы источников (ТЗ 4.2.7)
│
├─ scripts/
│  ├─ seed.py                   # xlsx + json → БД
│  ├─ normalize.py              # исходные 4 файла → catalog_master.xlsx
│  └─ refresh_sources.py
│
└─ docs/                        # ТЗ 6: сопроводительная документация
   ├─ deployment.md  data-model.md  economics.md  matching.md  api.md  limitations.md
```

---

## 6. Модель данных

### 6.1. Иерархия каталога — выводится, а не хранится

ТЗ 3.3.1 требует иерархию `отрасль → тип объекта → процесс → тип решения → продукт`. Дерево хранить **нельзя**: один продукт применим в нескольких ветках (транспортный AMR подходит и складу торговой компании, и цеху промышленного предприятия). Хранение деревом приведёт к дублированию карточек и расхождению данных.

Продукт висит только на типе решения. Дерево собирается джойнами по цепочке справочников.

```sql
create table industry      (id serial primary key, code text unique not null, name text not null);
create table object_type   (id serial primary key, code text unique not null, name text not null);
create table process       (id serial primary key, code text unique not null, name text not null);
create table solution_type (
  id serial primary key,
  code text unique not null,
  name text not null,
  family text not null,          -- семейство формул расчёта количества, см. §7.3
  rule_spec jsonb not null
);

create table industry_object  (industry_id int not null references industry,
                               object_type_id int not null references object_type,
                               primary key (industry_id, object_type_id));
create table object_process   (object_type_id int not null references object_type,
                               process_id int not null references process,
                               primary key (object_type_id, process_id));
create table process_solution (process_id int not null references process,
                               solution_type_id int not null references solution_type,
                               primary key (process_id, solution_type_id));
```

Ветка каталога:

```sql
select i.name as industry, o.name as object_type, p.name as process, st.name as solution_type,
       count(pr.id) as products
from industry i
join industry_object  io on io.industry_id      = i.id
join object_type      o  on o.id                = io.object_type_id
join object_process   op on op.object_type_id   = o.id
join process          p  on p.id                = op.process_id
join process_solution ps on ps.process_id       = p.id
join solution_type    st on st.id               = ps.solution_type_id
left join product     pr on pr.solution_type_id = st.id and pr.valid_to is null
group by 1,2,3,4
order by 1,2,3,4;
```

Добавление новой отрасли или типа объекта — вставка строк в справочник и две строки связей. Это выполнение ТЗ 4.2.6 и раздела 2 («архитектура должна допускать добавление новых отраслей, объектов и типов решений без переработки ядра»).

### 6.2. Продукт и параметры — гибрид колонок и JSONB

Чистые колонки требуют миграции на каждый новый параметр, что противоречит ТЗ 3.2.6 и 4.2.6. Чистый EAV даёт нечитаемый код и мёртвые фильтры. Решение: в колонках — то, по чему фильтруют всегда, остальное в JSONB с описанием в справочнике.

```sql
create table product (
  id uuid primary key default gen_random_uuid(),
  solution_type_id int not null references solution_type,
  name         text not null,
  manufacturer text not null,
  legal_entity text,                     -- уточнённое юрлицо, если отличается от каталога
  country      text,                     -- «страна происхождения», группа Идентификация
  availability text not null,            -- operation | piloting | rnd
  trl          smallint,                 -- УГТ 1..9
  market_potential smallint,             -- 1..5, из каталога организатора
  summary      text,
  attrs        jsonb not null default '{}',   -- ключ attribute_def.key → AttrValue
  valid_from   bigint not null references catalog_version(id),
  valid_to     bigint references catalog_version(id)
);
create index on product using gin (attrs jsonb_path_ops);
create index on product (solution_type_id) where valid_to is null;
create index on product using gin ((name || ' ' || manufacturer) gin_trgm_ops);

-- новый параметр = строка, не миграция (ТЗ 3.2.6, 4.2.6)
create table attribute_def (
  key          text primary key,         -- 'Грузоподъёмность_кг'
  group_code   text not null,            -- одна из 6 групп обязательной таблицы ТЗ 3.3
  label        text not null,
  unit         text,
  datatype     text not null,            -- number | range | text | enum | bool
  enum_values  text[],
  required_for text[],                   -- коды solution_type, где параметр обязателен
  sort         smallint
);
```

Группы `group_code` соответствуют обязательной таблице ТЗ 3.3 буквально: `identification`, `technical`, `infrastructure`, `economics`, `applicability`, `data_quality`.

**Карточка продукта, таблица сравнения, форма редактирования в админке и JSON-схема извлечения по ссылке — все четыре генерируются из `attribute_def`.** Одна строка справочника — и параметр появился везде сразу.

### 6.3. Значение характеристики — объект, а не скаляр

ТЗ 3.3.4 требует хранить ссылку на источник, дату получения или обновления данных и признак подтверждённости характеристики.

**Значение не подписывается буквой достоверности.** Оно ссылается на источник, а достоверность — свойство источника (§6.4) и выводится из него. Иначе буква и ссылка неизбежно разъезжаются: источник поменяли, `[A]` осталась. Дата по той же причине живёт на источнике, а не на каждом из семидесяти полей.

```python
class AttrValue(BaseModel):
    status: Literal["known", "unknown", "not_applicable"] = "known"
    value: float | str | bool | list[float] | None = None   # list = диапазон [min, max]
    unit: str | None = None
    source_id: int | None = None    # достоверность и дата берутся отсюда
    quote: str | None = None        # цитата из источника, подтверждающая значение
    note: str | None = None
    extracted_by: str | None = None # модель и версия, если значение извлечено автоматически
```

Достоверность считается, а не хранится:

```python
RELIABILITY = {"vendor": "A", "dealer": "B", "media": "B",
               "catalog": "B", "analogue": "C", "assumption": "D"}

def confirms(value, quote: str | None) -> bool:
    norm = lambda s: re.sub(r"[\s ,]", "", str(s)).lower()
    return bool(quote) and norm(value) in norm(quote)

def reliability(a: AttrValue, src: Source) -> str:
    grade = RELIABILITY[src.kind]
    if grade in ("A", "B") and not confirms(a.value, a.quote):
        return "C"      # источник есть, но значение им не подтверждается дословно
    return grade
```

Три состояния `status`, а не `value is None`:

- `known` — значение есть;
- `unknown` — данных нет, нужен запрос вендору; даёт `verdict: "unknown"` в MATCH и попадает в блок «требует уточнения»;
- `not_applicable` — поле осознанно закрыто (у стационарной системы нет автономности); считается заполненным и даёт `pass`.

Заполненность не хранится, а считается:

```python
def completeness(p: Product, defs: list[AttributeDef]) -> tuple[int, int]:
    req = [d for d in defs if not d.required_for or p.solution_type_code in d.required_for]
    ok = sum(1 for d in req
             if (a := p.attrs.get(d.key)) and a.status in ("known", "not_applicable"))
    return ok, len(req)
```

### 6.4. Источники, кейсы, нормативы

Достоверность живёт здесь и только здесь. «Оценка по аналогу» и «допущение команды» — такие же источники, просто без URL: это держит модель однородной, у любого значения ровно один источник и буква выводится из него.

| `kind` | Достоверность | Что это |
|---|---|---|
| `vendor` | A | официальный сайт производителя или разработчика, технический паспорт |
| `dealer` | B | дилер, интегратор |
| `media` | B | отраслевые СМИ, публикация о внедрении |
| `catalog` | B | публичный отраслевой каталог, каталог организатора |
| `analogue` | C | оценка по аналогу; `ref_product_id` указывает, по какому |
| `assumption` | D | допущение команды; `rationale` обязателен |

```sql
create table source (
  id serial primary key,
  kind text not null,              -- vendor | dealer | media | catalog | analogue | assumption
  url text, publisher text, title text,
  captured_at date not null,       -- дата получения или обновления данных (ТЗ 3.3.4)
  rationale text,                  -- обязателен для analogue и assumption
  ref_product_id uuid references product,   -- для analogue: с какого продукта снята оценка
  content_hash text,               -- для детекта изменений (ТЗ 3.3.6)
  last_checked_at timestamptz,
  constraint reasoned check (kind not in ('analogue', 'assumption') or rationale is not null)
);

-- «наличие реализованных кейсов» из группы Применимость (ТЗ 3.3) и вклад в скоринг (ТЗ 3.4.5)
create table product_case (
  id serial primary key,
  product_id uuid not null references product,
  object_type_id int references object_type,
  process_id int references process,
  customer text, summary text,
  source_id int references source
);

-- расчётные нормативы и коэффициенты. Источник обязателен по той же схеме, что и у значений
-- каталога: для допущения команды это source вида assumption, а там rationale — NOT NULL.
-- ТЗ 3.5.1 запрещает недокументированные коэффициенты, и здесь это обеспечено физически.
create table calc_norm (
  id serial primary key,
  solution_type_id int references solution_type,   -- null = общий норматив
  key text not null,               -- k_util | integration_pct | commissioning_pct | training_rub |
                                   -- spare_pct | service_pct | repair_pct | energy_tariff | ...
  value numeric not null,
  unit text,
  source_id int not null references source,        -- обоснование и достоверность берутся отсюда
  editable boolean not null default true,          -- ТЗ 3.5.3: пользователь меняет допущения
  unique (solution_type_id, key)
);
```

### 6.5. Версионирование каталога

ТЗ 3.1.5 требует переоткрыть проект и воспроизвести ранее выполненный расчёт **с указанием версии исходных данных и расчётной модели**. Это требование к каталогу, а не к проектам: если продукты правятся на месте, вчерашний расчёт воспроизвести нельзя.

```sql
create table catalog_version (
  id bigserial primary key,
  published_at timestamptz not null default now(),
  published_by text,
  note text
);
```

Продукты — append-only с интервалом жизни (`valid_from` / `valid_to`). Админ нажимает «Опубликовать» → создаётся версия, изменённые продукты закрываются и вставляются заново. Прогон сохраняет `catalog_version_id` и `engine_version`. Воспроизведение:

```sql
select * from product
where valid_from <= :v and (valid_to is null or valid_to > :v);
```

### 6.6. Проекты, прогоны, очередь модерации

```sql
create table app_user (
  id uuid primary key default gen_random_uuid(),
  login text unique not null,
  password_hash text not null,      -- argon2, ТЗ 4.4.2
  role text not null                -- guest | user | admin
);

create table project (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references app_user,   -- ТЗ 4.4.3: изоляция проектов
  name text not null,
  object_type_id int not null references object_type,
  site jsonb not null,              -- SiteProfile
  tasks jsonb not null,             -- list[Task]
  overrides jsonb not null default '{}',        -- ТЗ 3.5.4: ручные корректировки с фиксацией
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table calc_run (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references project on delete cascade,
  catalog_version_id bigint not null references catalog_version,
  engine_version text not null,
  request jsonb not null,
  response jsonb not null,          -- включая trace[] и events[]
  created_at timestamptz default now()
);

-- всё входящее — импорт, парсер, ручная правка — проходит через одну очередь (ТЗ 3.3.5)
create table attr_proposal (
  id bigserial primary key,
  product_id uuid references product,
  key text not null,
  new_value jsonb not null,         -- AttrValue
  origin text not null,             -- import | parser | manual
  status text not null default 'pending',   -- pending | approved | rejected
  created_at timestamptz default now(),
  reviewed_by text, reviewed_at timestamptz
);

create table refresh_run (
  id bigserial primary key,
  kind text not null,               -- sources_check | import
  status text not null,             -- running | done | failed
  started_at timestamptz default now(), finished_at timestamptz,
  stats jsonb, error text
);
```

### 6.7. Схема мастер-файла каталога

`data/catalog_master.xlsx`, лист `Каталог`. Одна строка — одно решение. Значения с пометками в квадратных скобках: `1500 [A]`, `±0,05 [C]`, `нет данных`, `не применимо`.

Пометка в файле — это **ссылка на источник, а не оценка значения**. При импорте `scripts/normalize.py` разрешает её в `source_id`: `[A]` — вендорский URL из колонки «Источники», `[B]` — дилерский или медийный оттуда же, `[C]` — создаётся источник вида `analogue` с обоснованием из колонки «Комментарий», `[D]` — `assumption`. В базе буква не хранится нигде; в файле она остаётся удобной формой записи для человека.

Обязательные группы колонок — по таблице ТЗ 3.3:

| Группа | Колонки |
|---|---|
| Идентификация | Название, Производитель, Юрлицо_уточнение, Тип_решения_код, Назначение, Страна, Статус, УГТ, Рын_потенциал |
| Технические | Грузоподъёмность_кг, Габариты_ДхШхВ_мм, Масса_кг, Скорость_с_грузом_мс, Скорость_без_груза_мс, Скорость_вертикальная_мс, Производительность, Производительность_ед, Время_работы_ч, Время_зарядки_ч, Замена_АКБ_мин, Точность_мм, Навигация, Темп_мин_C, Темп_макс_C, Влажность_макс_%, Исполнение, IP_класс |
| Инфраструктура | Мин_ширина_прохода_м, Нагрузка_на_пол_кг_м2, Тип_зарядки, Роботов_на_станцию, **Требования_к_связи**, Интеграция_ПО, Регламент_сервиса, Требования_к_инфраструктуре, Тип_тары, Габариты_тары_мм |
| Экономика | Цена_за_единицу_руб, Что_входит_в_цену, **Стоимость_ПО_руб**, **Стоимость_внедрения_руб**, Сервис_%_в_год, RaaS_доступен, Срок_службы_лет, Гарантия, Срок_внедрения |
| Применимость | Объекты, Процессы, Кейсы, Риски, Не_путать_с |
| Качество данных | Источники, Дата_актуализации, Достоверность_общая, Готов_к_автоподбору |

Три колонки выделены жирным — **их нет в исходных файлах, и без них не собирается экономическая модель** (§8.1): CAPEX по ТЗ 3.5 состоит из семи статей, а каталог даёт одну. Если данных от вендора нет, значение берётся из `calc_norm` — коэффициентом, за которым стоит источник вида `assumption` с обязательным обоснованием.

---

## 7. Подбор

### 7.1. MATCH — жёсткие ограничения

Для каждого продукта, чей `solution_type` привязан к процессу задачи, прогоняются предикаты `rule_spec.hard`. Предикат возвращает **три значения**:

```python
def check(pred: HardRule, product: Product, ctx: Context) -> Verdict:
    a = product.attrs.get(pred.field)
    if a is None or a.status == "unknown":
        return Verdict.UNKNOWN          # поле не заполнено — не вина продукта
    if a.status == "not_applicable":
        return Verdict.PASS             # ограничение к нему не относится
    return Verdict.PASS if compare(a.value, pred.op, resolve(pred.ref, ctx)) else Verdict.FAIL
```

Итог по продукту:

| Все предикаты | Результат | Куда попадает |
|---|---|---|
| хотя бы один `fail` | исключён | список с причиной (ТЗ 3.4.3) |
| нет `fail`, есть `unknown` | «требует проверки» | отдельный блок + запрос вендору |
| все `pass` | подходит | основная выдача |

Почему это принципиально: в собранных данных температурный диапазон известен у 2 позиций из 37 старого формата, IP-класс — у одной. На `bool`-предикате половина каталога вылетит на морозильном складе не из-за несоответствия, а из-за пустого поля.

Блок «требует уточнения у вендора» генерируется автоматически: продукт, поле, компания, ссылка на источник. Это выполнение ТЗ 3.4.3 («при недостатке данных решение может быть отмечено как требующее проверки») и одновременно практическая ценность платформы для самого ФЦ БАС, который этот каталог ведёт.

### 7.2. Скоринг

`rule_spec.soft`, нормировка каждого фактора в [0,1], взвешенная сумма. Вклад каждого фактора едет в `trace` — ТЗ 3.4.5 требует, чтобы пользователь видел критерии и вклад ключевых факторов.

Продукт со статусом `rnd` или УГТ < 7 в автоподбор не попадает, но доступен для ручного добавления в сравнение с предупреждением (ТЗ 3.4.4).

### 7.3. SIZE — пять семейств формул

Одиннадцать типов решений сводятся к пяти шаблонам. Добавление нового типа решения не требует кода, пока он попадает в существующее семейство.

**A. `flow_cycle`** — транспортные AMR, доставщики, FMR-штабелёры, тягачи, грузовики, курьеры, манипуляторы-комплектовщики.

```
t_cycle = 2 × L / v + t_load + t_unload + t_wait
uptime  = T_work / (T_work + T_charge)
q       = 3600 / t_cycle × uptime × k_util          # операций в час на единицу
N       = ceil(Q_peak / q) + n_reserve
```

**B. `area_window`** — уборщики.

```
N = ceil(S_clean × f_passes / (P_m2h × T_window))
```

**C. `station_robots`** — автоматизированное хранение.

```
# кубическое (goods-to-person)
stations = ceil(Q_peak_boxes_h / q_station)
robots   = stations × K                              # K из ТТХ продукта
shafts   = ceil(V_storage / (boxes_per_shaft × levels))

# шаттловое (глубинное)
shuttles = число одновременно обслуживаемых каналов
channels = pallet_places / (channel_depth × tiers)
+ отдельно считать погрузчики для постановки шаттла в канал

# кран-штабелёр
cranes = ceil(Q_peak_pallets_h / q_crane)
aisles = cranes                                      # один кран на проход
```

**D. `count_window`** — инвентаризаторы.

```
N = ceil(positions × f_frequency / (P_positions_h × T_window))
```

**E. `perimeter_rounds`** — охрана и патрулирование.

```
t_round = L_perimeter / v + n_stops × t_stop
N       = ceil(rounds_required × t_round / T_window)
```

`k_util`, `n_reserve`, `f_passes` и прочие — из `calc_norm`, редактируемые пользователем (ТЗ 3.5.3), с обоснованием в интерфейсе.

---

## 8. Экономическая модель

### 8.1. Формулы

По таблице «Рекомендуемые расчётные зависимости» ТЗ 3.5.2.

```
CAPEX = Σ(price_i × N_i)                    # оборудование
      + infrastructure                       # стеллажи, зарядные станции, сеть, покрытие пола
      + software                             # ПО и лицензии
      + integration_pct   × equipment        # интеграция        [D] calc_norm
      + commissioning_pct × equipment        # пусконаладка      [D] calc_norm
      + training_rub                         # обучение          [D] calc_norm
      + spare_pct         × equipment        # резерв            [D] calc_norm

OPEX_year = service_pct × equipment          # сервис
          + license_year                     # лицензии
          + energy_kwh × tariff              # электроэнергия
          + connectivity_year                # связь
          + consumables_year                 # расходные материалы
          + repair_pct × equipment           # ремонт
          + staff_ops_fte × salary_year      # персонал эксплуатации

energy_kwh = Σ(N_i × P_watt_i / 1000 × T_work_h × days_year)

Effect_year = fot_released                   # экономия ФОТ
            + throughput_gain                # дополнительный доход
            + prevented_losses               # предотвращённые потери
            − ΔOPEX                          # относительно базового сценария

Payback = CAPEX / Effect_year                       при Effect_year > 0
ROI(h)  = Σ Effect_year(1..h) / CAPEX × 100%
TCO(h)  = CAPEX + Σ OPEX_year(1..h) + replacement(h)     h ≥ 5 лет (ТЗ 3.5.2)
```

`fot_released` — единственная статья эффекта, которая считается достоверно. `throughput_gain` обязательно даётся диапазоном, а не точкой.

Все коэффициенты `[D]` живут в `calc_norm` с `rationale`. ТЗ 3.5.1: «Использование недокументированных коэффициентов не допускается».

### 8.2. Три сценария

ТЗ 3.5.5 требует сравнить не менее трёх сценариев. Они складываются сами, и третий — это оптимизатор из §8.5:

| Сценарий | Содержание |
|---|---|
| Без роботизации | текущие ручные операции, базовый OPEX |
| Подбор по задачам | каждый процесс закрывается отдельно, лучший продукт по скорингу |
| Оптимальный состав | CP-SAT по общему бюджету и площади |

Плюс варианты приобретения — покупка и услуга (RaaS), где вендор её предлагает (ТЗ 2.1.3).

### 8.3. What-if и чувствительность

ТЗ 3.5.3 — пользователь меняет: стоимость персонала, режим работы, производительность, стоимость оборудования, стоимость обслуживания, коэффициент загрузки, горизонт расчёта.

ТЗ 3.5.6 — чувствительность минимум к трём параметрам. Получается побочным продуктом Монте-Карло: разложение дисперсии по входам уже посчитано.

ТЗ 3.5.7 — рекомендация не строится на жёстком пороге. Интервалы настраиваемые: до 3 лет / 3–5 / более 5, и рядом — числовой результат, риски и интерпретация.

### 8.4. Монте-Карло по достоверности данных

Достоверность источника задаёт разброс значения; расчёт экономики повторяется N раз; результат — интервал и разложение неопределённости по входам.

```python
# engine/mc.py
SPREAD = {"A": 0.02, "B": 0.10, "C": 0.30, "D": 0.40}

def sample(a: AttrValue, src: Source, rng: random.Random) -> float:
    s = SPREAD[reliability(a, src)]        # §6.3, выводится из источника
    return a.value * rng.triangular(1 - s, 1 + s, 1.0)      # мода — заявленное значение

def monte_carlo(req, catalog, norms, n: int = 2000) -> Interval:
    runs = [cost_only(req, catalog, norms, rng=random.Random(i), sampler=sample)
            for i in range(n)]
    pb = sorted(r.payback_years for r in runs)
    return Interval(
        p10=pb[n // 10], p50=pb[n // 2], p90=pb[9 * n // 10],
        drivers=variance_attribution(runs),   # вклад каждого входа в разброс
    )
```

Главный выход — не интервал, а `drivers`. Платформа формулирует сама:

> Окупаемость 2,4–3,8 года. 63% ширины интервала даёт производительность Ronavi H1500 — значение снято по аналогу, а не с паспорта производителя. Один запрос вендору сузит интервал до ±4 месяцев.

Это превращает пробел в данных в рекомендацию к действию и закрывает ТЗ 3.5.7 по существу, а не формально.

### 8.5. Оптимальный состав парка

Реальный объект — несколько процессов, общий бюджет и общая площадь. Оптимум отличается от поштучного подбора: одна модель нередко закрывает два процесса дешевле двух специализированных. Это корректно поставленная задача целочисленного программирования — ТЗ в списке преимуществ требует «методы оптимизации при наличии обоснованной задачи».

```python
# engine/optimize.py
from ortools.sat.python import cp_model

m = cp_model.CpModel()
n = {p.id: m.NewIntVar(0, 50, f"n_{p.id}") for p in candidates}

for proc in processes:                       # покрыть пиковый поток каждого процесса
    m.Add(sum(n[p.id] * thr[p.id][proc.id] for p in candidates) >= proc.demand)

m.Add(sum(n[p.id] * price[p.id]     for p in candidates) <= budget)
m.Add(sum(n[p.id] * footprint[p.id] for p in candidates) <= site.free_m2)
m.Maximize(sum(n[p.id] * annual_effect[p.id] for p in candidates))
```

CP-SAT работает только с целыми коэффициентами: цены в копейках, производительность и эффект — умноженные на 100.

---

## 9. Каталог: наполнение и админка

### 9.1. Импорт от организатора (ТЗ 3.3.2)

`POST /api/v1/admin/catalog/import` принимает xlsx организатора. Соответствие колонок задаётся профилем маппинга в `data/mapping/*.json`, а не хардкодом — смена версии файла не должна требовать правки кода. Все значения попадают в `attr_proposal` со `origin: "import"`.

### 9.2. Дополнение из открытых источников (ТЗ 3.3.3)

Пункт требует, чтобы **данные** были собраны из открытых источников — официальных сайтов производителей и интеграторов, технических паспортов, публичных каталогов, материалов кейсов. Парсер он не требует; автоматизация названа преимуществом в ТЗ 3.3.5.

Базовый уровень (обязательный): каталог наполнен вручную, у каждой характеристики зафиксирован источник, а через него — дата и достоверность; всё это видно в карточке продукта и в отчёте.

Уровень-преимущество: **ассистент ввода по ссылке**. Админ вставляет URL, бэкенд берёт страницу, модель извлекает характеристики по JSON-схеме, сгенерированной из `attribute_def`, форма открывается предзаполненной черновиком. Правил под конкретные сайты нет — работает одинаково на любом вендоре.

```python
def extraction_schema(defs: list[AttributeDef], st_code: str) -> dict:
    props = {}
    for d in defs:
        if d.required_for and st_code not in d.required_for:
            continue
        props[d.key] = {
            "type": "object",
            "properties": {
                "value": {"type": ["number", "string", "boolean", "null"]},
                "unit":  {"type": ["string", "null"]},
                "quote": {"type": "string",
                          "description": "точная цитата со страницы, подтверждающая значение"},
            },
            "required": ["value", "quote"],
        }
    return {"type": "object", "properties": props, "additionalProperties": False}
```

**Защита от галлюцинаций обязательна.** Извлечённое значение привязывается к источнику; буква нигде не проставляется, но цитата проверяется машинно, и значение без подтверждения автоматически читается как `C` через `reliability()` из §6.3:

```python
def attach(value, quote: str | None, url: str, session) -> AttrValue:
    host = (urlparse(url).hostname or "").removeprefix("www.")
    kind = "vendor" if host in VENDOR_DOMAINS else "media"
    src = get_or_create_source(session, url=url, kind=kind, captured_at=date.today())
    ok = confirms(value, quote)
    return AttrValue(
        value=value, source_id=src.id,
        quote=quote if ok else None,
        note=None if ok else "цитата не подтверждает значение дословно",
    )
```

Извлечённое **никогда не пишется в каталог напрямую** — только в `attr_proposal` со `origin: "parser"`. Админ видит тройку «значение — цитата — ссылка» и подтверждает.

`VENDOR_DOMAINS` засевается из перечня открытых источников, который предоставляет организатор (ТЗ 7.3).

### 9.3. Снапшоты — требование, а не оптимизация

ТЗ 4.2.7: «Внешние источники не должны быть единственной точкой отказа демонстрации. Конкурсная версия должна работать на заранее загруженных данных.»

```python
SNAPSHOTS = Path("data/snapshots")
UA = "FCBAS-Hackathon-Catalog/1.0 (+контакты команды)"

def fetch(url: str, *, force: bool = False) -> str:
    snap = SNAPSHOTS / f"{hashlib.sha256(url.encode()).hexdigest()[:16]}.html"
    if snap.exists() and not force:
        return snap.read_text()
    r = httpx.get(url, headers={"User-Agent": UA}, timeout=10, follow_redirects=True)
    r.raise_for_status()
    snap.parent.mkdir(parents=True, exist_ok=True)
    snap.write_text(r.text)
    return r.text
```

Перед сдачей — прогон с `force=True` по всем источникам, снапшоты в репозиторий. Демонстрация извлечения работает без сети.

### 9.4. Обновление каталога (ТЗ 3.3.6)

**По запросу админа** — `POST /api/v1/admin/catalog/refresh`, `BackgroundTasks`, статус в `refresh_run`, фронт поллит.

**Планово** — APScheduler в `lifespan`, раз в сутки. Перекачивает источники и сравнивает `content_hash`. При изменении каталог **не трогается**: в админке появляется «Источник изменился: Ronavi H1500, страница ТТХ. Проверить». Извлечение при этом не запускается — только детект.

### 9.5. Админка (ТЗ 3.3.5, 3.1.4)

Обязательна: ручное добавление и редактирование решений через административный интерфейс, управление справочниками, нормативами и источниками. Форма редактирования генерируется из `attribute_def`, поэтому своей логики почти не содержит и делается последней.

Экраны: список продуктов с фильтрами → карточка с формой по шести группам → очередь `attr_proposal` → справочники → `calc_norm` → источники и изменения → «Опубликовать версию».

### 9.6. Фильтрация, поиск, сравнение (ТЗ 3.3.7)

Фильтры и сортировка — в Postgres по колонкам и JSONB с GIN; поиск — `pg_trgm` по названию и производителю. Сравнение строится из `attribute_def`, с явными ячейками «нет данных» и «не применимо» вместо прочерков.

---

## 10. Визуализация и симуляция

ТЗ 3.6.2: «Визуализация должна использовать параметры выбранного сценария и подтверждать расчётную производительность.» ТЗ раздел 2.2, шаг 7: «Визуализация должна подтверждать расчёт, а не быть только декоративной анимацией.»

Поэтому анимация проигрывает **тот же прогон**, который дал цифру количества:

```
SIZE → N = 7
  → engine/sim.py: тик 0,5 с, смена 8 ч
  → загрузка парка 94%, очередь на зарядке 0
  → events[]: t, robot_id, x, y, state
  → фронт проигрывает events[] по таймлайну
  → если загрузка > 95% — пересчёт с N+1
```

**Симулятор писать самостоятельно, не на SimPy.** Нужен плотный массив позиций по времени для анимации, а не поток событий ресурса; фиксированный тик на 100–150 строк отдаёт `events[]` ровно в том виде, в каком его потребляет фронт.

**2D — инлайн-SVG с реактивностью Vue, не Canvas и не библиотека.** На плане 50–300 элементов: контур здания, зоны, полилинии маршрутов, иконки роботов. DOM это тянет, а редактирование зон получается почти бесплатно. Canvas понадобился бы от тысяч объектов.

Слои: подложка (контур из параметров или один из трёх пресетов) → зоны (drag-resize) → маршруты (автотрассировка по манхэттенской метрике между центрами зон) → роботы → точки зарядки.

Управление по ТЗ 3.6.3: пуск, стоп, перезапуск, скорость воспроизведения, выбор сценария.

---

## 11. API

Контракт между фронтом и бэком генерируется, а не согласовывается:

```
engine/models.py (pydantic v2) → /api/v1/openapi.json → openapi-typescript → web/types/api.ts
```

`web/types/api.ts` руками не правится. Правка модели без перегенерации ломает сборку фронта — на этапе сборки, а не на защите.

```
# каталог
GET  /api/v1/catalog/tree                      # иерархия, ТЗ 3.3.1
GET  /api/v1/catalog/products?filters=…        # фильтр, поиск, сортировка, ТЗ 3.3.7
GET  /api/v1/catalog/products/{id}             # карточка с источником по каждому полю
POST /api/v1/catalog/compare {ids: […]}        # сравнение, ТЗ 3.3.7
GET  /api/v1/catalog/attributes                # attribute_def — из него строится UI

# справочники и демо
GET  /api/v1/refs/object-types
GET  /api/v1/refs/object-types/{code}/params   # состав параметров, ТЗ 3.2.1
GET  /api/v1/demo/sites/{code}                 # демо-наборы для гостя, ТЗ 3.1.2, 2.1.1

# проекты и расчёт
POST /api/v1/projects                          # CRUD, копирование, ТЗ 3.1.3
GET  /api/v1/projects/{id}
POST /api/v1/projects/{id}/import              # xlsx/csv параметров, ТЗ 3.2.3
POST /api/v1/calculate                         # основной расчёт
POST /api/v1/calculate/sensitivity             # Монте-Карло, ТЗ 3.5.6
GET  /api/v1/projects/{id}/runs/{run_id}       # воспроизведение, ТЗ 3.1.5
GET  /api/v1/projects/{id}/export.xlsx         # ТЗ 3.7.3
GET  /api/v1/projects/{id}/report              # HTML под печать в PDF

# админка
POST /api/v1/admin/catalog/import              # ТЗ 3.3.2
POST /api/v1/admin/catalog/extract {url}       # ассистент по ссылке, ТЗ 3.3.3
POST /api/v1/admin/catalog/refresh             # ТЗ 3.3.6
POST /api/v1/admin/catalog/publish             # новая версия, ТЗ 3.1.5
GET  /api/v1/admin/proposals?status=pending    # ТЗ 3.3.5
POST /api/v1/admin/proposals/{id}/approve
CRUD /api/v1/admin/products|refs|norms|sources # ТЗ 3.1.4
```

### 11.1. Два правила по эндпоинту расчёта

```python
@router.post("/calculate", response_model=CalcResponse)
def calculate(                       # именно def, не async def:
    req: CalcRequest,                # тело CPU-bound, async заблокирует event loop
    cat: Catalog = Depends(get_catalog),
    cache: Redis = Depends(get_cache),
) -> CalcResponse:
    key = f"calc:{payload_hash(req)}"
    if hit := cache.get(key):
        return CalcResponse.model_validate_json(hit)
    res = run_pipeline(req, cat)     # чистая функция из engine/
    cache.setex(key, 3600, res.model_dump_json())
    return res
```

Каталог, правила и нормативы грузятся один раз в `lifespan` и живут в `app.state` — ходить в БД на каждое движение ползунка незачем, а валидация `RuleSpec` при старте падает сразу, а не в середине расчёта.

---

## 12. Исходные данные: что есть и что с ними не так

### 12.1. Состояние на момент написания

47 решений в 11 категориях, в **двух несовместимых форматах**:

| Источник | Категории | Решений | Формат |
|---|---|---|---|
| Категории 1–2 AMR | 1–2 | 12 | старый, 14 колонок |
| Категории 3–6 | 3–6 | 15 | старый, 14 колонок |
| Категории 10–11 | 10–11 | 10 | старый, **13** колонок, без «Источники» |
| Каталог 7–9 v2 | 7–9 | 10 | целевой, 82 колонки, с достоверностью и формулами |

Профиль: 23 в эксплуатации / 12 пилот / 2 разработка. УГТ 8–9 у 28 позиций из 37. Тридцать одна из 37 — Москва. Пять вендоров дают 17 позиций.

### 12.2. Дефекты, которые ломают импорт — чинятся в `scripts/normalize.py`

1. **Битая строка.** В файле категорий 10–11 строка 10 (шапка категории 11) затёрта: в колонках ТТХ и «Вид» лежат данные охранного робота, у которого пропали название, производитель и цена. Одно решение потеряно — в категории 11 должно быть 5 позиций, не 4.
2. **Дубль.** «Ровер для работы с грузовыми вагонами» (НИИАС) занесён дважды — в категориях 5 и 10, во второй ТТХ пустые.
3. **Дубль-вариант.** Система патрулирования МАИ разнесена на две строки («Безопасность» 3,6 млн / «Транспорт» 3,0 млн) — это одна позиция с двумя комплектациями.
4. **Пустые ТТХ** у четырёх позиций: Белка, Легат Патрол, ровер НИИАС в категории 10, МАИ «Транспорт».
5. **Юрлица не нормализованы:** `ООО «Диком-Сервис»` / `ООО "Диком-Сервис"`, `АО «НИИАС»` / `АО "Нииас"`, `ГК «Автомакон»` / `ООО «Вейбот Автомакон Роботикс»` / `ООО "ГК Автомакон"`. Нужен справочник вендоров.
6. **Цена как текст** в двух файлах (неразрывные пробелы), числом в третьем.
7. **Выброс:** DMR 300 Carrier B — 10,8 млн при грузоподъёмности 300 кг, при соседях по категории 0,95–1,5 млн. Проверить до заноса: это цена комплекса с надстройкой или ошибка.
8. **Нет признака готовности к автоподбору** в старом формате — проставляется по правилу: `availability == "rnd"` или `trl < 7` → не участвует.

### 12.3. Покрытие ТТХ в старом формате

Вся техника лежит одним текстовым блоком в колонке «Основные ТТХ». Покрытие по 37 позициям:

| Параметр | Есть |
|---|---|
| Скорость | 24/37 |
| Габариты | 22/37 |
| Масса, автономность | 21/37 |
| Грузоподъёмность, навигация | 19/37 |
| Зарядка | 12/37 |
| Точность | 9/37 |
| Температура | 2/37 |
| IP-класс | 1/37 |

### 12.4. Риск на критическом пути

Шаг SIZE упирается в `t_cycle`, а тот — в производительность решения. **По 37 позициям старого формата производительности нет ни у одной.** Без неё движок не «работает хуже», а не работает вообще, и Монте-Карло с оптимизатором считать не на чем.

Два выхода: проставить производительность хотя бы оценкой по аналогу с честной пометкой `[C]` при нормализации, либо демонстрировать глубокий расчёт на 10 позициях категорий 7–9, где данные уже собраны по целевой схеме. **Первый вариант предпочтителен, работа делается до бэкенда.**

---

## 13. Порядок работ

### 13.1. Первый час — фиксация контракта

1. `engine/models.py` — единственная точка связи между всеми. Зафиксировать и не менять без объявления.
2. FastAPI со стабом `/calculate`, возвращающим захардкоженный `CalcResponse` с парой записей `trace` и сотней `events`.
3. Сгенерировать `web/types/api.ts`, закоммитить.
4. С этого момента фронт и 2D работают на настоящих типах с фейковыми данными, движок — на настоящих данных без фронта. Никто никого не ждёт.

### 13.2. Этапы

| Этап | Содержание | Готово, когда |
|---|---|---|
| E0 | Нормализация данных | `catalog_master.xlsx` собран, дефекты §12.2 починены, производительность проставлена |
| E1 | Схема БД, справочники, seed | `make up` поднимает и засеивает с нуля |
| E2 | Каталог: дерево, фильтры, карточка, сравнение | ТЗ 3.3 закрыт, источники видны на каждом поле |
| E3 | MATCH + SIZE + trace | подбор объясняет включение и исключение каждого решения |
| E4 | COST + три сценария + what-if | ТЗ 3.5 закрыт, все коэффициенты с обоснованиями |
| E5 | LAYOUT + SIM + 2D-реплей | анимация подтверждает цифру количества |
| E6 | Монте-Карло + оптимизатор | интервал окупаемости и драйверы неопределённости |
| E7 | Админка, экспорт, документация | ТЗ 3.3.5, 3.7, раздел 6 |

Админка идёт предпоследней намеренно: она генерируется из `attribute_def` и почти не содержит своей логики.

### 13.3. Зоны ответственности (команда 4 человека)

| Зона | Что делает | Артефакт |
|---|---|---|
| Данные | мастер-каталог, `RuleSpec`, `calc_norm`, seed | `data/`, `scripts/` |
| Движок | конвейер, симуляция, Монте-Карло, оптимизатор, тесты | `engine/` |
| API + фронт | роуты, кэш, мастер ввода, сравнение, экспорт | `api/`, `web/pages/` |
| 2D | план, зоны, маршруты, реплей | `web/components/plan/` |

---

## 14. Трассировка на ТЗ организатора

| Пункт ТЗ | Требование | Где реализовано |
|---|---|---|
| 3.1.1–3.1.3 | роли, гость, CRUD проектов | §6.6, `routers/auth.py`, `projects.py` |
| 3.1.4 | админ управляет каталогом и нормативами | §9.5 |
| 3.1.5 | воспроизведение расчёта с версией данных | §6.5, `calc_run` |
| 3.2.1–3.2.6 | параметры объектов, импорт, валидация, расширяемость | §6.2, `refs/*/params` |
| 3.3.1 | иерархия отрасль → объект → процесс → тип → продукт | §6.1 |
| 3.3.2 | загрузка таблицы организатора | §9.1 |
| 3.3.3 | дополнение из открытых источников | §9.2 |
| 3.3.4 | источник, дата, признак подтверждённости характеристики | §6.3 `AttrValue.source_id` → §6.4 `source` |
| 3.3.5 | ручное управление + парсинг как преимущество | §9.2, §9.5 |
| 3.3.6 | обновление по запросу + плановое | §9.4 |
| 3.3.7 | фильтр, поиск, сортировка, сравнение | §9.6 |
| таблица 3.3 | шесть групп обязательных характеристик | §6.7 `attribute_def.group_code` |
| 3.4.1–3.4.5 | подбор, причины, недостающие данные, ручное добавление, объяснимость | §7.1, §7.2, `TraceStep` |
| 3.5.1–3.5.8 | экономическая модель, три сценария, чувствительность, прозрачность | §8 |
| 3.6.1–3.6.3 | 2D, подтверждение расчёта, управление воспроизведением | §10 |
| 3.7.1–3.7.5 | дашборд, отчёт, PDF/Excel, экспорт визуализации, оговорка | §11, §2.2 |
| 3.8.1–3.8.5 | API, импорт, описание интеграций, документация | §11, `docs/api.md` |
| 4.1, 4.3 | обычный ПК, 50 пользователей, расчёт ≤10 с, модель ≤60 с | §3.2 |
| 4.2.3 | Dockerfile и docker-compose | §3.4 |
| 4.2.5 | OpenAPI | §11 |
| 4.2.6 | добавление отраслей, объектов, параметров без переработки ядра | §6.1, §6.2, §4.2 |
| 4.2.7 | внешние источники не единственная точка отказа | §9.3 |
| 4.4.1–4.4.6 | роли, хэши паролей, изоляция, TLS, удаление проекта | §6.6, §3.2 |
| 4.5.1–4.5.5 | русский интерфейс, единицы и подсказки, понятные ошибки, 1366×768 | §0 п.5, `attribute_def.unit` |
| 5.7 | явно указать, что прототип | §2.2 |
| раздел 6 | сопроводительная документация | `docs/` |
| раздел 9, преимущества | автообновление каталога, оптимизация, API, чувствительность, фиксация происхождения | §9.4, §8.5, §11, §8.4, §6.3 |

---

## 15. Журнал решений

Записывать сюда всё, что отклоняется от этого файла, — иначе через сутки никто не вспомнит почему.

| Дата | Решение | Причина |
|---|---|---|
| — | Иерархия каталога выводится джойнами, а не хранится деревом | продукт применим в нескольких ветках; дерево даст дубли и расхождения |
| — | Значение ссылается на источник; достоверность и дата — свойства источника, а не подпись к числу | буква и ссылка иначе разъезжаются при смене источника; дату на семьдесят полей никто не проставит |
| — | «Оценка по аналогу» и «допущение команды» — такие же источники, просто без URL | однородная модель: у любого значения ровно один источник, буква всегда выводится одинаково |
| — | Предикат подбора трёхзначный | температура известна у 2 позиций из 37; `bool` выбросит полкаталога из-за пустых полей |
| — | Админка обязательна | ТЗ 3.3.5 и 3.1.4 требуют ручное управление через интерфейс |
| — | Симулятор пишется вручную, не на SimPy | нужен плотный массив позиций по времени, а не поток событий ресурса |
| — | Целевой объект — склад; аэропорт и медучреждение в урезанном виде | ТЗ раздел 2 разрешает один тип полноценно, ТЗ 5.5 — остальные на уровне выбора и параметров |
| — | Воркера и брокера нет | расчёт укладывается в сотни мс при бюджете 10 с |
| 2026-09-21 | В `product` добавлена колонка `slug text unique not null` | slug — часть идентичности, а не характеристика; без него в URL каталога и в отчёте поедет UUID |
| 2026-09-21 | Админ пишет ТТХ прямо в `product.attrs`, минуя `attr_proposal` | админ и есть модератор; очередь остаётся для импорта и парсера (§9.2), где подтверждение человеком действительно нужно |
| 2026-09-21 | Связь отрасль → тип объекта заявляется в `data/mapping/industries.json`, а не выводится из сценариев | у продукта ТЭК есть сценарий «Доставка грузов», привязанный к складу; вывод из данных рождал ветку «ТЭК → Склад → Внутрискладская логистика» |
| 2026-09-21 | Все 59 строк без Тип и Подтип сведены в один тип решения `bas_unspecified` | исходный файл не даёт ничего, чем их разделить; коэффициент ветвления в дереве от этого завышен, зато видно, что классификации нет, — админ переклассифицирует через справочники |
| 2026-09-21 | `solution_type.rule_spec` засеян плейсхолдером из `data/rules/_default.json` с пустыми `hard` и `soft` | колонка NOT NULL, а формул в каталоге организатора нет; пустые правила означают «ограничений пока нет» и видны в trace, а не замаскированы |
