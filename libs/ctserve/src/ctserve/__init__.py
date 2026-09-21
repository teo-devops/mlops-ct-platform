"""ctserve — the serving-side contract of the platform, as a library for use-case APIs.

What every use-case API owes the platform and gets from it, in one import:
  * `metrics`        the `uc_*` series the platform's rules and dashboard query
  * `Telemetry`      `emit(model, record)`: prediction log (S3) and, when on, the event bus
  * `CircuitBreaker` graceful degradation of an optional model
  * `models_from_env` the predictor endpoint and served version of every declared model
  * `KServeClient`   the serving contract client (KServe v1 protocol), with upstream latency metrics
  * `configure_logging`  JSON logs bound to use case and git commit

The API keeps what is its own: fan-out, fallback rules, schemas. See docs/design/contracts.md.
"""

from ctserve import metrics
from ctserve.breaker import CircuitBreaker
from ctserve.event_bus import EventBus
from ctserve.kserve import KServeClient, ModelError
from ctserve.logging import configure as configure_logging
from ctserve.models import ModelEndpoint, models_from_env
from ctserve.prediction_log import PredictionLog
from ctserve.telemetry import Telemetry

__all__ = [
    "CircuitBreaker",
    "EventBus",
    "KServeClient",
    "ModelEndpoint",
    "ModelError",
    "PredictionLog",
    "Telemetry",
    "configure_logging",
    "metrics",
    "models_from_env",
]
__version__ = "0.1.0"
