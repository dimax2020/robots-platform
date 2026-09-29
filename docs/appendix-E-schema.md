# Приложение Е. Схема базы данных

PostgreSQL 16, база `platform`, 26 таблиц, миграции Alembic до `0014_match_settings`. Файл сформирован скриптом `docs/tools/gen_schema.py` из работающей БД. PK — первичный ключ, FK — внешний ключ, `?` — допускает NULL.

## `alembic_version`

Текущая ревизия миграций

| Поле | Тип | Ключ |
|---|---|---|
| `version_num` | character varying | PK |

## `app_user`

Пользователи и роли

| Поле | Тип | Ключ |
|---|---|---|
| `id` | uuid | PK |
| `login` | text |  |
| `password_hash` | text |  |
| `role` | text |  |

## `attribute_def`

Справочник характеристик роботов: подпись, единица, группа

| Поле | Тип | Ключ |
|---|---|---|
| `key` | text | PK |
| `label` | text |  |
| `unit`? | text |  |
| `usage` | text |  |
| `group_code` | text |  |
| `datatype` | text |  |
| `sort` | integer |  |

## `economy_norm`

Нормативы экономики (переопределяют значения по умолчанию из кода)

| Поле | Тип | Ключ |
|---|---|---|
| `key` | text | PK |
| `value` | numeric |  |
| `updated_at` | timestamp with time zone |  |
| `rationale`? | text |  |
| `origin`? | text |  |
| `url`? | text |  |

## `economy_norm_log`

Журнал изменений нормативов

| Поле | Тип | Ключ |
|---|---|---|
| `id` | integer | PK |
| `key` | text |  |
| `old_value`? | numeric |  |
| `new_value` | numeric |  |
| `note` | text |  |
| `at` | timestamp with time zone |  |
| `origin`? | text |  |

## `economy_norm_override`

Нормативы для конкретного типа решения

| Поле | Тип | Ключ |
|---|---|---|
| `norm_key` | text | PK |
| `solution_type_id` | integer | PK, FK → `solution_type` |
| `value` | numeric |  |
| `rationale` | text |  |
| `origin` | text |  |
| `updated_at` | timestamp with time zone |  |

## `industry`

Отрасли

| Поле | Тип | Ключ |
|---|---|---|
| `id` | integer | PK |
| `code` | text |  |
| `name` | text |  |

## `job`

Очередь заданий: импорт и парсеры

| Поле | Тип | Ключ |
|---|---|---|
| `id` | uuid | PK |
| `kind` | text |  |
| `parser_code` | text |  |
| `status` | text |  |
| `file_path`? | text |  |
| `error`? | text |  |
| `counters` | jsonb |  |
| `created_at`? | timestamp with time zone |  |
| `started_at`? | timestamp with time zone |  |
| `finished_at`? | timestamp with time zone |  |

## `match_setting`

Общие фильтры подбора (готовность)

| Поле | Тип | Ключ |
|---|---|---|
| `code` | text | PK |
| `value` | jsonb |  |
| `updated_at` | timestamp with time zone |  |

## `object_field`

Поля площадки объекта

| Поле | Тип | Ключ |
|---|---|---|
| `object_type_id` | integer | PK, FK → `object_type` |
| `field_key` | text | PK, FK → `site_field` |
| `group_name` | text |  |
| `label`? | text |  |
| `required` | boolean |  |
| `default_value`? | jsonb |  |
| `source` | text |  |
| `sort` | integer |  |

## `object_industry`

Связь объект — отрасль

| Поле | Тип | Ключ |
|---|---|---|
| `object_type_id` | integer | PK, FK → `object_type` |
| `industry_id` | integer | PK, FK → `industry` |

## `object_input_binding`

Привязка входов формул процесса к полям площадки

| Поле | Тип | Ключ |
|---|---|---|
| `object_type_id` | integer | PK, FK → `object_type` |
| `process_id` | integer | PK, FK → `process` |
| `input_key` | text | PK |
| `site_key` | text |  |

## `object_process`

Процессы объекта

| Поле | Тип | Ключ |
|---|---|---|
| `object_type_id` | integer | PK, FK → `object_type` |
| `process_id` | integer | PK, FK → `process` |

## `object_type`

Типы объектов; `in_match` разрешает выбор в мастере проекта

| Поле | Тип | Ключ |
|---|---|---|
| `id` | integer | PK |
| `code` | text |  |
| `name` | text |  |
| `in_match` | boolean |  |

## `parser_setting`

Расписание парсеров

| Поле | Тип | Ключ |
|---|---|---|
| `code` | text | PK |
| `enabled` | boolean |  |
| `hour` | integer |  |
| `last_enqueued_on`? | date |  |
| `minute` | integer |  |

## `process`

Процессы: формула количества, ключ ранжирования, шаблон схемы

| Поле | Тип | Ключ |
|---|---|---|
| `id` | integer | PK |
| `code` | text |  |
| `name` | text |  |
| `count_formula` | text |  |
| `count_inputs` | jsonb |  |
| `rank_key` | text |  |
| `rank_order` | text |  |
| `layout_items` | jsonb |  |

## `process_filter`

Правила подбора процесса

| Поле | Тип | Ключ |
|---|---|---|
| `id` | integer | PK |
| `process_id` | integer | FK → `process` |
| `name` | text |  |
| `object_keys` | jsonb |  |
| `robot_keys` | jsonb |  |
| `op` | text |  |
| `mode` | text |  |
| `inputs` | jsonb |  |
| `formula` | text |  |

## `product`

Карточки роботов; `attrs` значения, `column_sources` источники, `raw_catalog` исходная строка

| Поле | Тип | Ключ |
|---|---|---|
| `id` | uuid | PK |
| `slug` | text |  |
| `name` | text |  |
| `manufacturer`? | text |  |
| `availability`? | text |  |
| `trl`? | integer |  |
| `price_rub`? | numeric |  |
| `image_url`? | text |  |
| `summary`? | text |  |
| `raw_catalog` | jsonb |  |
| `attrs` | jsonb |  |
| `column_sources` | jsonb |  |
| `created_at`? | timestamp with time zone |  |
| `updated_at`? | timestamp with time zone |  |
| `solution_type_id`? | integer | FK → `solution_type` |

## `product_origin`

Внешний идентификатор карточки (платформа, ID)

| Поле | Тип | Ключ |
|---|---|---|
| `platform` | text | PK |
| `external_id` | text | PK |
| `product_id` | uuid | FK → `product` |

## `product_process`

Роботы процесса

| Поле | Тип | Ключ |
|---|---|---|
| `product_id` | uuid | PK, FK → `product` |
| `process_id` | integer | PK, FK → `process` |

## `project`

Проекты: площадка, ручные значения экономики, схема, признаки демо

| Поле | Тип | Ключ |
|---|---|---|
| `id` | uuid | PK |
| `name` | text |  |
| `object_type_id` | integer | FK → `object_type` |
| `site` | jsonb |  |
| `economy_overrides` | jsonb |  |
| `layout` | jsonb |  |
| `owner_id`? | uuid | FK → `app_user` |
| `is_demo` | boolean |  |
| `published` | boolean |  |
| `slug`? | text |  |

## `project_process`

Включённые процессы проекта

| Поле | Тип | Ключ |
|---|---|---|
| `project_id` | uuid | PK, FK → `project` |
| `process_id` | integer | PK, FK → `process` |
| `enabled` | boolean |  |
| `disabled_reason`? | text |  |

## `site_field`

Справочник полей площадки: подпись, единица, границы

| Поле | Тип | Ключ |
|---|---|---|
| `key` | text | PK |
| `label` | text |  |
| `unit` | text |  |
| `kind` | text |  |
| `min_value`? | numeric |  |
| `max_value`? | numeric |  |
| `hint` | text |  |
| `sort` | integer |  |

## `solution_type`

Типы решений

| Поле | Тип | Ключ |
|---|---|---|
| `id` | integer | PK |
| `code` | text |  |
| `name` | text |  |
| `group_name` | text |  |
| `family` | text |  |

## `solution_type_rule`

Правила автоназначения типа при импорте

| Поле | Тип | Ключ |
|---|---|---|
| `raw_key` | text | PK |
| `solution_type_id` | integer | FK → `solution_type` |

## `source`

Реестр источников значений

| Поле | Тип | Ключ |
|---|---|---|
| `id` | integer | PK |
| `kind` | text |  |
| `publisher` | text |  |
| `url`? | text |  |
| `parser_code`? | text |  |
| `title`? | text |  |
