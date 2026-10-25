.PHONY: dev down test lint bench migrate schemas
dev:
	docker compose -f infra/docker-compose.yml up --build
down:
	docker compose -f infra/docker-compose.yml down
test:
	cd backend && uv run pytest -q && cd ../frontend && npm test --silent
lint:
	cd backend && uv run ruff check . && uv run mypy --strict app && cd ../frontend && npm run lint && npx tsc --noEmit
bench:
	cd backend && uv run python -m benchmarks.runner
migrate:
	cd backend && uv run alembic upgrade head
schemas:
	cd backend && uv run python -m app.ops.schema_gen
