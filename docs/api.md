# Описание API

Базовый адрес: `http://localhost/platform/api/v1`. Формат JSON (UTF-8). Полная схема: [`/platform/api/v1/openapi.json`](http://localhost/platform/api/v1/openapi.json), Swagger UI: [`/platform/api/v1/docs`](http://localhost/platform/api/v1/docs). Всего 89 методов.

**Авторизация.** `POST /auth/login` ставит httpOnly-cookie `platform_session` (7 суток). Дальше запросы отправляются с cookie. `/admin/*` требует роль `admin`.

**Ошибки.** Тело `{"detail": "текст"}`; коды: 401 «Нужна авторизация», 403 нет прав, 404 не найдено, 422 неверные данные.

## Основные методы

| Метод | Путь | Роль | Назначение |
|---|---|---|---|
| GET | `/health` | все | Проверка сервиса, ответ `{"ok": true}` |
| POST | `/auth/login` | все | Вход: `{"login","password"}` |
| POST | `/auth/logout` | все | Выход |
| GET | `/auth/me` | вошедший | Текущий пользователь |
| GET | `/catalog/industries` | все | Отрасли и объекты для мастера проекта |
| GET | `/catalog/tree` | все | Дерево «отрасль → объект → процесс» со счётчиками |
| GET | `/catalog/products` | все | Порция карточек (параметры `process`, `solution_type`, `object_code`, `cursor`, `limit`) |
| GET | `/catalog/products/{slug}` | все | Карточка и источники значений |
| GET | `/catalog/objects/{code}/fields` | все | Поля формы параметров объекта |
| POST | `/catalog/preview/match` | все | Подбор без проекта: `{"object_code","site"}` |
| POST | `/catalog/preview/economy` | все | Экономика без проекта |
| GET | `/economy/norms` | все | Общие нормативы |
| GET | `/projects` | вошедший | Мои проекты |
| POST | `/projects` | user, admin | Создать: `{"name","object_code","site"}` |
| GET | `/projects/demo` | все | Опубликованные демо |
| GET | `/projects/{key}` | по доступу | Проект: площадка, процессы, `can_edit` |
| PATCH | `/projects/{key}` | владелец | Сохранить площадку, включённые процессы |
| DELETE | `/projects/{key}` | владелец | Удалить |
| POST | `/projects/{key}/copy` | вошедший | Копировать проект или демо |
| POST | `/projects/{key}/match` | по доступу | Подбор: `{"site": {...}}` |
| POST | `/projects/{key}/economy` | по доступу | Экономика: `{"site","picks","choices","preview"}` |
| PUT | `/projects/{key}/economy/overrides` | владелец | Сохранить ручные значения |
| GET/PUT | `/projects/{key}/layout` | по доступу | Схема расстановки |
| POST | `/projects/{key}/layout/background` | владелец | Подложка схемы (PNG/JPG/WebP до 20 МБ) |
| POST | `/admin/imports` | admin | Импорт CSV каталога или ручной таблицы (multipart) |
| GET | `/admin/jobs`, `/admin/jobs/{id}` | admin | Статус импорта и парсеров |
| GET/PATCH | `/admin/parsers`, `/admin/parsers/{code}` | admin | Расписание парсеров |
| POST | `/admin/parsers/{code}/runs` | admin | Запустить парсер |
| PUT | `/admin/economy/norms` | admin | Нормативы с источником и заметкой |
| GET/PUT | `/admin/match-filters` | admin | Общие фильтры подбора |
| GET/PUT | `/admin/processes/{code}`, `.../setup` | admin | Правила, формулы, ранжирование процесса |
| GET/PATCH | `/admin/products/{slug}` | admin | Карточка, ручные значения |
| GET/POST | `/admin/objects`, `/admin/industries`, `/admin/solution-types` | admin | Справочники |

Остальные методы админки (справочники характеристик, полей, типов) перечислены в OpenAPI.

## Примеры

**Вход.**

```bash
curl -c cookie.txt -X POST http://localhost/platform/api/v1/auth/login \
  -H 'content-type: application/json' -d '{"login":"user","password":"demo-2026"}'
```

**Подбор по демо-проекту.** Площадку лучше передавать явно, иначе правила не срабатывают.

```bash
SITE=$(curl -s http://localhost/platform/api/v1/projects/demo-warehouse | python3 -c "import json,sys;print(json.dumps(json.load(sys.stdin)['site']))")
curl -s -X POST http://localhost/platform/api/v1/projects/demo-warehouse/match \
  -H 'content-type: application/json' -d "{\"site\": $SITE}"
```

Ответ (сокращён):

```json
{"project_id": "888e9c05-…", "groups": [{
  "process_code": "warehouse_inventory", "process_name": "Инвентаризация товаров",
  "best_product_id": null, "technical_best_product_id": null,
  "hits": [{"name": "Инвентаризатор AI Stock Counter 12M", "slug": "inventarizator-ai-stock-counter-12m", "verdict": "unknown",
            "technical_ready": false, "sizing_ready": false, "economic_ready": false,
            "count": null, "data_basis": "published_catalog_v1"}]
}]}
```

`verdict`: `pass`, `conditional`, `unknown`, `fail`.

**Экономика.** `picks` — робот по процессам (`process_code → product_id`), `preview` — значения what-if, например `{"replacement_pct": 40}`. Ответ содержит `scenarios` (`asis`, `purchase`, `raas`), у каждого `capex`, `opex`, `effect`, `payback`, `roi`, `tco`: `{"value", "unit", "tex", "subst", "vars"}` (формула LaTeX, подстановка, переменные), а также `fleet`, `sensitivity`, `verdict`. Полный пример со скриптом: приложение Г.

**Импорт каталога.**

```bash
curl -b cookie.txt -X POST http://localhost/platform/api/v1/admin/imports \
  -F kind=import_catalog -F file=@catalog.csv
```

Поле `kind`: `import_catalog` или `import_manual`. В ответе идентификатор задания; статус: `GET /admin/jobs/{id}`. Форматы файлов: раздел 7.2.


## Допуск и неполная экономика (0024)

Актуальный расширенный контракт: [14-catalog-assessment.md](14-catalog-assessment.md). Опубликованные характеристики используются без reviewed=true и обязательных assessment-документов. Прежние verdict/notes/count/best_product_id сохранены; добавлены reasons, независимые technical_ready/sizing_ready/economic_ready, data_basis, resolved_facts, provenance и technical_best_product_id. Отсутствие цены/комплектации/модели количества не блокирует технический pass. Экономика проверяет выбор на сервере, различает picks отсутствует и picks={}, не принимает fail/unknown/conditional и не подставляет count=1. При неизвестных критичных данных возвращает HTTP 200, status=incomplete, blockers и nullable финансовые totals (в том числе annual_cost). Старые сохранённые ID диагностируются, не заменяются молча.

Необязательные дополнения/исправления и настройки модели количества администратор читает/заменяет через GET/PUT `/api/v1/admin/products/{slug}/assessment` и `/api/v1/admin/processes/{code}/assessment`. Эти документы не являются обязательным разрешением на использование каталога.

## Выборочные DEV-допущения

Для трёх карточек подключён отдельный файл дополнений; исходные attrs и источники не переписываются. Подбор и карточка возвращают `uses_demo_synthetic`, `demo_synthetic` (key/label/value/unit/origin/explanation/vendor_confirmed/requires_vendor_confirmation), `vendor_confirmation_fields`. В подборе `data_basis=catalog_with_demo_synthetic_v1`, если дополнения применены; происхождение каждого значения также есть в provenance. Структурированные причины `unknown` сохраняются, синтетические поля не считаются подтверждёнными вендором.

В экономике `demo_synthetic` сгруппирован по изделию/процессу, поле `included_in_economy` отличает техническое допущение от включения в финансовый парк. Дисклеймер сохраняет происхождение при любом состоянии полноты. Сведения и ограничения: [15-demo-synthetic.md](15-demo-synthetic.md).

### Сквозной DEV-расчёт

При `DEMO_SYNTHETIC_ENABLED=true` только зарегистрированные `is_demo`-проекты получают отдельные входы задач и финансовые допущения. В обычном окружении флаг false; опубликованный каталог и обычный preview используют исходные сведения.

Подбор дополнительно возвращает `calculation_mode`, `demo_economic_ready`, `demo_best_product_id`. Они не подменяют `economic_ready`/`best_product_id` подтверждённого контура. В `sizing` доступны model, inputs, input_provenance, рабочие машины, резерв, доступность, цикл/производительность; origin=calculated и зависимость от синтетики сохраняются. Для масштабированных What-if входов provenance содержит актуальное value и исходное base_value.

Экономика может иметь `status=demo_estimate`, `scope=automation_program`; complete относится к достаточности расчёта в этом охвате. `manual_processes` перечисляет процессы вне программы, их неизвестная стоимость не считается нулевой. `active_overrides` — пользовательские параметры текущего расчёта, `effective_overrides` включает DEV-основания. `demo_synthetic` содержит также группы входов задач и финансовых параметров; category отличает site/finance, а requires_vendor_confirmation относится к характеристикам изделия, не к обследованию предприятия. Неполный аэропорт остаётся incomplete с блокерами. Подробнее: [16-demo-calculation.md](16-demo-calculation.md).
