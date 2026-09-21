"""EventBus: off by default, and with a fake producer the record reaches the topic keyed by model."""

from __future__ import annotations

import json

from app.event_bus import EventBus


class FakeProducer:
    def __init__(self, conf):
        self.conf, self.sent, self.flushed = conf, [], False

    def produce(self, topic, key, value, on_delivery):
        self.sent.append((topic, key, json.loads(value)))
        on_delivery(None, type("M", (), {"key": lambda self: key})())

    def poll(self, t):
        return 0

    def flush(self, t):
        self.flushed = True


def test_disabled_without_bootstrap():
    bus = EventBus(bootstrap="", topic="predictions", use_case="uc")
    assert bus.enabled is False
    bus.record("categorizer", {"x": 1})  # no-op
    bus.stop()


def test_record_is_published_keyed_by_model():
    holder = {}

    def factory(conf):
        holder["p"] = FakeProducer(conf)
        return holder["p"]

    bus = EventBus(bootstrap="b:9093", topic="predictions", use_case="uc", producer_factory=factory)
    bus.record("fraud", {"model": "fraud", "prediction": True})
    bus.stop()
    p = holder["p"]
    assert p.conf["bootstrap.servers"] == "b:9093" and p.conf["client.id"] == "uc-api"
    assert p.sent == [("predictions", b"fraud", {"model": "fraud", "prediction": True})]
    assert p.flushed


def test_producer_failure_never_raises():
    class Broken(FakeProducer):
        def produce(self, *a, **k):
            raise RuntimeError("broker down")

    bus = EventBus(bootstrap="b:9093", topic="t", use_case="uc", producer_factory=Broken)
    bus.record("categorizer", {"x": 1})  # counted, logged, swallowed
