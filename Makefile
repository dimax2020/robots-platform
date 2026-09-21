.PHONY: up down logs migrate seed reseed normalize ttx reset ps test

# Поднять всё и привести БД в рабочее состояние: схема, каталог из CSV, ТТХ ручного поиска
up:
	docker compose up -d --build
	docker compose exec -T api alembic upgrade head
	docker compose exec -T api python -m scripts.seed
	docker compose exec -T api python -m scripts.import_ttx
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
