# Module gap: feature-store

| | |
|---|---|
| **Contract it would implement** | consistent features for training and serving, point-in-time correct |
| **Production counterpart** | Feast |
| **Where it plugs in** | a platform module; `UseCase.ingest` reads a Feast offline store, the API reads the online store instead of computing `title_len` inline |
| **What stands in for it in the demo** | features are computed by the estimator's pipeline (TF-IDF, log price) from raw inputs, so training/serving skew cannot happen — at the cost of no shared features across models |

Worth it when several models share features or when features come from many sources; the reference roadmap places it in phase 3.
