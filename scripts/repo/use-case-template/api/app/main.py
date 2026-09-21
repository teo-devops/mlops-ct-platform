"""__UC_TITLE__ API — the synchronous path of the platform for this use case.

One request in, every declared model called in parallel (serving contract), one answer with
lineage out; every prediction recorded through the platform's telemetry (prediction log / event
bus) for the drift monitor. There is no fallback here: a model down is a 503. Add one
(rules, cache, a cheaper model) where the business allows it — see the example use case.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import structlog
from ctserve import KServeClient, ModelError, Telemetry, configure_logging, metrics, models_from_env
from fastapi import FastAPI, HTTPException, Request
from prometheus_fastapi_instrumentator import Instrumentator

from app import __version__
from app.config import settings
from app.schemas import Features, Lineage, Prediction, Response

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.git_commit, settings.use_case)
    app.state.client = KServeClient(settings.use_case)
    app.state.models = models_from_env()  # CT_MODEL_<NAME>_URL / _VERSION from the chart
    app.state.telemetry = Telemetry.from_env(settings.use_case)
    app.state.telemetry.start()
    log.info(
        "api_started",
        version=__version__,
        models={m.name: m.version for m in app.state.models.values()},
        telemetry=app.state.telemetry.sinks,
    )
    yield
    app.state.telemetry.stop()
    await app.state.client.aclose()


app = FastAPI(title="__UC_TITLE__ API", version=__version__, lifespan=lifespan)
Instrumentator(
    should_group_status_codes=False, excluded_handlers=["/metrics", "/healthz", "/readyz"]
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    return {"status": "ok", "models": sorted(app.state.models)}


@app.post("/v1/__UC__/predict", response_model=Response)
async def predict(features: Features, request: Request):
    t_start = time.perf_counter()
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    metrics.REQUESTS.labels(settings.use_case).inc()
    client: KServeClient = request.app.state.client
    endpoints = request.app.state.models
    payload = features.model_dump()

    t0 = time.perf_counter()
    results = await asyncio.gather(
        *(
            client.predict(m.name, m.url, payload, settings.model_timeout)
            for m in endpoints.values()
        ),
        return_exceptions=True,
    )
    fan_out = (time.perf_counter() - t0) * 1000

    predictions: dict[str, Prediction] = {}
    now = datetime.now(UTC).isoformat()
    telemetry: Telemetry = request.app.state.telemetry
    for endpoint, result in zip(endpoints.values(), results, strict=True):
        if isinstance(result, BaseException):
            log.error(
                "model_unavailable", model=endpoint.name, error=str(result), request_id=request_id
            )
            raise HTTPException(status_code=503, detail=f"{endpoint.name} unavailable")
        value = result[0] if len(result) == 1 else result
        predictions[endpoint.name] = Prediction(value=value, model_version=endpoint.version)
        metrics.PREDICTIONS.labels(
            settings.use_case, endpoint.name, endpoint.version, "model"
        ).inc()
        # the record the drift monitor compares with the training reference
        telemetry.emit(
            endpoint.name,
            {
                "ts": now,
                "request_id": request_id,
                **payload,
                "model": endpoint.name,
                "model_version": endpoint.version,
                "prediction": value,
                "source": "model",
            },
        )

    total = (time.perf_counter() - t_start) * 1000
    log.info("predicted", request_id=request_id, models=list(predictions), ms=round(total, 1))
    return Response(
        predictions=predictions,
        lineage=Lineage(
            use_case=settings.use_case,
            api_version=__version__,
            git_commit=settings.git_commit,
            request_id=request_id,
        ),
        timings_ms={"fan_out": round(fan_out, 2), "total": round(total, 2)},
    )


# ModelError is what KServeClient raises; kept importable for a use case's own fallback logic.
__all__ = ["ModelError", "app"]
