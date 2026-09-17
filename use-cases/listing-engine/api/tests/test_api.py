from __future__ import annotations

import asyncio

import httpx
import pytest

from app.config import settings

CAT_URL = settings.categorizer_url
FRAUD_URL = settings.fraud_url

LISTING = {"title": "iPhone 13 Pro 128GB very good condition", "price": 450.0}


async def test_happy_path(client, models):
    r = await client.post("/v1/listings/analyze", json=LISTING)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["category"] == {
        "label": "electronics",
        "confidence": 0.9,
        "source": "model",
        "model_version": settings.categorizer_version,
    }
    assert body["fraud"]["source"] == "model" and body["fraud"]["is_suspicious"] is False
    assert body["lineage"]["request_id"] and body["lineage"]["git_commit"]
    assert body["timings_ms"]["total"] >= body["timings_ms"]["fan_out"]
    # KServe v1 shape: one instance = dict column -> list
    sent = models.calls[0].request
    assert (
        sent.read()
        == b'{"instances":[{"title":["iPhone 13 Pro 128GB very good condition"],"price":[450.0]}]}'
    )


async def test_fraud_timeout_falls_back_to_rules(client, models):
    async def slow(request):
        await asyncio.sleep(settings.fraud_timeout + 0.2)
        return httpx.Response(200, json={"predictions": [[0.9, 0.1]]})

    models.post(FRAUD_URL).mock(side_effect=slow)
    r = await client.post(
        "/v1/listings/analyze", json={"title": "iPhone 15 Pro Max URGENT whatsapp", "price": 3.0}
    )
    body = r.json()
    assert r.status_code == 200
    assert body["fraud"]["source"] == "fallback" and body["fraud"]["model_version"] == "rules"
    assert body["fraud"]["is_suspicious"] is True
    assert set(body["fraud"]["reasons"]) >= {"price_below_category_floor", "suspicious_keyword"}
    assert body["category"]["source"] == "model"  # the categorizer still answered


async def test_fraud_error_opens_circuit_after_threshold(client, models):
    models.post(FRAUD_URL).respond(500, text="boom")
    for _ in range(settings.breaker_failure_threshold):
        r = await client.post("/v1/listings/analyze", json=LISTING)
        assert r.json()["fraud"]["source"] == "fallback"
    assert client._transport.app.state.breaker.state == "open"
    calls_before = models.calls.call_count
    r = await client.post("/v1/listings/analyze", json=LISTING)
    assert r.json()["fraud"]["source"] == "fallback"
    # open circuit: the fraud model was not even called (only the categorizer)
    assert models.calls.call_count == calls_before + 1
    ready = await client.get("/readyz")
    assert ready.json()["fraud_circuit"] == "open"


async def test_categorizer_down_is_503(client, models):
    models.post(CAT_URL).respond(503)
    r = await client.post("/v1/listings/analyze", json=LISTING)
    assert r.status_code == 503 and r.json()["detail"] == "categorizer unavailable"


@pytest.mark.parametrize(
    "payload", [{"title": "", "price": 10}, {"title": "x", "price": 0}, {"price": 3}]
)
async def test_schema_validation(client, models, payload):
    r = await client.post("/v1/listings/analyze", json=payload)
    assert r.status_code == 422


async def test_metrics_exposed(client, models):
    await client.post("/v1/listings/analyze", json=LISTING)
    r = await client.get("/metrics")
    assert "le_requests_total" in r.text and "le_upstream_latency_seconds" in r.text
