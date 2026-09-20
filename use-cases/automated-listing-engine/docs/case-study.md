# The case study: from prototype to production

The platform was built against the hiring case study of a second-hand marketplace: standardise
the **Automated Listing Engine (ALE)**, a system that, from a listing's photo and title, must
immediately **categorise** the item and **detect fraud** (counterfeits, "scam" pricing patterns).
The company, its data and the original document are not part of this repository — the use case
keeps the name of the system, the symptoms and the constraints, and answers them in a generic way.

## The problem statement (paraphrased)

**Context.** The Data Science team has a "working" PyTorch model deployed as one big Docker
container: a Flask API that loads a 2 GB model file on every restart. There is no versioning,
deployments take 20 minutes, and the model often "hallucinates" categories because the training
data is six months old.

**Constraints of the business.** A marketplace with non-replenishable supply (every listing is
sold once, so there is no "same item" to A/B test on), extreme seasonality (post-holiday surges)
and traffic spikes at predictable hours (Sunday evenings).

**The challenge** is not only to fix the technical debt but to establish a sustainable MLOps
practice. Four questions, answered in [docs/study-guide.es.md §12](../../../docs/study-guide.es.md):

1. **Strategic roadmap and prioritisation** — a phased plan (stabilise → scale → govern) that
   balances rapid impact with long-term reliability and cost.
2. **Standardisation and governance** — a standard ML workflow and developer experience for DS;
   rollbacks under 2 minutes, lineage (data, code, model), cross-team ownership of the inference
   services.
3. **Resilience, scaling and cost** — fallbacks and failsafes when a critical component (the
   fraud model) fails; cost governance of compute and of future expensive dependencies (LLMs).
4. **Observability and alerting** — SLOs/SLIs across system health, data quality and model
   performance; detecting *silent failures* (data and prediction drift) and what they trigger.

## Symptoms → root causes → what fixes them here

| Symptom in the case | Root cause | Module / mechanism in this platform |
|---|---|---|
| A 2 GB model loaded into a Flask container on every restart; deploys take ~20 minutes | model coupled to the service, no artefact/registry separation | **serving** contract: image = runtime, model = data pulled by version from the artifact store; a deploy is a values bump, a rolling update with readiness |
| No versioning: nobody knows which model served which prediction | no registry, no lineage | **model-registry** (aliases, tags `data_hash` / `git_commit` / `serving_uri`), lineage block in every API answer, prediction log |
| Training data six months old: the model "hallucinates" categories | no retraining loop, no drift detection | weekly `CronWorkflow` (never older than a week) + **model-monitoring** (PSI → retrain on demand) |
| Monolith, no CI/CD, no standard | no paved road | the step contract + use-case plugin: a team ships `UseCase` + a chart; the pipeline, the gate, the promotion and the monitoring are the platform's |
| Non-replenishable inventory: no A/B testing possible | validation strategy | champion/challenger replay on labelled history (gate), shadow traffic via the event-bus module |
| Extreme seasonality (post-holiday, Sunday nights) | reactive scaling, no degradation policy | rules fallback + circuit breaker in the API; HPA/pre-warmed scaling in the prod profile |

## Ownership (the contract between teams)

| Team | Owns | Commits to |
|---|---|---|
| Data Science | the `UseCase` plugin: data, schema, estimator, metrics, thresholds | promoting only what beats the champion on the replay |
| Data Engineering | the upstream data and its schema (`ingest` source, `validate` schema) | freshness and schema validation before the pipeline sees the data |
| Platform / MLOps | modules, contracts, the paved road, SLOs, rollback | a model reaches production with zero Kubernetes manifests written by DS |

## SLOs (illustrative starting points, calibrated in the first quarter)

| SLI | SLO | Where it is measured |
|---|---|---|
| API p99 latency (both models, combined) | < 300 ms | `http_request_duration_seconds` — panel "API latency", rule `ServingP99LatencyHigh` (0.3 s). The per-model timeouts of the API (800 / 300 ms) are hard limits, deliberately wider than the SLO: they cap the damage, the SLO measures the norm |
| API availability | 99.9 % monthly | `http_requests_total` 5xx ratio — rule `ServingErrorRatioHigh` |
| Fraud fallback ratio | < 5 % (warn), < 20 % (page) | `uc_fallback_total / uc_requests_total` — rules `ServingFallbackRatioHigh` / `ServingFallbackRatioCritical` |
| Drift detection window | 30 min sliding window vs training reference, every 10 min | `ct_drift_psi` |
| Drift policy (PSI) | < 0.2 none · 0.2–0.3 review · > 0.3 automatic retrain | rules `CTDriftWarning`, `CTDriftRetrainTriggered` |
| Rollback time | < 2 min from decision to traffic on the previous version | `make promote MODEL=<m> VERSION=<previous>` → Argo CD sync → readiness |
| Model age | ≤ 7 days | weekly CronWorkflow |

## Roadmap the platform supports

| Phase | Goal | Delivered here |
|---|---|---|
| 0 — Foundations | namespaces + policies, GitOps, registry, observability from day one | yes: H0/H1 of this repo |
| 1 — Stabilisation | model/service separation, API, CI/CD, weekly retrain | yes: serving contract, pipeline, CronWorkflow |
| 2 — Scaling & resilience | paved-road template, canary + rollback, fallback, events, autoscaling | template and fallback yes; canary/events/autoscaling as documented gaps |
| 3 — Advanced governance | feature store, full lineage, drift → auto-retrain, SLOs, cost governance | drift → auto-retrain yes; feature store gap; SLO rules yes |
