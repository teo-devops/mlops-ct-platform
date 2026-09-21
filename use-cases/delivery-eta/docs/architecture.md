# Delivery Eta — architecture of the instance

```
user ──HTTP──▶ ingress-nginx ──▶ delivery-eta-api ──┬──▶ <model>-predictor (KServe, sklearn)   one per model
   delivery-eta.localhost:8088                      └── every prediction ──▶ s3://delivery-eta-predictions/delivery-eta/<model>/…
                                                                       (+ topic `predictions` when the event-bus module is on)
```

| Workload | Namespace | Chart | What |
|---|---|---|---|
| `delivery-eta-api` | `delivery-eta-api` | `workloads/api` | FastAPI (`api/`), ingress, ServiceMonitor, NetworkPolicies |
| `delivery-eta-serving` | `delivery-eta-serving` | `workloads/serving` | one InferenceService per model, ServiceAccount `models-reader` (user `delivery-eta-reader`) |
| `delivery-eta-pipelines` | `delivery-eta-pipelines` | `workloads/pipelines` | WorkflowTemplates `ct-pipeline` / `ct-promote` / `ct-drift`, weekly and drift CronWorkflows |

Artifact-store identities used (all this use case's own): `delivery-eta-reader` (ro `delivery-eta-models`),
`delivery-eta-pipeline` (rw `delivery-eta-models`, `delivery-eta-datasets`, `mlflow`; ro `delivery-eta-predictions`),
`delivery-eta-api` (wo `delivery-eta-predictions`). Registry: experiments `delivery-eta/<model>`, registered models
`delivery-eta-<model>` (isolation by name — MLflow has no auth in the demo).
