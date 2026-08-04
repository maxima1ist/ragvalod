.PHONY: help sync protos lint test smoke-qdrant up down

help:
	@echo "Targets: sync | protos | lint | test | smoke-qdrant | up | down"

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

up:
	bash scripts/up.sh

down:
	bash scripts/down.sh
