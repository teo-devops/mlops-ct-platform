"""Configuration, all from the environment (the chart's ConfigMap)."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LE_", env_file=None)

    use_case: str = "listing-engine"
    git_commit: str = "unknown"

    # serving contract: one InferenceService per model, KServe v1 protocol
    categorizer_url: str = "http://categorizer-predictor.listing-engine-serving.svc.cluster.local/v1/models/categorizer:predict"
    fraud_url: str = (
        "http://fraud-predictor.listing-engine-serving.svc.cluster.local/v1/models/fraud:predict"
    )
    categorizer_version: str = "0"
    fraud_version: str = "0"
    # class order of the categorizer's predict_proba (scikit-learn sorts classes)
    categorizer_labels: list[str] = Field(
        default=["books", "electronics", "fashion", "home", "kids", "sports"]
    )

    # latency budgets (seconds); the fraud check is the one allowed to degrade
    categorizer_timeout: float = 0.8
    fraud_timeout: float = 0.3
    fraud_threshold: float = 0.5

    # circuit breaker on the fraud model
    breaker_failure_threshold: int = 5
    breaker_reset_seconds: float = 30.0

    # rules-based fallback
    fallback_price_floor: float = 1.0
    fallback_ratio_below_median: float = 0.15
    fallback_medians: dict[str, float] = Field(
        default={
            "electronics": 350.0,
            "fashion": 40.0,
            "home": 90.0,
            "sports": 120.0,
            "books": 12.0,
            "kids": 45.0,
        }
    )
    fallback_keywords: list[str] = Field(
        default=[
            "urgent",
            "whatsapp",
            "western union",
            "paypal friends",
            "shipping only",
            "deposit first",
        ]
    )

    # prediction log (artifact-store contract) — the input of the drift monitor
    prediction_log_enabled: bool = False
    prediction_log_bucket: str = "predictions"
    prediction_log_flush_seconds: float = 10.0
    prediction_log_flush_records: int = 200
    s3_endpoint_url: str = ""


settings = Settings()
