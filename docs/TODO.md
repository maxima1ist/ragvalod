# TODO (ручная валидация / отложено)

Задачи, которые требуют секретов пользователя или отдельного ручного шага. Трекер шагов — [progress.md](./progress.md).

## Google Drive — live ingest через API (шаг D.2)

- **Статус:** адаптер и unit-тесты (мок `GoogleDriveReader`) — OK; **реальный ингест не проверялся**.
- **Нужно:** service account JSON (или OAuth `authorized_user_info`), folder/file IDs, расшарить папку на email SA.
- **Проверка:** `POST /ingest` с `name: google_drive` → poll job → `POST /generate` по содержимому файла.
- **Док:** README, раздел Google Drive.

## Langfuse LLM-as-a-judge (шаг D.1)

- **Статус:** внешний judge есть (`scripts/judge_traces.py`, `make judge`). Профиль `monitoring` поднимает сервис `judge`, который повторяет прогон примерно раз в час. В Kubernetes то же расписание — CronJob `judge`. Managed evals UI на Langfuse 2.95 OSS по-прежнему нет.
- **Модели:** `chat-default` — локальная Qwen (vLLM); `judge-default` — OpenRouter `qwen/qwen3.8-27b:free` через LiteLLM. Ключ — `OPENROUTER_API_KEY`.
- **Критерии:** faithfulness, answer_relevancy, context_precision ([configs/langfuse_judge.yaml](../configs/langfuse_judge.yaml)).
- **Проверка:** `make up-monitoring` (LiteLLM из базового стека тоже нужен). Сервис `judge` сам подхватывает новые трейсы; разовый прогон с хоста — `make judge`. В UI трейса и в `GET /stats` появляются три score. После правки `configs/litellm.yaml` пересоздать контейнер LiteLLM.
