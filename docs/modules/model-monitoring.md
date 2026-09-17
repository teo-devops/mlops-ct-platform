# Module: model-monitoring

| | |
|---|---|
| **Contract** | `ct_drift_*` series; PSI policy 0.2 / 0.3; retrain submission |
| **Demo implementation** | `ctsteps drift` (Evidently 0.7.23) on `CronWorkflow ct-drift` every 10 min, pushing to the Pushgateway and creating Workflows through the Kubernetes API |
| **Pinned version** | evidently 0.7.23 |
| **Namespace** | the use case's pipelines namespace |
| **Replace with** | Evidently service / Evidently consuming Kafka (prod); WhyLabs, NannyML behind the same series names |
| **Disable** | set `drift.enabled: false` in the pipelines chart |

Compares the champion's frozen `reference.parquet` (tagged on the registry version) with the prediction-log window, only for records the champion produced. Columns = `ModelSpec.drift_columns` + the prediction. Booleans and strings are categorical. `ct_drift_last_run_timestamp_seconds` feeds the staleness alert: a monitor that stops is itself an incident.
