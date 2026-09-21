"""Airflow adapter of the ctsteps contract — exercised on kind with the opt-in `airflow` platform
module (chart 1.22.0 / Airflow 3.2.2, docs/modules/airflow.md).

Same containers, same environment, same S3/MLflow layout as the Argo Workflows adapter
(use-cases/<uc>/workloads/pipelines/templates/workflowtemplate.yaml). Airflow passes the three
scalars through XCom (the step writes result.json to /airflow/xcom, the operator's sidecar returns
it) and short-circuits the gate. One DAG per model; each runs weekly (the safety net) and on demand
with `{"trigger": "manual", "profile": ""}` — a drift-triggered run would be a REST call from the
drift monitor (`trigger=drift`), which in the demo still submits Argo Workflows (the gap).

The DAG file is delivered by git-sync from this repository (`dags.gitSync.subPath`).
"""

from __future__ import annotations

from datetime import datetime, timezone

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from airflow.providers.standard.operators.python import ShortCircuitOperator
from kubernetes.client import (
    V1ConfigMapKeySelector,
    V1EnvFromSource,
    V1EnvVar,
    V1EnvVarSource,
    V1ResourceRequirements,
    V1SecretEnvSource,
)

# --- use-case data: the only place this adapter names one ---------------------------------
# Mirrors use-cases/automated-listing-engine/workloads/pipelines/values.yaml.
USE_CASE = "automated-listing-engine"
USE_CASE_REF = "automated_listing_engine:use_case"
NAMESPACE = f"{USE_CASE}-pipelines"
IMAGE = f"{USE_CASE}-steps:0.1.0"
MODELS = ["categorizer", "fraud"]
DATA = {"rows": 6000, "seed": 42, "holdout_ratio": 0.25, "reference_rows": 2000}
PROMOTE_VALUES_FILES = ",".join(
    [
        f"use-cases/{USE_CASE}/workloads/serving/values-demo.yaml",
        f"use-cases/{USE_CASE}/workloads/api/values-demo.yaml",
    ]
)
# --------------------------------------------------------------------------------------------

S3_ENDPOINT = "http://minio.minio.svc.cluster.local:9000"
MLFLOW = "http://mlflow.mlflow.svc.cluster.local"

# The contract variables of libs/ctsteps (docs/design/contracts.md), as in pipelines.stepEnv.
STEP_ENV = [
    V1EnvVar("CT_USE_CASE", USE_CASE_REF),
    V1EnvVar("CT_NAMESPACE", NAMESPACE),
    V1EnvVar("S3_ENDPOINT_URL", S3_ENDPOINT),
    V1EnvVar("MLFLOW_S3_ENDPOINT_URL", S3_ENDPOINT),
    V1EnvVar("AWS_DEFAULT_REGION", "us-east-1"),
    V1EnvVar("CT_DATASETS_BUCKET", "datasets"),
    V1EnvVar("CT_MODELS_BUCKET", "models"),
    V1EnvVar("CT_PREDICTIONS_BUCKET", "predictions"),
    V1EnvVar("MLFLOW_TRACKING_URI", MLFLOW),
    V1EnvVar("MLFLOW_DISABLE_AGENT_HINT", "1"),
    V1EnvVar(
        "CT_OUTPUTS_DIR", "/airflow/xcom"
    ),  # result.json becomes the XCom return value
    V1EnvVar("CT_GIT_COMMIT", IMAGE.split(":")[-1]),
    V1EnvVar("CT_DATA_PROFILE_OVERRIDE", "{{ params.profile }}"),
    V1EnvVar(
        "CT_DATA_PROFILE",
        value_from=V1EnvVarSource(
            config_map_key_ref=V1ConfigMapKeySelector(
                name="ct-data-source", key="profile", optional=True
            )
        ),
    ),
]
S3_CREDENTIALS = V1EnvFromSource(
    secret_ref=V1SecretEnvSource("pipeline-s3-credentials")
)
GIT_CREDENTIALS = V1EnvFromSource(
    secret_ref=V1SecretEnvSource("pipeline-git-credentials")
)
PROMOTE_ENV = [
    V1EnvVar("GIT_BRANCH", "main"),
    V1EnvVar("CT_PROMOTE_VALUES_FILE", PROMOTE_VALUES_FILES),
    V1EnvVar("GIT_AUTHOR_NAME", "ct-pipeline"),
    V1EnvVar("GIT_AUTHOR_EMAIL", "ct-pipeline@mlops-ct-platform.local"),
]
STEP_RESOURCES = V1ResourceRequirements(
    requests={"cpu": "250m", "memory": "512Mi"}, limits={"cpu": "2", "memory": "2Gi"}
)
PROMOTE_RESOURCES = V1ResourceRequirements(
    requests={"cpu": "100m", "memory": "256Mi"}, limits={"memory": "1Gi"}
)

# --run-id names the dataset folder in S3 and the MLflow run, like {{workflow.name}} in Argo.
RUN_ID_SUFFIX = (
    "{{ run_id | replace('__', '-') | replace('_', '-') | replace(':', '-') | replace('+', '-')"
    " | replace('.', '-') | replace('T', '-') | lower }}"
)


def step(model: str, task_id: str, args: list[str], **kw) -> KubernetesPodOperator:
    """One ctsteps container = one pod in the use case's pipelines namespace."""
    env = kw.pop("env_vars", STEP_ENV)
    env_from = kw.pop("env_from", [S3_CREDENTIALS])
    return KubernetesPodOperator(
        task_id=task_id,
        name=f"ct-{model}-{task_id}",
        namespace=NAMESPACE,
        image=IMAGE,
        image_pull_policy="IfNotPresent",
        cmds=["sh", "-ec"],
        arguments=[
            f"ctsteps {task_id} --model {model} --run-id ct-{model}-airflow-{RUN_ID_SUFFIX} "
            + " ".join(args)
            + " && cp /airflow/xcom/result.json /airflow/xcom/return.json"
        ],
        env_vars=env,
        env_from=env_from,
        container_resources=kw.pop("container_resources", STEP_RESOURCES),
        labels={
            "app.kubernetes.io/part-of": USE_CASE,
            "mlops-ct-platform.dev/use-case": USE_CASE,
            "ct.mlops/use-case": USE_CASE,
            "ct.mlops/model": model,
            "ct.mlops/trigger": "{{ params.trigger }}",
        },
        do_xcom_push=True,
        get_logs=True,
        on_finish_action="delete_succeeded_pod",
        **kw,
    )


def gate(ti) -> bool:
    """The champion/challenger gate: evaluate's `promote` scalar decides whether register/promote run."""
    return bool((ti.xcom_pull(task_ids="evaluate") or {}).get("promote"))


def build(model: str) -> DAG:
    with DAG(
        dag_id=f"ct_pipeline_{model}",
        description=f"Continuous-training pipeline of {USE_CASE}/{model} (ctsteps contract)",
        start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
        schedule="0 3 * * 1",  # weekly safety net; on-demand runs come via the REST API
        catchup=False,
        max_active_runs=1,
        params={"trigger": "cron", "profile": ""},
        tags=["ct", USE_CASE],
    ) as dag:
        ingest = step(model, "ingest", [f"--rows {DATA['rows']} --seed {DATA['seed']}"])
        validate = step(model, "validate", [])
        preprocess = step(
            model,
            "preprocess",
            [
                f"--holdout-ratio {DATA['holdout_ratio']}",
                f"--reference-rows {DATA['reference_rows']}",
                f"--seed {DATA['seed']}",
            ],
        )
        train = step(model, "train", ["--trigger {{ params.trigger }}"])
        mlflow_run_id = "{{ ti.xcom_pull(task_ids='train')['mlflow_run_id'] }}"
        evaluate = step(model, "evaluate", [f"--mlflow-run-id {mlflow_run_id}"])
        passed = ShortCircuitOperator(task_id="gate", python_callable=gate)
        register = step(model, "register", [f"--mlflow-run-id {mlflow_run_id}"])
        promote = step(
            model,
            "promote",
            [
                "--version {{ ti.xcom_pull(task_ids='register')['version'] }}",
                "--trigger {{ params.trigger }}",
            ],
            env_vars=STEP_ENV + PROMOTE_ENV,
            env_from=[S3_CREDENTIALS, GIT_CREDENTIALS],
            container_resources=PROMOTE_RESOURCES,
        )
        (
            ingest
            >> validate
            >> preprocess
            >> train
            >> evaluate
            >> passed
            >> register
            >> promote
        )
    return dag


for _model in MODELS:
    globals()[f"dag_{_model}"] = build(_model)
