"""A minimal use case + fake artifact store/registry for the step tests."""

from __future__ import annotations

import boto3
import numpy as np
import pandas as pd
import pytest
from moto import mock_aws
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ctsteps.contracts import ColumnCheck, ModelSpec


class ToyUseCase:
    name = "toy"
    models: ClassVar[dict[str, ModelSpec]] = {
        "colour": ModelSpec(
            name="colour",
            target="colour",
            features=("text", "size"),
            primary_metric="f1_macro",
            drift_columns=("size",),
        )
    }

    def ingest(self, model, *, profile, seed, rows):
        rng = np.random.default_rng(seed)
        colour = rng.choice(["red", "blue"], rows)
        words = {"red": ["apple", "cherry", "fire"], "blue": ["sky", "sea", "ink"]}
        text = [f"{rng.choice(words[c])} {rng.choice(words[c])}" for c in colour]
        size = np.where(colour == "red", rng.normal(10, 2, rows), rng.normal(20, 2, rows))
        if profile == "drift":
            size = size * 3
        return pd.DataFrame({"text": text, "size": size, "colour": colour})

    def schema(self, model):
        return {
            "text": ColumnCheck(dtype="string"),
            "size": ColumnCheck(dtype="number", min=0),
            "colour": ColumnCheck(dtype="string", allowed=("red", "blue")),
        }

    def build_model(self, model):
        return Pipeline(
            [
                (
                    "features",
                    ColumnTransformer(
                        [
                            ("text", TfidfVectorizer(), "text"),
                            ("size", StandardScaler(), ["size"]),
                        ]
                    ),
                ),
                ("clf", LogisticRegression(max_iter=200)),
            ]
        )

    def evaluate(self, model, estimator, df):
        pred = estimator.predict(df[["text", "size"]])
        return {"f1_macro": float(f1_score(df["colour"], pred, average="macro"))}


use_case = ToyUseCase()


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.delenv("S3_ENDPOINT_URL", raising=False)
    monkeypatch.setenv("CT_OUTPUTS_DIR", str(tmp_path / "outputs"))
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/mlflow.db")
    monkeypatch.setenv("CT_USE_CASE", "conftest:use_case")
    monkeypatch.chdir(tmp_path)
    with mock_aws():
        s3 = boto3.client("s3", region_name="us-east-1")
        for b in ("datasets", "models", "predictions"):
            s3.create_bucket(Bucket=b)
        yield tmp_path
