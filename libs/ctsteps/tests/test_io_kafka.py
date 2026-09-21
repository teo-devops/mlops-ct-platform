"""io_kafka.read_window against a fake consumer: offsets by time, watermark, model filter."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from confluent_kafka import TopicPartition

from ctsteps import io_kafka


class _Msg:
    def __init__(self, partition: int, offset: int, value: dict):
        self._p, self._o, self._v = partition, offset, json.dumps(value).encode()

    def error(self):
        return None

    def value(self):
        return self._v

    def offset(self):
        return self._o

    def partition(self):
        return self._p


class _Meta:
    def __init__(self, topic: str, partitions: list[int]):
        self.topics = {topic: type("T", (), {"partitions": {p: None for p in partitions}})()}


class FakeConsumer:
    """Two partitions; `since` lands at offset 1 of p0 and after the end of p1."""

    def __init__(self, conf):
        self.conf = conf
        self.closed = False
        self._queue = [
            _Msg(0, 1, {"model": "categorizer", "price": 10}),
            _Msg(0, 2, {"model": "fraud", "price": 11}),
            _Msg(0, 3, {"model": "categorizer", "price": 12}),
        ]

    def list_topics(self, topic, timeout):
        return _Meta(topic, [0, 1])

    def offsets_for_times(self, tps, timeout):
        out = []
        for tp in tps:
            out.append(TopicPartition(tp.topic, tp.partition, 1 if tp.partition == 0 else -1))
        return out

    def get_watermark_offsets(self, tp):
        return (0, 4) if tp.partition == 0 else (0, 2)

    def assign(self, tps):
        self.assigned = [(tp.partition, tp.offset) for tp in tps]

    def poll(self, timeout):
        return self._queue.pop(0) if self._queue else None

    def close(self):
        self.closed = True


def test_read_window_reads_up_to_the_watermark_and_filters_by_model():
    holder = {}

    def factory(conf):
        holder["c"] = FakeConsumer(conf)
        return holder["c"]

    since = datetime.now(UTC) - timedelta(minutes=30)
    df = io_kafka.read_window(
        "broker:9093", "predictions", since, model="categorizer", consumer_factory=factory
    )
    c = holder["c"]
    assert c.assigned == [(0, 1)]  # partition 1 has nothing after `since`
    assert c.conf["enable.auto.commit"] is False and c.closed
    assert list(df["price"]) == [10, 12]


def test_read_window_empty_when_nothing_after_since():
    class Quiet(FakeConsumer):
        def offsets_for_times(self, tps, timeout):
            return [TopicPartition(tp.topic, tp.partition, -1) for tp in tps]

    since = datetime.now(UTC)
    df = io_kafka.read_window("b:9093", "predictions", since, consumer_factory=Quiet)
    assert df.empty
