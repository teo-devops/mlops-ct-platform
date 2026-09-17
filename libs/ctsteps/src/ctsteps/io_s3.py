"""Artifact-store contract: S3 API, URIs `s3://bucket/key`."""

from __future__ import annotations

import io
import json
import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

import boto3
import joblib
import pandas as pd
from botocore.config import Config


def client(endpoint: str | None = None):
    endpoint = endpoint or os.environ.get("S3_ENDPOINT_URL") or None
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"),
        config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 5}),
    )


@dataclass(frozen=True)
class S3Uri:
    bucket: str
    key: str

    @classmethod
    def parse(cls, uri: str) -> S3Uri:
        if not uri.startswith("s3://"):
            raise ValueError(f"not an s3 uri: {uri}")
        bucket, _, key = uri[5:].partition("/")
        return cls(bucket, key)

    def __str__(self) -> str:
        return f"s3://{self.bucket}/{self.key}"


def put_bytes(s3, uri: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    u = S3Uri.parse(uri)
    s3.put_object(Bucket=u.bucket, Key=u.key, Body=data, ContentType=content_type)
    return uri


def get_bytes(s3, uri: str) -> bytes:
    u = S3Uri.parse(uri)
    return s3.get_object(Bucket=u.bucket, Key=u.key)["Body"].read()


def put_parquet(s3, uri: str, df: pd.DataFrame) -> str:
    buf = io.BytesIO()
    df.to_parquet(buf, index=False)
    return put_bytes(s3, uri, buf.getvalue(), "application/vnd.apache.parquet")


def get_parquet(s3, uri: str) -> pd.DataFrame:
    return pd.read_parquet(io.BytesIO(get_bytes(s3, uri)))


def put_json(s3, uri: str, obj) -> str:
    return put_bytes(s3, uri, json.dumps(obj, indent=2, default=str).encode(), "application/json")


def get_json(s3, uri: str):
    return json.loads(get_bytes(s3, uri))


def put_joblib(s3, uri: str, obj) -> str:
    buf = io.BytesIO()
    joblib.dump(obj, buf)
    return put_bytes(s3, uri, buf.getvalue())


def get_joblib(s3, uri: str):
    return joblib.load(io.BytesIO(get_bytes(s3, uri)))


def list_objects(
    s3, uri_prefix: str, newer_than: datetime | None = None
) -> Iterator[tuple[str, datetime]]:
    """Yield (uri, last_modified) under a prefix, optionally only recent ones."""
    u = S3Uri.parse(uri_prefix)
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=u.bucket, Prefix=u.key):
        for obj in page.get("Contents", []):
            ts = obj["LastModified"]
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=UTC)
            if newer_than is None or ts >= newer_than:
                yield f"s3://{u.bucket}/{obj['Key']}", ts


def read_jsonl(s3, uris: list[str]) -> pd.DataFrame:
    rows: list[dict] = []
    for uri in uris:
        for line in get_bytes(s3, uri).decode().splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return pd.DataFrame(rows)
