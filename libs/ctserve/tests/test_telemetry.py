"""Telemetry.from_env: off by default; every active sink receives the record."""

from __future__ import annotations

from ctserve.telemetry import Telemetry


def test_from_env_defaults_to_no_sinks(monkeypatch):
    for k in ("CT_PREDICTION_LOG_ENABLED", "CT_EVENT_BUS_BOOTSTRAP"):
        monkeypatch.delenv(k, raising=False)
    t = Telemetry.from_env("uc")
    assert t.sinks == []
    t.start()
    t.emit("m", {"x": 1})  # no-op everywhere
    t.stop()


def test_emit_reaches_every_sink():
    class Sink:
        def __init__(self):
            self.enabled, self.got = True, []

        def record(self, model, record):
            self.got.append((model, record))

        def start(self):
            pass

        def stop(self):
            pass

    log, bus = Sink(), Sink()
    t = Telemetry(prediction_log=log, event_bus=bus)
    t.emit("fraud", {"prediction": True})
    assert log.got == bus.got == [("fraud", {"prediction": True})]
    assert t.sinks == ["s3", "kafka"]
