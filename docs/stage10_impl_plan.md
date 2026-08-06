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

- [ ] `CREDENTIALS_ENCRYPTION_KEY` (Fernet url-safe / или raw → Fernet.generate_key)
- [ ] `credentials_crypto.py` — encrypt/decrypt map[str,str]
- [ ] Persist store (JSON на volume): schedules = cron + SourceSpec (creds encrypted)
- [ ] APScheduler внутри Ingestion: тикает → decrypt → `JobManager.start_job`
- [ ] gRPC: UpsertSchedule / ListSchedules / DeleteSchedule (+ опционально RunNow)
- [ ] Gateway REST: `POST/GET/DELETE /schedules`
- [ ] Volume `ingestion_data` в compose; unit-тесты crypto + schedule store

## 10.3 Дедуп / удаление через IngestionPipeline

- [ ] `SimpleDocumentStore` на volume (persist/load)
- [ ] В job runner: `IngestionPipeline` + `DocstoreStrategy.UPSERTS_AND_DELETE`
  - transformations = наш structure-aware chunking (как Transform)
  - embeddings остаются через LiteLLM (не OpenAIEmbedding)
- [ ] После run: upsert новых/изменённых чанков; delete Qdrant points по `doc_id` для удалённых документов
- [ ] Оценить: детерминированные chunk ID (шаг 4.5) оставляем — pipeline не заменяет их, а дополняет skip/delete
- [ ] Unit-тесты: unchanged skip, changed re-upsert, deleted → Qdrant delete

## Критерий успеха

Новый адаптер без правок остального кода; schedule крутит ингест с зашифрованными кредами; повторный ингест пропускает неизменённые docs и чистит удалённые.
