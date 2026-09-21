# __UC_TITLE__ — runbook

All `make` targets below take `USE_CASE=__UC__`.

| I want to | Do |
|---|---|
| retrain now | `make pipeline` (every model) or `MODELS=<m> make pipeline` |
| promote or roll back | `make promote MODEL=<m> VERSION=<n>` |
| see the gate decision of a run | MLflow → experiment `__UC__/<model>` → run tags `gate.*`; or the `evaluate` node outputs in Argo Workflows |
| watch drift | Grafana → *CT Loop* (`use_case=__UC__`); Prometheus `ct_drift_psi{use_case="__UC__"}` |
| reset the world after `make drift` | `kubectl -n __UC__-pipelines create configmap ct-data-source --from-literal=profile= --dry-run=client -o yaml \| kubectl apply -f -` |
| rebuild the API or the steps image | `make build`, then `kubectl -n __UC__-api rollout restart deploy/__UC__-api`; the next pipeline run picks the steps image |
| rotate its secrets | delete them in the `__UC__-*` namespaces, `make secrets`, restart the consumers |
