"""train — fit the estimator and record the run.

Params, metrics, lineage tags (data hash, pipeline run, git commit, trigger)
and the model go to the registry; the fitted artefact also lands next to the
data as `model.joblib`, so evaluate/register do not depend on MLflow artifact
proxying.
"""

from __future__ import annotations

import os
import time

import mlflow

from ctsteps import io_s3, registry, result
from ctsteps.steps.common import Context, data_hash


def run(ctx: Context, *, trigger: str) -> dict:
    train = io_s3.get_parquet(ctx.s3, ctx.dataset_uri("train.parquet"))
    features = list(ctx.spec.features)
    X, y = train[features], train[ctx.spec.target]

    registry.setup(ctx.settings.mlflow_tracking_uri, ctx.use_case.name, ctx.spec.name)
    with mlflow.start_run(run_name=f"{ctx.run_id}") as mlrun:
        estimator = ctx.use_case.build_model(ctx.spec.name)
        t0 = time.time()
        estimator.fit(X, y)
        fit_seconds = time.time() - t0

        train_metrics = ctx.use_case.evaluate(ctx.spec.name, estimator, train)
        mlflow.log_params(
            {
                "use_case": ctx.use_case.name,
                "model": ctx.spec.name,
                "pipeline_run": ctx.run_id,
                "trigger": trigger,
                "train_rows": len(train),
                "features": ",".join(features),
            }
        )
        mlflow.log_metrics({f"train_{k}": v for k, v in train_metrics.items()})
        mlflow.log_metric("fit_seconds", fit_seconds)
        mlflow.set_tags(
            {
                "data_hash": data_hash(train),
                "git_commit": os.environ.get("CT_GIT_COMMIT", "unknown"),
                "reference_uri": ctx.dataset_uri("reference.parquet"),
                "holdout_uri": ctx.dataset_uri("holdout.parquet"),
                "train_uri": ctx.dataset_uri("train.parquet"),
                **ctx.spec.tags,
            }
        )
        # Plain pickle: MLflow 3 defaults to skops, which refuses ColumnTransformer
        # internals. The registry copy is for lineage/UI; serving reads the joblib.
        mlflow.sklearn.log_model(
            estimator, name="model", serialization_format=mlflow.sklearn.SERIALIZATION_FORMAT_PICKLE
        )
        candidate_uri = io_s3.put_joblib(ctx.s3, ctx.dataset_uri("model.joblib"), estimator)

    return result.write(
        ctx.settings.outputs_dir,
        mlflow_run_id=mlrun.info.run_id,
        candidate_uri=candidate_uri,
        fit_seconds=round(fit_seconds, 2),
        **{f"train_{k}": round(v, 4) for k, v in train_metrics.items()},
    )
