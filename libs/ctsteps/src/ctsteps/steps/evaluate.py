"""evaluate — the champion/challenger gate.

The candidate and the current champion are both replayed on the same
labelled holdout; the candidate is promoted only if it beats the champion on
the primary metric (by `min_improvement`), or if there is no champion yet.

This replay on held-out data is what replaces A/B testing when every item is
served once (non-replenishable inventory): you cannot show two models the
same listing, but you can show both models the same history.
"""

from __future__ import annotations

import mlflow
from mlflow import MlflowClient

from ctsteps import io_s3, registry, result
from ctsteps.steps.common import Context


def decide(spec, candidate: float, champion: float | None) -> tuple[bool, str]:
    if champion is None:
        return True, "no champion yet"
    delta = candidate - champion if spec.higher_is_better else champion - candidate
    if delta > spec.min_improvement:
        return True, f"{spec.primary_metric} improved by {delta:.4f}"
    return (
        False,
        f"{spec.primary_metric} did not improve ({delta:+.4f}, need > {spec.min_improvement})",
    )


def run(ctx: Context, *, mlflow_run_id: str) -> dict:
    holdout = io_s3.get_parquet(ctx.s3, ctx.dataset_uri("holdout.parquet"))
    candidate = io_s3.get_joblib(ctx.s3, ctx.dataset_uri("model.joblib"))
    cand_metrics = ctx.use_case.evaluate(ctx.spec.name, candidate, holdout)

    registry.setup(ctx.settings.mlflow_tracking_uri, ctx.use_case.name, ctx.spec.name)
    client = MlflowClient()
    name = registry.registered_name(ctx.use_case.name, ctx.spec.name)
    champ = registry.champion_version(client, name)
    champ_metrics: dict[str, float] | None = None
    if champ is not None:
        champ_uri = champ.tags.get("serving_uri")
        estimator = (
            io_s3.get_joblib(ctx.s3, f"{champ_uri}/model.joblib")
            if champ_uri
            else mlflow.sklearn.load_model(f"models:/{name}@{registry.CHAMPION}")
        )
        champ_metrics = ctx.use_case.evaluate(ctx.spec.name, estimator, holdout)

    promote, reason = decide(
        ctx.spec,
        cand_metrics[ctx.spec.primary_metric],
        champ_metrics[ctx.spec.primary_metric] if champ_metrics else None,
    )
    with mlflow.start_run(run_id=mlflow_run_id):
        mlflow.log_metrics({f"holdout_{k}": v for k, v in cand_metrics.items()})
        if champ_metrics:
            mlflow.log_metrics({f"champion_holdout_{k}": v for k, v in champ_metrics.items()})
        mlflow.set_tags(
            {
                "gate.promote": str(promote).lower(),
                "gate.reason": reason,
                "gate.champion_version": champ.version if champ else "none",
            }
        )

    return result.write(
        ctx.settings.outputs_dir,
        promote=promote,
        reason=reason,
        primary_metric=ctx.spec.primary_metric,
        candidate=round(cand_metrics[ctx.spec.primary_metric], 4),
        champion=round(champ_metrics[ctx.spec.primary_metric], 4) if champ_metrics else None,
        champion_version=int(champ.version) if champ else None,
        candidate_metrics=cand_metrics,
        champion_metrics=champ_metrics,
    )
