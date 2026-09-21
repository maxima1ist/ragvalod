# Performance tuning (этап 11.1)

Руководство по профилированию и настройке узких мест RAG-пайплайна на тестовом стенде (RTX 3070, 8 ГБ VRAM, CPU Infinity для embed/rerank).

## Профилирование по фазам

Скрипт `scripts/profile_rag.py` повторяет цепочку orchestrator: embed → Qdrant search → rerank → prompt → chat.

```bash
# Стек должен быть поднят (минимум qdrant, litellm, infinity; для chat — profile local-llm).
make up-local-llm   # или up-all

LITELLM_BASE_URL=http://localhost:4000 \
QDRANT_HOST=localhost \
uv run python scripts/profile_rag.py
```

Полезные флаги:

- `--skip-chat` — только retrieval (без vLLM).
- `--top-k-sweep 10,20,30,50` — как растёт rerank при большем `top_k`.
- `--repeat-embed 3` — холодный vs закешированный embed в LiteLLM.

Сводный e2e wall-time через Gateway: `make bench-local-llm` (`scripts/bench_local_llm.py`).

Langfuse (профиль `monitoring`) даёт те же фазы в UI: spans `embed_query`, `vector_search`, `rerank`, `chat` внутри `rag.generate`.

### Типичная картина (стенд этапа 8, Qwen2.5-7B-AWQ)

| Фаза | Порядок | Комментарий |
|------|---------|-------------|
| **chat** | ~80–90% wall | vLLM ~20–80 tok/s; доминирует при `max_tokens` 128–512 |
| **rerank** | ~5–15% | CPU Infinity, растёт ~линейно с `top_k` (50 документов заметно дороже 10) |
| **embed** | ~1–5% | e5-small на CPU; повтор того же запроса → кеш LiteLLM |
| **search** | &lt;1% | Qdrant HNSW, десятки ms |
| **prompt** | пренебрежимо | Jinja2 локально |

**Вывод:** сначала тюнят `max_tokens` и параметры vLLM; затем `top_k` / `rerank_top_n`; embed/search редко первые кандидаты на оптимизацию.

## Retrieval: `top_k` и `rerank_top_n`

- REST: поля `top_k`, `rerank_top_n` в `POST /generate`.
- Дефолты orchestrator: `RAG_DEFAULT_TOP_K` (50), `RAG_DEFAULT_RERANK_TOP_N` (5) в `.env` / compose.

Рекомендации для ноутбука с CPU-rerank:

- **`top_k` 20–30** — баланс recall и latency rerank (нагрузочный bench использовал 10).
- **`rerank_top_n` 3–5** — столько чанков попадает в промпт; больше → длиннее контекст и медленнее chat.

После смены дефолтов перезапустите `rag_orchestrator`.

## LiteLLM cache

Текущий конфиг: in-memory cache (`configs/litellm.yaml`, `cache_params.type: local`). Кеширует идентичные embed/chat запросы — удобно в dev, искажает повторные замеры latency.

Для нескольких реплик LiteLLM / ingestion (этап 11.3) — **Redis**:

1. Поднять Redis (см. профиль `cache-redis` в `docker-compose.yml` или свой инстанс).
2. Переключить конфиг на `configs/litellm.redis.yaml` (volume в сервисе `litellm`).

Переменные: `REDIS_HOST`, `REDIS_PORT` (см. `.env.example`).

## Ingestion: чанки

- `INGESTION_CHUNK_SIZE` (default 512), `INGESTION_CHUNK_OVERLAP` (100) — в `.env` и compose.
- Structure-aware пайплайн: `MarkdownNodeParser` → `SentenceSplitter` + contextualize (`ingestion/pipeline/chunking.py`).

Эксперименты с качеством (не включены по умолчанию):

- **Semantic chunking** (`SemanticSplitterNodeParser`) — другой компромисс granularity/recall; требует переингеста и сравнения traces / ответов.
- Меньший `chunk_size` → больше точек в Qdrant, дольше ingest и search; больший overlap → дубли в контексте.

Меняйте размер чанка только с полным переингестом источников.

## vLLM / VRAM

См. [host_gpu_setup.md](./host_gpu_setup.md) и `.env`: `MAX_MODEL_LEN`, `VLLM_GPU_MEMORY_UTILIZATION`, `VLLM_MAX_NUM_SEQS`.

При OOM: `MAX_MODEL_LEN=2048` или модель меньше (например Phi-3-mini). На сервере — tensor parallelism (этап 11.3).

## Infinity: GPU для rerank

По умолчанию Infinity в compose на **CPU** (`torch`), чтобы не делить VRAM с vLLM. На машине с запасом GPU можно вынести reranker на GPU отдельным Infinity-процессом — правка `docker-compose` (второй сервис или `--device`); не обязательно на 8 ГБ shared VRAM.

## Чеклист после изменений

1. `make lint && make test`
2. `uv run python scripts/profile_rag.py` (и при необходимости `make bench-local-llm`)
3. Сравнить spans в Langfuse для 2–3 типовых запросов
