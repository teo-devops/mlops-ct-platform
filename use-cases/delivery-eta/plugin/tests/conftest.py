"""The platform's step harness (moto S3 + sqlite MLflow) pointed at this plugin."""

from __future__ import annotations

import boto3
import pytest
from moto import mock_aws


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("S3_ENDPOINT_URL", raising=False)
    monkeypatch.setenv("CT_OUTPUTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/mlflow.db")
    monkeypatch.setenv("MLFLOW_DISABLE_AGENT_HINT", "1")
    monkeypatch.setenv("CT_USE_CASE", "delivery_eta:use_case")
    for k, b in (
        ("CT_DATASETS_BUCKET", "datasets"),
        ("CT_MODELS_BUCKET", "models"),
        ("CT_PREDICTIONS_BUCKET", "predictions"),
    ):
        monkeypatch.setenv(k, b)
    monkeypatch.chdir(tmp_path)
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        for b in ("datasets", "models", "predictions"):
            s3.create_bucket(Bucket=b)
        yield tmp_path
