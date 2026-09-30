.PHONY: up down migrate seed api test tunnel web

up:
	docker compose up -d

down:
	docker compose down

migrate:
	cd apps/api && uv run alembic upgrade head

seed:
	cd apps/api && uv run python -m scripts.seed

api:
	cd apps/api && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --proxy-headers --forwarded-allow-ips="*"

test:
	cd apps/api && uv run pytest -v

tunnel:
	ngrok http 8000

web:
	cd apps/web && npm run dev
