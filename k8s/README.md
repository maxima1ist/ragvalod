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
make k8s-validate   # kubectl kustomize
```

## Ingress и TLS

`base/ingress.yaml` — host `ragvalod.local`, аннотации nginx. TLS: cert-manager `ClusterIssuer` или секрет `ragvalod-tls` вручную.

## gRPC-сервисы

- `ingestion-grpc` и `rag-orchestrator-grpc` — **ClusterIP** (порт 50051 / 50052). Gateway использует DNS `ingestion-grpc:50051`.
- При нескольких репликах RAG/ingestion клиентский gRPC LB в grpcio round-robin — см. overlay `ha` и [performance_tuning.md](../docs/performance_tuning.md).

## Qdrant

StatefulSet + PVC `10Gi`. Кластерный режим Qdrant — отдельный overlay `ha` (3 реплики + bootstrap); для dev достаточно одной реплики.
