"""Configuration, all from the environment (the chart's ConfigMap)."""

from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ALE_", env_file=None)

    # The platform contract (chart ConfigMap, docs/design/contracts.md): the use
    # case's name and, per model, the predictor endpoint and the version served.
    use_case: str = Field(
        "automated-listing-engine",
        validation_alias=AliasChoices("CT_USE_CASE_NAME", "ALE_USE_CASE"),
    )
    git_commit: str = "unknown"
    categorizer_url: str = Field(
        "http://categorizer-predictor.automated-listing-engine-serving.svc.cluster.local/v1/models/categorizer:predict",
        validation_alias=AliasChoices("CT_MODEL_CATEGORIZER_URL", "ALE_CATEGORIZER_URL"),
    )
    fraud_url: str = Field(
        "http://fraud-predictor.automated-listing-engine-serving.svc.cluster.local/v1/models/fraud:predict",
        validation_alias=AliasChoices("CT_MODEL_FRAUD_URL", "ALE_FRAUD_URL"),
    )
    categorizer_version: str = Field(
        "0",
        validation_alias=AliasChoices("CT_MODEL_CATEGORIZER_VERSION", "ALE_CATEGORIZER_VERSION"),
    )
    fraud_version: str = Field(
        "0", validation_alias=AliasChoices("CT_MODEL_FRAUD_VERSION", "ALE_FRAUD_VERSION")
    )
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

    # Where predictions are logged (S3 log, event bus) is NOT here: ctserve.Telemetry
    # reads the platform's CT_* / S3_ENDPOINT_URL variables set by the chart.


settings = Settings()
