# Pipelines — orchestrator adapters of the step contract

The pipeline is seven `ctsteps` containers (docs/design/ct-loop.md). An orchestrator only decides *when*
they run and *passes three scalars* between them: `mlflow_run_id` (train → evaluate/register),
`promote` (evaluate → gate), `version` (register → promote).

| Adapter | Status | File |
|---|---|---|
| **Argo Workflows** | runs the demo | `use-cases/automated-listing-engine/workloads/pipelines/templates/workflowtemplate.yaml` (the platform's `argo/` directory keeps the generic notes below) |
| Airflow | **exercised on kind** with the opt-in `airflow` platform module (docs/modules/airflow.md) | `adapters/airflow/dag_ct_pipeline.py` — one DAG per model, `KubernetesPodOperator` per step, XCom for the scalars, `ShortCircuitOperator` for the gate; delivered to Airflow by git-sync |
| Kubeflow Pipelines | reference, not exercised in kind | `adapters/kfp/pipeline.py` — `ContainerSpec` components, `dsl.Condition` for the gate |

Porting = rewriting the adapter file. The images, the environment variables (docs/design/contracts.md) and
the S3/MLflow layout are identical. The Airflow adapter has run the whole pipeline on kind (chart 1.22.0 / Airflow 3.2.2); the KFP adapter is
kept short and honest: it shows the shape, it has not been run against a live KFP.
