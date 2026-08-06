# Этап 10 — план реализации

Статус: IN PROGRESS · ветка `cursor_grok_iter_first`

## Цель этапа

- Новый источник = новый `DataSource` без правок пайплайна.
- Периодический ингест + креды at rest (Fernet).
- Дедуп/удаление через LlamaIndex `IngestionPipeline` (docstore + хэши).

## 10.1 Google Drive

- [x] Зависимость `llama-index-readers-google`
- [x] `sources/google_drive.py` — обёртка над `GoogleDriveReader`
  - credentials: `service_account_key` (JSON) или `authorized_user_info` (JSON)
  - options: `folder_id`, `file_ids`, `query`/`query_string`, `drive_id`
- [x] Регистрация в `SourceFactory`
- [x] Unit-тесты (мок ридера) + обновление factory-тестов
- [x] `.env.example` / README: как передать service account

## 10.2 Периодический ингест + шифрование кредов

- [x] `CREDENTIALS_ENCRYPTION_KEY` (Fernet url-safe / или raw → Fernet.generate_key)
- [x] `credentials_crypto.py` — encrypt/decrypt map[str,str]
- [x] Persist store (JSON на volume): schedules = cron + SourceSpec (creds encrypted)
- [x] APScheduler внутри Ingestion: тикает → decrypt → `JobManager.start_job`
- [x] gRPC: UpsertSchedule / ListSchedules / DeleteSchedule (+ RunSchedule)
- [x] Gateway REST: `POST/GET/DELETE /schedules` + `/run`
- [x] Volume `ingestion_data` в compose; unit-тесты crypto + schedule store

## 10.3 Дедуп / удаление через IngestionPipeline

- [x] `SimpleDocumentStore` на volume (persist/load), per-source файлы
- [x] В job runner: `IngestionPipeline` + `DocstoreStrategy.UPSERTS_AND_DELETE`
  - transformations пустые (чанкинг остаётся своим)
  - `RecordingVectorStore` — чтобы LI не откатывался на `duplicates_only`
  - embeddings через LiteLLM как раньше
- [x] После run: upsert новых/изменённых; delete Qdrant points по `doc_id`
- [x] Оценка: детерминированные chunk ID (4.5) **оставляем** — pipeline дополняет skip/delete, не заменяет upsert ID
- [x] Unit-тесты: unchanged skip, changed re-upsert, deleted → Qdrant delete, изоляция источников

## Критерий успеха

Новый адаптер без правок остального кода; schedule крутит ингест с зашифрованными кредами; повторный ингест пропускает неизменённые docs и чистит удалённые. — **выполнено**
