.PHONY: help install up down logs psql migrate fresh ingest dev test lint typecheck

help:
	@echo "make install    - install all deps (pnpm + uv)"
	@echo "make up         - start postgres"
	@echo "make down       - stop postgres"
	@echo "make logs       - tail postgres logs"
	@echo "make psql       - open psql against local postgres"
	@echo "make migrate    - alembic upgrade head"
	@echo "make fresh      - drop+recreate DB schema (DESTRUCTIVE; local only)"
	@echo "make ingest     - run ingest CLI: 'make ingest CMD=\"run --source ada\"'"
	@echo "make dev        - run Next.js dev server"
	@echo "make test       - run all tests (TS + Python)"
	@echo "make lint       - run all linters"
	@echo "make typecheck  - run all type checks"

install:
	pnpm install
	cd services/ingest && uv sync

up:
	docker compose up -d postgres

down:
	docker compose down

logs:
	docker compose logs -f postgres

psql:
	docker exec -it medevents-postgres psql -U medevents -d medevents

migrate:
	cd services/ingest && uv run alembic -c ../../db/migrations/alembic.ini upgrade head

fresh:
	docker exec -it medevents-postgres psql -U medevents -d medevents -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	$(MAKE) migrate

ingest:
	cd services/ingest && uv run medevents-ingest $(CMD)

dev:
	pnpm --filter @medevents/web dev

test:
	pnpm test
	cd services/ingest && uv run pytest

lint:
	pnpm lint
	cd services/ingest && uv run ruff check .

typecheck:
	pnpm typecheck
	cd services/ingest && uv run mypy medevents_ingest
