"""Configuration, all from the environment (the chart's ConfigMap: `extraEnv` for the
use case's own settings; the platform contract keys are read by ctserve)."""

from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="__UC_PREFIX___", env_file=None)

    use_case: str = Field("__UC__", validation_alias=AliasChoices("CT_USE_CASE_NAME"))
    git_commit: str = "unknown"
    # latency budget per model call (seconds)
    model_timeout: float = 0.8


settings = Settings()
