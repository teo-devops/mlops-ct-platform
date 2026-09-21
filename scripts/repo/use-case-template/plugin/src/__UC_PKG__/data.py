"""Synthetic data of __UC_TITLE__ — REPLACE with the real ingest.

The platform only needs `generate(seed, rows, profile)` to return one frame with the
features and the target of every model. `profile` is "what the world delivers now":
`None` = normal, the drift profile (usecase.yaml) = a shifted world the drift monitor
must notice and the retrained model must fit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ZONES = ("north", "south", "east", "west")
TARGETS = __MODELS_TUPLE__  # one target column per model (usecase.py: ModelSpec.target)


def generate(seed: int = 42, rows: int = 6000, profile: str | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    drift = profile == "drift"
    x1 = rng.normal(10 if not drift else 16, 3, rows)
    x2 = rng.lognormal(0.5, 0.4, rows)
    x3 = rng.uniform(0, 1, rows)
    zone = rng.choice(ZONES, rows, p=[0.4, 0.3, 0.2, 0.1] if not drift else [0.1, 0.2, 0.3, 0.4])
    signal = 0.8 * x1 + 2.0 * x2 - 4.0 * x3 + np.where(zone == "north", 1.5, 0.0)
    df = pd.DataFrame({"x1": x1, "x2": x2, "x3": x3, "zone": zone})
    for target in TARGETS:
        noise = rng.normal(0, 1.0, rows)
        df[target] = __TARGET_EXPR__
    return df
