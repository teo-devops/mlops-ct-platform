"""Telemetry: what a use-case API emits so that the platform can watch its models.

One object, one call — `emit(model, record)` — and the platform decides where the record goes:
the prediction log on the artifact store (the drift monitor's batch source, decisions.md #5) and,
when the opt-in event-bus module is on, the `predictions` topic. Configured from the environment
with the platform's own variable names (docs/design/contracts.md), so a use case's chart sets the
same keys the pipeline steps read and the API code never names a bucket or a broker.
"""

from __future__ import annotations

import os

from ctserve.event_bus import EventBus
from ctserve.prediction_log import PredictionLog


def _flag(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).lower() in ("1", "true", "yes")


class Telemetry:
    def __init__(self, *, prediction_log: PredictionLog, event_bus: EventBus) -> None:
        self.prediction_log = prediction_log
        self.event_bus = event_bus

    @classmethod
    def from_env(cls, use_case: str) -> Telemetry:
        """The platform contract, from the environment the use-case chart sets.

        CT_PREDICTION_LOG_ENABLED, CT_PREDICTIONS_BUCKET, S3_ENDPOINT_URL (+ AWS_* from the
        consumer's Secret) for the log; CT_EVENT_BUS_BOOTSTRAP, CT_EVENT_BUS_TOPIC for the bus
        (empty bootstrap = off).
        """
        return cls(
            prediction_log=PredictionLog(
                enabled=_flag("CT_PREDICTION_LOG_ENABLED"),
                bucket=os.environ.get("CT_PREDICTIONS_BUCKET", "predictions"),
                use_case=use_case,
                endpoint_url=os.environ.get("S3_ENDPOINT_URL", ""),
                flush_seconds=float(os.environ.get("CT_PREDICTION_LOG_FLUSH_SECONDS", "10")),
                flush_records=int(os.environ.get("CT_PREDICTION_LOG_FLUSH_RECORDS", "200")),
            ),
            event_bus=EventBus(
                bootstrap=os.environ.get("CT_EVENT_BUS_BOOTSTRAP", ""),
                topic=os.environ.get("CT_EVENT_BUS_TOPIC", "predictions"),
                use_case=use_case,
            ),
        )

    @property
    def sinks(self) -> list[str]:
        return [
            n
            for n, on in (("s3", self.prediction_log.enabled), ("kafka", self.event_bus.enabled))
            if on
        ]

    def start(self) -> None:
        self.prediction_log.start()

    def stop(self) -> None:
        self.prediction_log.stop()
        self.event_bus.stop()

    def emit(self, model: str, record: dict) -> None:
        """One prediction record (docs/modules/event-bus.md schema) to every active sink."""
        self.prediction_log.record(model, record)
        self.event_bus.record(model, record)
