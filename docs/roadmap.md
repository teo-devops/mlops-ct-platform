# Roadmap

What exists, what is next, in the order a platform team would actually do it.

| Phase | Weeks | Goal | Status here |
|---|---|---|---|
| 0 Foundations | 0–2 | GitOps engine, namespaces + policies, artifact store, registry, observability from day one | **done** (H0/H1) |
| 1 Stabilisation | 0–6 | model/service separation, step contract, pipeline with gates, promotion as a commit, weekly retrain, API with graceful degradation | **done** (H2) |
| 2 Scaling & resilience | 2–4 months | drift-driven retraining, dashboards and rules, manual promotion/rollback | **done** (H3); event bus done (Redpanda opt-in, Strimzi documented); progressive delivery done (Argo Rollouts opt-in, API canary); next: autoscaling by QPS, load tests |
| 3 Governance | 4–8+ months | feature store, label feedback and concept drift, HPO, SSO and per-team RBAC, cost governance, KFP adapter exercised (Airflow done, opt-in module), prod/aws profiles reconciled | gaps documented in docs/modules/ |

Near-term backlog, in order: a second use case to prove the plugin boundary · KFP adapter exercised ·
model-level canary (KServe Serverless) in the prod profile.
