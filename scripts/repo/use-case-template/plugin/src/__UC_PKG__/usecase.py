"""The `UseCase` of __UC_TITLE__: what the platform's steps call.

Four methods (docs/design/contracts.md): `ingest` (raw frame), `schema` (data-quality gate),
`build_model` (an unfitted scikit-learn estimator — built-ins only: the serving runtime
unpickles it), `evaluate` (metrics, must include every ModelSpec.primary_metric).
Everything else — split, training, gate, registry, promotion, drift — is the platform's.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pandas as pd
from sklearn.compose import ColumnTransformer

__ESTIMATOR_IMPORT__
from sklearn.metrics import __METRIC_IMPORTS__
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ctsteps.contracts import ColumnCheck, ModelSpec

from __UC_PKG__ import data

FEATURES = ("x1", "x2", "x3", "zone")


def _features() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("num", StandardScaler(), ["x1", "x2", "x3"]),
            ("zone", OneHotEncoder(handle_unknown="ignore"), ["zone"]),
        ]
    )


class __UC_CLASS__:
    name = "__UC__"
    models: ClassVar[dict[str, ModelSpec]] = {__MODELS_SPECS__}

    def ingest(self, model: str, *, profile: str | None, seed: int, rows: int) -> pd.DataFrame:
        return data.generate(seed=seed, rows=rows, profile=profile)

    def schema(self, model: str) -> dict[str, ColumnCheck]:
        return {
            "x1": ColumnCheck(dtype="number"),
            "x2": ColumnCheck(dtype="number", min=0),
            "x3": ColumnCheck(dtype="number", min=0, max=1),
            "zone": ColumnCheck(dtype="string", allowed=data.ZONES),
            self.models[model].target: ColumnCheck(dtype="__TARGET_DTYPE__"),
        }

    def build_model(self, model: str) -> Any:
        return Pipeline([("features", _features()), ("est", __ESTIMATOR__)])

    def evaluate(self, model: str, estimator: Any, df: pd.DataFrame) -> dict[str, float]:
        x, y = df[list(FEATURES)], df[self.models[model].target]
        pred = estimator.predict(x)
        return __EVALUATE_EXPR__


use_case = __UC_CLASS__()
