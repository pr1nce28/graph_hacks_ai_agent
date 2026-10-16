.PHONY: up down seed eval eval-baseline cypher-doc dev-api dev-web mcp test load-test reset-demo fmt lint

# ---- Stack lifecycle ----
up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

# ---- Data ----
seed:
	docker compose run --rm api python -m ingestion.run_seed

reset-demo:
	docker compose down -v
	docker compose up -d
	docker compose run --rm api python -m ingestion.run_seed

# ---- API & Web (without Docker) ----
dev-api:
	uvicorn api.main:app --reload --port 8000

dev-web:
	cd web && npm install && npm run dev

# ---- Tooling ----
eval:
	docker compose run --rm api python -m evals.run_evals

eval-baseline:
	docker compose run --rm api python -m evals.baseline_vector_only

cypher-doc:
	docker compose run --rm api python -m scripts.export_cypher_doc

mcp:
	docker compose run --rm api python -m mcp_server.server

test:
	docker compose run --rm api pytest -q

load-test:
	docker compose run --rm api python -m scripts.load_test

# ---- Quality ----
fmt:
	ruff check . --fix

lint:
	ruff check .