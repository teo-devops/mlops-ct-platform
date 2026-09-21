# Module: orchestration

| | |
|---|---|
| **Contract** | run `ctsteps <step>` containers in order; schedules; on-demand submission |
| **Demo implementation** | Argo Workflows; `WorkflowTemplate ct-pipeline`, `ct-promote`, `ct-drift` and CronWorkflows live in the use-case pipelines chart |
| **Pinned version** | chart 2.0.6 (Argo Workflows v4.1.3) |
| **Namespace** | argo (controller/server); Workflows in each use case's pipelines namespace |
| **Replace with** | Airflow — the opt-in [airflow](airflow.md) module runs `orchestrators/airflow` on kind; Kubeflow Pipelines (`orchestrators/kfp`, reference) — same containers, different DAG file |
| **Disable** | remove the line and bring another adapter |

Wave 2. The platform module owns the RBAC of the workflow namespaces (`controller.workflowNamespaces`, `workflow.rbac.rules` allowing the drift monitor to create Workflows), so no use case writes Role/RoleBinding. No artifact repository: steps exchange data through the artifact-store contract and pass three scalars as output parameters. Event-driven triggers (a new data partition) are the gap: an Airflow sensor or a Kafka consumer submitting `ct-pipeline`.
