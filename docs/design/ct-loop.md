# The continuous-training loop, step by step

`WorkflowTemplate ct-pipeline` (Argo Workflows, declared by each use case's pipelines chart) runs the same container seven times. Parameters:
`model`, `trigger` (manual | cron | drift | bootstrap), `profile` (data profile override), `rows`.

| # | Step | Reads | Writes | Gate? |
|---|---|---|---|---|
| 1 | `ingest` | the use case's data source (whatever `UseCase.ingest` reads; the example use case generates synthetic data and a `ct-data-source` ConfigMap says which "world") | `raw.parquet`, `data_hash` | |
| 2 | `validate` | `raw.parquet`, `UseCase.schema()` | `result.json {ok, violations}` | **yes** — schema, types, ranges, nulls, allowed values; failure stops the run |
| 3 | `preprocess` | `raw.parquet` | `train`, `holdout`, `reference` parquet (the reference is the frozen distribution the drift monitor will compare against) | |
| 4 | `train` | `train.parquet`, `UseCase.build_model()` | MLflow run (params, metrics, tags `data_hash`, `git_commit`, `reference_uri`, `trigger`), logged model, `model.joblib` | |
| 5 | `evaluate` | `holdout.parquet`, candidate `model.joblib`, champion via alias | metrics of both on the same holdout, `promote` decision + reason (MLflow tags `gate.*`) | **yes** — champion/challenger: promote only if the primary metric improves by `min_improvement`, or there is no champion |
| 6 | `register` | MLflow run | registered version `N`, alias `challenger`, `s3://models/…/v<N>/model.joblib`, tag `serving_uri` | skipped if the gate said no |
| 7 | `promote` | version `N`, `GIT_*` | alias `champion` (old one → `previous`), **one commit** bumping `models.<model>.version` in the values files the use case lists in `promote.valuesFiles` | skipped if the gate said no |

What happens after the commit is not the pipeline's business: Argo CD (≤ 3 min poll) syncs the
serving Application, KServe creates a new predictor pod that downloads `v<N>`, waits for readiness,
then shifts the Service — the old version keeps answering until then. The API Application syncs the
same commit, so `model_version` in every answer follows.

## Why the gate is a replay on labelled history

The gate never looks at live traffic: candidate and champion score the **same held-out, labelled
data**, so the comparison is exact, reproducible and cheap, and it works for use cases where live
A/B testing is impossible or meaningless (the example use case is one: see its
the use case's `docs/architecture.md`). Progressive delivery
(module gap) is the complement for what offline replay cannot see: latency, integration.

## Triggers

| Trigger | Who | When |
|---|---|---|
| `bootstrap` / `manual` | `make pipeline`, `make promote` | first run, experiments, rollback |
| `cron` | `CronWorkflow ct-weekly-<model>` | Monday 03:00 — the safety net against stale data |
| `drift` | `CronWorkflow ct-drift` → `ctsteps drift` | every 10 min; submits `ct-pipeline` when PSI > 0.3 and no run for that model is in flight |
| event-driven | *gap* — Airflow sensor / consumer of the event bus on a new data partition | docs/modules/orchestration.md, docs/modules/event-bus.md |

## Drift policy

`ctsteps drift` compares the champion's `reference.parquet` with the prediction-log window
(30 min in the demo, only records produced by the champion version) on `ModelSpec.drift_columns`
plus the prediction itself, using Evidently's PSI. Thresholds (from the reference document):
below 0.2 nothing, 0.2–0.3 `CTDriftWarning` fires, above 0.3 a retrain is submitted and
`CTDriftRetrainTriggered` fires. `CTDriftMonitorStale` fires if the monitor stops reporting — a
silent monitor is worse than none.
