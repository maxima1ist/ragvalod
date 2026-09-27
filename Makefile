.PHONY: help sync protos lint test smoke-qdrant smoke-litellm smoke-langfuse judge clear-qdrant bench-local-llm profile-rag k8s-sync-config k8s-validate up up-local-llm up-monitoring up-all down

help:
	@echo "Targets: sync | protos | lint | test | smoke-qdrant | smoke-litellm | smoke-langfuse | judge | clear-qdrant | bench-local-llm | profile-rag | k8s-validate | up | up-local-llm | up-monitoring | up-all | down"

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

judge:
	LANGFUSE_HOST=$${LANGFUSE_HOST:-http://localhost:3000} LITELLM_BASE_URL=$${LITELLM_BASE_URL:-http://localhost:4000} uv run python scripts/judge_traces.py

bench-local-llm:
	uv run python scripts/bench_local_llm.py

profile-rag:
	uv run python scripts/profile_rag.py

k8s-sync-config:
	cp configs/litellm.yaml k8s/base/configs/litellm.yaml
	cp configs/litellm.redis.yaml k8s/overlays/ha/configs/litellm.redis.yaml

k8s-validate: k8s-sync-config
	kubectl kustomize k8s/base >/dev/null
	kubectl kustomize k8s/overlays/ha >/dev/null
	kubectl kustomize k8s/overlays/local >/dev/null
	kubectl kustomize k8s/overlays/local-ha >/dev/null
	kubectl kustomize k8s/overlays/local-gpu >/dev/null
	kubectl kustomize k8s/overlays/monitoring >/dev/null
	kubectl kustomize k8s/overlays/observability >/dev/null

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
