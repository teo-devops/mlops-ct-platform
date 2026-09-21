"""Airflow adapter of the ctsteps contract — one continuous-training DAG per use case and model.

Platform code that names no use case: the DAGs are built from what each use case already
declares for its Argo pipelines chart (`use-cases/<name>/workloads/pipelines/values*.yaml`: image,
models, data parameters, contracts, promotion files, event bus) and from where that chart is
deployed (`gitops/environments/<env>/apps/<name>/<name>-pipelines.yaml`, the namespace). Same
containers, same environment, same arguments and resources as the Argo `WorkflowTemplate
ct-pipeline`; XCom carries the three scalars (`result.json` of every step), a `ShortCircuitOperator`
is the gate, `promote` pushes the deployment commit exactly as the Argo path does.

Delivered by git-sync of this repository (`dags.gitSync.subPath: orchestrators/airflow`); the
loader walks up to the repository root. Exercised on kind with the opt-in `airflow` platform
module (chart 1.22.0 / Airflow 3.2.2, docs/modules/airflow.md).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import yaml
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

from airflow import DAG

REPO = Path(__file__).resolve().parents[2]
ENV = "demo"
PROFILE_VALUES = f"values-{ENV}.yaml"

# --run-id names the dataset folder in S3 and the MLflow run, like {{workflow.name}} in Argo.
RUN_ID_SUFFIX = (
    "{{ run_id | replace('__', '-') | replace('_', '-') | replace(':', '-') | replace('+', '-')"
    " | replace('.', '-') | replace('T', '-') | lower }}"
)


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def discover() -> list[dict]:
    """Every use case with a pipelines chart deployed in this environment: its values + namespace."""
    found = []
    for values_file in sorted(REPO.glob("use-cases/*/workloads/pipelines/values.yaml")):
        chart = values_file.parent
        values = yaml.safe_load(values_file.read_text()) or {}
        profile = chart / PROFILE_VALUES
        if profile.exists():
            values = _merge(values, yaml.safe_load(profile.read_text()) or {})
        name = values["useCase"]
        app = REPO / "gitops/environments" / ENV / "apps" / name / f"{name}-pipelines.yaml"
        deployed = yaml.safe_load(
            (REPO / "gitops/environments" / ENV / "apps" / "kustomization.yaml").read_text()
        )
        if not app.exists() or name not in (deployed.get("resources") or []):
            continue  # declared but not deployed here (opt-in use case)
        namespace = yaml.safe_load(app.read_text())["spec"]["destination"]["namespace"]
        found.append({"values": values, "namespace": namespace})
    return found


def build(values: dict, namespace: str, model: str) -> DAG:
    uc = values["useCase"]
    image = f"{values['image']['repository']}:{values['image']['tag']}"
    store, registry, data, promote = (
        values["artifactStore"],
        values["registry"],
        values["data"],
        values["promote"],
    )
    bus = values.get("eventBus") or {}

    # the contract variables of libs/ctsteps, as pipelines.stepEnv in the Argo chart
    step_env = [
        V1EnvVar("CT_USE_CASE", values["useCaseRef"]),
        V1EnvVar("CT_NAMESPACE", namespace),
        V1EnvVar("S3_ENDPOINT_URL", store["endpointUrl"]),
        V1EnvVar("MLFLOW_S3_ENDPOINT_URL", store["endpointUrl"]),
        V1EnvVar("AWS_DEFAULT_REGION", "us-east-1"),
        V1EnvVar("CT_DATASETS_BUCKET", store["datasetsBucket"]),
        V1EnvVar("CT_MODELS_BUCKET", store["modelsBucket"]),
        V1EnvVar("CT_PREDICTIONS_BUCKET", store["predictionsBucket"]),
        V1EnvVar("MLFLOW_TRACKING_URI", registry["trackingUri"]),
        V1EnvVar("MLFLOW_DISABLE_AGENT_HINT", "1"),
        V1EnvVar("CT_OUTPUTS_DIR", "/airflow/xcom"),  # result.json becomes the XCom value
        V1EnvVar("CT_GIT_COMMIT", str(values["image"]["tag"])),
        V1EnvVar("CT_DATA_PROFILE_OVERRIDE", "{{ params.profile }}"),
        V1EnvVar(
            "CT_DATA_PROFILE",
            value_from=V1EnvVarSource(
                config_map_key_ref=V1ConfigMapKeySelector(
                    name=values["dataSource"]["configMap"], key="profile", optional=True
                )
            ),
        ),
    ]
    if bus.get("enabled"):
        step_env += [
            V1EnvVar("CT_EVENT_BUS_BOOTSTRAP", bus["bootstrap"]),
            V1EnvVar("CT_EVENT_BUS_TOPIC", bus["topic"]),
        ]
    s3_credentials = V1EnvFromSource(secret_ref=V1SecretEnvSource(store["secretName"]))
    git_credentials = V1EnvFromSource(secret_ref=V1SecretEnvSource(promote["gitSecretName"]))
    promote_env = [
        V1EnvVar("GIT_BRANCH", promote["branch"]),
        V1EnvVar("CT_PROMOTE_VALUES_FILE", ",".join(promote["valuesFiles"])),
        V1EnvVar("GIT_AUTHOR_NAME", promote["authorName"]),
        V1EnvVar("GIT_AUTHOR_EMAIL", promote["authorEmail"]),
    ]
    res = values.get("resources") or {}
    step_resources = V1ResourceRequirements(requests=res.get("requests"), limits=res.get("limits"))
    promote_resources = V1ResourceRequirements(
        requests={"cpu": "100m", "memory": "256Mi"}, limits={"memory": "1Gi"}
    )

    def step(task_id: str, args: list[str], **kw) -> KubernetesPodOperator:
        """One ctsteps container = one pod in the use case's pipelines namespace."""
        return KubernetesPodOperator(
            task_id=task_id,
            name=f"ct-{model}-{task_id}",
            namespace=namespace,
            image=image,
            image_pull_policy=values["image"].get("pullPolicy", "IfNotPresent"),
            cmds=["sh", "-ec"],
            arguments=[
                f"ctsteps {task_id} --model {model} --run-id ct-{model}-airflow-{RUN_ID_SUFFIX} "
                + " ".join(args)
                + " && cp /airflow/xcom/result.json /airflow/xcom/return.json"
            ],
            env_vars=kw.pop("env_vars", step_env),
            env_from=kw.pop("env_from", [s3_credentials]),
            container_resources=kw.pop("container_resources", step_resources),
            labels={
                "app.kubernetes.io/part-of": uc,
                "mlops-ct-platform.dev/use-case": uc,
                "ct.mlops/use-case": uc,
                "ct.mlops/model": model,
                "ct.mlops/trigger": "{{ params.trigger }}",
            },
            do_xcom_push=True,
            get_logs=True,
            on_finish_action="delete_succeeded_pod",
            **kw,
        )

    def gate(ti) -> bool:
        """The champion/challenger gate: evaluate's `promote` scalar decides the rest."""
        return bool((ti.xcom_pull(task_ids="evaluate") or {}).get("promote"))

    with DAG(
        dag_id=f"ct_pipeline_{uc.replace('-', '_')}_{model}",
        description=f"Continuous-training pipeline of {uc}/{model} (ctsteps contract)",
        start_date=datetime(2026, 1, 1, tzinfo=UTC),
        schedule=values.get("schedule", {}).get("cron", "0 3 * * 1"),  # the weekly safety net
        catchup=False,
        max_active_runs=1,
        params={"trigger": "cron", "profile": ""},
        tags=["ct", uc],
    ) as dag:
        ingest = step("ingest", [f"--rows {data['rows']} --seed {data['seed']}"])
        validate = step("validate", [])
        preprocess = step(
            "preprocess",
            [
                f"--holdout-ratio {data['holdoutRatio']}",
                f"--reference-rows {data['referenceRows']}",
                f"--seed {data['seed']}",
            ],
        )
        train = step("train", ["--trigger {{ params.trigger }}"])
        mlflow_run_id = "{{ ti.xcom_pull(task_ids='train')['mlflow_run_id'] }}"
        evaluate = step("evaluate", [f"--mlflow-run-id {mlflow_run_id}"])
        passed = ShortCircuitOperator(task_id="gate", python_callable=gate)
        register = step("register", [f"--mlflow-run-id {mlflow_run_id}"])
        promote_task = step(
            "promote",
            [
                "--version {{ ti.xcom_pull(task_ids='register')['version'] }}",
                "--trigger {{ params.trigger }}",
            ],
            env_vars=step_env + promote_env,
            env_from=[s3_credentials, git_credentials],
            container_resources=promote_resources,
        )
        (
            ingest
            >> validate
            >> preprocess
            >> train
            >> evaluate
            >> passed
            >> register
            >> promote_task
        )
    return dag


for _uc in discover():
    for _model in _uc["values"]["models"]:
        _dag = build(_uc["values"], _uc["namespace"], _model)
        globals()[_dag.dag_id] = _dag
