# Kubernetes deployment (этап 11)

Манифесты повторяют архитектуру `docker-compose.yml`: REST только через **Gateway**, внутренние вызовы — gRPC.

## Структура

- `base/` — одна реплика каждого сервиса, Ingress на Gateway `:8000`.
- `overlays/ha/` — горизонтальное масштабирование Gateway/RAG, Redis-кеш LiteLLM (этап 11.3).
- `overlays/monitoring/` — Langfuse + Postgres (этап 9).
- `overlays/secrets/` — пример SealedSecret / внешние секреты (этап 11.4).

## Требования

- Kubernetes 1.28+
- Ingress controller (nginx / traefik) для `Ingress`
- `StorageClass` для PVC (Qdrant, ingestion data, HuggingFace cache)
- Для vLLM: ноды с GPU, [NVIDIA device plugin](https://github.com/NVIDIA/k8s-device-plugin)

## Сборка образов

Сервисы собираются из корня репозитория (как в compose):

```bash
docker build -f gateway/Dockerfile -t ragvalod/gateway:latest .
docker build -f ingestion/Dockerfile -t ragvalod/ingestion:latest .
docker build -f rag_orchestrator/Dockerfile -t ragvalod/rag-orchestrator:latest .
# push в ваш registry и обновите images: в overlays
```

## Локальный smoke на kind (без GPU / Ingress)

Прошлый полный `base` на ноутбуке ломался на трёх вещах: Ingress без контроллера, vLLM без GPU, `:latest` / GHCR pull из ноды kind.

Overlay **`k8s/overlays/local`**: vLLM `replicas: 0`, Ingress убран, LiteLLM → локальный тег `ragvalod/litellm:local`.  
Overlay **`k8s/overlays/local-ha`**: то же + 2 реплики GW/RAG/LiteLLM и Redis.

```bash
# 1) кластер
kind create cluster --name ragvalod-smoke --config k8s/kind-smoke.yaml

# 2) образы приложений (как в compose) + одноплатформенный LiteLLM
docker compose build gateway ingestion rag_orchestrator
docker tag ragvalod-gateway:latest ragvalod/gateway:latest
docker tag ragvalod-ingestion:latest ragvalod/ingestion:latest
docker tag ragvalod-rag_orchestrator:latest ragvalod/rag-orchestrator:latest
printf 'FROM ghcr.io/berriai/litellm:main-stable\n' | docker build -t ragvalod/litellm:local -

kind load docker-image --name ragvalod-smoke \
  ragvalod/gateway:latest ragvalod/ingestion:latest \
  ragvalod/rag-orchestrator:latest ragvalod/litellm:local \
  michaelf34/infinity:latest-cpu

# 3) деплой
kubectl apply -f k8s/base/namespace.yaml
kubectl apply -f k8s/base/secret.example.yaml
kubectl apply -k k8s/overlays/local

# 4) проверка (Infinity может долго греть модели — /health его не ждёт)
kubectl -n ragvalod port-forward svc/gateway 8000:8000
curl -s http://127.0.0.1:8000/health
# ожидаем status=ok, data_initialized=false до ингеста

# 5) HA (опционально)
kubectl apply -k k8s/overlays/local-ha

# 6) снести кластер
kind delete cluster --name ragvalod-smoke
```

`imagePullPolicy: IfNotPresent` на локальных образах обязателен: тег `:latest` иначе всегда тянется с Docker Hub.

## Деплой (base)

```bash
# Секреты (не коммитить реальные значения)
cp k8s/base/secret.example.yaml k8s/base/secret.yaml
# отредактируйте secret.yaml, затем:
kubectl apply -f k8s/base/secret.yaml

kubectl apply -k k8s/base
kubectl -n ragvalod get pods,ingress
```

Проверка без кластера:

```bash
make k8s-validate   # sync LiteLLM configs into k8s/ + kubectl kustomize
kubectl kustomize k8s/base   # то же, без make
```

Kustomize разрешает только файлы **внутри** каталога overlay; копии `configs/litellm*.yaml` лежат в `k8s/base/configs/` и `k8s/overlays/ha/configs/`. После правки `configs/litellm.yaml` в корне: `make k8s-sync-config`.

## Ingress и TLS

`base/ingress.yaml` — host `ragvalod.local`, аннотации nginx. TLS: cert-manager `ClusterIssuer` или секрет `ragvalod-tls` вручную.

## gRPC-сервисы

- `ingestion-grpc` и `rag-orchestrator-grpc` — **ClusterIP** (порт 50051 / 50052). Gateway использует DNS `ingestion-grpc:50051`.
- При нескольких репликах RAG/ingestion клиентский gRPC LB в grpcio round-robin — см. overlay `ha` и [performance_tuning.md](../docs/performance_tuning.md).

## Qdrant

StatefulSet + PVC `10Gi`. Кластерный режим Qdrant — отдельный overlay `ha` (3 реплики + bootstrap); для dev достаточно одной реплики.
