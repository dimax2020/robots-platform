.PHONY: up down logs reset ps audit-platform normalize-platform snapshot

# Поднять платформу. Пустая база platform наполняется снимком каталога при старте контейнера.
up:
	docker compose up -d --build --remove-orphans
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
	docker compose logs -f platform-api platform-worker web

# Снимок текущей локальной БД в platform/seed/platform.sql: с него стартует чистая установка (и Coolify).
# Пользовательские проекты не попадают, остаются только демо. Рабочая база не меняется: правка идёт в копии.
snapshot:
	docker compose exec -T db psql -U robots -d postgres -qc "DROP DATABASE IF EXISTS platform_snapshot" -c "CREATE DATABASE platform_snapshot"
	docker compose exec -T db sh -c "pg_dump -U robots --no-owner --no-privileges platform | psql -q -U robots -d platform_snapshot" >/dev/null
	docker compose exec -T db psql -U robots -d platform_snapshot -v ON_ERROR_STOP=1 -qc "DELETE FROM project_process WHERE project_id IN (SELECT id FROM project WHERE NOT is_demo)" -c "DELETE FROM project WHERE NOT is_demo"
	docker compose exec -T db pg_dump -U robots --no-owner --no-privileges platform_snapshot > platform/seed/platform.sql
	docker compose exec -T db psql -U robots -d postgres -qc "DROP DATABASE platform_snapshot"
	@echo "Снимок обновлён: platform/seed/platform.sql"

# Аудит каталога: по умолчанию БД не меняется.
audit-platform:
	mkdir -p reports
	docker compose run --rm --no-deps -v "$(CURDIR)/reports:/reports" platform-api python -m app.normalize_catalog --report /reports/catalog-normalization-audit.json

# Применить те же правила к существующим карточкам с подробным отчётом.
normalize-platform:
	mkdir -p reports
	docker compose run --rm --no-deps -v "$(CURDIR)/reports:/reports" platform-api python -m app.normalize_catalog --apply --report /reports/catalog-normalization-applied.json
