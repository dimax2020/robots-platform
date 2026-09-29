# Платформа подбора роботизированных решений

Веб-платформа: выбор объекта, каталог и подбор роботов с объяснением вердиктов, три сценария экономики (без роботов, покупка, аренда) с формулами, имитация работы парка на плане объекта, отчёт.

![Главная страница](docs/img/01-home.png)

## Быстрый старт

Нужны Docker с Compose v2 и свободные порты 80 и 5432.

```bash
git clone <адрес репозитория> robots-platform
cd robots-platform
make up            # или: docker compose up -d --build
```

Через минуту сайт: <http://localhost>. Вход: `admin` / `demo-2026` (также `user`, `guest`). Открыть демо «Склад Внуково-Юг» и пройти шаги «Подбор → Сравнение → Экономика».

Остановить: `make down`. Сбросить данные: `make reset`.

## Сервисы

| Сервис | Назначение | Адрес |
|---|---|---|
| `traefik` | Единая точка входа | :80 |
| `web` | Nuxt 4 (Vue 3), страницы и имитация в браузере | `/` |
| `platform-api` | FastAPI: подбор, экономика, проекты | `/platform/api/v1` |
| `platform-worker` | Импорт каталога и парсеры | — |
| `db` | PostgreSQL 16 | :5432 |

Swagger UI: <http://localhost/platform/api/v1/docs>.

## Переменные окружения

Все необязательны, значения по умолчанию заданы в `docker-compose.yaml`.

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `DATABASE_URL` | `postgresql+psycopg://robots:robots@db:5432/platform` | БД платформы |
| `POSTGRES_ADMIN_URL` | `…/postgres` | Создание базы при старте |
| `SESSION_SECRET` | `platform-demo-session-secret` | Подпись cookie. Сменить в проде |
| `UPLOAD_DIR` | `/app/uploads` | Фото карточек и подложки схем |
| `ROOT_PATH` | `/platform` | Префикс API за Traefik |
| `NUXT_PUBLIC_PLATFORM_API_BASE` | `/platform/api/v1` | Путь к API для сайта |

Полный список: [docs/03-deployment.md](docs/03-deployment.md).

## Структура репозитория

```
frontend/   Nuxt 4: страницы, компоненты, имитация (app/sim)
platform/   FastAPI: app/api, app/domain (подбор, экономика), app/parsers, alembic, seed
docs/       Документация, скриншоты, генераторы приложений
docker-compose.yaml, Makefile
```

## Демо-данные

Каталог из 555 карточек и три демо-проекта (склад, аэропорт, медучреждение) загружаются при первом запуске из `platform/seed/platform.sql`. Учётные записи и сценарий проверки с ожидаемыми числами: [docs/appendix-G-demo-and-check.md](docs/appendix-G-demo-and-check.md).

## Тесты

```bash
cd platform && uv run pytest -q          # нужна БД из compose
cd frontend && npm ci && npm run test:sim && npx nuxi typecheck
```

## Документация

| Документ | Файл |
|---|---|
| Оглавление пакета | [docs/README.md](docs/README.md) |
| Развёртывание | [docs/03-deployment.md](docs/03-deployment.md) |
| Архитектура | [docs/02-architecture.md](docs/02-architecture.md) |
| API | [docs/api.md](docs/api.md) |
| Экономическая модель | [docs/05-economics.md](docs/05-economics.md) |
| Ограничения и план | [docs/12-limitations-roadmap.md](docs/12-limitations-roadmap.md) |

## Ограничения

Это экспресс-оценка: результат требует проверки при обследовании объекта. Экономика и визуализация в интерфейсе доступны для склада, аэропорт и медучреждение доходят до сравнения. Полный список: раздел 12.
