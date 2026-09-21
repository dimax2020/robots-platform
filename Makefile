.PHONY: up down logs migrate seed reseed normalize reset ps test

# Поднять всё и привести БД в рабочее состояние: схема плюс каталог из CSV
up:
	docker compose up -d --build
	docker compose exec -T api alembic upgrade head
	docker compose exec -T api python -m scripts.seed
	# Снимок каталога для движка грузится в lifespan, поэтому после сида api перезапускается
	docker compose restart api
	@echo
	@echo "Платформа: http://localhost"
	@echo "API:        http://localhost/api/v1/docs"

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

# Перечитать каталог заново, не теряя проекты и пользователей
reseed:
	docker compose exec -T api python -m scripts.seed --reset
	docker compose restart api

# Пересобрать data/catalog_normalized.json из файла организатора.
# Локально, а не в контейнере: resources/ в образ не попадает.
normalize:
	cd backend && uv run python -m scripts.normalize

test:
	cd backend && uv run pytest
