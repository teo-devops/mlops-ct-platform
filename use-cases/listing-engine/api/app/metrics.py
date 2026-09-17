from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

REQUESTS = Counter("le_requests_total", "Listing analyses", ["use_case"])
FALLBACKS = Counter(
    "le_fraud_fallback_total", "Fraud checks answered by the rules fallback", ["use_case", "reason"]
)
UPSTREAM = Histogram(
    "le_upstream_latency_seconds",
    "Latency of model calls",
    ["use_case", "model", "outcome"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 2.0),
)
CIRCUIT = Gauge(
    "le_circuit_state",
    "Circuit breaker state (0 closed, 1 half-open, 2 open)",
    ["use_case", "model"],
)
PREDICTIONS = Counter(
    "le_predictions_total", "Predictions served", ["use_case", "model", "model_version", "source"]
)
LOG_FLUSHED = Counter(
    "le_prediction_log_records_total",
    "Prediction-log records flushed to the artifact store",
    ["use_case", "model"],
)
LOG_ERRORS = Counter("le_prediction_log_errors_total", "Prediction-log flush errors", ["use_case"])
