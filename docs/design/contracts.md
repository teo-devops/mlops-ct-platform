# Contracts

A contract is what a module promises to the rest of the platform. Swap the tool, keep the promise.

| Contract | Promise | Demo implementation | Consumers |
|---|---|---|---|
| **artifact-store** | S3 API at `S3_ENDPOINT_URL`; buckets `datasets`, `models`, `predictions`, `mlflow`; one least-privilege user per consumer | MinIO (`workloads/minio`) | steps, MLflow, KServe storage-initializer, API prediction log |
| **model-registry** | MLflow tracking + registry at `MLFLOW_TRACKING_URI`; registered model `<use-case>-<model>`; aliases `champion` (served), `challenger` (last gated candidate), `previous` (rollback target); version tags `serving_uri`, `data_hash`, `git_commit`, `reference_uri` | MLflow chart | steps, humans |
| **serving** | an `InferenceService` per model; `storageUri = s3://models/<use-case>/<model>/v<N>` with one `model.joblib`; endpoint `http://<model>-predictor.<ns>.svc/v1/models/<model>:predict` (KServe v1 protocol: `{"instances":[{"col":[v],…}]}`); the served version is `models.<model>.version` in the workload values | KServe Standard mode + sklearn runtime | API, promote step |
| **orchestration** | runs `ctsteps <step>` containers in order, passes three scalars between them (`mlflow_run_id`, `promote`, `version`), triggers on schedule and on demand | Argo Workflows (`WorkflowTemplate ct-pipeline`) | pipelines, drift monitor |
| **monitoring** | Prometheus scrapes every ServiceMonitor/PodMonitor/PrometheusRule; batch jobs push to the Pushgateway; Grafana loads any ConfigMap labelled `grafana_dashboard: "1"` | kube-prometheus-stack + pushgateway | everything |
| **model-monitoring** | series `ct_drift_psi{use_case,model,column}`, `ct_drift_detected`, `ct_drift_window_rows`, `ct_drift_last_run_timestamp_seconds`; policy PSI <0.2 ok · 0.2–0.3 warn · >0.3 retrain; retrain = one Workflow from `ct-pipeline` with `trigger=drift` | `ctsteps drift` (Evidently) on a CronWorkflow | rules, dashboards, pipeline |
| **event-bus** (opt-in) | topic `predictions` on a Kafka-protocol bootstrap URL; one record per prediction, the prediction log's JSON document, keyed by model; topics provisioned by the platform | Redpanda single node (`platform/redpanda`); prod: Kafka via Strimzi | API producer, `ctsteps drift --source kafka` |
| **progressive-delivery** (opt-in) | a workload's `Rollout` with a canary strategy; traffic split by the ingress; `ClusterAnalysisTemplate ct-slo` (args `use-case`, `canary-hash`) judges the canary on the api-metrics contract | Argo Rollouts (`platform/argo-rollouts`) + ingress-nginx weights; prod: the same behind a mesh, KServe `canaryTrafficPercent` for the model | use-case api charts |
| **promotion** | the deployment is a commit: bump `models.<model>.version` in the profile values of the serving and API charts; rollback is another commit | `ctsteps promote` (git push; `pr` mode documented) | Argo CD |

## The api-metrics contract (what a use-case API exposes)

`libs/ctserve` implements this contract for any use-case API: `ctserve.metrics` (the series below),
`ctserve.Telemetry.from_env(use_case)` (prediction log + event bus, configured by the platform's
`CT_PREDICTION_LOG_ENABLED` / `CT_PREDICTIONS_BUCKET` / `S3_ENDPOINT_URL` / `CT_EVENT_BUS_BOOTSTRAP` /
`CT_EVENT_BUS_TOPIC`, set by the use case's chart), `ctserve.CircuitBreaker`. The API calls
`telemetry.emit(model, record)` and never names a bucket or a broker.

The platform's alerting rules and the *CT Loop* dashboard know no use case: they query these
series by the `use_case` label. A use-case API must expose them under `/metrics` (a ServiceMonitor
in its chart adds the `use_case` label):

| Series | Labels | Meaning |
|---|---|---|
| `uc_requests_total` | `use_case` | requests answered |
| `uc_predictions_total` | `use_case, model, model_version, source` | predictions served (`source` = `model` or `fallback`) — the served version over time |
| `uc_upstream_latency_seconds` (histogram) | `use_case, model, outcome` | latency of each model call (`ok`, `timeout`, `error`) |
| `uc_fallback_total` | `use_case, model, reason` | answers produced by a fallback instead of a model |
| `uc_circuit_state` | `use_case, model` | 0 closed · 1 half-open · 2 open |
| `uc_prediction_log_records_total`, `uc_prediction_log_errors_total` | `use_case[, model]` | the prediction log feeding the drift monitor |
| `uc_event_bus_records_total`, `uc_event_bus_errors_total` | `use_case[, model]` | optional: records delivered to / lost by the event bus when the module is on |
| `http_request_duration_seconds` (histogram) | `handler` under `/v1/…` | request latency (any instrumentation library) |

## The step contract (`libs/ctsteps`)

```
ctsteps <ingest|validate|preprocess|train|evaluate|register|promote|drift> --model <m> --run-id <id> [step flags]
```

* **Inputs**: flags and environment — `CT_USE_CASE` (`module:attr` implementing `UseCase`),
  `S3_ENDPOINT_URL`, `CT_*_BUCKET`, `MLFLOW_TRACKING_URI`, `AWS_*`, and for promote `GIT_REPO`,
  `GIT_TOKEN`, `CT_PROMOTE_VALUES_FILE`.
* **Artefacts**: `s3://datasets/<use-case>/<model>/<run-id>/{raw,train,holdout,reference}.parquet`
  and `model.joblib`; `s3://models/<use-case>/<model>/v<N>/model.joblib`.
* **Metadata**: one MLflow run per pipeline run (params, metrics, lineage tags, the model), one
  registry version per registered candidate.
* **Output**: `$CT_OUTPUTS_DIR/result.json` plus one file per scalar (`promote`, `version`,
  `mlflow_run_id`) so that any orchestrator can read them as parameters.

A use case implements `ctsteps.contracts.UseCase`: `models` (a `ModelSpec` each: target, features,
primary metric, drift columns, minimum improvement), `ingest`, `schema`, `build_model`, `evaluate`.
Estimators must be plain scikit-learn: the serving runtime unpickles them without the plugin.
