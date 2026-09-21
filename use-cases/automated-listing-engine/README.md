# Use case: Automated Listing Engine (ALE)

A second-hand marketplace publishes a listing (title, price) and needs, at once, its **category**
and whether it looks **fraudulent** (counterfeit, price anomaly). Two independent models behind one
API: the category is mandatory, the fraud check may degrade to explainable rules. Inspired by, and
answering, a hiring case study of a second-hand marketplace ([docs/case-study.md](docs/case-study.md));
the data is synthetic.

## Quick start

```bash
make demo USE_CASE=automated-listing-engine     # cluster → platform → this use case → smoke   (≈15 min)
```

Deployed by default (`make use-case` shows it), so plain `make demo` runs it too. When it ends,
`make status` prints the UIs; the API is at http://automated-listing-engine.localhost:8088/docs.

## Play

**1. Ask it something**

```bash
curl -s -X POST http://automated-listing-engine.localhost:8088/v1/listings/analyze \
  -H 'content-type: application/json' \
  -d '{"title":"iPhone 13 Pro 128GB very good condition","price":450}' | jq
```

```json
{
  "category": {"label": "electronics", "confidence": 0.98, "source": "model", "model_version": "1"},
  "fraud":    {"is_suspicious": false, "score": 0.05, "source": "model", "model_version": "1", "reasons": []},
  "lineage":  {"use_case": "automated-listing-engine", "api_version": "0.1.0", "git_commit": "…", "request_id": "…"},
  "timings_ms": {"fan_out": 69.4, "total": 69.9}
}
```

Try a suspicious one: `{"title":"iPhone 15 Pro Max URGENT whatsapp","price":40}` → `is_suspicious: true`.

**2. See where that answer came from**

| | |
|---|---|
| the pipelines that trained v1 | http://argo.localhost:8088 → namespace `automated-listing-engine-pipelines`: `ct-categorizer-…`, `ct-fraud-…` |
| the gate decision, the registry | http://mlflow.localhost:8088 → experiments `automated-listing-engine/categorizer` and `…/fraud`, models `automated-listing-engine-categorizer` / `-fraud` with aliases `champion` / `previous` |
| the deployment | http://argocd.localhost:8088 → `automated-listing-engine-serving` (two InferenceServices) and `-api` |
| the dashboard | http://grafana.localhost:8088 → *CT Loop*, variable `use_case = automated-listing-engine` |

**3. Break the fraud model — the listing flow must not stop**

```bash
kubectl -n automated-listing-engine-serving scale deploy/fraud-predictor --replicas=0
# same request: "fraud": {"source": "fallback", "model_version": "rules", "reasons": ["price_below_category_floor", …]}
kubectl -n automated-listing-engine-serving scale deploy/fraud-predictor --replicas=1
```

The categorizer is the opposite: kill `categorizer-predictor` and the API answers **503** — without a
category the listing flow has nothing sensible to return. `make smoke` runs this drill.

**4. Close the loop**

```bash
make drift USE_CASE=automated-listing-engine
```

The world turns "post-season": prices collapse, electronics floods, new vocabulary. 600 such
listings hit the API, the monitor measures the PSI of what the models see against their training
reference, retrains, the gate compares, promote commits, Argo CD rolls, the API answers with the
new version:

```
drift-categorizer  level=retrain max_psi=0.72 rows=604 retrain=ct-categorizer-drift-…
drift-fraud        level=retrain max_psi=0.51 rows=602 retrain=ct-fraud-drift-…
✓ ct-categorizer-drift-… Succeeded      gate: f1_macro improved by 0.16
2c3008d ct: promote automated-listing-engine/categorizer v2 (trigger=drift)
1cc8d19 ct: promote automated-listing-engine/fraud v2 (trigger=drift)
served versions after: categorizer=2 fraud=2   (before: categorizer=1 fraud=1)
```

**5. Roll back, retrain, reset**

```bash
make rollback MODEL=categorizer USE_CASE=automated-listing-engine      # previous champion, one commit
make pipeline USE_CASE=automated-listing-engine                        # retrain both models now
kubectl -n automated-listing-engine-pipelines create configmap ct-data-source \
  --from-literal=profile= --dry-run=client -o yaml | kubectl apply -f -   # the world back to normal
```

More in [docs/runbook.md](docs/runbook.md); the instance architecture in [docs/architecture.md](docs/architecture.md).

## Models

| Model | Target | Features | Primary metric | Drift columns | If it is down |
|---|---|---|---|---|---|
| `categorizer` | `category` (6 classes) | TF-IDF(title) + log(price) → logistic regression | `f1_macro` | `price`, `title_len`, prediction | API answers 503 |
| `fraud` | `is_fraud` | same features, balanced logistic regression | `f1` | `price`, `title_len`, prediction | rules fallback, circuit breaker |

Only scikit-learn built-ins: the artefacts load in KServe's generic sklearn runtime. To add a model:
a `ModelSpec` in `AutomatedListingEngine.models`, its branch in `build_model`/`evaluate`, one entry in
`workloads/serving/values-demo.yaml` (`version: "0"`) and `workloads/pipelines/values.yaml` (`models:`),
`usecase.yaml`; the pipeline bootstraps it on its first run.

## Layout

```
usecase.yaml what the platform's flow scripts need (models, API host/path/sample, `fraud` degradable, drift profile)
docs/        architecture of the instance, the case study, the runbook
plugin/      the `UseCase` (data generator with a `drift` profile, schema, two scikit-learn pipelines,
             metrics) and the steps image: FROM ctsteps-base + this package
api/         FastAPI: parallel fan-out, per-model timeouts, circuit breaker + rules fallback for fraud,
             lineage in every answer; metrics, prediction log and KServe client from libs/ctserve
workloads/   the three workloads (1 namespace = 1 AppProject = 1 Application each):
  api/         Deployment (or Rollout), Service, Ingress `automated-listing-engine.localhost`, ServiceMonitor, NetworkPolicies
  serving/     two InferenceServices pulled by version from s3://automated-listing-engine-models/…/<model>/v<N>
  pipelines/   WorkflowTemplates ct-pipeline / ct-promote / ct-drift, weekly CronWorkflows, drift CronWorkflow
```

Isolated like every use case: its namespaces `automated-listing-engine-{api,serving,pipelines}`, its
buckets and artifact-store users, NetworkPolicies that admit only its own namespaces.
