# Automated Listing Engine — architecture of the instance

The platform's generic picture is in [docs/design/architecture.md](../../../docs/design/architecture.md);
this is what it looks like with this use case plugged in.

```
user ──HTTP──▶ ingress-nginx ──▶ automated-listing-engine-api ──┬──▶ categorizer-predictor (KServe, sklearn)
   automated-listing-engine.localhost:8088     │                  └──▶ fraud-predictor       (KServe, sklearn)
                                     │        parallel fan-out, timeouts 800 ms / 300 ms
                                     ├── fraud slow/down/fused ──▶ rules fallback (never blocks)
                                     ├── categorizer down ──▶ 503 (required)
                                     └── every prediction ──▶ s3://predictions/automated-listing-engine/<model>/…
                                                         (+ topic `predictions` when the event-bus module is on)
```

| Workload | Namespace | Chart | What it holds |
|---|---|---|---|
| `automated-listing-engine-api` | `automated-listing-engine-api` | `workloads/api` | FastAPI orchestrator (`api/`), ingress, ServiceMonitor, NetworkPolicies |
| `automated-listing-engine-serving` | `automated-listing-engine-serving` | `workloads/serving` | InferenceServices `categorizer` and `fraud`, ServiceAccount `models-reader`, PodMonitor, NetworkPolicies |
| `automated-listing-engine-pipelines` | `automated-listing-engine-pipelines` | `workloads/pipelines` | WorkflowTemplates `ct-pipeline` / `ct-promote` / `ct-drift`, weekly CronWorkflows, `ct-drift` CronWorkflow, NetworkPolicies |

## Models

| Model | Target | Features | Primary metric | Drift columns | Registry name |
|---|---|---|---|---|---|
| `categorizer` | `category` (6 classes) | TF-IDF(title) + log(price) → logistic regression | `f1_macro` | `price`, `title_len`, prediction | `automated-listing-engine-categorizer` |
| `fraud` | `is_fraud` | same features, balanced logistic regression | `f1` | `price`, `title_len`, prediction | `automated-listing-engine-fraud` |

Served from `s3://models/automated-listing-engine/<model>/v<N>/model.joblib`; the served version is
`models.<model>.version` in `workloads/serving/values-demo.yaml` **and** `workloads/api/values-demo.yaml`
(bumped together by `promote`, so the API's lineage always matches the predictor).

## Graceful degradation (the product decision)

The fraud check may degrade; the category may not. `api/app/fallback.py` implements explainable
rules (`price_at_floor`, `price_below_category_floor` against per-category medians,
`suspicious_keyword`); `ctserve.CircuitBreaker` (libs/ctserve) opens the circuit after 5 failures for 30 s so a dead
model costs no latency budget. Every answer says which source produced the fraud verdict
(`model` | `fallback`) and which version.

Known limitation, on purpose: the rules use **static per-category medians** (chart values). When
the market moves (the `drift` profile collapses prices ×0.25) the model retrains and adapts, the
rules do not — they over-flag until someone recalibrates them. That is the honest trade-off of a
fallback: predictable and explainable, not adaptive. A follow-up is to derive the medians from
the champion's `reference.parquet` at promote time.

## Why the gate replays instead of A/B testing

In a marketplace every listing is served once (non-replenishable inventory): there is no "same
item" to show to two models. The platform's champion/challenger gate — both models scored on the
same labelled holdout — is the right primitive here, complemented in production by shadow traffic
(event-bus module). Live A/B is the wrong tool for this domain.

## Artifact-store identities used

| Artifact-store user | Secret | Namespace | Rights |
|---|---|---|---|
| `models-reader` | `models-s3-credentials` | `automated-listing-engine-serving` | read `models` |
| `pipeline` | `pipeline-s3-credentials` | `automated-listing-engine-pipelines` | read/write `models`, `datasets`, `mlflow`; read `predictions` |
| `api-writer` | `api-s3-credentials` | `automated-listing-engine-api` | write `predictions` |

Plus `pipeline-git-credentials` (promote) and the `ct-data-source` ConfigMap (which "world" the
synthetic data source generates). All created by `scripts/secrets.sh`, never in Git.
