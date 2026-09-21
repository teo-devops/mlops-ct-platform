"""Prediction log: what the model saw and what it answered, to the artifact store.

This is the model-monitoring input in the demo profile (the event-bus module
is the production alternative: same records, published to Kafka). Records are
buffered and flushed as JSONL objects to
`s3://<bucket>/<use_case>/<model>/<yyyy-mm-dd>/<pod>-<timestamp>.jsonl`.
Losing a buffer on crash is acceptable: the monitor works on windows.
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import defaultdict
from datetime import UTC, datetime

import structlog

from ctserve import metrics

log = structlog.get_logger()


class PredictionLog:
    def __init__(
        self,
        *,
        enabled: bool,
        bucket: str,
        use_case: str,
        endpoint_url: str,
        flush_seconds: float,
        flush_records: int,
    ) -> None:
        self.enabled = enabled
        self.bucket = bucket
        self.use_case = use_case
        self.flush_seconds = flush_seconds
        self.flush_records = flush_records
        self._buffers: dict[str, list[dict]] = defaultdict(list)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._s3 = None
        self._pod = os.environ.get("HOSTNAME", "local")
        if enabled:
            import boto3
            from botocore.config import Config

            self._s3 = boto3.client(
                "s3",
                endpoint_url=endpoint_url or None,
                region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
                config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 2}),
            )

    def start(self) -> None:
        if not self.enabled:
            return
        self._thread = threading.Thread(target=self._loop, name="prediction-log", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        self.flush()

    def record(self, model: str, record: dict) -> None:
        if not self.enabled:
            return
        with self._lock:
            self._buffers[model].append(record)
            full = len(self._buffers[model]) >= self.flush_records
        if full:
            self.flush()

    def _loop(self) -> None:
        while not self._stop.wait(self.flush_seconds):
            self.flush()

    def flush(self) -> None:
        if not self.enabled:
            return
        with self._lock:
            pending = {m: rows for m, rows in self._buffers.items() if rows}
            self._buffers = defaultdict(list)
        for model, rows in pending.items():
            now = datetime.now(UTC)
            key = f"{self.use_case}/{model}/{now:%Y-%m-%d}/{self._pod}-{now:%H%M%S%f}.jsonl"
            body = "\n".join(json.dumps(r, default=str) for r in rows) + "\n"
            try:
                self._s3.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=body.encode(),
                    ContentType="application/x-ndjson",
                )
                metrics.LOG_FLUSHED.labels(self.use_case, model).inc(len(rows))
            except Exception as e:  # noqa: BLE001 — never let monitoring break serving
                metrics.LOG_ERRORS.labels(self.use_case).inc()
                log.warning(
                    "prediction_log_flush_failed", model=model, rows=len(rows), error=str(e)
                )
                time.sleep(0)
