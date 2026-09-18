# Listing Engine — runbook

Platform-level operations are in [docs/operations/runbook.md](../../../docs/operations/runbook.md).
All `make` targets below assume `USE_CASE=listing-engine` (the default).

| I want to… | Do |
|---|---|
| bootstrap / retrain both models | `make pipeline` — or one: `MODELS=fraud TRIGGER=manual make pipeline` |
| promote a registered version / roll back | `make promote MODEL=fraud VERSION=1` (a commit; Argo CD syncs it in ≤ 3 min) |
| see the gate decision of a run | MLflow → experiment `listing-engine/<model>` → run tags `gate.*`; or the `evaluate` node outputs in Argo Workflows (`http://argo.localhost:8088`) |
| watch drift | Grafana → *CT Loop* (`use_case=listing-engine`); Prometheus `ct_drift_psi{use_case="listing-engine"}` |
| run the closed loop on purpose | `make drift` (flips `ct-data-source` to `drift`, sends 600 post-season listings, runs the monitor, waits for the retrain, the commit and the new version) |
| reset the world after `make drift` | `kubectl -n listing-engine-pipelines create configmap ct-data-source --from-literal=profile= --dry-run=client -o yaml \| kubectl apply -f -` |
| rebuild the API or the steps image | `make build`, then `kubectl -n listing-engine-api rollout restart deploy/listing-engine-api`; the next pipeline run picks the new steps image |
| call the API | `curl -s -X POST http://listing-engine.localhost:8088/v1/listings/analyze -H 'content-type: application/json' -d '{"title":"iPhone 13 Pro","price":450}'` |
| prove degradation | `make smoke` (scales `fraud-predictor` to 0, expects `fraud.source == "fallback"`, restores it) |
| rotate its secrets | delete them in `listing-engine-*` namespaces, `scripts/secrets.sh`, restart the consumers |

Its Secrets, identities and the data-source ConfigMap: [architecture.md](architecture.md#artifact-store-identities-used).
