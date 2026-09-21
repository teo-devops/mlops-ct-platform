"""Request/response of __UC_TITLE__ — REPLACE `Features` with the real request."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Features(BaseModel):
    """One instance: the model's feature columns (usecase.py FEATURES)."""

    x1: float
    x2: float = Field(ge=0)
    x3: float = Field(ge=0, le=1)
    zone: str


class Prediction(BaseModel):
    value: float | list[float]
    model_version: str
    source: str = "model"


class Lineage(BaseModel):
    use_case: str
    api_version: str
    git_commit: str
    request_id: str


class Response(BaseModel):
    predictions: dict[str, Prediction]
    lineage: Lineage
    timings_ms: dict[str, float]
