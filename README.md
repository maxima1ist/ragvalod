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

# 3. Start (profiles can be combined)
make up                 # base stack
make up-local-llm       # base + vLLM
make up-monitoring      # base + Langfuse
make up-all             # base + vLLM + Langfuse

# 4. Smoke test only — ingests sample corpus from test_data/ (not your real docs)
uv sync --all-packages --group dev   # once, for host-side scripts
uv run python gateway/scripts/e2e_rest.py
```

**Real usage:** put `.txt` / `.md` / `.pdf` / `.docx` into empty `data/`, then [ingest](#ingest) that folder (default path). Keep `test_data/` for smoke/e2e only. After smoke/e2e, [clear the index](#clear-the-vector-db) completely before that ingest — smoke chunks stay until you do.

Tear down (keeps volumes): `make down`.

| Endpoint | URL |
| --- | --- |
| Gateway (user API) | http://localhost:8000 |
| LiteLLM | http://localhost:4000 |
| Qdrant | http://localhost:6333 |
| Langfuse UI (profile `monitoring`) | http://localhost:3000 |
| vLLM (profile `local-llm`) | http://localhost:8001 |

Langfuse default login (compose seed): `admin@ragvalod.local` / `ragvalod-admin`.

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

Two host dirs are mounted into the ingestion container:

| Host | Container | Purpose |
| --- | --- | --- |
| `data/` (default `LOCAL_FILES_DIR`) | `/data/local_files` | **Your** documents (empty by default) |
| `test_data/` | `/test_data` | Sample corpus for smoke/e2e only |

Choose the directory with ingest `options.path` (already supported). Omit it to use the default `/data/local_files`.

**Real ingest** (files you put in `data/`):

```bash
curl -s -X POST http://localhost:8000/ingest \
  -H "X-API-Key: change-me" \
  -H "Content-Type: application/json" \
  -d '{"sources": [{"name": "local_files"}]}'
# same as: "options": {"path": "/data/local_files"}
```

**Smoke / test ingest** (`test_data/`):

```bash
curl -s -X POST http://localhost:8000/ingest \
  -H "X-API-Key: change-me" \
  -H "Content-Type: application/json" \
  -d '{"sources": [{"name": "local_files", "options": {"path": "/test_data"}}]}'
```

Or: `uv run python gateway/scripts/e2e_rest.py` (uses `/test_data` by default).

Before ingesting real files from `data/`, [clear the index](#clear-the-vector-db) completely.

Poll until done:

```bash
curl -s -H "X-API-Key: change-me" http://localhost:8000/ingest/<job_id>
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

### Google Drive

Enable the Drive API in GCP, create a service account, download its JSON key, and **share** the target folder/files with the service account email. Pass the key as a JSON string in credentials (aliases: `service_account_key`, `service_account_json`) or mount a file and pass `service_account_key_path`. OAuth refresh token JSON is also accepted as `authorized_user_info`.

```bash
curl -s -X POST http://localhost:8000/ingest \
  -H "X-API-Key: change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "sources": [{
      "name": "google_drive",
      "credentials": {"service_account_key": "{\"type\":\"service_account\",...}"},
      "options": {"folder_id": "FOLDER_ID"}
    }]
  }'
```

Useful `options` (all strings):

| Option | Meaning |
| --- | --- |
| `folder_id` / `folder` | Drive folder to crawl recursively |
| `file_ids` / `file_id` | Comma-separated file IDs (instead of folder) |
| `query` / `query_string` / `search` | Extra Drive query filter |
| `drive_id` | Shared drive id (optional) |

After a full success, `GET /health` shows `data_initialized: true` and you can call `POST /generate`.

Re-ingest is incremental: LlamaIndex `IngestionPipeline` + per-source docstore (under `/data/ingestion/docstores`) skips unchanged documents, re-embeds changed ones, and deletes Qdrant chunks for removed docs. Deterministic chunk IDs are kept for upserts.

### Scheduled ingest

Periodic ingest lives in the Ingestion Service (APScheduler). Credentials on schedules are **Fernet-encrypted at rest** (`INGESTION_CREDENTIALS_ENCRYPTION_KEY` in `.env`). One-shot `POST /ingest` still keeps creds in memory only.

```bash
# Create (5-field cron: min hour day month dow)
curl -s -X POST http://localhost:8000/schedules \
  -H "X-API-Key: change-me" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "local-daily",
    "cron": "0 3 * * *",
    "enabled": true,
    "sources": [{"name": "local_files", "options": {"path": "/data/local_files"}}]
  }'

curl -s -H "X-API-Key: change-me" http://localhost:8000/schedules
curl -s -X POST -H "X-API-Key: change-me" http://localhost:8000/schedules/<id>/run
curl -s -X DELETE -H "X-API-Key: change-me" http://localhost:8000/schedules/<id>
```

### Delete stored data

`doc_id` removes that document and its chunks. Omit `doc_id` to remove the whole source (every stored document, its chunks, and the source marker). Returns 404 when the document or source is not stored.

```bash
curl -s -X DELETE -G \
  -H "X-API-Key: change-me" \
  "http://localhost:8000/documents" \
  --data-urlencode "source=notion" \
  --data-urlencode "doc_id=PAGE_ID"

curl -s -X DELETE -G \
  -H "X-API-Key: change-me" \
  "http://localhost:8000/documents" \
  --data-urlencode "source=notion"
```

### Clear the vector DB

Deletes the Qdrant collection `documents` (chunks + ingest markers). Stack stays up. Required after smoke/e2e, before the first ingest of real documents in `data/`.

```bash
make clear-qdrant
# drop RAG's in-memory data_initialized cache:
docker compose restart rag_orchestrator
```

Equivalent: `curl -X DELETE http://localhost:6333/collections/documents`

To wipe the whole Qdrant volume (and other Compose volumes): `make down` then `docker compose down -v` (also removes HF cache / Langfuse DB).

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
- **`LOCAL_FILES_DIR`** — host path mounted at `/data/local_files` (default `./data`)
- **vLLM:** `MODEL_NAME`, `VLLM_QUANTIZATION`, `MAX_MODEL_LEN`, …
- **Langfuse:** keys / admin user (defaults match compose seed: `admin@ragvalod.local` / `ragvalod-admin`)

Service hostnames inside Compose (`qdrant`, `litellm`, …) are already wired in `docker-compose.yml`; you usually only change secrets and optional profiles.

### `configs/litellm.yaml`

Maps stable aliases used by services:

| Alias | Current backend |
| --- | --- |
| `chat-default` | Local vLLM (`http://vllm:8000/v1`) — needs profile `local-llm` |
| `judge-default` | OpenRouter `qwen/qwen3.8-27b:free` — judge only, needs `OPENROUTER_API_KEY` |
| `judge-fallback` | OpenRouter `nvidia/nemotron-3-super-120b-a12b:free` — used when `judge-default` is rate-limited |
| `embedder-default` | Infinity (`intfloat/multilingual-e5-small`) |
| `reranker-default` | Infinity (`BAAI/bge-reranker-v2-m3`) |

Without `local-llm`, either start that profile or uncomment the OpenRouter block for `chat-default` and set `OPENROUTER_API_KEY`. `judge-default` stays on OpenRouter even when chat is local.

### `configs/langfuse_judge.yaml`

Rubric for the external judge. `make judge` runs one pass from the host. With profile `monitoring`, service `judge` repeats that pass about once an hour (`JUDGE_INTERVAL_SECONDS`, default 3600) and writes faithfulness, answer relevancy, and context precision through the Langfuse scores API. It calls LiteLLM alias `judge-default`, not `chat-default`. Kubernetes uses a CronJob (`k8s/overlays/monitoring/judge-cronjob.yaml`) with the same image instead of the in-container loop.

---

## Useful Make targets

```text
make sync              # uv sync --all-packages --group dev
make up                # docker compose up -d --build
make up-local-llm      # + profile local-llm
make up-monitoring     # + profile monitoring (Langfuse and the hourly judge)
make up-all            # + local-llm + monitoring
make down              # stop all profiles
make clear-qdrant      # delete Qdrant collection `documents`
make test / make lint
make smoke-qdrant | smoke-litellm | smoke-langfuse | judge
```

---

## Docs

- [Design & plan](docs/design_and_plan.md) — architecture and roadmap
- [Progress](docs/progress.md) — step tracker
- [TODO](docs/TODO.md) — manual follow-ups (Google Drive live, run `make judge`)
- [Host GPU setup](docs/host_gpu_setup.md) — NVIDIA driver + Container Toolkit (profile `local-llm` / vLLM)
