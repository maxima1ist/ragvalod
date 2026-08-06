<div align="center">

# ragvalod

Personal RAG chatbot with pluggable data sources and inference backends.

<img src="assets/ragvalod.png" alt="Rogvolod of Polotsk" width="280" />

*Named after [Rogvolod](https://ru.wikipedia.org/wiki/%D0%A0%D0%BE%D0%B3%D0%B2%D0%BE%D0%BB%D0%BE%D0%B4) — prince of Polotsk*
</div>

## Quick start

**Requirements:** Docker + Docker Compose, and a free host port set below. GPU is only needed for the optional local LLM.

```bash
# 1. Config
cp .env.example .env
# Edit .env — at least GATEWAY_API_KEY (default: change-me)

# 2. Chat model backend (pick one)
#    A) Local GPU (vLLM) — needs NVIDIA Container Toolkit; see docs/host_gpu_setup.md
#    B) OpenRouter — set OPENROUTER_API_KEY in .env and switch chat-default
#       in configs/litellm.yaml to the commented OpenRouter block

# 3. Put files to ingest under data/local_files/ (sample welcome.md is already there)

# 4. Start (profiles can be combined)
make up                 # base stack
make up-local-llm       # base + vLLM
make up-monitoring      # base + Langfuse
make up-all             # base + vLLM + Langfuse

# 5. Smoke: health → ingest local files → generate
uv sync --all-packages --group dev   # once, for host-side scripts
uv run python gateway/scripts/e2e_rest.py
```

Tear down (keeps volumes): `make down`.

| Endpoint | URL |
| --- | --- |
| Gateway (user API) | http://localhost:8000 |
| LiteLLM | http://localhost:4000 |
| Qdrant | http://localhost:6333 |
| Langfuse UI (profile `monitoring`) | http://localhost:3000 |
| vLLM (profile `local-llm`) | http://localhost:8001 |

Auth on Gateway: header `X-API-Key: <GATEWAY_API_KEY>` (or `Authorization: Bearer …`). Empty key disables auth.

The stack starts **empty**. Until a successful ingest, `POST /generate` returns HTTP 409 (`data_not_initialized`). Check readiness via `GET /health` → `data_initialized`.

---

## Ingest

Ingest is asynchronous: `POST /ingest` returns a `job_id`; poll `GET /ingest/{job_id}` until `state` is `succeeded`, `failed`, or `partial`. Credentials are per-request (not taken from `.env` inside containers) and live only in memory for the job.

List adapters:

```bash
curl -s -H "X-API-Key: change-me" http://localhost:8000/sources
```

### Local files

1. Put `.txt` / `.md` / `.pdf` / `.docx` under `data/local_files/` (or whatever `LOCAL_FILES_DIR` points to). That host path is mounted read-only into the ingestion container as `/data/local_files`.
2. Start a job:

```bash
curl -s -X POST http://localhost:8000/ingest \
  -H "X-API-Key: change-me" \
  -H "Content-Type: application/json" \
  -d '{"sources": [{"name": "local_files"}]}'
# → {"job_id":"..."}
```

Optional override of the directory inside the container:

```json
{"sources": [{"name": "local_files", "options": {"path": "/data/local_files"}}]}
```

3. Poll until done:

```bash
curl -s -H "X-API-Key: change-me" http://localhost:8000/ingest/<job_id>
```

Or run the all-in-one smoke script (health → ingest `local_files` → generate):

```bash
uv run python gateway/scripts/e2e_rest.py
```

### Notion

Create a Notion integration, share the target pages/databases with it, then pass the token in the request body (aliases: `integration_token`, `token`, `notion_token`, `access_key`):

```bash
curl -s -X POST http://localhost:8000/ingest \
  -H "X-API-Key: change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "sources": [{
      "name": "notion",
      "credentials": {"integration_token": "ntn_..."},
      "options": {"page_ids": "PAGE_ID_1,PAGE_ID_2"}
    }]
  }'
```

Useful `options` (all strings):

| Option | Meaning |
| --- | --- |
| `page_ids` / `page_id` | Comma-separated page IDs (preferred when you know them) |
| `database_ids` / `database_id` | Query database(s) for page IDs |
| `query` / `search` | Search when no IDs given (default discovery cap: 10 pages) |
| `max_pages` | Cap discovery (`all` or `0` = no cap) |
| `max_concurrency` | Parallel page fetches |

Without `page_ids` / `database_ids`, Notion searches accessible pages (default `max_pages=10`).

### Multiple sources / both adapters

```json
{
  "sources": [
    {"name": "local_files"},
    {
      "name": "notion",
      "credentials": {"integration_token": "ntn_..."},
      "options": {"max_pages": "20"}
    }
  ]
}
```

`{"all_with_credentials": true}` runs every adapter that does not need credentials (today: `local_files`) plus any credentialed sources you listed with tokens.

After a full success, `GET /health` shows `data_initialized: true` and you can call `POST /generate`.

---

## Components

You talk only to the **Gateway**. Everything else is internal.

| Component | Role | How it runs | Ports |
| --- | --- | --- | --- |
| **gateway** | REST entrypoint (`/health`, `/ingest`, `/generate`, …) | Docker build from `gateway/` | 8000 |
| **ingestion** | gRPC: scrape sources → chunk → embed → Qdrant | Docker build from `ingestion/` | 50051 |
| **rag_orchestrator** | gRPC: retrieve → rerank → prompt → chat | Docker build from `rag_orchestrator/` | 50052 |
| **qdrant** | Vector DB | Official image | 6333 / 6334 |
| **litellm** | Model gateway (chat / embed / rerank aliases) | Official image + `configs/litellm.yaml` | 4000 |
| **infinity** | CPU embedder + reranker | Official image | 7997 |
| **vllm** *(optional)* | Local LLM | Profile `local-llm`, needs GPU | 8001→8000 |
| **langfuse** + **Postgres** *(optional)* | Tracing / eval UI | Profile `monitoring` | 3000 |

Flow: User → Gateway (REST) → Ingestion / RAG (gRPC) → LiteLLM (HTTP) → Infinity / vLLM / external API; Ingestion & RAG ↔ Qdrant (gRPC).

---

## Configs (current examples)

### `.env`

Copy `.env.example` → `.env` (or let `make up` / `scripts/up.sh` create it). Important knobs:

- **`GATEWAY_API_KEY`** — protect the REST API
- **`LITELLM_MASTER_KEY`** — shared key for LiteLLM (`sk-ragvalod-local` by default)
- **`OPENROUTER_API_KEY` / `OPENAI_API_KEY`** — if chat goes through an external API
- **`LOCAL_FILES_DIR`** — host path mounted read-only into ingestion (default `./data/local_files`)
- **vLLM:** `MODEL_NAME`, `VLLM_QUANTIZATION`, `MAX_MODEL_LEN`, …
- **Langfuse:** keys / admin user (defaults match compose seed: `admin@ragvalod.local` / `ragvalod-admin`)

Service hostnames inside Compose (`qdrant`, `litellm`, …) are already wired in `docker-compose.yml`; you usually only change secrets and optional profiles.

### `configs/litellm.yaml`

Maps stable aliases used by services:

| Alias | Current backend |
| --- | --- |
| `chat-default` | Local vLLM (`http://vllm:8000/v1`) — needs profile `local-llm` |
| `embedder-default` | Infinity (`intfloat/multilingual-e5-small`) |
| `reranker-default` | Infinity (`BAAI/bge-reranker-v2-m3`) |

Without `local-llm`, either start that profile or uncomment the OpenRouter block for `chat-default` and set `OPENROUTER_API_KEY`.

### `configs/langfuse_judge.yaml`

Reference for LLM-as-a-judge evaluators in Langfuse (not auto-loaded). Point Langfuse’s LLM connection at LiteLLM (`http://litellm:4000/v1`, key = `LITELLM_MASTER_KEY`, model `chat-default`).

---

## Useful Make targets

```text
make sync              # uv sync --all-packages --group dev
make up                # docker compose up -d --build
make up-local-llm      # + profile local-llm
make up-monitoring     # + profile monitoring
make up-all            # + local-llm + monitoring
make down              # stop all profiles
make test / make lint
make smoke-qdrant | smoke-litellm | smoke-langfuse
```

---

## Docs

- [Design & plan](docs/design_and_plan.md) — architecture and staged roadmap
- [Progress](docs/progress.md) — step tracker
- [Host GPU setup](docs/host_gpu_setup.md) — NVIDIA driver + Container Toolkit (profile `local-llm` / vLLM)
