"""ctserve — the serving-side contract of the platform, as a library for use-case APIs.

What every use-case API owes the platform and gets from it, in one import:
  * `metrics`        the `uc_*` series the platform's rules and dashboard query
  * `Telemetry`      `emit(model, record)`: prediction log (S3) and, when on, the event bus
  * `CircuitBreaker` graceful degradation of an optional model
  * `configure_logging`  JSON logs bound to use case and git commit

The API keeps what is its own: fan-out, fallback rules, schemas. See docs/design/contracts.md.
"""

from ctserve import metrics
from ctserve.breaker import CircuitBreaker
from ctserve.event_bus import EventBus
from ctserve.logging import configure as configure_logging
from ctserve.prediction_log import PredictionLog
from ctserve.telemetry import Telemetry

__all__ = [
    "CircuitBreaker",
    "EventBus",
    "PredictionLog",
    "Telemetry",
    "configure_logging",
    "metrics",
]
__version__ = "0.1.0"
