"""Request/response of Delivery ETA."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DeliveryIn(BaseModel):
    """One order about to be promised an ETA (the model's feature columns)."""

    distance_km: float = Field(gt=0, le=100)
    weight_kg: float = Field(gt=0, le=50)
    hour: int = Field(ge=0, le=23)
    zone: Literal["north", "south", "east", "west"]


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
