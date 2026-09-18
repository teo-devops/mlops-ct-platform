# Architecture

Four domains, each a set of modules behind contracts. The use case only touches the top row.

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│  USE CASE (plugin)   listing-engine-api  ·  listing-engine-serving  ·  listing-engine-pipelines │
├──────────────────────────────────────────────────────────────────────────────────────┤
│  SERVING             KServe (Standard mode)      contract: InferenceService + storageUri        │
│  CONTROL / MLOPS     MLflow · Argo Workflows     contracts: model-registry · orchestration       │
│  DATA                MinIO                       contract: artifact-store (S3 API)               │
│  OBSERVABILITY       Prometheus · Grafana · Pushgateway · Evidently   contracts: monitoring · model-monitoring │
├──────────────────────────────────────────────────────────────────────────────────────┤
│  GITOPS ENGINE       Argo CD app-of-apps — every box above is an Application it reconciles      │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## The synchronous path (a user request)

```
user ──HTTP──▶ ingress-nginx ──▶ listing-engine-api ──┬──▶ categorizer-predictor (KServe, sklearn)
                                    │                  └──▶ fraud-predictor       (KServe, sklearn)
                                    │        parallel fan-out, per-model timeouts (800 ms / 300 ms)
                                    ├── fraud slow/down/fused ──▶ rules fallback (never blocks)
                                    ├── categorizer down ──▶ 503 (required)
                                    └── every answer: lineage {model versions, git commit, request id}
                                        every prediction: JSONL record ──▶ s3://predictions/…
```

## The asynchronous path (the continuous-training loop)

```
s3://predictions ──▶ ct-drift (CronWorkflow, every 10 min, Evidently PSI vs champion's reference)
       │                        │ metrics ct_drift_* ──▶ Pushgateway ──▶ Prometheus ──▶ rules, Grafana
       │                        └── PSI > 0.3 ──▶ submits Workflow ct-pipeline (trigger=drift)
       ▼
ct-pipeline: ingest ▶ validate ▶ preprocess ▶ train ▶ evaluate ▶ register ▶ promote
                                 (gate)        MLflow   (gate)    MLflow    git push: models.<m>.version++
                                                                              │
Argo CD sync ◀────────────────────────────────────────────────────────────────┘
       └──▶ InferenceService storageUri = s3://models/<use-case>/<model>/v<N> ──▶ rolling update, readiness
```

Weekly `CronWorkflow`s retrain regardless of drift (the safety net for stale data); `make promote`
runs the promote step alone for a manual promotion or a rollback.

## Namespaces and network

| Namespace | Workload / module | Ingress allowed from | Egress allowed to |
|---|---|---|---|
| `listing-engine-api` | API | ingress-nginx, observability | serving :8080, minio :9000 |
| `listing-engine-serving` | InferenceServices | api, observability | minio :9000 (storage-initializer) |
| `listing-engine-pipelines` | Workflows | — | minio, mlflow, pushgateway, API server, GitHub (promote) |
| `minio` | artifact store | mlflow, serving, pipelines, api, ingress-nginx, observability, host CIDR | intra-namespace |
| `mlflow`, `observability` | registry, monitoring | unrestricted ingress | unrestricted |
| `argocd`, `argo`, `kserve`, `cert-manager`, `ingress-nginx` | engine / controllers | no policies (webhooks come from the API server) | |

Policies are emitted by each workload's chart (the platform does not impose them) and enforced by
kindnet in the demo, by Cilium in the prod profile. DNS egress to `kube-system` is always allowed.

## Isolation model (inherited from Argo-cd-Labs)

`1 workload = 1 namespace = 1 AppProject = 1 Application` (= 1 directory of this monorepo). A
workload's AppProject may read only this repository and write only its own namespace; it may not
create RBAC. Everything cluster-scoped — CRDs, webhooks, ClusterRoles, the RBAC that pipelines
need — belongs to the `platform` project. Secrets are never in Git (docs/design/secrets.md).
