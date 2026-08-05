# Настройка хоста для GPU (профиль `local-llm`)

Базовый стек ragvalod (Gateway, ingest, RAG, Qdrant, LiteLLM, Infinity) **GPU не требует**. NVIDIA нужна только для профиля Compose `local-llm` (vLLM).

Цель одна на любом железе: **драйвер NVIDIA на хосте + NVIDIA Container Toolkit + `docker run --gpus all … nvidia-smi` показывает GPU**. Дальше Compose сам пробросит устройство в контейнер `vllm`.

## Общий чеклист (PC / ноутбук / сервер)

1. **Драйвер NVIDIA** установлен, модуль загружен:
   ```bash
   nvidia-smi
   ```
   Должна быть таблица с именем GPU и версией драйвера. Если падает с «couldn't communicate with the NVIDIA driver», а `lsmod | grep nvidia` не пустой — часто нет device nodes:
   ```bash
   sudo apt install -y nvidia-modprobe   # если бинаря нет
   sudo nvidia-modprobe -u -c=0
   ls /dev/nvidia*
   nvidia-smi
   ```
2. **NVIDIA Container Toolkit** (пакет обычно **не** в дефолтных Ubuntu-репо — нужен репозиторий NVIDIA):
   ```bash
   curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
     | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
   curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
     | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
     | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
   sudo apt update
   sudo apt install -y nvidia-container-toolkit
   sudo nvidia-ctk runtime configure --runtime=docker
   sudo systemctl restart docker
   ```
3. **Проверка из Docker** (критерий готовности к этапу 8):
   ```bash
   sg docker -c 'docker run --rm --gpus all nvidia/cuda:12.6.0-base-ubuntu22.04 nvidia-smi'
   ```
4. Подъём стека с локальной LLM:
   ```bash
   sg docker -c 'docker compose --profile local-llm up -d'
   # или: make up-local-llm
   ```

## Что обычно отличается по типу машины

| | Десктоп / GPU-сервер | Ноутбук (PRIME / hybrid) | Прод (K8s / multi-GPU) |
|---|---|---|---|
| GPU в Docker | Обычно сразу после toolkit | Те же шаги + чаще нужны `nvidia-modprobe` / reboot после смены драйвера | Device plugin / RuntimeClass вместо ручного `--gpus` |
| VRAM | Часто целиком под compute | Делится с дисплеем (Xorg/Wayland, браузер, IDE) — закладывай запас, `gpu-memory-utilization` < 0.9 | Выделенные GPU / MIG; tensor parallelism в vLLM |
| PRIME | Не актуально | `on-demand` / `nvidia` — норма; без `/dev/nvidia*` compute из Docker не взлетит | Не актуально |
| Конфликт драйверов | Реже | Часто стоят несколько metapackage (`nvidia-driver-550` и `580`) — оставь одну линейку utils/driver под загруженный модуль | Образы нод с зафиксированной версией драйвера |

Инвариант везде один: **userspace (`nvidia-smi`, toolkit) должен совпадать с загруженным kernel module**, а Docker должен видеть runtime `nvidia`.

## Типичные симптомы

| Симптом | Что чинить |
|---|---|
| `could not select device driver "" with capabilities: [[gpu]]` | Нет / не настроен Container Toolkit → шаг 2 чеклиста |
| Хост `nvidia-smi` ок, в контейнере пусто/ошибка | Toolkit, `nvidia-ctk runtime configure`, restart Docker |
| Хост `nvidia-smi` падает, `/dev/nvidia*` нет | `nvidia-modprobe`, перезагрузка, проверка PRIME/драйвера |
| OOM в vLLM на 8 ГБ | AWQ/GPTQ 7B, снизить `MAX_MODEL_LEN` (4096→2048), `VLLM_GPU_MEMORY_UTILIZATION` (0.9→0.8) |
| После reboot снова нет `/dev/nvidia*` | Повторить `nvidia-modprobe` или включить persistenced / проверить, что DKMS-модуль собрался под текущее ядро |

## Связь с планом

- План: [design_and_plan.md](./design_and_plan.md) §2.6 (железо), этап 8 (vLLM).
- Прогресс: [progress.md](./progress.md) — этап 8, чекпоинт 5.
- Compose: сервис `vllm`, профиль `local-llm`; без профиля образ не тянется.
