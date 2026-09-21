# Use case: Delivery ETA

A courier marketplace promises a delivery time at checkout. Given an order (distance, parcel
weight, hour, zone), predict **`eta`**, the minutes from order to door. One regression model, no
fallback: an ETA nobody can compute is a 503 the checkout handles. Generated with
`make new-use-case NAME=delivery-eta MODELS=eta TASK=regression`, then `data.py`, `usecase.py` and
`schemas.py` were filled in. The data is synthetic.

## Quick start

```bash
make use-case ENABLE=delivery-eta COMMIT=1      # opt-in: deploy it (a commit; Argo CD creates its workloads)
make demo USE_CASE=delivery-eta                 # cluster → platform → this use case → smoke   (≈15 min)
```

On a cluster that already runs the platform, `USE_CASE=delivery-eta make build pipeline smoke` is
enough. When it ends, `make status` prints the UIs; the API is at http://delivery-eta.localhost:8088/docs.

## Play

**1. Ask it something**

```bash
curl -s -X POST http://delivery-eta.localhost:8088/v1/deliveries/eta \
  -H 'content-type: application/json' \
  -d '{"distance_km": 4.2, "weight_kg": 1.5, "hour": 18, "zone": "north"}' | jq
```

```json
{
  "predictions": {"eta": {"value": 27.4, "model_version": "1", "source": "model"}},
  "lineage": {"use_case": "delivery-eta", "api_version": "0.1.0", "git_commit": "…", "request_id": "…"},
  "timings_ms": {"fan_out": 12.1, "total": 12.4}
}
```

Same order at `"hour": 3` in `"west"`: no peak, far zone — a different number.

**2. See where that answer came from**

| | |
|---|---|
| the pipeline that trained v1 | http://argo.localhost:8088 → namespace `delivery-eta-pipelines`: `ct-eta-…` |
| the gate decision (`mae`, lower is better), the registry | http://mlflow.localhost:8088 → experiment `delivery-eta/eta`, model `delivery-eta-eta`, aliases `champion` / `previous` |
| the deployment | http://argocd.localhost:8088 → `delivery-eta-serving` (InferenceService `eta`, `predictProba` off) and `-api` |
| the dashboard | http://grafana.localhost:8088 → *CT Loop*, variable `use_case = delivery-eta` |

**3. Break the model — there is nothing to fall back to**

```bash
kubectl -n delivery-eta-serving scale deploy/eta-predictor --replicas=0
# same request → HTTP 503 "eta unavailable"; uc_fallback_total does not move (no degradable model declared)
kubectl -n delivery-eta-serving scale deploy/eta-predictor --replicas=1
```

`make smoke` skips the fallback drill for this use case (`usecase.yaml`: `degradable_model: ""`).

**4. Close the loop**

```bash
make drift USE_CASE=delivery-eta
```

A transport strike: longer distances, evening peaks, a different zone mix, +6 minutes everywhere.
PSI on `distance_km` crosses the retrain threshold, the retrained model beats the champion on the
new holdout, promote commits v2:

```
drift-eta   level=retrain max_psi=0.991 rows=602 psi={distance_km: 0.87, hour: 0.18, weight_kg: 0.01, prediction: 0.99}
✓ ct-eta-drift-… Succeeded
c9834ea ct: promote delivery-eta/eta v2 (trigger=drift)
served versions after: eta=2   (before: eta=1)
```

**5. Roll back, retrain, reset**

```bash
make rollback MODEL=eta USE_CASE=delivery-eta
make pipeline USE_CASE=delivery-eta
kubectl -n delivery-eta-pipelines create configmap ct-data-source \
  --from-literal=profile= --dry-run=client -o yaml | kubectl apply -f -
```

More in [docs/runbook.md](docs/runbook.md); the instance architecture in [docs/architecture.md](docs/architecture.md).

## Models

| Model | Target | Features | Primary metric | Drift columns | If it is down |
|---|---|---|---|---|---|
| `eta` | `eta_minutes` | distance_km, weight_kg, hour, zone → HistGradientBoostingRegressor | `mae` (lower is better) | `distance_km`, `hour`, `weight_kg`, prediction | API answers 503 |

## Layout

```
usecase.yaml   what the platform's flow scripts need (model, API host/path/sample, drift profile `strike`)
docs/          architecture of the instance, runbook
plugin/        the `UseCase` (ingest, schema, build_model, evaluate) + the steps image
api/           FastAPI `/v1/deliveries/eta`: one model call, lineage; telemetry and KServe client from libs/ctserve
workloads/     api/ · serving/ (InferenceService `eta`) · pipelines/ — one Helm chart per workload
```

Isolated like every use case: namespaces `delivery-eta-{api,serving,pipelines}`, buckets
`delivery-eta-{models,datasets,predictions}`, users `delivery-eta-{reader,pipeline,api}`, NetworkPolicies
that admit only its own namespaces. Nothing here names another use case (the validator checks).
