"""Shared plumbing for the steps."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

import pandas as pd

from ctsteps import io_s3
from ctsteps.config import Settings
from ctsteps.contracts import ModelSpec, UseCase, load_use_case


@dataclass
class Context:
    settings: Settings
    use_case: UseCase
    spec: ModelSpec
    run_id: str
    s3: object

    @classmethod
    def build(cls, use_case_ref: str | None, model: str, run_id: str) -> Context:
        settings = Settings.from_env()
        uc = load_use_case(use_case_ref)
        if model not in uc.models:
            raise SystemExit(f"unknown model {model!r}; use case {uc.name} has {sorted(uc.models)}")
        return cls(settings, uc, uc.models[model], run_id, io_s3.client(settings.s3_endpoint))

    # --- artifact-store layout (the contract every profile honours) --------
    def dataset_uri(self, name: str) -> str:
        s = self.settings
        return (
            f"s3://{s.datasets_bucket}/{self.use_case.name}/{self.spec.name}/{self.run_id}/{name}"
        )

    def serving_uri(self, version: int | str) -> str:
        """Directory the serving layer pulls: one `model.joblib` inside."""
        s = self.settings
        return f"s3://{s.models_bucket}/{self.use_case.name}/{self.spec.name}/v{version}"

    def predictions_prefix(self) -> str:
        s = self.settings
        return f"s3://{s.predictions_bucket}/{self.use_case.name}/{self.spec.name}/"


def data_hash(df: pd.DataFrame) -> str:
    """Stable content hash of a frame (lineage: which data trained the model)."""
    h = hashlib.sha256()
    h.update(pd.util.hash_pandas_object(df, index=False).values.tobytes())
    return h.hexdigest()[:16]
