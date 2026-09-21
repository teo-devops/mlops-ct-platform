"""Synthetic deliveries of Delivery ETA: what a courier marketplace's data platform would deliver.

`generate(seed, rows, profile)` returns one frame with the features and the target. `profile`
is "what the world delivers now": `None` = normal operations, `strike` = a transport strike —
longer distances (riders re-routed), evening peaks, a different zone mix — the drift the monitor
must notice and the retrained model must fit.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ZONES = ("north", "south", "east", "west")
ZONE_MINUTES = {"north": 4.0, "south": 9.0, "east": 6.0, "west": 12.0}  # base handling per zone


def generate(seed: int = 42, rows: int = 6000, profile: str | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    strike = profile == "strike"
    distance_km = rng.lognormal(mean=1.2 if not strike else 1.7, sigma=0.5, size=rows).clip(0.3, 40)
    weight_kg = rng.lognormal(mean=0.2, sigma=0.7, size=rows).clip(0.1, 30)
    hour = rng.choice(
        24,
        size=rows,
        p=_hour_profile(evening_shift=strike),
    )
    zone = rng.choice(
        ZONES, size=rows, p=[0.35, 0.3, 0.2, 0.15] if not strike else [0.15, 0.2, 0.25, 0.4]
    )
    peak = np.isin(hour, (12, 13, 14, 19, 20, 21)).astype(float)
    eta = (
        np.array([ZONE_MINUTES[z] for z in zone])
        + 3.1 * distance_km
        + 0.9 * weight_kg
        + 8.0 * peak
        + (6.0 if strike else 0.0)
        + rng.normal(0, 2.5, rows)
    )
    return pd.DataFrame(
        {
            "distance_km": distance_km.round(2),
            "weight_kg": weight_kg.round(2),
            "hour": hour.astype(int),
            "zone": zone,
            "eta_minutes": eta.clip(3, None).round(1),
        }
    )


def _hour_profile(*, evening_shift: bool) -> np.ndarray:
    base = np.ones(24)
    base[11:15] = 3.0  # lunch
    base[18:22] = 4.0 if not evening_shift else 9.0  # dinner (a strike piles orders here)
    base[0:7] = 0.2
    return base / base.sum()
