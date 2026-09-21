# Use case: Automated Listing Engine (ALE)

Given a listing (title, price), predict its **category** and whether it looks **fraudulent**
(counterfeit, price anomaly). Two independent models behind one API with graceful degradation.
Inspired by, and answering, the hiring case study of a second-hand marketplace
([docs/case-study.md](docs/case-study.md)); the data is synthetic.

```
usecase.yaml what the platform's flow scripts need (models, API host/path/sample, `fraud` degradable, drift profile)
docs/       architecture of the instance, the case study, the runbook
plugin/     the `UseCase` implementation (data generator with a `drift` profile, schema, two
            scikit-learn pipelines, metrics) and the steps image: FROM ctsteps-base + this package
api/        FastAPI orchestrator: parallel fan-out, per-model timeouts, circuit breaker + rules
            fallback for fraud, Prometheus metrics, lineage in every answer, prediction log to S3
workloads/  the three workloads (1 namespace = 1 AppProject = 1 Application each):
  api/        Deployment, Service, Ingress `automated-listing-engine.localhost`, ServiceMonitor, NetworkPolicies
  serving/    two InferenceServices pulled by version from s3://models/automated-listing-engine/<model>/v<N>
  pipelines/  WorkflowTemplates ct-pipeline / ct-promote / ct-drift, weekly CronWorkflows, drift CronWorkflow
```

## Its demo

```bash
make demo USE_CASE=automated-listing-engine    # or just `make demo` while it is the first deployed use case
make drift USE_CASE=automated-listing-engine
```

The loop, as `make drift` shows it (the world turns "post-season": prices collapse, electronics
floods, new vocabulary):

```
drift-categorizer  level=retrain max_psi=0.3285 rows=1205 retrain=ct-categorizer-drift-j7m77
✓ ct-categorizer-drift-j7m77 Succeeded      gate: f1_macro improved by 0.1511 (0.99 vs 0.84)
46e44d1 ct: promote automated-listing-engine/categorizer v2 (trigger=drift)
served versions after: categorizer=2 fraud=1   (before: categorizer=1 fraud=1)
```

* **No model is deployed by hand** — only through the pipeline's gates and a promotion commit.
* **Silent failure is caught by distributions**, not by errors: every prediction is logged, the
  monitor compares it with the champion's training reference every 10 minutes.
* **Degradation is a product decision**: the fraud check falls back to explainable rules, the
  listing flow never blocks; the categorizer fails loud.
* **Isolation is declared**: one namespace/AppProject/Application per workload, its own buckets and
  users, NetworkPolicies shipped by each chart — verified by `make smoke`.

## Try it

```bash
curl -s -X POST http://automated-listing-engine.localhost:8088/v1/listings/analyze \
  -H 'content-type: application/json' \
  -d '{"title":"iPhone 13 Pro 128GB very good condition","price":450}' | jq
```

```json
{
  "category": {"label": "electronics", "confidence": 0.98, "source": "model", "model_version": "2"},
  "fraud":    {"is_suspicious": false, "score": 0.05, "source": "model", "model_version": "1", "reasons": []},
  "lineage":  {"use_case": "automated-listing-engine", "api_version": "0.1.0", "git_commit": "99f3e70", "request_id": "…"},
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

Add a `ModelSpec` to `AutomatedListingEngine.models`, handle it in `build_model`/`evaluate`, list it in
`workloads/serving/values-demo.yaml` (`version: "0"`) and `workloads/pipelines/values.yaml`
(`models:`), build, push. The pipeline bootstraps it on its first run.
