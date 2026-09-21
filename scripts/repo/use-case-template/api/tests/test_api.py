from __future__ import annotations

import httpx

from tests.conftest import MODELS, URLS

SAMPLE = {"x1": 1.0, "x2": 2.0, "x3": 0.3, "zone": "north"}


async def test_happy_path(client, models):
    r = await client.post("/v1/__UC__/predict", json=SAMPLE)
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body["predictions"]) == set(MODELS)
    assert all(p["model_version"] == "1" for p in body["predictions"].values())
    assert body["lineage"]["use_case"] == "__UC__" and body["lineage"]["request_id"]


async def test_model_down_is_503(client, models):
    models.post(URLS[MODELS[0]]).mock(return_value=httpx.Response(500))
    r = await client.post("/v1/__UC__/predict", json=SAMPLE)
    assert r.status_code == 503


async def test_schema_validation(client, models):
    r = await client.post("/v1/__UC__/predict", json={"x1": "no"})
    assert r.status_code == 422


async def test_metrics_exposed(client, models):
    await client.post("/v1/__UC__/predict", json=SAMPLE)
    text = (await client.get("/metrics")).text
    assert "uc_requests_total" in text and "uc_predictions_total" in text
