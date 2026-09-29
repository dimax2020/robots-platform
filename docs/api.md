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
  "process_code": "pallet_storage", "process_name": "Автоматизированное хранение и выдача грузов",
  "best_product_id": "cebbdfa8-…",
  "hits": [{"name": "AS-RS P", "slug": "as-rs-p", "verdict": "pass", "notes": [],
            "trl": 9, "stage": "operation", "count": 4.0, "count_note": "",
            "specs": [{"key": "price_rub", "label": "Цена", "unit": "₽", "direction": "low", "value": 10000000.0}]}]
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
