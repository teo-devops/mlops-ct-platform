# Automated Listing Engine — runbook

Platform-level operations are in [docs/operations/runbook.md](../../../docs/operations/runbook.md).
All `make` targets below assume `USE_CASE=automated-listing-engine` (the default).

| I want to… | Do |
|---|---|
| bootstrap / retrain both models | `make pipeline` — or one: `MODELS=fraud TRIGGER=manual make pipeline` |
| promote a registered version / roll back | `make promote MODEL=fraud VERSION=1` (a commit; Argo CD syncs it in ≤ 3 min) |
| see the gate decision of a run | MLflow → experiment `automated-listing-engine/<model>` → run tags `gate.*`; or the `evaluate` node outputs in Argo Workflows (`http://argo.localhost:8088`) |
| watch drift | Grafana → *CT Loop* (`use_case=automated-listing-engine`); Prometheus `ct_drift_psi{use_case="automated-listing-engine"}` |
| run the closed loop on purpose | `make drift` (flips `ct-data-source` to `drift`, sends 600 post-season listings, runs the monitor, waits for the retrain, the commit and the new version) |
| reset the world after `make drift` | `kubectl -n automated-listing-engine-pipelines create configmap ct-data-source --from-literal=profile= --dry-run=client -o yaml \| kubectl apply -f -` |
| rebuild the API or the steps image | `make build`, then `kubectl -n automated-listing-engine-api rollout restart deploy/automated-listing-engine-api` (with `rollout.enabled`: `kubectl argo rollouts restart automated-listing-engine-api`, or bump the ConfigMap); the next pipeline run picks the new steps image |
| call the API | `curl -s -X POST http://automated-listing-engine.localhost:8088/v1/listings/analyze -H 'content-type: application/json' -d '{"title":"iPhone 13 Pro","price":450}'` |
| prove degradation | `make smoke` (scales `fraud-predictor` to 0, expects `fraud.source == "fallback"`, restores it) |
| rotate its secrets | delete them in `automated-listing-engine-*` namespaces, `scripts/secrets.sh`, restart the consumers |

Its Secrets, identities and the data-source ConfigMap: [architecture.md](architecture.md#artifact-store-identities-used).
| move it to other buckets (migration) | the registry keeps `serving_uri` / `reference_uri` of the old bucket: migrate the objects and re-tag, or reset its registered models (`DELETE /api/2.0/mlflow/registered-models/delete`) so the next `make pipeline` bootstraps v1 |
