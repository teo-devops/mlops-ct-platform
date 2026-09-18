# Pipelines — orchestrator adapters of the step contract

The pipeline is seven `ctsteps` containers (docs/design/ct-loop.md). An orchestrator only decides *when*
they run and *passes three scalars* between them: `mlflow_run_id` (train → evaluate/register),
`promote` (evaluate → gate), `version` (register → promote).

| Adapter | Status | File |
|---|---|---|
| **Argo Workflows** | runs the demo | `use-cases/listing-engine/workloads/pipelines/templates/workflowtemplate.yaml` (the platform's `argo/` directory keeps the generic notes below) |
| Airflow | reference, not exercised in kind | `adapters/airflow/dag_ct_pipeline.py` — `KubernetesPodOperator` per step, XCom for the scalars, `ShortCircuitOperator` for the gate |
| Kubeflow Pipelines | reference, not exercised in kind | `adapters/kfp/pipeline.py` — `ContainerSpec` components, `dsl.Condition` for the gate |

Porting = rewriting the adapter file. The images, the environment variables (docs/design/contracts.md) and
the S3/MLflow layout are identical. The reference adapters are kept short and honest: they show the
shape, they have not been run against a live Airflow or KFP.
