"""The plugin: what the platform needs to know about the Automated Listing Engine models."""

from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import pandas as pd
from ctsteps.contracts import ColumnCheck, ModelSpec
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from automated_listing_engine import data

FEATURES = ("title", "price")


def _features() -> ColumnTransformer:
    # Only scikit-learn built-ins (and numpy ufuncs): the artefact is loaded by
    # a generic sklearn runtime that does not have this package.
    return ColumnTransformer(
        [
            ("title", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True), "title"),
            (
                "price",
                Pipeline([("log", FunctionTransformer(np.log1p)), ("scale", StandardScaler())]),
                ["price"],
            ),
        ]
    )


class AutomatedListingEngine:
    name = "automated-listing-engine"
    models: ClassVar[dict[str, ModelSpec]] = {
        "categorizer": ModelSpec(
            name="categorizer",
            target="category",
            features=FEATURES,
            primary_metric="f1_macro",
            drift_columns=("price", "title_len"),
            min_improvement=0.0,
            tags={"description": "Listing category from title and price"},
        ),
        "fraud": ModelSpec(
            name="fraud",
            target="is_fraud",
            features=FEATURES,
            primary_metric="f1",
            drift_columns=("price", "title_len"),
            min_improvement=0.0,
            tags={"description": "Suspicious listing (counterfeit / price anomaly)"},
        ),
    }

    def ingest(self, model: str, *, profile: str | None, seed: int, rows: int) -> pd.DataFrame:
        df = data.generate(seed=seed, rows=rows, profile=profile)
        # derived column used by the drift monitor (the API logs it too)
        df["title_len"] = df["title"].str.len()
        return df

    def schema(self, model: str) -> dict[str, ColumnCheck]:
        return {
            "title": ColumnCheck(dtype="string"),
            "price": ColumnCheck(dtype="number", min=0.01, max=100_000),
            "title_len": ColumnCheck(dtype="int", min=1),
            "category": ColumnCheck(dtype="string", allowed=data.CATEGORIES),
            "is_fraud": ColumnCheck(dtype="bool"),
        }

    def build_model(self, model: str) -> Any:
        if model == "categorizer":
            clf = LogisticRegression(max_iter=2000, C=3.0)
        else:
            clf = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced")
        return Pipeline([("features", _features()), ("clf", clf)])

    def evaluate(self, model: str, estimator: Any, df: pd.DataFrame) -> dict[str, float]:
        X, y = df[list(FEATURES)], df[self.models[model].target]
        pred = estimator.predict(X)
        if model == "categorizer":
            return {
                "f1_macro": float(f1_score(y, pred, average="macro")),
                "accuracy": float(accuracy_score(y, pred)),
            }
        proba = estimator.predict_proba(X)[:, 1]
        return {
            "f1": float(f1_score(y, pred)),
            "precision": float(precision_score(y, pred, zero_division=0)),
            "recall": float(recall_score(y, pred)),
            "roc_auc": float(roc_auc_score(y, proba)),
        }


use_case = AutomatedListingEngine()
