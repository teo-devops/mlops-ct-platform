"""The serving contract as seen by an API: one predictor endpoint per model, and its version.

The use case's api chart writes, for every model it declares, `CT_MODEL_<NAME>_URL` (the KServe v1
predict endpoint) and `CT_MODEL_<NAME>_VERSION` (the version served, bumped by `ctsteps promote`).
An API reads them here and never hardcodes a hostname.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

_KEY = re.compile(r"^CT_MODEL_([A-Z0-9_]+)_URL$")


@dataclass(frozen=True)
class ModelEndpoint:
    name: str
    url: str
    version: str


def models_from_env(environ: dict[str, str] | None = None) -> dict[str, ModelEndpoint]:
    """`{model: ModelEndpoint}` from the environment; model names come back lower-case, dashed."""
    env = os.environ if environ is None else environ
    out: dict[str, ModelEndpoint] = {}
    for key, url in env.items():
        m = _KEY.match(key)
        if not m:
            continue
        name = m.group(1).lower().replace("_", "-")
        version = env.get(f"CT_MODEL_{m.group(1)}_VERSION", "0")
        out[name] = ModelEndpoint(name=name, url=url, version=version)
    return out
