"""Kubeflow Pipelines adapter of the ctsteps contract — REFERENCE, not exercised in the kind demo.

Each step is a container component running the same image; KFP carries the three scalars as
outputs, and `dsl.Condition` implements the gate.
"""

from __future__ import annotations

from kfp import dsl

IMAGE = "automated-listing-engine-steps:0.1.0"


def _step(name: str, extra: list[str], outputs: dict[str, str]) -> dsl.ContainerSpec:
    return dsl.ContainerSpec(
        image=IMAGE,
        command=["sh", "-ec"],
        args=[
            f"ctsteps {name} --model {{{{$.inputs.parameters['model']}}}} --run-id {{{{$.pipeline_job_name}}}} "
            + " ".join(extra)
            + " && "
            + " && ".join(f"cp /tmp/outputs/{k} {v}" for k, v in outputs.items()),
        ],
    )


@dsl.container_component
def train(model: str, trigger: str, mlflow_run_id: dsl.OutputPath(str)):
    return _step("train", [f"--trigger {trigger}"], {"mlflow_run_id": mlflow_run_id})


@dsl.container_component
def evaluate(model: str, mlflow_run_id: str, promote: dsl.OutputPath(str)):
    return _step("evaluate", [f"--mlflow-run-id {mlflow_run_id}"], {"promote": promote})


@dsl.container_component
def register(model: str, mlflow_run_id: str, version: dsl.OutputPath(str)):
    return _step("register", [f"--mlflow-run-id {mlflow_run_id}"], {"version": version})


@dsl.container_component
def promote(model: str, version: str, trigger: str):
    return _step("promote", [f"--version {version} --trigger {trigger}"], {})


@dsl.container_component
def simple(step: str, model: str):
    return _step(step, [], {})


@dsl.pipeline(name="ct-pipeline")
def ct_pipeline(model: str = "categorizer", trigger: str = "manual"):
    # Environment (S3, MLflow, credentials) is injected with kfp-kubernetes
    # (`use_secret_as_env`, `set_env`) exactly as in docs/design/contracts.md.
    i = simple(step="ingest", model=model)
    v = simple(step="validate", model=model).after(i)
    p = simple(step="preprocess", model=model).after(v)
    t = train(model=model, trigger=trigger).after(p)
    e = evaluate(model=model, mlflow_run_id=t.outputs["mlflow_run_id"])
    with dsl.Condition(e.outputs["promote"] == "true", name="gate"):
        r = register(model=model, mlflow_run_id=t.outputs["mlflow_run_id"])
        promote(model=model, version=r.outputs["version"], trigger=trigger)
