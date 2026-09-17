"""Step result: the only thing a step hands back to the orchestrator."""

from __future__ import annotations

import json
from pathlib import Path


def write(outputs_dir: Path, **result) -> dict:
    outputs_dir.mkdir(parents=True, exist_ok=True)
    (outputs_dir / "result.json").write_text(json.dumps(result, indent=2, default=str))
    # One file per scalar as well: Argo (and Airflow XCom, KFP) read single
    # values more easily than a JSON document.
    for k, v in result.items():
        if isinstance(v, (str, int, float, bool)):
            (outputs_dir / k).write_text(str(v).lower() if isinstance(v, bool) else str(v))
    print(json.dumps(result, default=str))
    return result
