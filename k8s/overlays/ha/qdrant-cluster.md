# Qdrant cluster mode (11.3)

Базовый `base/qdrant.yaml` — **одна реплика** StatefulSet + PVC (достаточно для dev/single-node).

Для production-кластера Qdrant:

1. Развернуть [Qdrant Helm chart](https://github.com/qdrant/qdrant-helm) или официальный distributed setup (3+ nodes, consensus).
2. Указать `INGESTION_QDRANT_HOST` / `RAG_QDRANT_HOST` на service discovery кластера.
3. Миграция данных: snapshot/restore с одиночного PVC.

Не включено в kustomize по умолчанию — требует отдельного storage class и ops-процедур.
