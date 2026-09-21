"""Event-bus source of the drift monitor: the prediction records read from a Kafka topic.

The record is the same JSON document the prediction log writes to the artifact store
(docs/modules/event-bus.md); only the transport changes. A window is read by timestamp:
`offsets_for_times` on every partition, then consume up to the high watermark. No consumer
group, no commits: the monitor is stateless and windows overlap on purpose.
"""

from __future__ import annotations

import json
from datetime import datetime

import pandas as pd


def read_window(
    bootstrap: str,
    topic: str,
    since: datetime,
    *,
    model: str | None = None,
    poll_seconds: float = 2.0,
    consumer_factory=None,
) -> pd.DataFrame:
    """Records of `topic` produced after `since` (optionally only those of `model`)."""
    if consumer_factory is None:
        from confluent_kafka import Consumer

        consumer_factory = Consumer
    consumer = consumer_factory(
        {
            "bootstrap.servers": bootstrap,
            "group.id": "ct-drift-monitor",  # required by the client, never committed
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )
    try:
        from confluent_kafka import TopicPartition

        meta = consumer.list_topics(topic, timeout=10)
        parts = list(meta.topics[topic].partitions)
        if not parts:
            return pd.DataFrame()
        ts_ms = int(since.timestamp() * 1000)
        starts = consumer.offsets_for_times(
            [TopicPartition(topic, p, ts_ms) for p in parts], timeout=10
        )
        pending = {}
        for tp in starts:
            _, high = consumer.get_watermark_offsets(TopicPartition(topic, tp.partition))
            first = tp.offset if tp.offset >= 0 else high  # -1: nothing after `since`
            if first < high:
                pending[tp.partition] = high
                tp.offset = first
        if not pending:
            return pd.DataFrame()
        consumer.assign([tp for tp in starts if tp.partition in pending])
        rows: list[dict] = []
        while pending:
            msg = consumer.poll(poll_seconds)
            if msg is None:
                break  # quiet topic: whatever arrived is the window
            if msg.error():
                continue
            rows.append(json.loads(msg.value()))
            if msg.offset() + 1 >= pending.get(msg.partition(), 0):
                pending.pop(msg.partition(), None)
    finally:
        consumer.close()
    frame = pd.DataFrame(rows)
    if model and len(frame) and "model" in frame.columns:
        frame = frame[frame["model"] == model].reset_index(drop=True)
    return frame
