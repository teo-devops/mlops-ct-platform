# Use case: Delivery ETA

A courier marketplace promises a delivery time at checkout. Given an order (distance, parcel
weight, hour, zone), predict **`eta`**, the minutes from order to door — one regression model, no
fallback rules (an ETA nobody can compute is a 503 the checkout handles). The second use case of
the platform: generated with `make new-use-case NAME=delivery-eta MODELS=eta TASK=regression`,
then `data.py`, `usecase.py` and `schemas.py` were filled in. The data is synthetic.

```
usecase.yaml   what the platform's flow scripts need (model, API host/path/sample, drift profile `strike`)
docs/          architecture of the instance, runbook
plugin/        the `UseCase` (ingest, schema, build_model, evaluate) + the steps image
api/           FastAPI `/v1/deliveries/eta`: one model call, lineage; telemetry through ctserve
workloads/     api/ · serving/ (InferenceService `eta`, predictProba off) · pipelines/
```

## Try it

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

## Models

| Model | Target | Features | Primary metric | Drift columns |
|---|---|---|---|---|
| `eta` | `eta_minutes` | distance_km, weight_kg, hour, zone → HistGradientBoostingRegressor | `mae` (lower is better) | `distance_km`, `hour`, `weight_kg`, prediction |

`make drift` flips the data source to the `strike` profile: longer distances, evening peaks, a
different zone mix, +6 minutes everywhere. PSI on `distance_km` and `hour` crosses the retrain
threshold; the retrained model beats the champion on the new holdout; promote commits v2.

## Isolation

This use case owns namespaces `delivery-eta-{api,serving,pipelines}`, buckets
`delivery-eta-{models,datasets,predictions}` and artifact-store users `delivery-eta-{reader,pipeline,api}`;
its NetworkPolicies admit only its own namespaces. Nothing here names another use case
(`scripts/repo/validate-coherence.py` checks it).
