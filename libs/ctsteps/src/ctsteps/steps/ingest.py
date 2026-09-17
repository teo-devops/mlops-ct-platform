"""ingest — bring the raw dataset into the artifact store.

In a real platform this is where the ETL/orchestrator hands over a versioned
partition (Airflow DAG, feature store snapshot). The use case decides the
source; the step only fixes where it lands and records its hash.
"""

from __future__ import annotations

from ctsteps import io_s3, result
from ctsteps.steps.common import Context, data_hash


def run(ctx: Context, *, profile: str | None, seed: int, rows: int) -> dict:
    df = ctx.use_case.ingest(ctx.spec.name, profile=profile, seed=seed, rows=rows)
    uri = io_s3.put_parquet(ctx.s3, ctx.dataset_uri("raw.parquet"), df)
    return result.write(
        ctx.settings.outputs_dir,
        raw_uri=uri,
        rows=len(df),
        columns=list(df.columns),
        data_hash=data_hash(df),
        profile=profile or "default",
    )
