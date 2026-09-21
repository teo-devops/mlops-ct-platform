# Orchestrators — adapters of the step contract

The pipeline is seven `ctsteps` containers (docs/design/ct-loop.md). An orchestrator only decides *when*
they run and *passes three scalars* between them: `mlflow_run_id` (train → evaluate/register),
`promote` (evaluate → gate), `version` (register → promote). It never contains use-case logic: a use
case declares its pipeline as **data** (`use-cases/<name>/workloads/pipelines/values*.yaml`: image,
models, data parameters, contracts, promotion files) and every adapter reads that.

| Adapter | Status | Where |
|---|---|---|
| **Argo Workflows** | runs the demo | the use case's pipelines chart (`WorkflowTemplate ct-pipeline` rendered from its values); `argo/README.md` keeps the generic notes |
| **Airflow** | exercised on kind with the opt-in `airflow` platform module (docs/modules/airflow.md) | `airflow/ct_dags.py` — a factory: one DAG per use case and model built from the pipelines values and the Application's namespace; `KubernetesPodOperator` per step, XCom for the scalars, `ShortCircuitOperator` for the gate; delivered by git-sync |
| Kubeflow Pipelines | reference, not exercised in kind | `kfp/pipeline.py` — `ContainerSpec` components, `dsl.Condition` for the gate |

Porting = one adapter file. The images, the environment variables (docs/design/contracts.md) and the
S3/MLflow layout are identical. The KFP adapter is kept short and honest: it shows the shape, it has not
been run against a live KFP.
