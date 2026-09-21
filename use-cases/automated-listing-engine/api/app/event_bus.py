"""Event bus: every prediction record published to a Kafka topic, next to the prediction log.

Same record as `prediction_log.py` (docs/modules/event-bus.md); the topic adds fan-out and
latency: the drift monitor can read a window straight from it, a shadow model or a label join
can consume the same stream. Off unless `ALE_EVENT_BUS_BOOTSTRAP` is set (the opt-in redpanda
module). The producer is asynchronous and never blocks a request: a broker outage costs
`uc_event_bus_errors_total`, not availability — the S3 log stays the batch source of truth.
"""

from __future__ import annotations

import json

import structlog

from app import metrics

log = structlog.get_logger()


class EventBus:
    def __init__(
        self,
        *,
        bootstrap: str,
        topic: str,
        use_case: str,
        producer_factory=None,
    ) -> None:
        self.enabled = bool(bootstrap)
        self.topic = topic
        self.use_case = use_case
        self._producer = None
        if not self.enabled:
            return
        if producer_factory is None:
            from confluent_kafka import Producer

            producer_factory = Producer
        self._producer = producer_factory(
            {
                "bootstrap.servers": bootstrap,
                "client.id": f"{use_case}-api",
                "acks": "1",
                "linger.ms": 50,
                "message.timeout.ms": 5000,  # give up on a record before it piles up
                "enable.idempotence": False,
            }
        )

    def record(self, model: str, record: dict) -> None:
        if not self.enabled:
            return
        try:
            self._producer.produce(
                self.topic,
                key=model.encode(),
                value=json.dumps(record, default=str).encode(),
                on_delivery=self._delivered,
            )
            self._producer.poll(0)  # serve delivery callbacks without blocking
        except BufferError:
            metrics.BUS_ERRORS.labels(self.use_case).inc()
            log.warning("event_bus_queue_full", model=model)
        except Exception as e:  # noqa: BLE001 — never let the bus break serving
            metrics.BUS_ERRORS.labels(self.use_case).inc()
            log.warning("event_bus_produce_failed", model=model, error=str(e))

    def _delivered(self, err, msg) -> None:
        if err is not None:
            metrics.BUS_ERRORS.labels(self.use_case).inc()
            log.warning("event_bus_delivery_failed", error=str(err))
        else:
            metrics.BUS_RECORDS.labels(self.use_case, msg.key().decode()).inc()

    def stop(self) -> None:
        if self._producer is not None:
            self._producer.flush(5)
