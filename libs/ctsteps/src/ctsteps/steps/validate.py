"""validate — the data-quality gate.

Schema, types, ranges, null ratios and allowed values, declared by the use
case. A failing gate stops the pipeline: garbage in, no model out. Great
Expectations would be a drop-in implementation of this step (docs/modules/
data-quality.md); the checks here keep the demo dependency-free.
"""

from __future__ import annotations

import pandas as pd

from ctsteps import io_s3, result
from ctsteps.contracts import ColumnCheck
from ctsteps.steps.common import Context


def check_frame(df: pd.DataFrame, schema: dict[str, ColumnCheck]) -> list[str]:
    violations: list[str] = []
    for col, chk in schema.items():
        if col not in df.columns:
            if chk.required:
                violations.append(f"{col}: missing column")
            continue
        s = df[col]
        null_ratio = float(s.isna().mean()) if len(s) else 0.0
        if null_ratio > chk.max_null_ratio:
            violations.append(f"{col}: null ratio {null_ratio:.3f} > {chk.max_null_ratio}")
        values = s.dropna()
        if chk.dtype == "number" and not pd.api.types.is_numeric_dtype(values):
            violations.append(f"{col}: expected number, got {values.dtype}")
        elif chk.dtype == "int" and not pd.api.types.is_integer_dtype(values):
            violations.append(f"{col}: expected int, got {values.dtype}")
        elif chk.dtype == "bool" and not pd.api.types.is_bool_dtype(values):
            violations.append(f"{col}: expected bool, got {values.dtype}")
        elif chk.dtype == "string" and not (
            pd.api.types.is_string_dtype(values) or values.dtype == object
        ):
            violations.append(f"{col}: expected string, got {values.dtype}")
        if (
            chk.min is not None
            and pd.api.types.is_numeric_dtype(values)
            and len(values)
            and values.min() < chk.min
        ):
            violations.append(f"{col}: min {values.min()} < {chk.min}")
        if (
            chk.max is not None
            and pd.api.types.is_numeric_dtype(values)
            and len(values)
            and values.max() > chk.max
        ):
            violations.append(f"{col}: max {values.max()} > {chk.max}")
        if chk.allowed is not None:
            bad = set(values.unique()) - set(chk.allowed)
            if bad:
                violations.append(f"{col}: unexpected values {sorted(map(str, bad))[:5]}")
    return violations


def run(ctx: Context) -> dict:
    df = io_s3.get_parquet(ctx.s3, ctx.dataset_uri("raw.parquet"))
    violations = check_frame(df, ctx.use_case.schema(ctx.spec.name))
    res = result.write(
        ctx.settings.outputs_dir, ok=not violations, violations=violations, rows=len(df)
    )
    if violations:
        raise SystemExit("data-quality gate failed: " + "; ".join(violations))
    return res
