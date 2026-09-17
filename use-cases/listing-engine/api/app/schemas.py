from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class ListingIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    price: float = Field(gt=0, le=1_000_000)
    image_url: HttpUrl | None = None


class Category(BaseModel):
    label: str
    confidence: float
    source: str  # model
    model_version: str


class Fraud(BaseModel):
    is_suspicious: bool
    score: float
    source: str  # model | fallback
    model_version: str
    reasons: list[str] = []


class Lineage(BaseModel):
    use_case: str
    api_version: str
    git_commit: str
    request_id: str


class Analysis(BaseModel):
    listing: dict
    category: Category
    fraud: Fraud
    lineage: Lineage
    timings_ms: dict[str, float]
