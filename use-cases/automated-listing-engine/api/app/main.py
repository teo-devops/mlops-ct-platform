"""Automated Listing Engine API — the synchronous path of the platform.

user -> API -> parallel fan-out to the categorizer and fraud models -> one
combined answer. The fraud check degrades to rules when the model is slow,
failing or fused; the categorizer is required. Every answer carries lineage
(model versions, git commit, request id) and every prediction is logged for
the drift monitor.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import structlog
from fastapi import FastAPI, HTTPException, Request
from prometheus_fastapi_instrumentator import Instrumentator

from app import __version__, metrics
from app.breaker import CircuitBreaker
from app.clients import KServeClient, ModelError
from app.config import settings
from app.event_bus import EventBus
from app.fallback import fraud_rules
from app.logging_setup import configure
from app.prediction_log import PredictionLog
from app.schemas import Analysis, Category, Fraud, Lineage, ListingIn

log = structlog.get_logger()
STATE = {"closed": 0, "half-open": 1, "open": 2}


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure(settings.git_commit, settings.use_case)
    app.state.client = KServeClient(settings.use_case)
    app.state.breaker = CircuitBreaker(
        settings.breaker_failure_threshold, settings.breaker_reset_seconds
    )
    app.state.plog = PredictionLog(
        enabled=settings.prediction_log_enabled,
        bucket=settings.prediction_log_bucket,
        use_case=settings.use_case,
        endpoint_url=settings.s3_endpoint_url,
        flush_seconds=settings.prediction_log_flush_seconds,
        flush_records=settings.prediction_log_flush_records,
    )
    app.state.plog.start()
    app.state.bus = EventBus(
        bootstrap=settings.event_bus_bootstrap,
        topic=settings.event_bus_topic,
        use_case=settings.use_case,
    )
    log.info(
        "api_started",
        version=__version__,
        categorizer=settings.categorizer_version,
        fraud=settings.fraud_version,
        event_bus=app.state.bus.enabled,
    )
    yield
    app.state.plog.stop()
    app.state.bus.stop()
    await app.state.client.aclose()


app = FastAPI(title="Automated Listing Engine API", version=__version__, lifespan=lifespan)
Instrumentator(
    should_group_status_codes=False, excluded_handlers=["/metrics", "/healthz", "/readyz"]
).instrument(app).expose(app)


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/readyz")
async def readyz():
    return {"status": "ok", "fraud_circuit": app.state.breaker.state}


async def call_categorizer(request: Request, features: dict) -> Category:
    proba = await request.app.state.client.predict_proba(
        "categorizer", settings.categorizer_url, features, settings.categorizer_timeout
    )
    best = max(range(len(proba)), key=proba.__getitem__)
    label = (
        settings.categorizer_labels[best] if best < len(settings.categorizer_labels) else str(best)
    )
    return Category(
        label=label,
        confidence=round(proba[best], 4),
        source="model",
        model_version=settings.categorizer_version,
    )


async def call_fraud(request: Request, features: dict) -> tuple[float, str, str | None]:
    """Returns (score, source, fallback_reason)."""
    breaker: CircuitBreaker = request.app.state.breaker
    metrics.CIRCUIT.labels(settings.use_case, "fraud").set(STATE[breaker.state])
    if not breaker.allow():
        return -1.0, "fallback", "circuit_open"
    try:
        proba = await request.app.state.client.predict_proba(
            "fraud", settings.fraud_url, features, settings.fraud_timeout
        )
        breaker.record_success()
        return proba[1] if len(proba) > 1 else proba[0], "model", None
    except ModelError as e:
        breaker.record_failure()
        reason = "timeout" if "timeout" in str(e) else "error"
        log.warning("fraud_model_unavailable", error=str(e), circuit=breaker.state)
        return -1.0, "fallback", reason


@app.post("/v1/listings/analyze", response_model=Analysis)
async def analyze(listing: ListingIn, request: Request):
    t_start = time.perf_counter()
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    metrics.REQUESTS.labels(settings.use_case).inc()
    features = {"title": listing.title, "price": listing.price}

    t0 = time.perf_counter()
    cat_task = asyncio.create_task(call_categorizer(request, features))
    fraud_task = asyncio.create_task(call_fraud(request, features))
    cat_result, fraud_result = await asyncio.gather(cat_task, fraud_task, return_exceptions=True)
    elapsed = (time.perf_counter() - t0) * 1000

    if isinstance(cat_result, BaseException):
        # The category is what the listing flow needs; without it there is
        # nothing sensible to return. 503 makes the caller retry/queue.
        log.error("categorizer_unavailable", error=str(cat_result), request_id=request_id)
        raise HTTPException(status_code=503, detail="categorizer unavailable")
    category: Category = cat_result

    score, source, reason = (
        fraud_result if not isinstance(fraud_result, BaseException) else (-1.0, "fallback", "error")
    )
    reasons: list[str] = []
    if source == "fallback":
        score, reasons = fraud_rules(listing.title, listing.price, category.label, settings)
        metrics.FALLBACKS.labels(settings.use_case, "fraud", reason or "unknown").inc()
    fraud = Fraud(
        is_suspicious=score >= settings.fraud_threshold,
        score=round(score, 4),
        source=source,
        model_version=settings.fraud_version if source == "model" else "rules",
        reasons=reasons,
    )

    metrics.PREDICTIONS.labels(
        settings.use_case, "categorizer", category.model_version, "model"
    ).inc()
    metrics.PREDICTIONS.labels(settings.use_case, "fraud", fraud.model_version, source).inc()

    now = datetime.now(UTC).isoformat()
    base = {
        "ts": now,
        "request_id": request_id,
        "title": listing.title,
        "price": listing.price,
        "title_len": len(listing.title),
    }
    # the same record goes to the prediction log (artifact store) and, when the
    # event-bus module is on, to the topic
    plog: PredictionLog = request.app.state.plog
    bus: EventBus = request.app.state.bus

    def emit(model: str, record: dict) -> None:
        plog.record(model, record)
        bus.record(model, record)

    emit(
        "categorizer",
        {
            **base,
            "model": "categorizer",
            "model_version": category.model_version,
            "prediction": category.label,
            "score": category.confidence,
            "source": "model",
        },
    )
    if source == "model":
        emit(
            "fraud",
            {
                **base,
                "model": "fraud",
                "model_version": fraud.model_version,
                "prediction": fraud.is_suspicious,
                "score": fraud.score,
                "source": source,
            },
        )

    total = (time.perf_counter() - t_start) * 1000
    log.info(
        "listing_analyzed",
        request_id=request_id,
        category=category.label,
        fraud=fraud.is_suspicious,
        fraud_source=source,
        ms=round(total, 1),
    )
    return Analysis(
        listing={"title": listing.title, "price": listing.price},
        category=category,
        fraud=fraud,
        lineage=Lineage(
            use_case=settings.use_case,
            api_version=__version__,
            git_commit=settings.git_commit,
            request_id=request_id,
        ),
        timings_ms={"fan_out": round(elapsed, 2), "total": round(total, 2)},
    )
