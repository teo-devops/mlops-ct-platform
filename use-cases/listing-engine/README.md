# Use case: Listing Engine

Given a listing (title, price), predict its **category** and whether it looks **fraudulent**
(counterfeit, price anomaly). Two independent models behind one API with graceful degradation.
Inspired by a marketplace hiring case study (use-cases/listing-engine/docs/case-study.md); the data is synthetic.

```
docs/       architecture of the instance, the case study, the runbook
scripts/    06-build-images · 07-run-pipeline · 08-smoke · 09-induce-drift · promote · secrets
            (steps 06-09 continue the platform's launch flow; `make` runs them with USE_CASE=listing-engine)
plugin/     the `UseCase` implementation (data generator with a `drift` profile, schema, two
            scikit-learn pipelines, metrics) and the steps image: FROM ctsteps-base + this package
api/        FastAPI orchestrator: parallel fan-out, per-model timeouts, circuit breaker + rules
            fallback for fraud, Prometheus metrics, lineage in every answer, prediction log to S3
workloads/  the three workloads (1 namespace = 1 AppProject = 1 Application each):
  api/        Deployment, Service, Ingress `listing-engine.localhost`, ServiceMonitor, NetworkPolicies
  serving/    two InferenceServices pulled by version from s3://models/listing-engine/<model>/v<N>
  pipelines/  WorkflowTemplates ct-pipeline / ct-promote / ct-drift, weekly CronWorkflows, drift CronWorkflow
```

## Try it

```bash
curl -s -X POST http://listing-engine.localhost:8088/v1/listings/analyze \
  -H 'content-type: application/json' \
  -d '{"title":"iPhone 13 Pro 128GB very good condition","price":450}' | jq
```

```json
{
  "category": {"label": "electronics", "confidence": 0.98, "source": "model", "model_version": "2"},
  "fraud":    {"is_suspicious": false, "score": 0.05, "source": "model", "model_version": "1", "reasons": []},
  "lineage":  {"use_case": "listing-engine", "api_version": "0.1.0", "git_commit": "99f3e70", "request_id": "…"},
  "timings_ms": {"fan_out": 69.4, "total": 69.9}
}
```

Kill the fraud predictor and the same call answers `"source": "fallback"` with explainable
`reasons` (`price_below_category_floor`, `suspicious_keyword`); `make smoke` does exactly that.

## Models

| Model | Target | Features | Primary metric | Drift columns |
|---|---|---|---|---|
| `categorizer` | `category` (6 classes) | TF-IDF(title) + log(price) → logistic regression | `f1_macro` | `price`, `title_len`, prediction |
| `fraud` | `is_fraud` | same features, balanced logistic regression | `f1` | `price`, `title_len`, prediction |

Only scikit-learn built-ins: the artefacts load in KServe's generic sklearn runtime.

## Adding a model

Add a `ModelSpec` to `ListingEngine.models`, handle it in `build_model`/`evaluate`, list it in
`workloads/serving/values-demo.yaml` (`version: "0"`) and `workloads/pipelines/values.yaml`
(`models:`), build, push. The pipeline bootstraps it on its first run.
