# Трекер прогресса

Трекер шагов из [design_and_plan.md](./design_and_plan.md). Нумерация этапов и шагов совпадает с планом.

## Правила ведения

- Статусы: `TODO` → `IN PROGRESS` → `DONE` (или `SKIPPED` с причиной).
- Берёшь шаг в работу — меняешь `[ ] TODO` на `[~] IN PROGRESS`. В работе одновременно должен быть минимум шагов (в идеале один).
- Завершил шаг — меняешь на `[x] DONE`, добавляешь дату и короткую заметку: что сделано, где лежит (модуль/скрипт), чем проверено (тесты/ручная проверка). Пример:
  - `- [x] **Шаг 2.1:** ... — DONE 2026-07-10: qdrant в compose, UI на :6333, gRPC на :6334 проверены`
- Шаг считается `DONE` только если выполнены сквозные требования плана (раздел 2.7): тесты зелёные, линтеры чистые, debug-скрипт работает (там, где применимо).
- Этап помечается `DONE`, когда все его шаги `DONE`/`SKIPPED` и выполнен критерий успеха этапа (раздел 5 плана).
- Если по ходу работы появляется новый шаг — добавляешь его в соответствующий этап сюда **и** в `design_and_plan.md` (план — источник правды, трекер не должен с ним расходиться), с пометкой даты добавления.
- Если шаг отменяется или переносится — не удаляешь строку, а помечаешь `SKIPPED`/переносишь с причиной, чтобы история решений сохранялась.
- **Чекпоинты (`🛑 ЧЕКПОИНТ`)** — точки обязательной остановки агента. Дойдя до чекпоинта, агент **останавливается и не начинает следующий этап**: просит пользователя выполнить перечисленную ручную валидацию и предоставить указанные данные (ключи, токены и т.д.). Продолжать можно только после явного подтверждения пользователя; тогда чекпоинт помечается `[x] DONE` с датой. Автопроверки агента (тесты, линтеры, debug-скрипты) чекпоинты не заменяют — они про то, что агент проверить не может: чужие секреты, реальное железо, личные данные, субъективное качество.

Легенда: `[ ]` TODO · `[~]` IN PROGRESS · `[x]` DONE · `[-]` SKIPPED

> Ревизия плана 2026-07-07: самописный Inference Service заменён на LiteLLM Proxy (AI gateway) + Infinity для эмбеддера/реранкера (см. раздел 2.2 плана); этапы 3 и 4 переставлены местами (ингест зависит от эмбеддингов через LiteLLM). Дополнительно «велосипеды» заменены на готовые решения: адаптеры источников — на ридерах LlamaHub, judge — встроенные эвалюаторы Langfuse + метрики Ragas, кеш эмбеддингов — встроенный кеш LiteLLM, дедупликация — IngestionPipeline LlamaIndex; гибридная криптосхема кредов убрана, логирование — только stdout.

---

## Этап 0: Подготовка окружения и инфраструктуры — DONE

- [x] **Шаг 0.1:** Docker, Docker Compose, NVIDIA Container Toolkit — DONE 2026-08-04: Docker 29.1.3 + Compose 2.40.3 + `uv` 0.12.1 установлены (на машине Docker не было — поставлены через apt). NVIDIA Container Toolkit отложен до этапа 8 (нужен только для профиля `local-llm`).
- [x] **Шаг 0.2:** Структура репозитория — DONE 2026-08-04: каркасы `gateway/`, `ingestion/`, `rag_orchestrator/`, `proto/`, `scripts/`, `configs/` по плану; uv workspace (`pyproject.toml` + member-пакеты).
- [x] **Шаг 0.3:** docker-compose.yml (сервисы, профили, сети, volumes) — DONE 2026-08-04: `docker-compose.yml` с qdrant/gateway/ingestion/rag_orchestrator; профили `models` (litellm+infinity, добавлено 2026-08-04 — не тянуть модели до этапа 3), `local-llm` (vllm), `monitoring` (langfuse). Volumes `qdrant_data`, `hf_cache`. Проверено: `sudo docker compose up -d --build` → все 4 базовых сервиса healthy.
- [x] **Шаг 0.4:** Тулинг: кодогенерация gRPC, линтеры, pytest, каркасы debug-скриптов — DONE 2026-08-04: `scripts/generate_protos.sh`, `Makefile` (sync/protos/lint/test/smoke-qdrant/up/down), ruff + pytest, debug-скрипты в `*/scripts/run_debug.sh`, `.env.example`. Проверено: `make lint`, `make test`.

## Этап 1: gRPC-контракты — DONE

- [x] **Шаг 1.1:** `.proto` для ingestion/rag — DONE 2026-08-04: `proto/ingestion.proto` (TriggerIngest/GetJobStatus/ListSources), `proto/rag.proto` (GenerateAnswer/GetDataStatus).
- [x] **Шаг 1.2:** Кодогенерация клиентов/серверов, gRPC health-checks — DONE 2026-08-04: stubs в `proto/ragvalod_proto/` (пакет `ragvalod-proto`); сервисы отдают standard gRPC Health Checking Protocol; gateway `GET /health`. Проверено: unit-тесты health, compose healthchecks зелёные, ручной Check на :50051/:50052 → SERVING.

## Этап 2: Vector Database (Qdrant) — DONE

- [x] **Шаг 2.1:** Поднять Qdrant, проверить UI (6333) и gRPC (6334) — DONE 2026-08-04: сервис `qdrant` (образ `qdrant/qdrant:v1.14.1`) в compose, порты 6333/6334, volume `qdrant_data`. Проверено: `/readyz` → ready, healthcheck healthy.
- [x] **Шаг 2.2:** Smoke-скрипт в корневом `scripts/`: создание коллекции, запись/чтение векторов по gRPC — DONE 2026-08-04: `scripts/smoke_qdrant.py` (`prefer_grpc=True`) + интеграционный тест `scripts/test_smoke_qdrant.py`. Проверено: `make smoke-qdrant` / `uv run python scripts/smoke_qdrant.py` → OK; pytest 6 passed.

> ### 🛑 ЧЕКПОИНТ 1 — после этапов 0–2 — [x] DONE 2026-08-04
>
> Пользователь валидировал: compose healthy, smoke Qdrant OK, lint/test зелёные, структура/тулинг ок.
> Для этапа 3 предоставлен `OPENROUTER_API_KEY` в `.env` (проверен curl к `openrouter/free`).

## Этап 3: Model Gateway (LiteLLM + Infinity) — DONE

- [x] **Шаг 3.1:** Сервис `litellm` в compose (DB-less, `configs/litellm.yaml`, алиасы chat/embedder/reranker) — DONE 2026-08-04: `configs/litellm.yaml` — `chat-default` → OpenRouter (`openrouter/openrouter/free` + `OPENROUTER_API_KEY`), embed/rerank → Infinity; in-memory cache (`cache_params.type: local`). Образ `ghcr.io/berriai/litellm:main-stable`, порт 4000. Проверено: health healthy + smoke chat.
- [x] **Шаг 3.2:** Сервис `infinity` в compose (эмбеддер + реранкер, CPU), маппинг алиасов — DONE 2026-08-04: образ `michaelf34/infinity:latest-cpu` (исправление имени из плана), модели e5-small + bge-reranker-v2-m3, `--engine torch` (optimum падает: у reranker нет ONNX). Volume `hf_cache`. Проверено: health healthy.
- [x] **Шаг 3.3:** Smoke-скрипт в корневом `scripts/`: chat, embeddings (батч), rerank через LiteLLM — DONE 2026-08-04: `scripts/smoke_litellm.py` + `scripts/test_smoke_litellm.py`, `make smoke-litellm`. Проверено: chat→pong, embeddings batch dim=384, rerank OK; pytest 7 passed.

> ### 🛑 ЧЕКПОИНТ 2 — после этапа 3 — [x] DONE 2026-08-04
>
> Пользователь подтвердил: smoke LiteLLM/Infinity ок, OpenRouter chat работает, скорость приемлема.

## Этап 4: Ingestion Service (локальные файлы) — DONE

- [x] **Шаг 4.1:** Каркас gRPC-сервиса с job-моделью (несколько источников в одном job, per-source статусы) — DONE 2026-08-04: `ingestion/jobs.py` + `TriggerIngest`/`GetJobStatus`; asyncio-задача, статус в памяти.
- [x] **Шаг 4.2:** Абстракция `DataSource` + фабрика адаптеров — DONE 2026-08-04: `sources/base.py`, `sources/factory.py`; unit-тесты фабрики.
- [x] **Шаг 4.3:** Адаптер локальных файлов на `SimpleDirectoryReader` (.txt, .md, .pdf, .docx) — DONE 2026-08-04: `sources/local_files.py`; sample `data/local_files/`; volume mount в compose.
- [x] **Шаг 4.4:** Пайплайн: structure-aware чанкинг + эмбеддинги через LiteLLM — DONE 2026-08-04: `pipeline/chunking.py` (MarkdownNodeParser → SentenceSplitter + contextualize, без NLTK), `pipeline/embeddings.py` (батчи, `passage:`).
- [x] **Шаг 4.5:** Запись в Qdrant + манифест/маркеры — DONE 2026-08-04: `qdrant_store.py` — upsert по uuid5, manifest, per-source + write-once init marker.
- [x] **Шаг 4.6:** Приём кредов через `TriggerIngest` — DONE 2026-08-04: credentials в SourceSpec, только в памяти, `clear()` после источника.
- [x] **Шаг 4.7:** Debug-скрипт + тесты — DONE 2026-08-04: `ingestion/scripts/run_debug.sh`, `trigger_ingest.py`; unit + live ingest → SUCCEEDED, 5 chunks. pytest 13 passed.

## Этап 5: RAG Orchestrator — DONE

- [x] **Шаг 5.1:** Каркас gRPC-сервиса, `GenerateAnswer` + проверка инициализации данных (`FAILED_PRECONDITION`) — DONE 2026-08-04: `RagServicer`; init marker cache; `GetDataStatus`.
- [x] **Шаг 5.2:** Эмбеддинг запроса через LiteLLM + валидация модели против манифеста коллекции — DONE 2026-08-04: `query:` prefix; `validate_manifest_at_startup`.
- [x] **Шаг 5.3:** Первый фильтр: векторный поиск в Qdrant (`top_k`) — DONE 2026-08-04: `QdrantReader.search` (kind=chunk), default top_k=50.
- [x] **Шаг 5.4:** Второй фильтр: реранкер через LiteLLM `/rerank` (`rerank_top_n`) — DONE 2026-08-04: `LiteLLMClient.rerank`, default top_n=5.
- [x] **Шаг 5.5:** Промпт через Jinja2-шаблон — DONE 2026-08-04: inline Jinja2 + `---USER---` split.
- [x] **Шаг 5.6:** Генерация через LiteLLM (`chat-default`) — DONE 2026-08-04: `/v1/chat/completions`.
- [x] **Шаг 5.7:** Возврат ответа + использованных чанков — DONE 2026-08-04: `GenerateAnswerResponse.used_chunks`.
- [x] **Шаг 5.8:** Логирование запросов/ответов в stdout — DONE 2026-08-04: pipeline logs query/candidates/answer.
- [x] **Шаг 5.9:** Debug-скрипт + тесты — DONE 2026-08-04: `run_debug.sh`, `generate_answer.py`; unit + HTTP-mock pipeline; live GenerateAnswer.

## Этап 6: API Gateway — DONE

- [x] **Шаг 6.1:** FastAPI-роуты: `/health` (вкл. `data_initialized` + per-source маркеры), `/generate`, `/ingest` (мульти-source), `/ingest/{job_id}`, `/sources` — DONE 2026-08-04
- [x] **Шаг 6.2:** Асинхронные gRPC-клиенты (`grpc.aio`), маппинг ошибок в HTTP (вкл. 409 «данных нет») — DONE 2026-08-04: `clients.py` + `errors.py`
- [x] **Шаг 6.3:** TLS / аутентификация по API-key — DONE 2026-08-04: `X-API-Key` / Bearer (`GATEWAY_API_KEY`); TLS — на reverse proxy / K8s Ingress (локальный compose остаётся HTTP)
- [x] **Шаг 6.4:** Сквозная проверка: ингест → генерация через REST; рестарт с сохранением инициализации; тесты — DONE 2026-08-04: `gateway/scripts/e2e_rest.py` + unit tests

> ### 🛑 ЧЕКПОИНТ 3 — после этапа 6 (главный) — [x] DONE 2026-08-04
>
> Пользователь валидировал e2e через Gateway (Skrygalov-amber / Markus); Notion token (`NOTION_ACCESS_KEY`) проверен, страница Work (+ дерево) доступна integration `ragvalod-dev`.

## Этап 7: Адаптер Notion — DONE

- [x] **Шаг 7.1:** `NotionDataSource` — обёртка над ридером `llama-index-readers-notion` — DONE 2026-08-04: `MarkdownNotionPageReader` (heading_1/2/3 → `#`, child pages не flatten)
- [x] **Шаг 7.2:** Регистрация в фабрике, токен per-request через `/ingest` — DONE 2026-08-04: credentials `integration_token`/`access_key`; options `page_ids`/`query`/`max_pages`
- [x] **Шаг 7.3:** Ингест тестовой выборки из Notion, проверка инкрементального upsert — DONE 2026-08-04: query=RAG → 1 doc / 10 chunks; повтор 1/10; generate по Notion chunk score~0.93

> ### 🛑 ЧЕКПОИНТ 4 — после этапа 7 — [x] DONE 2026-08-05
>
> Пользователь подтвердил: Notion retrieval/чанки нормальные (текст, заголовки, метаданные).
> GPU из Docker подтверждена 2026-08-05 (`docker run --gpus all … nvidia-smi` → RTX 3070). Шпаргалка хоста: [host_gpu_setup.md](./host_gpu_setup.md).

## Этап 8: Локальный инференс через vLLM — DONE

- [x] **Шаг 8.1:** Выбор модели (7B в 4-bit под тестовый стенд) — DONE 2026-08-05: сначала `TheBloke/Mistral-7B-Instruct-v0.2-AWQ`; после CP5-пробы переключили на `Qwen/Qwen2.5-7B-Instruct-AWQ` (русский). Env: `MODEL_NAME` / `VLLM_*`.
- [x] **Шаг 8.2:** Сервис `vllm` в compose под профилем `local-llm` — DONE 2026-08-05: образ `vllm/vllm-openai:v0.9.2`, `gpus: all`, health `/v1/models`, порт хоста 8001, `make up-local-llm`; litellm `depends_on.vllm` с `required: false`. Позже: `HF_HUB_DISABLE_XET=1`, квантизация `awq_marlin`.
- [x] **Шаг 8.3:** Перевод алиаса `chat-default` на vLLM-бекенд в `configs/litellm.yaml` — DONE 2026-08-05: сейчас `hosted_vllm/Qwen/Qwen2.5-7B-Instruct-AWQ` → `http://vllm:8000/v1`; OpenRouter закомментирован.
- [x] **Шаг 8.4:** Полный цикл через Gateway на локальной модели, без OOM — DONE 2026-08-05: Mistral e2e ok (EN); Qwen e2e RU «Артур Люпа» → список вопросов из Notion, VRAM ~7.7/8.2 ГБ. Chat: system→user fold.
- [x] **Шаг 8.5:** Нагрузочное тестирование, тюнинг параметров vLLM — DONE 2026-08-05: `scripts/bench_local_llm.py`; pure vLLM (Mistral) ~77 tok/s; e2e wall ~9–11s; parallel=2 без ошибок. Дефолты `max-num-seqs=64`, `gpu-memory-utilization=0.85`.

> ### 🛑 ЧЕКПОИНТ 5 — после этапа 8 — [x] DONE 2026-08-05
>
> Пользователь подтвердил: локальный цикл ок (без OOM), `Qwen/Qwen2.5-7B-Instruct-AWQ` устраивает по русскому/качеству — оставляем основным `chat-default` (vLLM / `local-llm`).

## Этап 9: Мониторинг и оценка (Langfuse + Judge) — DONE

- [x] **Шаг 9.1:** Langfuse под профилем `monitoring`, трассировка из RAG Orchestrator — DONE 2026-08-05: `langfuse` + `langfuse-db` (Postgres 17) под `monitoring`; SDK `langfuse<3` в RAG; `tracing.py` + spans embed/search/rerank/prompt/chat. Seed keys через `LANGFUSE_INIT_*`. `make up-monitoring` / `make smoke-langfuse`. Проверено: health OK, `rag.generate` в UI/API.
- [x] **Шаг 9.2:** Judge: встроенные LLM-as-a-judge эвалюаторы Langfuse + метрики Ragas (конфигурация, не код) — DONE 2026-08-05 / уточнение 2026-08-06: рецепт в `configs/langfuse_judge.yaml` + vLLM tool calling (`hermes`) включён. **Managed LLM-as-a-judge UI на Langfuse `2.95` OSS недоступен** (entitlement `model-based-evaluations` / `playground` только cloud; в Settings нет LLM Connections — путать с Project API Keys `pk-lf-…` нельзя). Разбор/включение отложен в конец плана (после этапа 11).
- [x] **Шаг 9.3:** Персистентное хранение отладочных данных запросов — DONE 2026-08-05: Langfuse Postgres volume; в трейсе — query, used_chunks, system/user prompts (span `prompt`), answer. Проверено: trace `rag.generate` с 5 observations + metadata.chunk_ids.
- [x] **Шаг 9.4:** Эндпоинт агрегированной статистики в Gateway (опционально) — DONE 2026-08-05: `GET /stats` (API-key) → Langfuse HTTP traces/scores; без ключей `enabled: false`. Unit + live `/stats` с recent `rag.generate`.

> ### 🛑 ЧЕКПОИНТ 6 — после этапа 9 — [x] DONE 2026-08-06
>
> Пользователь подтвердил: трейсы `rag.generate` в UI ок (query / chunks / prompts / answer).
> Managed Langfuse LLM-as-a-judge **пока нет** (OSS 2.95) — не блокирует переход; разобрать позже (шаг после этапа 11).

## Этап 10: Расширение источников и автоматизация ингеста — DONE

- [x] **Шаг 10.1:** Адаптер Google Drive на ридере `llama-index-readers-google` (и далее прочие источники) — DONE 2026-08-06: `sources/google_drive.py` + factory; credentials `service_account_key`/`authorized_user_info`/`service_account_key_path`; options `folder_id`/`file_ids`/`query`/`drive_id`. Unit-тесты мок-ридера + factory. **Live ingest через Google Drive API не проверялся** (нет SA/OAuth у агента) — см. [TODO.md](./TODO.md).
- [x] **Шаг 10.2:** Периодический ингест + шифрованное хранение кредов at rest — DONE 2026-08-06: Fernet (`credentials_crypto.py`), `ScheduleStore` + APScheduler, gRPC Upsert/List/Delete/RunSchedule, Gateway `POST/GET/DELETE /schedules` + `/run`; volume `ingestion_data`; креды в JSON только ciphertext. Unit + gateway tests.
- [x] **Шаг 10.3:** Дедупликация и удаление через `IngestionPipeline` LlamaIndex (docstore + хэши) — DONE 2026-08-06: per-source `SimpleDocumentStore` + `DocstoreStrategy.UPSERTS_AND_DELETE` (`pipeline/doc_manager.py`); `RecordingVectorStore` включает upsert/delete без записи эмбеддингов в LI; Qdrant delete по `doc_id` + наш LiteLLM upsert. Детерминированные chunk ID (4.5) сохранены. Unit-тесты skip/change/delete/isolation.

> ### 🛑 ЧЕКПОИНТ 7 — после этапа 10 — [x] DONE 2026-08-06
>
> Пользователь подтвердил этап 10: schedules + docstore skip/delete проверены live (docker exec → Gateway); Notion — mocked fetch-тесты + ранее live (CP4).
> **Google Drive live ingest не проверялся** (только unit-тесты с моком ридера) — вынесено в [TODO.md](./TODO.md).
> Managed Langfuse LLM-as-a-judge по-прежнему отложен (шаг D.1 после этапа 11).

## Этап 11: Оптимизация и Kubernetes — DONE

- [x] **Шаг 11.1:** Профилирование и оптимизация узких мест — DONE 2026-09-21: `scripts/profile_rag.py` + `make profile-rag`, `docs/performance_tuning.md`, `configs/litellm.redis.yaml` + compose profile `cache-redis`; env `RAG_DEFAULT_TOP_K`, `INGESTION_CHUNK_*`. pytest + lint OK (live profile — при поднятом стеке).
- [x] **Шаг 11.2:** Kubernetes-манифесты — DONE 2026-09-21: `k8s/base` (Gateway Ingress, Qdrant StatefulSet+PVC, gRPC Services, vLLM/infinity/litellm); `make k8s-validate`, `scripts/test_k8s_kustomize.py`.
- [x] **Шаг 11.3:** Горизонтальное масштабирование (Qdrant, реплики, мульти-GPU vLLM) — DONE 2026-09-21: overlay `k8s/overlays/ha` (GW/RAG/LiteLLM×2, Redis+litellm.redis); `qdrant-cluster.md`, `vllm-multigpu.yaml.example`.
- [x] **Шаг 11.4:** Vault/KMS, Prometheus + Grafana — DONE 2026-09-21: `k8s/examples/sealed-secret.yaml.example`, `external-secrets-vault.md`; overlay `k8s/overlays/observability` (Prometheus+Grafana); monitoring overlay Langfuse.

## После этапа 11 (отложено) — TODO

- [x] **Шаг D.1:** Внешний Langfuse LLM-as-a-judge — DONE 2026-09-27: `scripts/judge_traces.py` + `make judge`. Алиас `judge-default` → OpenRouter `qwen/qwen3.8-27b:free` (не `chat-default`). Почасовой прогон: сервис Compose `judge` (профиль `monitoring`) и CronJob `k8s/overlays/monitoring/judge-cronjob.yaml`. Критерии из `configs/langfuse_judge.yaml` пишутся в scores API. Managed evals UI на Langfuse 2.95 по-прежнему нет.
- [ ] **Шаг D.2:** Google Drive — live ingest через Google API (этап 10.1: адаптер + мок-тесты OK; **реальный вызов Drive не проверялся**) — TODO: service account JSON или OAuth в `POST /ingest`, расшаренная папка/`folder_id`, poll job → `POST /generate` по содержимому; детали — [TODO.md](./TODO.md), README (Google Drive).
