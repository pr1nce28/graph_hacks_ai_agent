.PHONY: up down seed eval eval-baseline eval-repeat cypher-doc dev-api dev-web mcp mcp-smoke llm-smoke live-check configure-falkordb test load-test reset-demo fmt lint

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

eval-repeat:
	docker compose run --rm api python -m evals.repeat_evals --runs 10

cypher-doc:
	docker compose run --rm api python -m scripts.export_cypher_doc

mcp:
	docker compose run --rm api python -m mcp_server.server

mcp-smoke:
	docker compose run --rm api python -m scripts.mcp_smoke

llm-smoke:
	docker compose run --rm api python -m scripts.llm_smoke

live-check:
	docker compose run --rm api python -m scripts.live_query_check --require

configure-falkordb:
	docker compose run --rm api python -m scripts.configure_falkordb --url "$(URL)"

test:
	docker compose run --rm api pytest -q

load-test:
	docker compose run --rm api python -m scripts.load_test

# ---- Quality ----
fmt:
	ruff check . --fix

lint:
	ruff check .