# External Secrets + Vault (11.4)

Альтернатива Sealed Secrets для rotation и централизованного KMS:

1. Развернуть [External Secrets Operator](https://external-secrets.io/).
2. Хранить значения в Vault path `secret/ragvalod/prod`.
3. `ExternalSecret` синхронизирует Kubernetes `Secret` `ragvalod-secrets`.

Пример (адаптируйте `secretStoreRef` под ваш Vault):

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: ragvalod-secrets
  namespace: ragvalod
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: vault-backend
    kind: ClusterSecretStore
  target:
    name: ragvalod-secrets
  data:
    - secretKey: GATEWAY_API_KEY
      remoteRef:
        key: secret/ragvalod/prod
        property: gateway_api_key
```

GPU-метрики: [NVIDIA DCGM exporter](https://github.com/NVIDIA/dcgm-exporter) DaemonSet на GPU-нодах; добавьте job в `overlays/observability/prometheus.yaml`.
