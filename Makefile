.PHONY: up down logs migrate seed reseed normalize ttx reset ps test parse

# Поднять платформу. Пустая база platform наполняется снимком каталога при старте контейнера.
# Контейнер api — старый бэкенд: сайт его больше не вызывает, но make up всё ещё гоняет его миграции.
up:
	docker compose up -d --build
	docker compose exec -T api alembic upgrade head
	docker compose exec -T api python -m scripts.seed
	docker compose exec -T api python -m scripts.import_ttx
	docker compose restart api
	@echo "Ждём платформу…"
	@i=0; until docker compose exec -T platform-api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')" >/dev/null 2>&1; do \
		i=$$((i+1)); \
		if [ $$i -gt 60 ]; then echo "Платформа не ответила"; exit 1; fi; \
		sleep 2; \
	done
	@echo
	@echo "Сайт:      http://localhost"
	@echo "Платформа: http://localhost/platform/api/v1/health"
	@echo "Swagger:   http://localhost/platform/api/v1/docs"

down:
	docker compose down

# Снести и данные тоже: следующий up соберёт каталог с нуля
reset:
	docker compose down -v

ps:
	docker compose ps

logs:
	docker compose logs -f api web

migrate:
	docker compose exec -T api alembic upgrade head

seed:
	docker compose exec -T api python -m scripts.seed

# Перечитать каталог заново, не теряя проекты и пользователей.
# Сид очищает product.attrs, поэтому ТТХ накатываются следом
reseed:
	docker compose exec -T api python -m scripts.seed --reset
	docker compose exec -T api python -m scripts.import_ttx
	docker compose restart api

# Пересобрать data/catalog_normalized.json из файла организатора.
# Локально, а не в контейнере: resources/ в образ не попадает.
normalize:
	cd backend && uv run python -m scripts.normalize

# Пересобрать data/ttx_manual.csv из таблиц ручного поиска и записать ТТХ в каталог.
# Выгрузка и сборка локально (resources/ вне образа), запись — в контейнере.
ttx:
	cd backend && uv run python -m scripts.dump_manual_xlsx
	cd backend && uv run python -m scripts.merge_ttx
	docker compose exec -T api python -m scripts.import_ttx
	docker compose restart api

test:
	cd backend && uv run pytest

# Парсер и импорт работают последовательно в отдельном контейнере.
parse:
	docker compose build api parser
	docker compose run --rm api alembic upgrade head
	docker compose run --rm parser python run.py --once
	docker compose up -d api
	docker compose restart api

# Аудит новой платформы: по умолчанию БД не меняется.
.PHONY: audit-platform normalize-platform
audit-platform:
	mkdir -p reports
	docker compose run --rm --no-deps -v "$(CURDIR)/reports:/reports" platform-api python -m app.normalize_catalog --report /reports/catalog-normalization-audit.json

# Применить те же правила к существующим карточкам с подробным отчётом.
normalize-platform:
	mkdir -p reports
	docker compose run --rm --no-deps -v "$(CURDIR)/reports:/reports" platform-api python -m app.normalize_catalog --apply --report /reports/catalog-normalization-applied.json
