# Delivery Eta — runbook

All `make` targets below take `USE_CASE=delivery-eta`.

| I want to | Do |
|---|---|
| retrain now | `make pipeline` (every model) or `MODELS=<m> make pipeline` |
| promote or roll back | `make promote MODEL=<m> VERSION=<n>` |
| see the gate decision of a run | MLflow → experiment `delivery-eta/<model>` → run tags `gate.*`; or the `evaluate` node outputs in Argo Workflows |
| watch drift | Grafana → *CT Loop* (`use_case=delivery-eta`); Prometheus `ct_drift_psi{use_case="delivery-eta"}` |
| reset the world after `make drift` | `kubectl -n delivery-eta-pipelines create configmap ct-data-source --from-literal=profile= --dry-run=client -o yaml \| kubectl apply -f -` |
| rebuild the API or the steps image | `make build`, then `kubectl -n delivery-eta-api rollout restart deploy/delivery-eta-api`; the next pipeline run picks the steps image |
| rotate its secrets | delete them in the `delivery-eta-*` namespaces, `make secrets`, restart the consumers |
