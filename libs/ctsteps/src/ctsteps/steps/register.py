"""register — a candidate becomes a versioned, servable artefact.

The registry assigns the version number; the artefact is copied to the
serving layout `s3://models/<use_case>/<model>/v<N>/model.joblib` and the
version is tagged with that URI (the lineage link registry -> serving) and
aliased `challenger` until promote decides.
"""

from __future__ import annotations

import mlflow
from mlflow import MlflowClient

from ctsteps import io_s3, registry, result
from ctsteps.steps.common import Context


def run(ctx: Context, *, mlflow_run_id: str) -> dict:
    registry.setup(ctx.settings.mlflow_tracking_uri, ctx.use_case.name, ctx.spec.name)
    client = MlflowClient()
    name = registry.registered_name(ctx.use_case.name, ctx.spec.name)
    mv = mlflow.register_model(f"runs:/{mlflow_run_id}/model", name)
    serving_dir = ctx.serving_uri(mv.version)
    artefact = io_s3.get_bytes(ctx.s3, ctx.dataset_uri("model.joblib"))
    io_s3.put_bytes(ctx.s3, f"{serving_dir}/model.joblib", artefact)
    run_tags = client.get_run(mlflow_run_id).data.tags
    for k, v in {
        "serving_uri": serving_dir,
        "pipeline_run": ctx.run_id,
        "data_hash": run_tags.get("data_hash", ""),
        "git_commit": run_tags.get("git_commit", ""),
        "reference_uri": run_tags.get("reference_uri", ""),
    }.items():
        client.set_model_version_tag(name, mv.version, k, v)
    client.set_registered_model_alias(name, registry.CHALLENGER, mv.version)
    return result.write(
        ctx.settings.outputs_dir,
        registered_name=name,
        version=int(mv.version),
        serving_uri=serving_dir,
    )
