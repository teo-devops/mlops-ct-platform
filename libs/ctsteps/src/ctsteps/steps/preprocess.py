"""preprocess — split and freeze the reference.

train / holdout split, plus `reference.parquet`: the feature distribution the
drift monitor will compare live traffic against. Freezing it here, next to the
data that trained the model, is what makes "drift" a precise question.
"""

from __future__ import annotations

from sklearn.model_selection import train_test_split

from ctsteps import io_s3, result
from ctsteps.steps.common import Context


def run(ctx: Context, *, holdout_ratio: float, seed: int, reference_rows: int) -> dict:
    df = io_s3.get_parquet(ctx.s3, ctx.dataset_uri("raw.parquet"))
    stratify = df[ctx.spec.target] if df[ctx.spec.target].nunique() > 1 else None
    train, holdout = train_test_split(
        df, test_size=holdout_ratio, random_state=seed, stratify=stratify
    )
    reference = train.sample(n=min(reference_rows, len(train)), random_state=seed)
    return result.write(
        ctx.settings.outputs_dir,
        train_uri=io_s3.put_parquet(ctx.s3, ctx.dataset_uri("train.parquet"), train),
        holdout_uri=io_s3.put_parquet(ctx.s3, ctx.dataset_uri("holdout.parquet"), holdout),
        reference_uri=io_s3.put_parquet(ctx.s3, ctx.dataset_uri("reference.parquet"), reference),
        train_rows=len(train),
        holdout_rows=len(holdout),
    )
