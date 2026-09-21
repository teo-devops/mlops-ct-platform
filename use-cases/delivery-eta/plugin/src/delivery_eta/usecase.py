"""The `UseCase` of Delivery ETA: what the platform's steps call.

One regression model, `eta`: minutes from order to door, from the distance, the parcel weight,
the hour and the zone. Four methods (docs/design/contracts.md); everything else — split,
training, gate, registry, promotion, drift — is the platform's.
"""

from __future__ import annotations

from typing import Any, ClassVar

import pandas as pd
from ctsteps.contracts import ColumnCheck, ModelSpec
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from delivery_eta import data

FEATURES = ("distance_km", "weight_kg", "hour", "zone")


def _features() -> ColumnTransformer:
    return ColumnTransformer(
        [
            ("num", StandardScaler(), ["distance_km", "weight_kg", "hour"]),
            ("zone", OneHotEncoder(handle_unknown="ignore"), ["zone"]),
        ]
    )


class DeliveryEta:
    name = "delivery-eta"
    models: ClassVar[dict[str, ModelSpec]] = {
        "eta": ModelSpec(
            name="eta",
            target="eta_minutes",
            features=FEATURES,
            primary_metric="mae",
            higher_is_better=False,
            drift_columns=("distance_km", "hour", "weight_kg"),
            min_improvement=0.0,
            tags={"description": "Minutes from order to door"},
        ),
    }

    def ingest(self, model: str, *, profile: str | None, seed: int, rows: int) -> pd.DataFrame:
        return data.generate(seed=seed, rows=rows, profile=profile)

    def schema(self, model: str) -> dict[str, ColumnCheck]:
        return {
            "distance_km": ColumnCheck(dtype="number", min=0.1, max=100),
            "weight_kg": ColumnCheck(dtype="number", min=0.01, max=50),
            "hour": ColumnCheck(dtype="int", min=0, max=23),
            "zone": ColumnCheck(dtype="string", allowed=data.ZONES),
            "eta_minutes": ColumnCheck(dtype="number", min=1),
        }

    def build_model(self, model: str) -> Any:
        return Pipeline(
            [("features", _features()), ("est", HistGradientBoostingRegressor(max_iter=200))]
        )

    def evaluate(self, model: str, estimator: Any, df: pd.DataFrame) -> dict[str, float]:
        x, y = df[list(FEATURES)], df[self.models[model].target]
        pred = estimator.predict(x)
        return {
            "mae": float(mean_absolute_error(y, pred)),
            "rmse": float(root_mean_squared_error(y, pred)),
            "r2": float(r2_score(y, pred)),
        }


use_case = DeliveryEta()
