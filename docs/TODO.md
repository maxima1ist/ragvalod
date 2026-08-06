# TODO (ручная валидация / отложено)

Задачи, которые **не блокируют** закрытие этапов в [progress.md](./progress.md), но требуют секретов пользователя или отдельного шага после этапа 11.

## Google Drive — live ingest через API

- **Статус:** адаптер и unit-тесты (мок `GoogleDriveReader`) — OK; **реальный ингест не проверялся**.
- **Нужно:** service account JSON (или OAuth `authorized_user_info`), folder/file IDs, расшарить папку на email SA.
- **Проверка:** `POST /ingest` с `name: google_drive` → poll job → `POST /generate` по содержимому файла.
- **Док:** README, раздел Google Drive.

## Langfuse LLM-as-a-judge (шаг D.1)

- **Статус:** трейсы `rag.generate` работают (этап 9); managed evals UI на Langfuse 2.95 OSS недоступен.
- **Варианты:** апгрейд Langfuse v3 (OSS evals) **или** внешний judge через LiteLLM + scores API.
- **Критерии:** [configs/langfuse_judge.yaml](../configs/langfuse_judge.yaml) (Ragas: faithfulness, answer_relevancy, context_precision).
- **Не путать:** Project API Keys (`pk-lf-…`) ≠ LLM Connections.
- **Когда:** после этапа 11 (см. [design_and_plan.md](./design_and_plan.md), шаг D.1).
