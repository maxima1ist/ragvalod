.PHONY: help sync protos lint test smoke-qdrant smoke-litellm smoke-langfuse clear-qdrant bench-local-llm profile-rag up up-local-llm up-monitoring up-all down

help:
	@echo "Targets: sync | protos | lint | test | smoke-qdrant | smoke-litellm | smoke-langfuse | clear-qdrant | bench-local-llm | profile-rag | up | up-local-llm | up-monitoring | up-all | down"

sync:
	uv sync --all-packages --group dev

protos:
	bash scripts/generate_protos.sh

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff format .
	uv run ruff check --fix .

test:
	uv run pytest -q

smoke-qdrant:
	uv run python scripts/smoke_qdrant.py

clear-qdrant:
	uv run python scripts/clear_qdrant.py

smoke-litellm:
	uv run python scripts/smoke_litellm.py

smoke-langfuse:
	LANGFUSE_HOST=$${LANGFUSE_HOST:-http://localhost:3000} uv run python scripts/smoke_langfuse.py

bench-local-llm:
	uv run python scripts/bench_local_llm.py

profile-rag:
	uv run python scripts/profile_rag.py

up:
	bash scripts/up.sh

up-local-llm:
	bash scripts/up.sh --profile local-llm

up-monitoring:
	bash scripts/up.sh --profile monitoring

up-all:
	bash scripts/up.sh --profile local-llm --profile monitoring

down:
	bash scripts/down.sh
