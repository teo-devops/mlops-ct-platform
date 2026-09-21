"""Metrics of a use-case API — the names are a platform contract.

The platform's rules and the *CT Loop* dashboard query these series for every
use case, keyed by the `use_case` label; a use-case API must expose them with
these exact names (docs/design/contracts.md, "api-metrics").
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

REQUESTS = Counter("uc_requests_total", "Requests answered by the use-case API", ["use_case"])
FALLBACKS = Counter(
    "uc_fallback_total",
    "Answers produced by a fallback instead of a model",
    ["use_case", "model", "reason"],
)
UPSTREAM = Histogram(
    "uc_upstream_latency_seconds",
    "Latency of model calls",
    ["use_case", "model", "outcome"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 2.0),
)
CIRCUIT = Gauge(
    "uc_circuit_state",
    "Circuit breaker state (0 closed, 1 half-open, 2 open)",
    ["use_case", "model"],
)
PREDICTIONS = Counter(
    "uc_predictions_total", "Predictions served", ["use_case", "model", "model_version", "source"]
)
LOG_FLUSHED = Counter(
    "uc_prediction_log_records_total",
    "Prediction-log records flushed to the artifact store",
    ["use_case", "model"],
)
LOG_ERRORS = Counter("uc_prediction_log_errors_total", "Prediction-log flush errors", ["use_case"])
BUS_RECORDS = Counter(
    "uc_event_bus_records_total",
    "Prediction records delivered to the event bus",
    ["use_case", "model"],
)
BUS_ERRORS = Counter("uc_event_bus_errors_total", "Event-bus produce/delivery errors", ["use_case"])
