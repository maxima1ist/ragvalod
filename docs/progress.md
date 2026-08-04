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

> ### 🛑 ЧЕКПОИНТ 2 — после этапа 3 — [ ] TODO
>
> Пользователь валидирует (первый момент, когда система тратит его деньги):
> - smoke-скрипт проходит chat через его API-ключ, расход по ключу выглядит адекватно;
> - модели Infinity скачались, скорость эмбеддингов/rerank на его CPU приемлема.
## Этап 4: Ingestion Service (локальные файлы) — TODO

- [ ] **Шаг 4.1:** Каркас gRPC-сервиса с job-моделью (несколько источников в одном job, per-source статусы) — TODO
- [ ] **Шаг 4.2:** Абстракция `DataSource` + фабрика адаптеров — TODO
- [ ] **Шаг 4.3:** Адаптер локальных файлов на `SimpleDirectoryReader` (.txt, .md, .pdf, .docx) — TODO
- [ ] **Шаг 4.4:** Пайплайн: structure-aware чанкинг (`MarkdownNodeParser` → `SentenceSplitter`, контекстуализация заголовками) + эмбеддинги через LiteLLM (батчами, префиксы модели) — TODO
- [ ] **Шаг 4.5:** Запись в Qdrant, `upsert` по детерминированным ID; манифест модели при создании коллекции + сверка перед записью; per-source маркеры + write-once маркер инициализации по полностью успешному job — TODO
- [ ] **Шаг 4.6:** Приём кредов через `TriggerIngest` (в памяти на время задачи) — TODO
- [ ] **Шаг 4.7:** Debug-скрипт `ingestion/scripts/run_debug.sh`, unit + интеграционные тесты — TODO

## Этап 5: RAG Orchestrator — TODO

- [ ] **Шаг 5.1:** Каркас gRPC-сервиса, `GenerateAnswer` + проверка инициализации данных (`FAILED_PRECONDITION`) — TODO
- [ ] **Шаг 5.2:** Эмбеддинг запроса через LiteLLM + валидация модели против манифеста коллекции — TODO
- [ ] **Шаг 5.3:** Первый фильтр: векторный поиск в Qdrant (`top_k`) — TODO
- [ ] **Шаг 5.4:** Второй фильтр: реранкер через LiteLLM `/rerank` (`rerank_top_n`) — TODO
- [ ] **Шаг 5.5:** Промпт через Jinja2-шаблон — TODO
- [ ] **Шаг 5.6:** Генерация через LiteLLM (`chat-default`) — TODO
- [ ] **Шаг 5.7:** Возврат ответа + использованных чанков — TODO
- [ ] **Шаг 5.8:** Логирование запросов/ответов в stdout — TODO
- [ ] **Шаг 5.9:** Debug-скрипт `rag_orchestrator/scripts/run_debug.sh`, unit + интеграционные тесты — TODO

## Этап 6: API Gateway — TODO

- [ ] **Шаг 6.1:** FastAPI-роуты: `/health` (вкл. `data_initialized` + per-source маркеры), `/generate`, `/ingest` (мульти-source), `/ingest/{job_id}`, `/sources` — TODO
- [ ] **Шаг 6.2:** Асинхронные gRPC-клиенты (`grpc.aio`), маппинг ошибок в HTTP (вкл. 409 «данных нет») — TODO
- [ ] **Шаг 6.3:** TLS / аутентификация по API-key — TODO
- [ ] **Шаг 6.4:** Сквозная проверка: ошибка до ингеста → ингест → статус job → генерация; рестарт; интеграционные тесты — TODO

> ### 🛑 ЧЕКПОИНТ 3 — после этапа 6 (главный) — [ ] TODO
>
> Пользователь валидирует качество системы end-to-end — единственное, что агент оценить не может:
> - прогоняет руками сценарий шага 6.4 через REST Gateway (409 до ингеста → ингест → генерация → рестарт с сохранением инициализации);
> - кладёт в тестовую директорию **свои реальные заметки** и задаёт вопросы с известными ему ответами — оценивает качество retrieval и ответов, разумность нарезки чанков на его документах.
>
> Пользователь предоставляет для этапа 7: Notion integration token с доступом к тестовым страницам.

## Этап 7: Адаптер Notion — TODO

- [ ] **Шаг 7.1:** `NotionDataSource` — обёртка над ридером `llama-index-readers-notion` — TODO
- [ ] **Шаг 7.2:** Регистрация в фабрике, токен per-request через `/ingest` — TODO
- [ ] **Шаг 7.3:** Ингест тестовой выборки из Notion, проверка инкрементального upsert — TODO

> ### 🛑 ЧЕКПОИНТ 4 — после этапа 7 — [ ] TODO
>
> Пользователь валидирует на маленькой выборке страниц Notion (прежде чем заливать весь workspace):
> - текст и структура заголовков переживают конвертацию (риск из шага 7.1 — плоский текст вместо Markdown);
> - метаданные (заголовок, URL) корректны, ответы по данным из Notion осмысленны.
>
> Пользователь подтверждает для этапа 8: NVIDIA Container Toolkit установлен, GPU доступна из Docker (`nvidia-smi` в контейнере).

## Этап 8: Локальный инференс через vLLM — TODO

- [ ] **Шаг 8.1:** Выбор модели (7B в 4-bit под тестовый стенд) — TODO
- [ ] **Шаг 8.2:** Сервис `vllm` в compose под профилем `local-llm` — TODO
- [ ] **Шаг 8.3:** Перевод алиаса `chat-default` на vLLM-бекенд в `configs/litellm.yaml` — TODO
- [ ] **Шаг 8.4:** Полный цикл через Gateway на локальной модели, без OOM — TODO
- [ ] **Шаг 8.5:** Нагрузочное тестирование, тюнинг параметров vLLM — TODO

> ### 🛑 ЧЕКПОИНТ 5 — после этапа 8 — [ ] TODO
>
> Пользователь валидирует на своём железе (RTX 3070, агент из контейнера это не проверит):
> - полный цикл на локальной модели без OOM, скорость генерации приемлема (~20 ток/с по критерию этапа);
> - субъективное качество локальной 7B против внешнего API — по итогам решает, оставлять ли внешний API основным бекендом.

## Этап 9: Мониторинг и оценка (Langfuse + Judge) — TODO

- [ ] **Шаг 9.1:** Langfuse под профилем `monitoring`, трассировка из RAG Orchestrator — TODO
- [ ] **Шаг 9.2:** Judge: встроенные LLM-as-a-judge эвалюаторы Langfuse + метрики Ragas (конфигурация, не код) — TODO
- [ ] **Шаг 9.3:** Персистентное хранение отладочных данных запросов — TODO
- [ ] **Шаг 9.4:** Эндпоинт агрегированной статистики в Gateway (опционально) — TODO

## Этап 10: Расширение источников и автоматизация ингеста — TODO

- [ ] **Шаг 10.1:** Адаптер Google Drive на ридере `llama-index-readers-google` (и далее прочие источники) — TODO
- [ ] **Шаг 10.2:** Периодический ингест + шифрованное хранение кредов at rest — TODO
- [ ] **Шаг 10.3:** Дедупликация и удаление через `IngestionPipeline` LlamaIndex (docstore + хэши) — TODO

## Этап 11: Оптимизация и Kubernetes — TODO

- [ ] **Шаг 11.1:** Профилирование и оптимизация узких мест — TODO
- [ ] **Шаг 11.2:** Kubernetes-манифесты — TODO
- [ ] **Шаг 11.3:** Горизонтальное масштабирование (Qdrant, реплики, мульти-GPU vLLM) — TODO
- [ ] **Шаг 11.4:** Vault/KMS, Prometheus + Grafana — TODO
