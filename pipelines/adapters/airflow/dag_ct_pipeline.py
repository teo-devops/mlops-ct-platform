"""Airflow adapter of the ctsteps contract — REFERENCE, not exercised in the kind demo.

Same containers, same environment, same S3/MLflow layout as the Argo Workflows adapter. Airflow
passes the three scalars through XCom and short-circuits the gate. The DAG id would be triggered
weekly (the safety net) and by a sensor / REST call from the drift monitor (`trigger=drift`).
"""

from __future__ import annotations

import json
from datetime import datetime

from airflow import DAG
from airflow.operators.python import ShortCircuitOperator
from airflow.providers.cncf.kubernetes.operators.pod import KubernetesPodOperator
from kubernetes.client import V1EnvFromSource, V1EnvVar, V1SecretEnvSource

IMAGE = "listing-engine-steps:0.1.0"
NAMESPACE = "listing-engine-pipelines"
MODEL = "categorizer"

ENV = [
    V1EnvVar("CT_USE_CASE", "listing_engine:use_case"),
    V1EnvVar("S3_ENDPOINT_URL", "http://minio.minio.svc.cluster.local:9000"),
    V1EnvVar("MLFLOW_S3_ENDPOINT_URL", "http://minio.minio.svc.cluster.local:9000"),
    V1EnvVar("MLFLOW_TRACKING_URI", "http://mlflow.mlflow.svc.cluster.local"),
    V1EnvVar("AWS_DEFAULT_REGION", "us-east-1"),
    V1EnvVar("CT_OUTPUTS_DIR", "/airflow/xcom"),  # result.json is picked up as the XCom return value
]
ENV_FROM = [V1EnvFromSource(secret_ref=V1SecretEnvSource("pipeline-s3-credentials"))]


def step(task_id: str, args: list[str], **kw) -> KubernetesPodOperator:
    return KubernetesPodOperator(
        task_id=task_id,
        name=f"ct-{MODEL}-{task_id}",
        namespace=NAMESPACE,
        image=IMAGE,
        cmds=["sh", "-ec"],
        arguments=[
            f"ctsteps {task_id} --model {MODEL} --run-id {{{{ run_id | replace(':', '-') | lower }}}} "
            + " ".join(args)
            + " && cp /airflow/xcom/result.json /airflow/xcom/return.json"
        ],
        env_vars=ENV,
        env_from=ENV_FROM,
        do_xcom_push=True,
        service_account_name="argo-workflow",
        **kw,
    )


with DAG(
    dag_id=f"ct_pipeline_{MODEL}",
    start_date=datetime(2026, 1, 1),
    schedule="0 3 * * 1",  # weekly safety net; drift-triggered runs come via the REST API
    catchup=False,
    params={"trigger": "cron", "profile": ""},
) as dag:
    ingest = step("ingest", ["--rows 6000"])
    validate = step("validate", [])
    preprocess = step("preprocess", [])
    train = step("train", ["--trigger {{ params.trigger }}"])
    evaluate = step("evaluate", ["--mlflow-run-id {{ ti.xcom_pull('train')['mlflow_run_id'] }}"])

    def gate(**ctx) -> bool:
        return bool(json.loads(json.dumps(ctx["ti"].xcom_pull("evaluate")))["promote"])

    passed = ShortCircuitOperator(task_id="gate", python_callable=gate)
    register = step("register", ["--mlflow-run-id {{ ti.xcom_pull('train')['mlflow_run_id'] }}"])
    promote = step(
        "promote",
        ["--version {{ ti.xcom_pull('register')['version'] }} --trigger {{ params.trigger }}"],
        env_from=ENV_FROM + [V1EnvFromSource(secret_ref=V1SecretEnvSource("pipeline-git-credentials"))],
    )

    ingest >> validate >> preprocess >> train >> evaluate >> passed >> register >> promote
