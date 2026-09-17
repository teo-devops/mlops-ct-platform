"""The contracts a use case and the platform agree on.

A use case plugs into the platform by implementing `UseCase`. Everything the
pipeline needs to know about a model — how to get data, what the data must
look like, how to build and score the estimator, which columns to watch for
drift — comes from here. The steps themselves never contain use-case logic.
"""

from __future__ import annotations

import importlib
import os
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import pandas as pd


@dataclass(frozen=True)
class ColumnCheck:
    """A data-quality check on one column (the `validate` gate)."""

    dtype: str  # "string" | "number" | "int" | "bool"
    required: bool = True
    min: float | None = None
    max: float | None = None
    max_null_ratio: float = 0.0
    allowed: tuple[str, ...] | None = None


@dataclass(frozen=True)
class ModelSpec:
    """What the pipeline needs to know about one model of a use case."""

    name: str
    target: str
    features: tuple[str, ...]
    primary_metric: str
    higher_is_better: bool = True
    # Columns the drift monitor compares between the training reference and
    # live predictions. The prediction column is always compared too.
    drift_columns: tuple[str, ...] = ()
    # Minimum improvement of the primary metric for a challenger to replace
    # the champion (absolute). 0 = any improvement.
    min_improvement: float = 0.0
    # Extra info surfaced in the registry (description, owner...).
    tags: dict[str, str] = field(default_factory=dict)


@runtime_checkable
class UseCase(Protocol):
    """A use case = data + schema + estimator + metrics, per model."""

    name: str
    models: dict[str, ModelSpec]

    def ingest(self, model: str, *, profile: str | None, seed: int, rows: int) -> pd.DataFrame:
        """Return the raw dataset (features + target) for `model`.

        `profile` lets a use case return a variant of its data (the demo uses
        `drift` to simulate a changed world); `None` is the normal path.
        """
        ...

    def schema(self, model: str) -> dict[str, ColumnCheck]:
        """Column checks enforced by the `validate` gate."""
        ...

    def build_model(self, model: str) -> Any:
        """An unfitted scikit-learn estimator/pipeline.

        Only scikit-learn built-ins: the artefact is unpickled by a generic
        serving runtime that does not have the use-case package installed.
        """
        ...

    def evaluate(self, model: str, estimator: Any, df: pd.DataFrame) -> dict[str, float]:
        """Metrics of a fitted estimator on a labelled frame (must include primary_metric)."""
        ...


def load_use_case(ref: str | None = None) -> UseCase:
    """Load the use-case plugin from `module:attribute` (default env CT_USE_CASE)."""
    ref = ref or os.environ.get("CT_USE_CASE")
    if not ref:
        raise SystemExit("no use case: pass --use-case module:attr or set CT_USE_CASE")
    module_name, _, attr = ref.partition(":")
    module = importlib.import_module(module_name)
    obj = getattr(module, attr or "use_case")
    use_case = obj() if callable(obj) and not isinstance(obj, UseCase) else obj
    if not isinstance(use_case, UseCase):
        raise SystemExit(f"{ref} does not implement ctsteps.contracts.UseCase")
    return use_case
