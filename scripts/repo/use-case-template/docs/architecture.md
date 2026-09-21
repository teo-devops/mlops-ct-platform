# __UC_TITLE__ — architecture of the instance

```
user ──HTTP──▶ ingress-nginx ──▶ __UC__-api ──┬──▶ <model>-predictor (KServe, sklearn)   one per model
   __UC__.localhost:8088                      └── every prediction ──▶ s3://__UC__-predictions/__UC__/<model>/…
                                                                       (+ topic `predictions` when the event-bus module is on)
```

| Workload | Namespace | Chart | What |
|---|---|---|---|
| `__UC__-api` | `__UC__-api` | `workloads/api` | FastAPI (`api/`), ingress, ServiceMonitor, NetworkPolicies |
| `__UC__-serving` | `__UC__-serving` | `workloads/serving` | one InferenceService per model, ServiceAccount `models-reader` (user `__UC__-reader`) |
| `__UC__-pipelines` | `__UC__-pipelines` | `workloads/pipelines` | WorkflowTemplates `ct-pipeline` / `ct-promote` / `ct-drift`, weekly and drift CronWorkflows |

Artifact-store identities used (all this use case's own): `__UC__-reader` (ro `__UC__-models`),
`__UC__-pipeline` (rw `__UC__-models`, `__UC__-datasets`, `mlflow`; ro `__UC__-predictions`),
`__UC__-api` (wo `__UC__-predictions`). Registry: experiments `__UC__/<model>`, registered models
`__UC__-<model>` (isolation by name — MLflow has no auth in the demo).
